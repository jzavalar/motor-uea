"""Utilidades del español que usa un programa analítico: fechas, números escritos con
letra, normalización de nombres de columnas y filtros de Jinja."""

import datetime as dt
import json
import re
import unicodedata

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
DIAS_C = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MESES_C = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep",
           "oct", "nov", "dic"]
MES_NUM = {m: i for i, m in enumerate(MESES) if m}
MES_NUM.update({m: i for i, m in enumerate(MESES_C) if m})
MES_NUM["set"] = 9
PALABRAS = ["cero", "una", "dos", "tres", "cuatro", "cinco", "seis", "siete",
            "ocho", "nueve", "diez", "once", "doce", "trece", "catorce", "quince",
            "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte"]
PALABRAS_NUM = {p: i for i, p in enumerate(PALABRAS)}
PALABRAS_NUM.update({"uno": 1, "un": 1})


def sin_acentos(texto):
    t = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in t if not unicodedata.combining(c))


def clave(texto):
    """'Producto de la sesión' -> 'producto_de_la_sesion'. Nombre de campo estable a
    partir del encabezado de una columna o de una etiqueta."""
    t = sin_acentos(texto).lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


def slug(texto):
    """'P1 La máquina al desnudo' -> 'p1-la-maquina-al-desnudo'."""
    t = sin_acentos(texto).lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def numero(texto):
    """'tres' -> 3, '12' -> 12. None si no se reconoce."""
    t = texto.strip().lower()
    if re.fullmatch(r"\d+", t):
        return int(t)
    return PALABRAS_NUM.get(t)


def numeros(texto):
    """'9, 10, 15 y 16' -> [9, 10, 15, 16]."""
    return [int(n) for n in re.findall(r"\d+", texto)]


def fecha_texto(texto, anio):
    """'17 de septiembre de 2026' o '21 de septiembre' (con año supuesto)."""
    m = re.search(r"(\d{1,2}) de ([a-záéíóú]+)(?: de (\d{4}))?", texto, re.I)
    if not m or m.group(2).lower() not in MES_NUM:
        return None
    return dt.date(int(m.group(3) or anio), MES_NUM[m.group(2).lower()], int(m.group(1)))


def rango_texto(texto):
    """'17 de septiembre al 11 de diciembre de 2026' -> (date, date).
    También '7 al 11 de diciembre de 2026'."""
    m = re.search(r"(\d{1,2})(?: de ([a-záéíóú]+))?(?: de (\d{4}))?\s+al\s+(\d{1,2}) de "
                  r"([a-záéíóú]+) de (\d{4})", texto, re.I)
    if not m:
        return None
    anio_fin = int(m.group(6))
    mes_fin = MES_NUM.get(m.group(5).lower())
    mes_ini = MES_NUM.get((m.group(2) or m.group(5)).lower())
    if not mes_fin or not mes_ini:
        return None
    anio_ini = int(m.group(3)) if m.group(3) else (anio_fin if mes_ini <= mes_fin
                                                   else anio_fin - 1)
    return dt.date(anio_ini, mes_ini, int(m.group(1))), dt.date(anio_fin, mes_fin,
                                                                 int(m.group(4)))


def fecha_corta(texto, inicio, fin):
    """'Lun 21 sep' -> date, eligiendo el año para que caiga en [inicio, fin] (con
    holgura de un mes). Devuelve (fecha, dia_de_semana_escrito) o (None, None)."""
    m = re.match(r"^\s*([A-Za-zÁÉÍÓÚáéíóú]{3})\.?\s+(\d{1,2})\s+([a-z]{3})\.?\s*$", texto)
    if not m or m.group(3).lower() not in MES_NUM:
        return None, None
    mes, dia = MES_NUM[m.group(3).lower()], int(m.group(2))
    for anio in sorted({inicio.year, fin.year, inicio.year - 1, fin.year + 1}):
        try:
            d = dt.date(anio, mes, dia)
        except ValueError:
            continue
        if inicio - dt.timedelta(days=31) <= d <= fin + dt.timedelta(days=31):
            return d, m.group(1)
    return None, m.group(1)


# ------------------------------------------------------------------ filtros

def f_corta(d):
    return f"{DIAS_C[d.weekday()]} {d.day} {MESES_C[d.month]}"


def f_larga(d):
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month]}"


def f_dm(d):
    return f"{d.day} de {MESES[d.month]}"


def f_dma(d):
    return f"{d.day} de {MESES[d.month]} de {d.year}"


def f_rango(a, b):
    if a.month == b.month:
        return f"{a.day} al {b.day} de {MESES[b.month]}"
    return f"{f_dm(a)} al {f_dm(b)}"


def f_palabra(n, genero="f"):
    if not isinstance(n, int) or n < 0 or n >= len(PALABRAS):
        return str(n)
    if genero == "m" and n == 1:
        return "uno"
    return PALABRAS[n]


def f_y(lista, conj="y"):
    lista = [str(x) for x in lista]
    if len(lista) <= 1:
        return "".join(lista)
    return ", ".join(lista[:-1]) + f" {conj} " + lista[-1]


def f_nums(lista):
    lista = sorted(lista)
    if not lista:
        return ""
    tramos, ini, prev = [], lista[0], lista[0]
    for n in lista[1:] + [None]:
        if n is not None and n == prev + 1:
            prev = n
            continue
        tramos.append((ini, prev))
        if n is not None:
            ini = prev = n
    partes = []
    for a, b in tramos:
        if a == b:
            partes.append(str(a))
        elif b == a + 1:
            partes.append(f"{a}, {b}")
        else:
            partes.append(f"{a} a {b}")
    return "; ".join(partes)


def f_punto(texto):
    texto = str(texto).rstrip()
    return texto if texto.endswith((".", "?", "!", ":")) else texto + "."


def f_minuscula_inicial(texto):
    texto = str(texto)
    return texto[:1].lower() + texto[1:]


FILTROS = {
    "corta": f_corta, "larga": f_larga, "dm": f_dm, "dma": f_dma,
    "dsem": lambda d: DIAS[d.weekday()], "mes": lambda d: MESES[d.month],
    "mayus": lambda s: str(s)[:1].upper() + str(s)[1:],
    "minuscula_inicial": f_minuscula_inicial,
    "palabra": f_palabra, "y": f_y, "nums": f_nums, "punto": f_punto,
    "sin_protocolo": lambda u: re.sub(r"^https?://", "", str(u)).rstrip("/"),
    # cadena YAML entre comillas, legible (sin escapar acentos)
    "yaml": lambda s: json.dumps(str(s), ensure_ascii=False),
    "slug": slug,
    # conjunto de días del calendario escolar: «del 6 al 8 de enero de 2027»,
    # «2, 3 y 6 de septiembre de 2027»
    "dias": lambda d: d.texto() if hasattr(d, "texto") else str(d),
}
GLOBALES = {"rango": f_rango}
