"""El calendario escolar como dato: lectura, validación, combinación y vista.

Cada calendario escolar APROBADO se transcribe en su propio archivo JSON
(programa_sitio/calendarios/AAAA-AAAA.json; uno que modifica a otro, por ejemplo por una
huelga: AAAA-AAAA-sNNN.json), con la forma de calendario-escolar.schema.json (formato 3).

Tres niveles de comprobación:

  1. el esquema (JSON Schema): la forma, los nombres de los campos, el formato de las fechas;
  2. la coherencia de cada documento:
       · cada día hábil (que no es de descanso) pertenece a exactamente un periodo: un
         trimestre (azul), un periodo intertrimestral (amarillo), unas vacaciones (blanco) o
         el registro de calificaciones posterior a un trimestre (azul o verde);
       · las semanas lectivas van del primer al último día de clases de cada semana (la
         primera puede empezar a media semana y la última terminar antes del viernes), solo se
         interrumpen por vacaciones y la «11 bis» es la 12;
       · inscripción/reinscripción y recuperación caen en un periodo intertrimestral;
         evaluaciones globales, en el trimestre;
       · el orden de los sucesos (inscripción → clases → globales → actas → recuperación);
  3. la combinación de todos los documentos: cada trimestre aparece completo en el
     calendario de su año escolar y, parcialmente, en los vecinos. Los datos se combinan; si
     dos documentos vigentes no coinciden, el trimestre queda EN CONFLICTO y no se usa hasta
     que se transcriba el calendario que resuelve la diferencia (el que «modifica» a otro).

`vista()` (Markdown) y `vista_html()` (con los colores del original) vuelven a dibujar un
documento mes por mes, para cotejar la transcripción con el original.
"""

import datetime as dt
import glob
import html
import json
import os

from . import lexico as L

CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calendarios")
ESQUEMA = os.path.join(CARPETA, "calendario-escolar.schema.json")
FORMATO = 3
ESTACIONES = {"I": "Invierno", "P": "Primavera", "O": "Otoño"}
UN_DIA = dt.timedelta(days=1)

# código interno, símbolo del calendario oficial, concepto de la simbología del documento
SIMBOLOS = [
    ("inicio", ">", None, "Inicio de clases"),
    ("fin", "<", None, "Terminación de clases"),
    ("IER", "Φ", "inscripcion_recuperacion", "Inscripción a evaluaciones de recuperación"),
    ("IR", "•", "inscripcion_reinscripcion",
     "Inscripción (nuevo ingreso) y reinscripción (a partir del segundo trimestre)"),
    ("EG", "*", "evaluaciones_globales", "Evaluaciones globales"),
    ("ER", "®", "evaluaciones_recuperacion", "Evaluaciones de recuperación"),
    ("RCA", "△", "registro_de_calificaciones", "Registro de calificaciones en actas"),
    ("RCR", "▲", "registro_recuperacion", "Registro de calificaciones de recuperación"),
]

# clases de día (colores del original)
TRIMESTRE, INTER, VACACIONES, CIERRE = "trimestre", "intertrimestral", "vacaciones", "cierre"

# campos de un trimestre que se combinan entre documentos: (clave interna, descripción)
CAMPOS = [
    ("periodo", "periodo del trimestre"),
    ("clases_inicio", "inicio de clases"),
    ("clases_fin", "terminación de clases"),
    ("inscripcion", "inscripción/reinscripción"),
    ("globales", "evaluaciones globales"),
    ("actas", "registro de calificaciones"),
    ("rec_inscripcion", "inscripción a recuperación"),
    ("rec_evaluaciones", "evaluaciones de recuperación"),
    ("rec_actas", "registro de calificaciones de recuperación"),
]


def siguiente(clave):
    """'25-I' -> '25-P' -> '25-O' -> '26-I' (orden del año natural)."""
    aa, e = clave.split("-")
    if e == "I":
        return f"{aa}-P"
    if e == "P":
        return f"{aa}-O"
    return f"{int(aa) + 1:02d}-I"


def del_motor():
    """Los calendarios que trae el motor (todo *.json de la carpeta, menos el esquema)."""
    return sorted(a for a in glob.glob(os.path.join(CARPETA, "*.json"))
                  if not a.endswith(".schema.json"))


def lunes_de(d):
    return d - dt.timedelta(days=d.weekday())


def habiles_entre(a, b):
    d, out = a, []
    while d <= b:
        if d.weekday() < 5:
            out.append(d)
        d += UN_DIA
    return out


class ErrorDeCalendario(Exception):
    pass


class Dias(list):
    """Lista explícita de días, en orden. `inicio` y `fin` son el primero y el último; el
    texto dice «del 6 al 8 de enero de 2027» solo si son días hábiles seguidos (sin más
    huecos que los fines de semana) y, si no, los enumera: «14, 16 y 19 de mayo»."""

    @property
    def inicio(self):
        return self[0] if self else None

    @property
    def fin(self):
        return self[-1] if self else None

    @property
    def seguidos(self):
        for a, b in zip(self, self[1:]):
            d = a + UN_DIA
            while d.weekday() >= 5:
                d += UN_DIA
            if d != b:
                return False
        return True

    def texto(self, anio=True):
        if not self:
            return ""
        cola = f" de {self.fin.year}" if anio else ""
        if len(self) == 1:
            return L.f_dm(self[0]) + cola
        if self.seguidos:
            if self.inicio.year != self.fin.year:
                return f"del {L.f_dma(self.inicio)} al {L.f_dma(self.fin)}"
            return "del " + L.f_rango(self.inicio, self.fin) + cola
        grupos = []
        for d in self:
            if grupos and (grupos[-1][0].month, grupos[-1][0].year) == (d.month, d.year):
                grupos[-1].append(d)
            else:
                grupos.append([d])
        partes = [L.f_y([str(x.day) for x in g]) + f" de {L.MESES[g[0].month]}" for g in grupos]
        return L.f_y(partes) + cola

    def __str__(self):
        return self.texto()


def rango(a, b):
    """«17 de septiembre al 11 de diciembre de 2026»; con el año en ambos extremos si
    cambia: «21 de octubre de 2024 al 24 de enero de 2025»; un solo día: «22 de diciembre
    de 2023»."""
    if a == b:
        return L.f_dma(a)
    if a.year != b.year:
        return f"{L.f_dma(a)} al {L.f_dma(b)}"
    return f"{L.f_rango(a, b)} de {b.year}"


def rango_largo(a, b):
    """«jueves 17 de septiembre al viernes 4 de diciembre de 2026»."""
    ai = f"{L.f_larga(a)}" + (f" de {a.year}" if a.year != b.year else "")
    return f"{ai} al {L.f_larga(b)} de {b.year}"


def rango_semana(s):
    a, b = s["inicio"], s["fin"]
    if a == b:
        return f"{L.DIAS_C[a.weekday()].lower()} {L.f_dm(a)}"
    if a.month == b.month:
        return f"{L.DIAS_C[a.weekday()].lower()} {a.day} a {L.DIAS_C[b.weekday()].lower()} " \
               f"{b.day} {L.MESES_C[b.month]}"
    return f"{L.DIAS_C[a.weekday()].lower()} {a.day} {L.MESES_C[a.month]} a " \
           f"{L.DIAS_C[b.weekday()].lower()} {b.day} {L.MESES_C[b.month]}"


def _texto(valor):
    if valor is None:
        return "—"
    if isinstance(valor, Dias):
        return valor.texto()
    if isinstance(valor, dt.date):
        return L.f_dma(valor)
    if isinstance(valor, tuple) and len(valor) in (2, 3) and isinstance(valor[0], dt.date):
        return rango(valor[0], valor[1])
    if isinstance(valor, list):
        return "; ".join(_texto(v) for v in valor) or "ninguno"
    return str(valor)


def en_periodos(periodos, d):
    return any(a <= d <= b for a, b, *_ in periodos if a and b)


def en_receso(T, d):
    """¿El día cae en unas vacaciones dentro del trimestre (sin clases)?"""
    return en_periodos(T.get("vacaciones") or [], d)


# ------------------------------------------------------------------- lectura

def _mensaje_de_esquema(e):
    ruta = "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in e.absolute_path)
    ruta = ruta.lstrip(".") or "(raíz)"
    v = e.validator
    if v == "required":
        falta = e.message.split("'")[1] if "'" in e.message else e.message
        return f"{ruta}: falta el campo «{falta}»"
    if v == "additionalProperties":
        extra = e.message.split("'")[1] if "'" in e.message else e.message
        return f"{ruta}: el campo «{extra}» no existe en el formato (¿está mal escrito?)"
    if v in ("pattern", "format"):
        return f"{ruta}: «{e.instance}» no tiene la forma esperada"
    if v == "const":
        return f"{ruta}: debe ser {json.dumps(e.validator_value, ensure_ascii=False)}"
    if v == "type":
        return f"{ruta}: debe ser de tipo {e.validator_value}"
    if v == "minItems":
        return f"{ruta}: no puede estar vacío"
    if v == "uniqueItems":
        return f"{ruta}: tiene fechas repetidas"
    if v == "minimum":
        return f"{ruta}: debe ser al menos {e.validator_value}"
    if v == "not":
        return f"{ruta}: un trimestre completo lleva «periodo» y no «tramo_visible»; uno " \
               "parcial, al revés"
    return f"{ruta}: {e.message}"


def _fecha(texto, ruta, E):
    try:
        return dt.date.fromisoformat(texto)
    except (TypeError, ValueError):
        E(f"{ruta}: «{texto}» no es una fecha válida")
        return None


def leer(ruta):
    """Lee y valida UN documento. Devuelve el documento normalizado (fechas de Python) con
    sus avisos; si hay errores, lanza ErrorDeCalendario con todos juntos."""
    import jsonschema

    nombre_archivo = os.path.basename(ruta)
    try:
        with open(ruta, encoding="utf-8") as f:
            crudo = json.load(f)
    except FileNotFoundError:
        raise ErrorDeCalendario(f"{nombre_archivo}: no existe ({ruta})")
    except json.JSONDecodeError as e:
        raise ErrorDeCalendario(f"{nombre_archivo}: no es JSON válido (renglón {e.lineno}, "
                                f"columna {e.colno}: {e.msg})")
    with open(ESQUEMA, encoding="utf-8") as f:
        esquema = json.load(f)
    validador = jsonschema.Draft202012Validator(
        esquema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)
    errores = sorted(validador.iter_errors(crudo), key=lambda e: list(e.absolute_path))
    if errores:
        mensajes = list(dict.fromkeys(f"{nombre_archivo}: {_mensaje_de_esquema(e)}"
                                      for e in errores))
        raise ErrorDeCalendario("\n".join(mensajes))
    return _normalizar(crudo, ruta)


def _normalizar(crudo, ruta):
    errores, avisos = [], []
    nombre_archivo = os.path.basename(ruta)

    def E(m):
        errores.append(f"{nombre_archivo}: {m}")

    def A(m):
        avisos.append(f"{nombre_archivo}: {m}")

    def fechas(lista, r):
        out = Dias(x for x in (_fecha(t, f"{r}[{i}]", E) for i, t in enumerate(lista)) if x)
        if list(out) != sorted(out):
            E(f"{r}: las fechas no están en orden ascendente")
        if len(set(out)) != len(out):
            E(f"{r}: tiene fechas repetidas")
        return out

    def periodo(p, r):
        if not p:
            return None
        a, b = _fecha(p["inicio"], f"{r}.inicio", E), _fecha(p["fin"], f"{r}.fin", E)
        if a and b and a > b:
            E(f"{r}: el inicio ({L.f_dma(a)}) es posterior al fin ({L.f_dma(b)})")
        return (a, b, p.get("nota", ""))

    d = crudo["documento"]
    doc = {"archivo": ruta, "nombre": d["nombre"], "anio_escolar": d["anio_escolar"],
           "institucion": d["institucion"], "fuente": d.get("fuente", ""),
           "motivo": d.get("motivo", ""), "transcripcion": d.get("transcripcion", ""),
           "aprobacion": dict(d["aprobacion"]),
           "modifica": [(m["anio_escolar"], m["sesion"]) for m in d.get("modifica") or []],
           "simbologia": crudo["simbologia"]}
    ap = doc["aprobacion"]
    ap["fecha"] = _fecha(ap["fecha"], "documento.aprobacion.fecha", E)
    doc["texto_aprobacion"] = (f"Aprobado por el {ap['organo']} en su sesión número "
                               f"{ap['sesion']}, celebrada el "
                               f"{L.f_dma(ap['fecha']) if ap['fecha'] else '¿?'}")
    doc["id"] = f"{d['nombre']} (sesión {ap['sesion']})"
    a1, a2 = (int(x) for x in d["anio_escolar"].split("-"))
    if a2 != a1 + 1:
        E(f"documento.anio_escolar: «{d['anio_escolar']}» debe ser de dos años seguidos")
    if not d["nombre"].startswith(f"Calendario Escolar {d['anio_escolar']}"):
        E(f"documento.nombre: «{d['nombre']}» no corresponde al año escolar "
          f"«{d['anio_escolar']}»")
    c_ini, c_fin, _ = periodo(crudo["cobertura"], "cobertura")
    doc["cobertura"] = (c_ini, c_fin)

    def dentro(x, r):
        if x and c_ini and c_fin and not c_ini <= x <= c_fin:
            E(f"{r}: el {L.f_dma(x)} está fuera de la cobertura del documento "
              f"({L.f_dma(c_ini)} al {L.f_dma(c_fin)})")

    descansos = fechas([x["fecha"] for x in crudo["descansos"]], "descansos")
    for i, x in enumerate(descansos):
        dentro(x, f"descansos[{i}]")
    doc["descansos"] = descansos
    doc["notas_descansos"] = {dt.date.fromisoformat(x["fecha"]): x["nota"]
                              for x in crudo["descansos"] if x.get("nota")}
    descanso = set(descansos)

    def bloques(nombre):
        lista = [periodo(p, f"{nombre}[{j}]") for j, p in enumerate(crudo[nombre])]
        for j, (a, b, _) in enumerate(lista):
            dentro(a, f"{nombre}[{j}].inicio")
            dentro(b, f"{nombre}[{j}].fin")
            for x, que in ((a, "inicio"), (b, "fin")):
                if x and (x.weekday() >= 5 or x in descanso) and not (
                        (que == "inicio" and x == c_ini) or (que == "fin" and x == c_fin)):
                    E(f"{nombre}[{j}].{que}: el {L.f_larga(x)} de {x.year} no es día hábil; "
                      "un periodo empieza y termina en un día hábil de su color")
        for j in range(1, len(lista)):
            if lista[j - 1][1] and lista[j][0] and lista[j][0] <= lista[j - 1][1]:
                E(f"{nombre}[{j}]: no es posterior al anterior (en orden y sin traslaparse)")
        return lista
    doc["intertrimestrales"] = bloques("periodos_intertrimestrales")
    doc["vacaciones"] = bloques("vacaciones")

    def habiles(dias, r, que):
        for x in dias:
            dentro(x, r)
            if x.weekday() >= 5:
                E(f"{r}: {que} el {L.f_larga(x)} de {x.year}, que es {L.DIAS[x.weekday()]}")
            elif x in descanso:
                E(f"{r}: {que} el {L.f_dma(x)}, que es día de descanso obligatorio")

    trimestres, orden = {}, []
    for i, t in enumerate(crudo["trimestres"]):
        r = f"trimestres[{i}] ({t['clave']})"
        clave = t["clave"]
        aa, est = clave.split("-")
        if t["nombre"] != f"{aa}-{ESTACIONES[est]}":
            E(f"{r}: el nombre «{t['nombre']}» no corresponde a la clave {clave} "
              f"(debe ser «{aa}-{ESTACIONES[est]}»)")
        if clave in trimestres:
            E(f"{r}: la clave {clave} está repetida")
        T = {"clave": clave, "nombre": t["nombre"], "parcial": bool(t.get("parcial")),
             "documento": doc["id"], "_cobertura": (c_ini, c_fin)}
        p = periodo(t.get("periodo"), f"{r}.periodo")
        T["periodo"] = p[:2] if p else None
        tv = periodo(t.get("tramo_visible"), f"{r}.tramo_visible")
        T["tramo_visible"] = tv[:2] if tv else None
        cl = t.get("clases") or {}
        T["clases_inicio"] = _fecha(cl["inicio"], f"{r}.clases.inicio", E) if "inicio" in cl \
            else None
        T["clases_fin"] = _fecha(cl["fin"], f"{r}.clases.fin", E) if "fin" in cl else None
        extension = T["periodo"] or T["tramo_visible"]
        T["vacaciones"] = [v for v in doc["vacaciones"] if extension and v[0] and v[1] and
                           v[0] <= extension[1] and v[1] >= extension[0]]
        T["semanas"] = []
        for j, s in enumerate(t.get("semanas") or []):
            T["semanas"].append({"orden": s["orden"], "etiqueta": s["etiqueta"],
                                 "inicio": _fecha(s["inicio"], f"{r}.semanas[{j}].inicio", E),
                                 "fin": _fecha(s["fin"], f"{r}.semanas[{j}].fin", E)})
        for campo, destino in (("inscripcion_reinscripcion", "inscripcion"),
                               ("evaluaciones_globales", "globales"),
                               ("registro_de_calificaciones", "actas")):
            T[destino] = fechas(t.get(campo) or [], f"{r}.{campo}")
        rec = t.get("recuperacion") or {}
        T["rec_inscripcion"] = fechas(rec.get("inscripcion") or [], f"{r}.recuperacion.inscripcion")
        T["rec_evaluaciones"] = fechas(rec.get("evaluaciones") or [],
                                       f"{r}.recuperacion.evaluaciones")
        T["rec_actas"] = fechas(rec.get("registro_de_calificaciones") or [],
                                f"{r}.recuperacion.registro_de_calificaciones")
        _coherencia_trimestre(T, r, E, A, dentro, habiles, descanso, doc)
        trimestres[clave] = T
        orden.append(T)

    # orden de los trimestres del documento y sucesos entre uno y otro
    for x, y in zip(orden, orden[1:]):
        if y["clave"] != siguiente(x["clave"]):
            A(f"trimestres: después de {x['clave']} el documento pone {y['clave']} (el "
              f"siguiente en el año sería {siguiente(x['clave'])}); confírmelo")
        ex = x["periodo"] or x["tramo_visible"]
        ey = y["periodo"] or y["tramo_visible"]
        if ex and ey and ex[1] >= ey[0]:
            E(f"trimestres: {x['clave']} y {y['clave']} se traslapan")
        if y["clases_inicio"]:
            for nombre, dias in (("las evaluaciones de recuperación", x["rec_evaluaciones"]),
                                 ("la inscripción a recuperación", x["rec_inscripcion"])):
                if dias and dias.fin >= y["clases_inicio"]:
                    E(f"{x['clave']}: {nombre} ({dias.texto()}) no terminan antes del inicio de "
                      f"clases de {y['clave']} ({L.f_dma(y['clases_inicio'])})")
    if not any(not T["parcial"] for T in orden):
        E("trimestres: el documento no enuncia ningún trimestre completo")
    doc["trimestres"] = trimestres
    doc["orden"] = [T["clave"] for T in orden]
    if not errores:
        _particion(doc, E, A)
        _vacaciones_de_verano(doc, A)
    if errores:
        raise ErrorDeCalendario("\n".join(errores))
    doc["avisos"] = avisos
    return doc


def clase_de_dia(doc, d):
    """Las clases (colores) a que pertenece un día según el documento: subconjunto de
    {trimestre, intertrimestral, vacaciones, cierre}."""
    clases = set()
    en_vac = en_periodos(doc["vacaciones"], d)
    if en_vac:
        clases.add(VACACIONES)
    if en_periodos(doc["intertrimestrales"], d):
        clases.add(INTER)
    for T in doc["trimestres"].values():
        ext = T["periodo"] or T["tramo_visible"]
        if ext and ext[0] <= d <= ext[1] and not en_vac:
            clases.add(TRIMESTRE)
        elif d in T["actas"] and (not ext or d > ext[1]):
            clases.add(CIERRE)
    return clases


def _particion(doc, E, A):
    """Cada día hábil que no es de descanso cae en exactamente un periodo."""
    ini, fin = doc["cobertura"]
    descanso = set(doc["descansos"])
    sin, dobles = [], []
    for d in habiles_entre(ini, fin):
        if d in descanso:
            continue
        c = clase_de_dia(doc, d)
        if not c:
            sin.append(d)
        elif len(c) > 1:
            dobles.append((d, c))
    for grupo in _agrupar(sin, descanso):
        E(f"días hábiles sin periodo ({rango(grupo[0], grupo[-1])}): no están en ningún "
          "trimestre, periodo intertrimestral, vacaciones ni registro de calificaciones")
    for d, c in dobles:
        E(f"el {L.f_dma(d)} está a la vez en {L.f_y(sorted(c))}")
    # dónde caen los sucesos
    for T in doc["trimestres"].values():
        for dias, que in ((T["inscripcion"], "la inscripción/reinscripción"),
                          (T["rec_inscripcion"], "la inscripción a recuperación"),
                          (T["rec_evaluaciones"], "las evaluaciones de recuperación"),
                          (T["rec_actas"], "el registro de calificaciones de recuperación")):
            fuera = Dias(x for x in dias if not en_periodos(doc["intertrimestrales"], x))
            if fuera:
                E(f"{T['clave']}: {que} cae fuera de un periodo intertrimestral ({fuera.texto()})")
        fuera = Dias(x for x in T["globales"] if TRIMESTRE not in clase_de_dia(doc, x))
        if fuera:
            E(f"{T['clave']}: hay evaluaciones globales fuera del trimestre ({fuera.texto()})")


def _agrupar(dias, saltar=()):
    """Agrupa días hábiles seguidos (se saltan fines de semana y los días de `saltar`)."""
    grupos = []
    for d in dias:
        if grupos:
            siguiente_habil = grupos[-1][-1] + UN_DIA
            while siguiente_habil.weekday() >= 5 or siguiente_habil in saltar:
                siguiente_habil += UN_DIA
            if siguiente_habil == d:
                grupos[-1].append(d)
                continue
        grupos.append([d])
    return grupos


def _vacaciones_de_verano(doc, A):
    """Las vacaciones de verano (antes de un Otoño) son de cuatro semanas."""
    ini, fin = doc["cobertura"]
    for a, b, _ in doc["vacaciones"]:
        if a == ini or b == fin or a.month not in (7, 8, 9):
            continue
        n = len([d for d in habiles_entre(a, b) if d not in set(doc["descansos"])])
        if n != 20:
            A(f"las vacaciones de verano ({rango(a, b)}) tienen {n} días hábiles; las "
              "obligatorias son cuatro semanas (20); confírmelo")


def _coherencia_trimestre(T, r, E, A, dentro, habiles, descanso, doc):
    p = T["periodo"]
    ci, cf = T["clases_inicio"], T["clases_fin"]
    ext = p or T["tramo_visible"]
    if p:
        dentro(p[0], f"{r}.periodo.inicio")
        dentro(p[1], f"{r}.periodo.fin")
        aa = int(T["clave"][:2])
        if p[0] and p[0].year % 100 != aa:
            A(f"{r}: el trimestre empieza en {p[0].year}, pero su clave dice 20{aa:02d}; "
              "confírmelo en el documento")
    if T["tramo_visible"]:
        dentro(T["tramo_visible"][0], f"{r}.tramo_visible.inicio")
        dentro(T["tramo_visible"][1], f"{r}.tramo_visible.fin")
    for nombre, x in (("el inicio de clases", ci), ("la terminación de clases", cf)):
        if x:
            dentro(x, r)
            if x.weekday() >= 5 or x in descanso or en_receso(T, x):
                E(f"{r}: {nombre} cae el {L.f_larga(x)} de {x.year}, que no es día de clases")
    if ci and cf and ci >= cf:
        E(f"{r}: el inicio de clases ({L.f_dma(ci)}) no es anterior a su terminación "
          f"({L.f_dma(cf)})")
    if ext and ci and not ext[0] <= ci <= ext[1]:
        E(f"{r}: el inicio de clases ({L.f_dma(ci)}) no cae en el trimestre")
    if p and cf and not p[0] <= cf <= p[1]:
        E(f"{r}: la terminación de clases ({L.f_dma(cf)}) no cae en el trimestre")

    # semanas: del primer al último día de clases de cada semana
    S = T["semanas"]
    etiquetas = [s["etiqueta"] for s in S]
    if len(set(etiquetas)) != len(etiquetas):
        E(f"{r}.semanas: hay etiquetas repetidas")
    tope = cf or doc["cobertura"][1]
    for j, s in enumerate(S):
        q = f"{r}.semanas[{j}] (semana {s['etiqueta']})"
        if s["orden"] != j + 1:
            E(f"{q}: el orden debe ser {j + 1}, no {s['orden']}")
        if s["etiqueta"].endswith("bis"):
            if s["orden"] != 12 or j == 0 or S[j - 1]["etiqueta"] != s["etiqueta"].split()[0]:
                E(f"{q}: la «11 bis» equivale a la semana 12 y sigue a la 11")
        a, b = s["inicio"], s["fin"]
        if not (a and b):
            continue
        dentro(a, f"{q}.inicio")
        dentro(b, f"{q}.fin")
        if lunes_de(a) != lunes_de(b) or a > b:
            E(f"{q}: {rango(a, b)} no es una sola semana")
            continue
        m = lunes_de(a)
        esperados = [x for x in habiles_entre(max(m, ci or m), min(m + dt.timedelta(4), tope))
                     if not en_receso(T, x)]
        if esperados and (a, b) != (esperados[0], esperados[-1]):
            E(f"{q}: dice {rango_semana(s)}, pero sus días de clase van del "
              f"{L.f_larga(esperados[0])} al {L.f_larga(esperados[-1])}")
        if j:
            ant = S[j - 1]["inicio"]
            if ant and lunes_de(ant) >= m:
                E(f"{q}: no es posterior a la semana {S[j - 1]['etiqueta']}")
                continue
            hueco = lunes_de(ant) + dt.timedelta(days=7) if ant else m
            while hueco < m:
                if not all(en_receso(T, x) or x in descanso
                           for x in habiles_entre(hueco, hueco + dt.timedelta(4))):
                    E(f"{q}: entre la semana {S[j - 1]['etiqueta']} y esta queda la del "
                      f"{L.f_dma(hueco)}, sin número; solo puede faltar número en vacaciones")
                hueco += dt.timedelta(days=7)
    if S and ci and S[0]["inicio"] and S[0]["inicio"] != ci:
        E(f"{r}: la primera semana empieza el {L.f_dma(S[0]['inicio'])}, pero las clases "
          f"empiezan el {L.f_dma(ci)}")
    if not T["parcial"] and S and cf and S[-1]["fin"] and S[-1]["fin"] != cf:
        E(f"{r}: la última semana termina el {L.f_dma(S[-1]['fin'])}, pero las clases terminan "
          f"el {L.f_dma(cf)}")
    if not T["parcial"] and S and len(S) not in (11, 12):
        A(f"{r}: tiene {len(S)} semanas lectivas (lo usual es 11, o 12 con la 11 bis)")

    # días de los sucesos
    for campo, dias, que in (
            ("inscripcion_reinscripcion", T["inscripcion"], "hay inscripción/reinscripción"),
            ("evaluaciones_globales", T["globales"], "hay evaluación global"),
            ("registro_de_calificaciones", T["actas"], "hay registro de calificaciones"),
            ("recuperacion.inscripcion", T["rec_inscripcion"], "hay inscripción a recuperación"),
            ("recuperacion.evaluaciones", T["rec_evaluaciones"],
             "hay evaluación de recuperación"),
            ("recuperacion.registro_de_calificaciones", T["rec_actas"],
             "hay registro de calificaciones de recuperación")):
        habiles(dias, f"{r}.{campo}", que)
    G, RCA = T["globales"], T["actas"]
    if ci and T["inscripcion"] and T["inscripcion"].fin >= ci:
        E(f"{r}: la inscripción/reinscripción ({T['inscripcion'].texto()}) debe terminar antes "
          f"del inicio de clases ({L.f_dma(ci)})")
    if G and cf and G.inicio <= cf:
        E(f"{r}: las evaluaciones globales ({G.texto()}) deben empezar después de la "
          f"terminación de clases ({L.f_dma(cf)})")
    if G and p and not (p[0] <= G.inicio and G.fin <= p[1]):
        E(f"{r}: las evaluaciones globales ({G.texto()}) no caben en el trimestre")
    if G and p and G.fin != p[1]:
        A(f"{r}: las evaluaciones globales terminan el {L.f_dma(G.fin)} y el trimestre el "
          f"{L.f_dma(p[1])}; confírmelo")
    if G and RCA and RCA.inicio < G.inicio:
        E(f"{r}: el registro de calificaciones ({RCA.texto()}) empieza antes que las "
          f"evaluaciones globales ({G.texto()})")
    ER = T["rec_evaluaciones"]
    if ER:
        if RCA and ER.inicio <= RCA.fin:
            E(f"{r}: las evaluaciones de recuperación ({ER.texto()}) deben ser posteriores al "
              f"registro de calificaciones del trimestre ({RCA.texto()})")
        if T["rec_inscripcion"] and T["rec_inscripcion"].fin >= ER.inicio:
            E(f"{r}: la inscripción a recuperación ({T['rec_inscripcion'].texto()}) debe ser "
              f"anterior a las evaluaciones de recuperación ({ER.texto()})")
        if T["rec_actas"] and T["rec_actas"].inicio < ER.inicio:
            E(f"{r}: el registro de calificaciones de recuperación ({T['rec_actas'].texto()}) "
              f"empieza antes que las evaluaciones de recuperación ({ER.texto()})")


# ------------------------------------------------------ combinación de documentos

def _iguales(a, b):
    return list(a) == list(b) if isinstance(a, list) else a == b


def _presente(v):
    return v not in (None, [], ()) and not (isinstance(v, list) and not v)


def cargar_todos(archivos, prioritario=None):
    """Combina los documentos. `prioritario` (la copia propia de un curso) sustituye, en su
    cobertura, a todos los demás, como si los modificara. Devuelve (completos, parciales,
    errores, avisos): `completos` son los trimestres que algún documento vigente enuncia en
    su encabezado; `parciales`, los que solo aparecen parcialmente. Cada trimestre trae
    `conflictos`: los campos en que dos documentos vigentes no coinciden (entonces no debe
    usarse)."""
    docs, errores, avisos = [], [], []
    for a in archivos:
        try:
            doc = leer(a)
        except ErrorDeCalendario as e:
            errores += str(e).split("\n")
            continue
        docs.append(doc)
        avisos += doc["avisos"]
    docs.sort(key=lambda d: (d["aprobacion"]["fecha"], d["aprobacion"]["sesion"]))

    # vigencia: un documento que «modifica» a otro lo sustituye dentro de su cobertura
    por_id = {(d["anio_escolar"], d["aprobacion"]["sesion"]): d for d in docs}
    sustituido_en = {id(d): [] for d in docs}      # coberturas en que d ya no rige
    sustitutos = {id(d): [] for d in docs}         # documentos que sustituyen a d
    prio = [d for d in docs if prioritario and os.path.abspath(d["archivo"]) ==
            os.path.abspath(prioritario)]
    for p in prio:
        for d in docs:
            if d is not p:
                sustituido_en[id(d)].append(p["cobertura"])
                sustitutos[id(d)].append(p)
    for d in docs:
        for ref in d["modifica"]:
            viejo = por_id.get(ref)
            if viejo is None:
                avisos.append(f"{os.path.basename(d['archivo'])}: modifica el calendario "
                              f"{ref[0]} de la sesión {ref[1]}, que no está transcrito")
                continue
            if viejo["aprobacion"]["fecha"] and d["aprobacion"]["fecha"] and \
                    viejo["aprobacion"]["fecha"] > d["aprobacion"]["fecha"]:
                errores.append(f"{os.path.basename(d['archivo'])}: dice modificar un calendario "
                               "aprobado después que él")
            sustituido_en[id(viejo)].append(d["cobertura"])
            sustitutos[id(viejo)].append(d)

    def rige(doc, fecha):
        return not any(a <= fecha <= b for a, b in sustituido_en[id(doc)])

    def rige_trimestre(doc, T):
        """Un trimestre de un documento sustituido deja de regir si el que lo sustituye lo
        trae, o si alguna de sus fechas cae en la cobertura sustituida."""
        if not sustituido_en[id(doc)]:
            return True
        fechas = [x for x in (T["clases_inicio"], T["clases_fin"]) if x]
        for k in ("inscripcion", "globales", "actas", "rec_inscripcion", "rec_evaluaciones",
                  "rec_actas"):
            fechas += list(T[k])
        for k in ("periodo", "tramo_visible"):
            if T[k]:
                fechas += list(T[k])
        return all(rige(doc, f) for f in fechas) and not any(
            T["clave"] in o["trimestres"] for o in sustitutos[id(doc)])

    # descansos vigentes, y cotejo de cada día donde dos documentos vigentes se traslapan
    descansos = set()
    for d in docs:
        descansos |= {x for x in d["descansos"] if rige(d, x)}
    for i, a in enumerate(docs):
        for b in docs[i + 1:]:
            ini = max(a["cobertura"][0], b["cobertura"][0])
            fin = min(a["cobertura"][1], b["cobertura"][1])
            if ini > fin:
                continue
            distintos = []
            for x in habiles_entre(ini, fin):
                if not (rige(a, x) and rige(b, x)):
                    continue
                ca = "descanso" if x in a["descansos"] else "/".join(sorted(clase_de_dia(a, x)))
                cb = "descanso" if x in b["descansos"] else "/".join(sorted(clase_de_dia(b, x)))
                if ca != cb:
                    distintos.append((x, ca, cb))
            for x, ca, cb in distintos:
                avisos.append(f"CONFLICTO: el {L.f_dma(x)} es {ca or 'sin periodo'} según el "
                              f"{a['id']} y {cb or 'sin periodo'} según el {b['id']}")

    # combinación por trimestre
    versiones = {}
    for d in docs:
        for T in d["trimestres"].values():
            if rige_trimestre(d, T):
                versiones.setdefault(T["clave"], []).append((d, T))
    completos, parciales = {}, {}
    for clave, vs in versiones.items():
        principales = [(d, T) for d, T in vs if not T["parcial"]]
        base = principales[-1] if principales else vs[-1]
        M = {"clave": clave, "nombre": base[1]["nombre"], "parcial": not principales,
             "conflictos": [], "_documentos": [d["id"] for d, _ in vs],
             "_calendario": base[0]["nombre"], "_archivo": base[0]["archivo"],
             "_texto_aprobacion": base[0]["texto_aprobacion"],
             "_simbologia": base[0]["simbologia"], "tramo_visible": base[1]["tramo_visible"]}
        for campo, desc in CAMPOS:
            valores = [(d, T[campo]) for d, T in vs if _presente(T[campo])]
            M[campo] = valores[-1][1] if valores else (
                None if campo in ("periodo", "clases_inicio", "clases_fin") else Dias())
            distintos = []
            for d, v in valores:
                if not any(_iguales(v, w) for _, w in distintos):
                    distintos.append((d, v))
            if len(distintos) > 1:
                M["conflictos"].append({"campo": desc, "valores": [(d["id"], _texto(v))
                                                                   for d, v in distintos]})
        # semanas: cada una, por su orden; la de un documento que no muestra la semana
        # completa (parcial, recortada por su cobertura) se compara hasta donde la muestra
        semanas = {}
        for d, T in vs:
            for s in T["semanas"]:
                previa = semanas.get(s["orden"])
                if previa:
                    corte = min(previa[0]["cobertura"][1], d["cobertura"][1])
                    pa = (previa[1]["etiqueta"], previa[1]["inicio"], min(previa[1]["fin"], corte))
                    pb = (s["etiqueta"], s["inicio"], min(s["fin"], corte))
                    if pa != pb:
                        M["conflictos"].append({"campo": f"semana {s['etiqueta']}", "valores": [
                            (previa[0]["id"], rango_semana(previa[1])),
                            (d["id"], rango_semana(s))]})
                        continue
                if not previa or not T["parcial"]:
                    semanas[s["orden"]] = (d, s)
        M["semanas"] = [semanas[k][1] for k in sorted(semanas)]
        vacas = []
        for d, T in vs:
            for v in T["vacaciones"]:
                if v[:2] not in [w[:2] for w in vacas] and rige(d, v[0]):
                    vacas.append(v)
        M["vacaciones"] = sorted(vacas)
        M["_descansos"] = sorted(descansos)
        M["recuperacion"] = {"inscripcion": M["rec_inscripcion"],
                             "evaluaciones": M["rec_evaluaciones"], "actas": M["rec_actas"]}
        M["clases"] = (M["clases_inicio"], M["clases_fin"])
        for c in M["conflictos"]:
            avisos.append(f"CONFLICTO en {clave}, {c['campo']}: " + "; ".join(
                f"{quien}: {texto}" for quien, texto in c["valores"]))
        (parciales if M["parcial"] else completos)[clave] = M
    return completos, parciales, errores, avisos


# ------------------------------------------------------------------ plantilla

def plantilla(anio_escolar):
    """Esqueleto de un año escolar nuevo, con la forma exacta del formato."""
    a1 = int(anio_escolar.split("-")[0])
    a2 = a1 + 1
    yy1, yy2 = a1 % 100, a2 % 100
    F = "AAAA-MM-DD"
    P = {"inicio": F, "fin": F}

    def completo(clave, nombre):
        return {"clave": clave, "nombre": nombre, "periodo": dict(P),
                "clases": {"inicio": F, "fin": F},
                "semanas": [{"orden": i + 1, "etiqueta": e, "inicio": F, "fin": F}
                            for i, e in enumerate([str(k) for k in range(1, 12)] + ["11 bis"])],
                "inscripcion_reinscripcion": [F], "evaluaciones_globales": [F],
                "registro_de_calificaciones": [F],
                "recuperacion": {"inscripcion": [F], "evaluaciones": [F],
                                 "registro_de_calificaciones": [F]}}
    simb = {
        "inscripcion_reinscripcion": {"sigla": "IR", "texto": "Inscripción/reinscripción (IR), "
                                                              "artículo NN RESUAM"},
        "evaluaciones_globales": {"sigla": "EG", "texto": "Evaluaciones globales (EG)"},
        "registro_de_calificaciones": {"sigla": "RCA", "texto": "Registro de calificaciones "
                                                                "en actas (RCA)"},
        "inscripcion_recuperacion": {"sigla": "IER", "texto": "Inscripción evaluaciones de "
                                                              "recuperación (IER)"},
        "evaluaciones_recuperacion": {"sigla": "ER", "texto": "Evaluaciones de recuperación (ER)"},
        "registro_recuperacion": {"sigla": "RCR", "texto": "Registro de calificaciones en actas "
                                                           "de recuperación (RCR)"},
    }
    datos = {
        "$schema": "./calendario-escolar.schema.json", "formato": FORMATO,
        "documento": {"nombre": f"Calendario Escolar {a1}-{a2}", "anio_escolar": f"{a1}-{a2}",
                      "institucion": "Universidad Autónoma Metropolitana",
                      "aprobacion": {"organo": "Colegio Académico", "sesion": 0, "fecha": F},
                      "fuente": "", "transcripcion": ""},
        "simbologia": simb,
        "cobertura": dict(P),
        "descansos": [{"fecha": F}],
        "periodos_intertrimestrales": [dict(P), dict(P), dict(P), dict(P)],
        "vacaciones": [dict(P, nota="fin de año"), dict(P, nota="verano: cuatro semanas")],
        "trimestres": [
            {"clave": f"{yy1:02d}-P", "nombre": f"{yy1:02d}-Primavera", "parcial": True,
             "recuperacion": {"inscripcion": [F], "evaluaciones": [F],
                              "registro_de_calificaciones": [F]}},
            completo(f"{yy1:02d}-O", f"{yy1:02d}-Otoño"),
            completo(f"{yy2:02d}-I", f"{yy2:02d}-Invierno"),
            completo(f"{yy2:02d}-P", f"{yy2:02d}-Primavera"),
            {"clave": f"{yy2:02d}-O", "nombre": f"{yy2:02d}-Otoño", "parcial": True,
             "tramo_visible": dict(P), "clases": {"inicio": F},
             "semanas": [{"orden": 1, "etiqueta": "1", "inicio": F, "fin": F}],
             "inscripcion_reinscripcion": [F]},
        ],
    }
    return json.dumps(datos, ensure_ascii=False, indent=2) + "\n"


# ---------------------------------------------------------------------- vista

def _marcas(doc):
    """{fecha: set(códigos)} y {lunes: etiqueta de semana} de un documento."""
    m, sem = {}, {}

    def poner(dias, codigo):
        for x in dias:
            m.setdefault(x, set()).add(codigo)
    for T in doc["trimestres"].values():
        if T["clases_inicio"]:
            poner([T["clases_inicio"]], "inicio")
        if T["clases_fin"]:
            poner([T["clases_fin"]], "fin")
        poner(T["inscripcion"], "IR")
        poner(T["globales"], "EG")
        poner(T["actas"], "RCA")
        poner(T["rec_inscripcion"], "IER")
        poner(T["rec_evaluaciones"], "ER")
        poner(T["rec_actas"], "RCR")
        for s in T["semanas"]:
            sem[lunes_de(s["inicio"])] = s["etiqueta"]
    return m, sem


def _meses(doc):
    """Para cada mes de la cobertura: (título, [(celdas, columna Sem)]), con cada celda
    (día o None, texto, clase de color, marcas)."""
    marcas, sem = _marcas(doc)
    descanso = set(doc["descansos"])
    ini, fin = doc["cobertura"]
    simb = doc["simbologia"]
    sigla = {c: (simb[k]["sigla"] if k else "") for c, _, k, _ in SIMBOLOS}
    orden_siglas = [simb[k]["sigla"] for _, _, k, _ in SIMBOLOS if k]
    meses = []
    d = ini.replace(day=1)
    while d <= fin:
        filas = []
        lunes = lunes_de(d)
        while lunes.month == d.month or lunes < d:
            celdas, codigos = [], []
            for k in range(7):
                x = lunes + dt.timedelta(days=k)
                for codigo, _, _, _ in SIMBOLOS:        # la columna Sem ve toda la semana
                    s = sigla[codigo]
                    if s and codigo in marcas.get(x, ()) and s not in codigos:
                        codigos.append(s)
                if x.month != d.month or not ini <= x <= fin:
                    celdas.append((None, "", "", ""))
                    continue
                simbolos = "".join(s for c, s, _, _ in SIMBOLOS if c in marcas.get(x, ()))
                if x in descanso:
                    color = "descanso"
                elif "inicio" in marcas.get(x, ()) or "fin" in marcas.get(x, ()):
                    color = "limite"
                elif x.weekday() >= 5:
                    color = ""
                else:
                    c = clase_de_dia(doc, x)
                    color = next(iter(c)) if len(c) == 1 else ("error" if c else "error")
                celdas.append((x, str(x.day), color, simbolos))
            codigos.sort(key=orden_siglas.index)
            col = "/".join(([sem[lunes]] if lunes in sem else []) + codigos)
            filas.append((celdas, col))
            lunes += dt.timedelta(days=7)
        meses.append((f"{L.MESES[d.month].capitalize()} {d.year}", filas))
        d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return meses


def _resumen(doc):
    """Renglones (concepto, fechas) por trimestre, y los periodos del documento."""
    simb = doc["simbologia"]
    out = []
    for clave in doc["orden"]:
        T = doc["trimestres"][clave]
        rec = (T["rec_inscripcion"], T["rec_evaluaciones"], T["rec_actas"])
        filas = []
        if T["parcial"]:
            titulo = f"{T['nombre']} (no enunciado en este documento; solo lo que muestra)"
            if T["tramo_visible"]:
                filas.append(("Días del trimestre que muestra", rango(*T["tramo_visible"])))
            if T["clases_inicio"]:
                filas.append(("Inicio de clases", L.f_larga(T["clases_inicio"]) +
                              f" de {T['clases_inicio'].year}"))
        else:
            titulo = f"{T['nombre']} ({clave})"
            p, ci, cf = T["periodo"], T["clases_inicio"], T["clases_fin"]
            filas += [("Trimestre", rango(*p)), ("Clases", rango_largo(ci, cf))]
            desc = [x for x in doc["descansos"] if p[0] <= x <= p[1]]
            filas.append(("Descansos en el trimestre",
                          ", ".join(L.f_larga(x) for x in desc) or "ninguno"))
            if T["vacaciones"]:
                filas.append(("Vacaciones dentro del trimestre",
                              "; ".join(rango(a, b) for a, b, _ in T["vacaciones"])))
        if T["semanas"]:
            filas.append((f"Semanas lectivas ({len(T['semanas'])})", "; ".join(
                f"{s['etiqueta']}: {rango_semana(s)}" for s in T["semanas"])))
        for nombre, dias in ((simb["inscripcion_reinscripcion"]["texto"], T["inscripcion"]),
                             (simb["evaluaciones_globales"]["texto"], T["globales"]),
                             (simb["registro_de_calificaciones"]["texto"], T["actas"]),
                             (simb["inscripcion_recuperacion"]["texto"], rec[0]),
                             (simb["evaluaciones_recuperacion"]["texto"], rec[1]),
                             (simb["registro_recuperacion"]["texto"], rec[2])):
            if dias or not T["parcial"]:
                filas.append((nombre, dias.texto() or "— (en otro documento)"))
        ext = T["periodo"] or T["tramo_visible"]
        cierre = Dias(x for x in T["actas"] if not ext or x > ext[1])
        if cierre:
            filas.append(("Registro de calificaciones posterior al trimestre", cierre.texto()))
        out.append((titulo, filas))
    periodos = [("Periodos intertrimestrales", "; ".join(
        rango(a, b) for a, b, _ in doc["intertrimestrales"]) or "ninguno"),
        ("Vacaciones", "; ".join(rango(a, b) + (f" ({n})" if n else "")
                                 for a, b, n in doc["vacaciones"]) or "ninguna")]
    return out, periodos


def vista(doc):
    """Un documento en Markdown: resumen por trimestre, periodos y los meses con su
    simbología (los colores, como letras: T trimestre, i intertrimestral, v vacaciones,
    c registro posterior al trimestre)."""
    simb = doc["simbologia"]
    letra = {TRIMESTRE: "", INTER: "ⁱ", VACACIONES: "ᵛ", CIERRE: "ᶜ", "error": "‼"}
    R = [f"# {doc['nombre']}", "",
         f"*{doc['texto_aprobacion']}. Fuente: {doc.get('fuente') or '—'}.*", ""]
    if doc["modifica"]:
        R += ["**Modifica a:** " + ", ".join(f"Calendario Escolar {a} (sesión {s})"
                                             for a, s in doc["modifica"]) +
              (f". Motivo: {doc['motivo']}." if doc["motivo"] else "."), ""]
    R += ["Simbología: **N** descanso obligatorio · > inicio de clases · < terminación de "
          "clases · " + " · ".join(f"{s} {simb[k]['texto']}" for _, s, k, _ in SIMBOLOS if k)
          + ". Días hábiles sin marca: trimestre; ⁱ periodo intertrimestral; ᵛ vacaciones; "
          "ᶜ registro de calificaciones posterior al trimestre. La columna Sem trae el número "
          "de semana lectiva o las siglas de los sucesos de esa semana.", ""]
    resumen, periodos = _resumen(doc)
    R += ["## Periodos del documento", "", "| Periodo | Fechas |", "|---|---|"]
    R += [f"| {a} | {b} |" for a, b in periodos] + [""]
    R += ["## Trimestres", ""]
    for titulo, filas in resumen:
        R += [f"### {titulo}", "", "| Concepto | Fechas |", "|---|---|"]
        R += [f"| {a} | {b} |" for a, b in filas] + [""]
    R += ["## Mes por mes", ""]
    for titulo, filas in _meses(doc):
        R += [f"### {titulo}", "", "| Lun | Mar | Mié | Jue | Vie | Sáb | Dom | Sem |",
              "|---|---|---|---|---|---|---|---|"]
        for celdas, col in filas:
            txt = []
            for x, dia, color, simbolos in celdas:
                if x is None:
                    txt.append(" ")
                elif color == "descanso":
                    txt.append(f"**{dia}**{simbolos}")
                else:
                    txt.append(f"{dia}{letra.get(color, '')}{simbolos}")
            R.append("| " + " | ".join(txt) + f" | {col} |")
        R.append("")
    return "\n".join(R).rstrip() + "\n"


_CSS = """
:root{--trim:#dcecf7;--inter:#fff9c4;--vac:#ffffff;--desc:#bdbdbd;--lim:#e6007e;
--cierre:#e3efd9;--borde:#222;--txt:#111;--fondo:#fff;--suave:#666}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--fondo:#fff;--txt:#111}}
body{font-family:Arial,Helvetica,sans-serif;background:var(--fondo);color:var(--txt);
margin:0;padding:16px;max-width:1400px}
h1{font-size:1.4rem;margin:.2rem 0}h2{font-size:1.1rem;margin:1.4rem 0 .5rem}
h3{font-size:.95rem;margin:.2rem 0;text-align:center}
.nota{color:var(--suave);font-size:.85rem}
.meses{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
table.mes{border-collapse:collapse;width:100%;font-size:.8rem}
table.mes th,table.mes td{border:1px solid var(--borde);padding:2px 4px;text-align:left;
height:1.3rem}
table.mes th{font-size:.7rem;text-align:center}
td.sem{text-align:center;font-size:.7rem;white-space:nowrap}
.trimestre{background:var(--trim)}.intertrimestral{background:var(--inter)}
.vacaciones{background:var(--vac)}.descanso{background:var(--desc)}
.limite{background:var(--lim);color:#fff;font-weight:bold}.cierre{background:var(--cierre)}
.error{background:repeating-linear-gradient(45deg,#fbb,#fbb 4px,#fff 4px,#fff 8px)}
table.res{border-collapse:collapse;font-size:.85rem;margin-bottom:.8rem;width:100%}
table.res td,table.res th{border:1px solid #ccc;padding:3px 6px;vertical-align:top;
text-align:left}
.leyenda span{display:inline-block;border:1px solid var(--borde);padding:1px 6px;margin:2px}
"""


def vista_html(doc):
    """Un documento en HTML, con los colores del calendario oficial."""
    e = html.escape
    simb = doc["simbologia"]
    resumen, periodos = _resumen(doc)
    H = ["<!doctype html><html lang='es'><head><meta charset='utf-8'>",
         "<meta name='viewport' content='width=device-width, initial-scale=1'>",
         f"<title>{e(doc['nombre'])}</title><style>{_CSS}</style></head><body>",
         f"<h1>{e(doc['nombre'])}</h1>",
         f"<p class='nota'>{e(doc['texto_aprobacion'])}. Fuente: {e(doc.get('fuente') or '—')}. "
         "Dibujado por programa-sitio a partir del JSON, para cotejarlo con el original.</p>"]
    if doc["modifica"]:
        H.append("<p><b>Modifica a:</b> " + e(", ".join(
            f"Calendario Escolar {a} (sesión {s})" for a, s in doc["modifica"])) +
            (e(f". Motivo: {doc['motivo']}.") if doc["motivo"] else "") + "</p>")
    H.append("<p class='leyenda'><span class='limite'>&gt;</span> inicio de clases "
             "<span class='limite'>&lt;</span> terminación de clases "
             "<span class='descanso'>&nbsp;</span> descanso obligatorio "
             "<span class='trimestre'>&nbsp;</span> trimestre "
             "<span class='intertrimestral'>&nbsp;</span> periodo inter-trimestral "
             "<span class='vacaciones'>&nbsp;</span> vacaciones "
             "<span class='cierre'>&nbsp;</span> registro de calificaciones posterior al "
             "trimestre <span class='error'>&nbsp;</span> día sin periodo o en dos<br>" +
             " · ".join(f"{s} {e(simb[k]['texto'])}" for _, s, k, _ in SIMBOLOS if k) + "</p>")
    H.append("<h2>Mes por mes</h2><div class='meses'>")
    for titulo, filas in _meses(doc):
        H.append(f"<div><h3>{e(titulo.upper())}</h3><table class='mes'><tr>" + "".join(
            f"<th>{x}</th>" for x in ("LUN", "MAR", "MIE", "JUE", "VIE", "SAB", "DOM", "SEM")) +
            "</tr>")
        for celdas, col in filas:
            H.append("<tr>" + "".join(
                f"<td class='{color}'>{e(dia)}{e(simbolos)}</td>" if x else "<td></td>"
                for x, dia, color, simbolos in celdas) + f"<td class='sem'>{e(col)}</td></tr>")
        H.append("</table></div>")
    H.append("</div><h2>Periodos del documento</h2><table class='res'>")
    H += [f"<tr><th>{e(a)}</th><td>{e(b)}</td></tr>" for a, b in periodos]
    H.append("</table><h2>Trimestres</h2>")
    for titulo, filas in resumen:
        H.append(f"<h3 style='text-align:left'>{e(titulo)}</h3><table class='res'>")
        H += [f"<tr><th>{e(a)}</th><td>{e(b)}</td></tr>" for a, b in filas]
        H.append("</table>")
    H.append("</body></html>")
    return "\n".join(H) + "\n"
