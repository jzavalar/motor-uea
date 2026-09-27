"""Del programa analítico al modelo del curso.

construir_modelo() lee la fuente con markdown.Documento, extrae lo que tiene la
estructura común de un programa analítico con aprendizaje basado en proyectos
(identificación, fases, calendario, proyectos, evaluación, lecturas), aplica las reglas
propias del curso declaradas en curso.yml (extraer, tablas, listas), combina los datos
que solo usa el sitio y valida que todo sea internamente consistente. Si algo no
cuadra, reúne TODOS los errores y lanza ErrorDeFuente: nunca devuelve un modelo a
medias."""

import datetime as dt
import glob
import os
import re

import jinja2

from . import lexico as L
from .markdown import (Documento, etiquetados, items_parentesis, numerada, parrafos,
                       partir_nivel_cero, texto_plano, vinetas)


class ErrorDeFuente(Exception):
    pass


class Errores(list):
    def __call__(self, mensaje):
        self.append(mensaje)


GUIONES = {"—", "–", "-", ""}


def _plano(t):
    return texto_plano(t or "")


# ------------------------------------------------------------ §1 identificación

def analizar_identificacion(doc, cfg, datos, E):
    ci = cfg["identificacion"]
    t = doc.tabla(ci["columnas"], ci.get("seccion"))
    if t is None:
        E(f"§{ci.get('seccion')}: no se encontró la tabla «{' | '.join(ci['columnas'])}»")
        return {}, [], {}
    filas = {}
    grupos_filas = []
    for f in t.filas:
        if len(f) < 2:
            continue
        etiqueta, contenido = _plano(f[0]), f[1]
        mg = re.match(r"^Grupo\s+(\S+)$", etiqueta)
        if mg:
            grupos_filas.append((mg.group(1), contenido))
        filas[etiqueta] = contenido

    def buscar(nombre):
        buscada = L.clave(ci["campos"].get(nombre, nombre))
        for etiqueta, contenido in filas.items():
            if L.clave(etiqueta).startswith(buscada):
                return contenido
        return None

    uea = {"filas": {L.clave(k): _plano(v) for k, v in filas.items()}}
    for nombre in ci["campos"]:
        v = buscar(nombre)
        if v is None:
            if nombre in ci.get("obligatorios", []):
                E(f"§1: falta el renglón «{ci['campos'][nombre]}»")
            continue
        uea[nombre] = v
    uea["nombre"] = _plano(uea.get("nombre", ""))
    uea["clave"] = re.sub(r"\s*\(véase.*?\)\s*$", "", _plano(uea.get("clave", ""))).strip()
    for k in ("plan", "division", "profesor", "modalidad"):
        if k in uea:
            uea[k] = _plano(uea[k])
    # correo: texto del enlace mailto o la dirección escrita
    crudo = uea.get("correo", "")
    m = (re.search(r"\[([^\]]+)\]\(mailto:", crudo)
         or re.search(r"[\w.+-]+(?:\\?@)[\w-]+(?:\.[\w-]+)+", crudo))
    if crudo and not m:
        E("§1: no se pudo leer el correo de contacto")
    uea["correo"] = (m.group(1) if m and m.groups() else (m.group(0) if m else "")) \
        .replace("\\@", "@")
    # mensajería (opcional): usuario de Telegram
    msj = uea.pop("mensajeria", None)
    if msj:
        mt = re.search(r"t\.me/([\w_]+)", msj) or re.search(r"\\?@([\w_]+)", msj)
        if mt:
            uea["telegram"] = mt.group(1)
    # sitio y repositorio: de la fuente o, si no están ahí, de curso.yml
    for k, desde in (("sitio", "url"), ("repositorio", "repositorio")):
        v = uea.get(k)
        mu = re.search(r"https?://[^\s)\]]+", v or "")
        uea[k] = (mu.group(0) if mu else cfg["sitio"].get(desde)
                  or (datos.get("uea") or {}).get(k))
        if not uea[k]:
            E(f"§1: no hay «{ci['campos'][k]}» en la fuente ni sitio.{desde} en curso.yml")
    if uea.get("sitio") and not uea["sitio"].endswith("/"):
        uea["sitio"] += "/"
    uea["unidad_corta"] = (cfg["sitio"].get("unidad_corta")
                           or (datos.get("uea") or {}).get("unidad_corta") or "")
    # encabezado: «Trimestre 26-Otoño · …» y «Universidad …»
    cab = "\n".join(doc.lineas[:doc.seccion(ci.get("seccion")).linea]) \
        if doc.seccion(ci.get("seccion")) else doc.texto
    mt = re.search(r"^Trimestre (\S+)", cab, re.M)
    uea["trimestre"] = mt.group(1) if mt else ""
    if not mt:
        E("encabezado: falta la línea «Trimestre NN-Periodo · …» antes de la sección 1")
    mi = re.search(r"^(Universidad [^\n]+?)\s*$", cab, re.M)
    uea["institucion"] = mi.group(1) if mi else ""

    # grupos: renglón por grupo («Grupo HA09 | Lunes y miércoles, de 14:00 a 16:00 h;
    # sala; 23 inscritos») o renglón «Grupo | HE57» más «Horario | …»
    grupos = []
    for gid, contenido in grupos_filas:
        grupos.append(_grupo(gid, contenido))
    if not grupos:
        g = filas.get("Grupo") or filas.get("Grupos")
        if g:
            horario = uea.get("horario", "")
            for gid in re.findall(r"\b[A-Z]{1,3}\d{2,3}\b", g) or [g.strip()]:
                grupos.append(_grupo(gid, horario))
        else:
            mg = re.search(r"Grupos?\s+([A-Z]{1,3}\d{2,3}(?:\s*(?:,|y)\s*[A-Z]{1,3}\d{2,3})*)",
                           cab)
            if mg:
                for gid in re.findall(r"[A-Z]{1,3}\d{2,3}", mg.group(1)):
                    grupos.append(_grupo(gid, uea.get("horario", "")))
    if not grupos:
        E("§1: no se encontró ningún grupo (renglón «Grupo XXNN» o «Grupo»)")
    return uea, grupos, filas


def _grupo(gid, contenido):
    g = {"id": gid, "horario": _plano(contenido), "dias": "", "inicio": "", "fin": "",
         "sala": "", "inscritos": None}
    mh = re.search(r"de (\d{1,2}:\d\d) a (\d{1,2}:\d\d)", contenido)
    if mh:
        g["inicio"], g["fin"] = mh.group(1), mh.group(2)
    md = re.match(r"^\s*([^,;]+?),\s*de\s+\d", contenido)
    if md:
        g["dias"] = md.group(1).strip()
    partes = [p.strip() for p in contenido.split(";")]
    for p in partes[1:]:
        mi = re.match(r"^(\d+) inscritos?$", p)
        if mi:
            g["inscritos"] = int(mi.group(1))
        elif p:
            g["sala"] = _plano(p)
    return g


def periodo_base(uea, doc, E):
    """Fechas del periodo a partir de los renglones de §1 (sin bloque de datos)."""
    per = {}
    r = L.rango_texto(uea.get("trimestre_lectivo", "") or "")
    if r:
        per["trimestre_inicio"], per["trimestre_fin"] = r
    elif uea.get("trimestre_lectivo"):
        E("§1: no se entiende el «Trimestre lectivo» (se espera «17 de septiembre al 11 "
          "de diciembre de 2026»)")
    r = L.rango_texto(uea.get("periodo_clases", "") or "")
    if r:
        per["primera_sesion"], per["ultima_sesion"] = r
    m = re.search(r"\((\d+) sesiones\)", uea.get("periodo_clases", "") or "")
    if m:
        per["sesiones_declaradas"] = int(m.group(1))
    r = L.rango_texto(uea.get("globales", "") or "")
    if r:
        per["globales_inicio"], per["globales_fin"] = r
    return per


# ---------------------------------------------------------------------- fases

def analizar_fases(doc, cfg, E):
    t = doc.tabla(cfg["secciones"]["fases"]["columnas"])
    if t is None:
        E("§5: no se encontró la tabla de fases «Fase | Actividad | …»")
        return []
    fases = []
    for f in t.filas:
        if not f or not f[0].strip():
            continue
        celda = _plano(f[0])
        m = re.match(r"^(.+?)\s*\((.+)\)$", celda)
        fase = {"fase": m.group(1).strip() if m else celda,
                "actividad": f[1] if len(f) > 1 else ""}
        if m:
            fase["nombre_largo"] = celda
        if len(f) > 2:
            fase["iag"] = _plano(f[2])
        fases.append(fase)
    return fases


def normalizar_fase(texto, fases):
    """'activista' -> 'Activista'; None si no es una fase conocida."""
    c = L.clave(texto)
    for f in fases:
        if L.clave(f) == c or L.clave(f).startswith(c) or c.startswith(L.clave(f)):
            return f
    return None


# ------------------------------------------------------------------ calendario

def analizar_calendario(doc, cfg, fases, periodo, E):
    t = doc.tabla(cfg["secciones"]["calendario"]["columnas"])
    if t is None:
        E("§7: no se encontró la tabla de sesiones «Núm. | Fecha | Bloque | Fase | "
          "Actividad | IAG»")
        return {}, [], []
    vocab = cfg["vocabulario"]
    iag = {_plano(k): v for k, v in vocab["iag"].items()}
    ini = periodo.get("trimestre_inicio") or dt.date.today()
    fin = periodo.get("trimestre_fin") or ini
    efectivas = periodo.get("_efectivas")
    S, filas, descansos = {}, [], []
    ni = 0
    # columnas por su nombre, no por su posición: una columna agregada no desordena nada
    cols = [L.clave(c) for c in cfg["secciones"]["calendario"]["columnas"]]
    idx = [t.claves.index(c) for c in cols]
    for fila in t.filas:
        if len(fila) < len(t.claves):
            E(f"§7: una fila de la tabla de sesiones tiene {len(fila)} columnas y el "
              f"encabezado {len(t.claves)}: {' | '.join(fila)}")
            continue
        num, fecha_txt, bloque, fase_txt, actividad, ia_txt = [fila[i].strip() for i in idx]
        ia_cod = iag.get(_plano(ia_txt))
        if ia_cod is None:
            E(f"§7: valor de IAG desconocido «{ia_txt}» en la fila «{num} {fecha_txt}»; "
              "agréguelo a vocabulario.iag en curso.yml")
            ia_cod = "na"
        if num in GUIONES:
            if vocab["descanso"] and re.search(r"\b" + re.escape(vocab["descanso"].split()[0])
                                               + r"\b", actividad, re.I):
                d, _ = L.fecha_corta(fecha_txt, ini, fin)
                if d is None:
                    E(f"§7: no se entiende la fecha del descanso «{fecha_txt}»")
                descansos.append({"fecha": d, "texto": fecha_txt})
                filas.append({"fecha": fecha_txt, "descanso": True, "nota": ""})
            else:
                filas.append({"fecha": fecha_txt, "bloque": bloque,
                              "actividad": actividad, "ia": ia_cod})
            continue
        if not num.isdigit():
            E(f"§7: número de sesión no válido «{num}»")
            continue
        ni += 1
        numero = int(num)
        if numero != ni:
            E(f"§7: la sesión {numero} está en el lugar {ni}: la numeración debe ser "
              "consecutiva desde 1")
        fecha, dsem = L.fecha_corta(fecha_txt, ini, fin)
        if fecha is None:
            E(f"§7: no se entiende la fecha «{fecha_txt}» de la sesión {numero} "
              "(se espera «Lun 21 sep»)")
        elif L.sin_acentos(dsem).lower()[:3] != L.sin_acentos(L.DIAS_C[fecha.weekday()]).lower():
            E(f"§7: la sesión {numero} dice «{fecha_txt}», pero el {L.f_dma(fecha)} es "
              f"{L.DIAS[fecha.weekday()]}")
        if efectivas is not None:
            if ni <= len(efectivas) and fecha and fecha != efectivas[ni - 1]:
                E(f"§7: la sesión {numero} dice «{fecha_txt}», pero el periodo calcula "
                  f"«{L.f_corta(efectivas[ni - 1])}»")
        mh = re.match(vocab["holgura"], bloque)
        proyectos = re.findall(r"\bP\d+\b", bloque)
        if mh:
            tipo, n_h, bloque_id = "holgura", int(mh.group(1)), None
        elif proyectos:
            tipo, n_h, bloque_id = "proyecto", None, proyectos[0]
        else:
            tipo, n_h, bloque_id = "intro", None, bloque
        fases_s = {}
        if tipo == "proyecto" and fase_txt not in GUIONES:
            partes = [x for x in re.split(r"\s+y\s+|\s*,\s*", fase_txt) if x]
            nombres = [normalizar_fase(x, fases) for x in partes]
            if None in nombres:
                E(f"§7: la sesión {numero} tiene la fase «{fase_txt}», que no está en la "
                  f"tabla de fases ({', '.join(fases)})")
            elif len(nombres) == len(proyectos):
                fases_s = dict(zip(proyectos, nombres))
            elif len(nombres) == 1:
                fases_s = {pid: nombres[0] for pid in proyectos}
            else:
                E(f"§7: la sesión {numero} tiene {len(proyectos)} proyectos "
                  f"({bloque}) y {len(nombres)} fases ({fase_txt}): deben coincidir")
        s = {"num": numero, "fecha": fecha, "bloque": bloque_id, "bloque_texto": bloque,
             "proyectos": proyectos, "fases": fases_s, "tipo": tipo, "n": n_h,
             "fase": fases_s.get(bloque_id) if bloque_id else None,
             "actividad": actividad, "ia": ia_cod}
        S[numero] = s
        filas.append({"num": numero, "fecha": fecha_txt, "sesion": s,
                      "fase": s["fase"] or "—", "actividad": actividad, "ia": ia_cod})
    fechas = [s["fecha"] for s in S.values() if s["fecha"]]
    if fechas != sorted(fechas):
        E("§7: las fechas de las sesiones no están en orden")
    return S, filas, descansos


def fechas_de_clase(periodo):
    d, fin = periodo["primera_sesion"], periodo["ultima_sesion"]
    dias = set(periodo["dias"])
    desc = {x["fecha"] for x in periodo.get("descansos", [])}
    todas, efectivas = [], []
    while d <= fin:
        if d.weekday() in dias:
            todas.append(d)
            if d not in desc:
                efectivas.append(d)
        d += dt.timedelta(days=1)
    return todas, efectivas


def armar_periodo(doc, base, E):
    """Si la fuente trae el bloque oculto «fuente-datos: periodo», manda ese (y se
    contrasta con §1); si no, el periodo sale de §1 y de la tabla de sesiones."""
    oculto = doc.datos.get("periodo")
    if isinstance(oculto, dict) and "periodo" in oculto:
        oculto = oculto["periodo"]
    if not oculto:
        return dict(base), False
    per = dict(oculto)
    for campo in ("trimestre_inicio", "trimestre_fin", "primera_sesion", "ultima_sesion",
                  "globales_inicio", "globales_fin"):
        if campo in base and campo in per and base[campo] != per[campo]:
            E(f"§7: el bloque de datos dice {campo} = {per[campo]}, pero §1 dice "
              f"{base[campo]}")
    for campo in ("primera_sesion", "ultima_sesion", "dias", "descansos"):
        if campo not in per:
            E(f"§7: falta «{campo}» en el bloque de datos del periodo")
    for d in per.get("descansos", []):
        if "dias" in per and d["fecha"].weekday() not in per["dias"]:
            E(f"§7: el descanso {d['fecha']} no cae en día de clase")
    if all(k in per for k in ("primera_sesion", "ultima_sesion", "dias")):
        per["_todas"], per["_efectivas"] = fechas_de_clase(per)
    return per, True


# -------------------------------------------------------------------- proyectos

def _etiqueta(lista, patron):
    for etiqueta, cuerpo, bloque in lista:
        if re.search(patron, etiqueta, re.I):
            return etiqueta, cuerpo, bloque
    return None


def _una_linea(t):
    return " ".join(t.split())


def analizar_evaluacion_escrita(cuerpo, bloque):
    ev = {}
    m = re.search(r"Reactivos(?: sobre ([^:\n]+))?:\s*", cuerpo)
    if not m:
        return {"ambito": "", "reactivos": numerada(bloque)}
    previo = _una_linea(cuerpo[:m.start()])
    if previo:
        ev["previo"] = previo
    ev["ambito"] = (m.group(1) or "").strip()
    en_linea = _una_linea(cuerpo[m.end():])
    ps = _siguientes(cuerpo, bloque)
    if en_linea:
        ev["reactivos"] = [r.rstrip(".") for r in partir_nivel_cero(en_linea.rstrip("."))]
        resto = ps
    else:
        lista, resto = _primer_grupo(ps, numerada)
        ev["reactivos"] = lista
    posterior = "\n\n".join(p for p in resto if p)
    if posterior.strip():
        ev["posterior"] = posterior.strip()
    md = re.search(r"(\d+) minutos", cuerpo)
    if md:
        ev["duracion"] = int(md.group(1))
    return ev


def _primer_grupo(ps, extraer):
    """(elementos del primer grupo de párrafos consecutivos que son lista, resto)"""
    items, resto, dentro, cerrado = [], [], False, False
    for p in ps:
        e = extraer(p) if not cerrado else []
        if e and not cerrado:
            items += e
            dentro = True
        else:
            if dentro:
                cerrado = True
            resto.append(p)
    return items, resto


def _siguientes(cuerpo, bloque):
    """Párrafos del bloque que siguen al del cuerpo de la etiqueta."""
    ps = parrafos(bloque)
    if cuerpo.strip() and ps and ps[0] == cuerpo.strip():
        return ps[1:]
    return ps


def analizar_criterios(cuerpo, bloque):
    if vinetas(cuerpo):
        items = vinetas(cuerpo)
    elif cuerpo.strip():
        items = partir_nivel_cero(_una_linea(cuerpo).rstrip("."))
    else:
        items, _ = _primer_grupo(_siguientes(cuerpo, bloque), vinetas)
    criterios = []
    for b in items:
        b = b.strip().rstrip(".")
        mc = re.match(r"^(.*?)\s*\(([^()]+)\)$", b)
        nombre, nota = (mc.group(1).strip(), mc.group(2).strip()) if mc else (b, None)
        c = {"nombre": nombre[:1].upper() + nombre[1:]}
        if nota:
            c["nota"] = nota
        criterios.append(c)
    return criterios


LEGIBLE = {"proposito": "«**Propósito.**»",
           "condiciones": "«**Condiciones.**» o «**Insumo.**»",
           "expediente": "«**Expediente.**» o «**Contenido del expediente….**»",
           "evaluacion": "«**Evaluación escrita N.**» o «**Examen escrito N.**»",
           "criterios": "«**Criterios de la rúbrica.**»"}


def analizar_proyecto(doc, s, pid, nombre, cfg, E):
    cp = cfg["proyecto"]
    texto = doc.texto_de(s)
    p = {"id": pid, "nombre": nombre, "slug": L.slug(f"{pid} {nombre}"),
         "seccion": s.numero, "texto": texto}
    et = etiquetados(texto)

    def campo(rol, obligatorio=True):
        r = _etiqueta(et, cp["etiquetas"][rol])
        if r is None and obligatorio:
            E(f"{pid}: no se encontró el párrafo que empieza con {LEGIBLE.get(rol, rol)} "
              f"(etiqueta en negritas; se busca con proyecto.etiquetas.{rol} de curso.yml)")
        return r

    r = campo("proposito")
    p["proposito"] = _una_linea(r[1]) if r else ""
    r = campo("condiciones")
    p["condiciones"] = {"titulo": r[0], "texto": _una_linea(r[1])} if r else \
        {"titulo": "", "texto": ""}
    r = campo("expediente")
    p["expediente"] = []
    if r:
        cuerpo = r[1].split("**")[0]
        for txt, insumo in items_parentesis(cuerpo):
            e = {"texto": txt}
            if insumo:
                e["insumo_de"] = insumo
            p["expediente"].append(e)
        if not p["expediente"]:
            E(f"{pid}: el expediente no tiene puntos «(1) … (2) …»")
    r = campo("evaluacion")
    p["evaluacion"] = analizar_evaluacion_escrita(r[1], r[2]) if r else \
        {"ambito": "", "reactivos": []}
    r = campo("criterios")
    p["criterios"] = analizar_criterios(r[1], r[2]) if r else []
    if r and not p["criterios"]:
        E(f"{pid}: la lista de criterios de la rúbrica está vacía")

    # productos de cada sesión, desde la tabla del proyecto
    p["_tabla_sesiones"] = {}
    t = None
    for tb in doc.tablas(texto):
        if tb.tiene(cp["sesiones"]["columnas"]):
            t = tb
            break
    if t is None:
        E(f"{pid}: no se encontró la tabla de sesiones del proyecto "
          f"«{' | '.join(cp['sesiones']['columnas'])} | …»")
    else:
        i_prod = next((i for i, c in enumerate(t.claves) if c.startswith("producto")), None)
        i_fase = t.claves.index("fase")
        i_act = t.claves.index("actividad")
        i_fecha = t.claves.index("fecha") if "fecha" in t.claves else None
        for f in t.filas:
            nums = L.numeros(f[0])
            if not nums:
                E(f"{pid}: número de sesión no válido «{f[0]}» en la tabla del proyecto")
                continue
            p["_tabla_sesiones"][nums[0]] = {
                "fecha": f[i_fecha] if i_fecha is not None and i_fecha < len(f) else "",
                "fase": f[i_fase] if i_fase < len(f) else "",
                "actividad": f[i_act] if i_act < len(f) else "",
                "producto": f[i_prod] if i_prod is not None and i_prod < len(f) else ""}
    return p


def analizar_sintesis(doc, cfg, ids, E):
    s = doc.seccion(cfg["secciones"]["organizacion"])
    if s is None:
        return {}
    sintesis = {}
    for b in vinetas(doc.texto_de(s)):
        m = re.match(r"^(?:\*\*)?(P\d+)(?:\*\*)?[\s:—–-]+(.+?)\.?$", b)
        if m:
            sintesis[m.group(1)] = m.group(2).strip()
    for pid in ids:
        if pid not in sintesis:
            E(f"§{s.numero}: no se encontró la síntesis de {pid} («- **{pid}** …»)")
    for pid in sintesis:
        if pid not in ids:
            E(f"§{s.numero}: hay síntesis de {pid}, pero la sección 6 no tiene ese proyecto")
    return sintesis


# ------------------------------------------------------------------- evaluación

RE_PCT = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")


def _pct(t):
    return [float(x.replace(",", ".")) if "." in x or "," in x else int(x)
            for x in RE_PCT.findall(t)]


def analizar_componentes(doc, cfg, ids, E):
    ce = cfg["evaluacion"]
    t = doc.tabla(cfg["secciones"]["componentes"]["columnas"])
    if t is None:
        E("§8: no se encontró la tabla de componentes «Componente | … | Ponderación»")
        return {"componentes": [], "escrito": 0, "total": 0}
    i_peso = t.claves.index("ponderacion")
    i_fecha = next((i for i, c in enumerate(t.claves) if c.startswith("fecha")), None)
    i_forma = 1 if i_peso != 1 else None
    comps, subtotal, total_tabla = [], None, None
    for f in t.filas:
        nombre = _plano(f[0])
        peso_txt = f[i_peso] if i_peso < len(f) else ""
        fecha_txt = f[i_fecha] if i_fecha is not None and i_fecha < len(f) else ""
        forma = _plano(f[i_forma]) if i_forma is not None and i_forma < len(f) else ""
        pesos = _pct(peso_txt)
        if re.match(r"^Subtotal", nombre, re.I):
            subtotal = pesos[-1] if pesos else None
            continue
        if re.match(r"^Total\b", nombre, re.I):
            total_tabla = pesos[-1] if pesos else None
            continue
        me = re.match(ce["escrita"], nombre, re.I)
        if me:
            n = int(me.group(1))
            mp = re.search(r"\((P\d+)\)", nombre)
            pid = mp.group(1) if mp else (f"P{n}" if f"P{n}" in ids else None)
            c = {"id": f"e{n}", "n": n, "nombre": nombre, "escrita": True,
                 "peso": pesos[0] if pesos else 0, "forma": forma, "cuando": fecha_txt}
            if pid:
                c["proyecto"] = pid
            ms = re.search(r"[Ss]esi[oó]n (\d+)", fecha_txt)
            if ms:
                c["sesion_declarada"] = int(ms.group(1))
            else:
                c["_fecha_texto"] = fecha_txt
            if not pesos:
                E(f"§8.2: el componente «{nombre}» no tiene ponderación")
            comps.append(c)
            continue
        if re.match(ce["expediente"], nombre, re.I):
            projs = re.findall(r"\bP\d+\b", nombre) or list(ids)
            if len(pesos) == len(projs) + 1 and abs(sum(pesos[:-1]) - pesos[-1]) < 1e-9:
                cada = pesos[:-1]
            elif len(pesos) == len(projs):
                cada = pesos
            elif pesos and "cada" in peso_txt:
                cada = [pesos[0]] * len(projs)
                if len(pesos) > 1 and abs(pesos[0] * len(projs) - pesos[1]) > 1e-9:
                    E(f"§8.2: «{peso_txt}»: {len(projs)} × {pesos[0]} % no es {pesos[1]} %")
            else:
                E(f"§8.2: no sé repartir «{peso_txt}» entre {', '.join(projs)}; escriba "
                  "«10 % + 12 % + 18 % = 40 %» o «5 % cada uno»")
                cada = [0] * len(projs)
            if len(pesos) == len(projs) + 1 and abs(sum(pesos[:-1]) - pesos[-1]) > 1e-9:
                E(f"§8.2: «{peso_txt}»: la suma de las partes no es el total")
            for pid, peso in zip(projs, cada):
                comps.append({"id": f"exp{pid[1:]}", "nombre": f"Expediente {pid}",
                              "proyecto": pid, "escrita": False, "peso": peso,
                              "forma": forma, "cuando": fecha_txt, "fila": nombre})
            continue
        cid = next((v for k, v in ce["ids"].items() if re.match(k, nombre, re.I)),
                   L.slug(nombre)[:20])
        comps.append({"id": cid, "nombre": nombre, "escrita": False,
                      "peso": pesos[0] if pesos else 0, "forma": forma,
                      "cuando": fecha_txt})
        if not pesos:
            E(f"§8.2: el componente «{nombre}» no tiene ponderación")
    total = sum(c["peso"] for c in comps)
    escrito = sum(c["peso"] for c in comps if c["escrita"])
    if abs(total - 100) > 1e-9:
        E(f"§8.2: las ponderaciones suman {total} %, no 100 %")
    if subtotal is not None and abs(subtotal - escrito) > 1e-9:
        E(f"§8.2: el subtotal de la tabla dice {subtotal} %, pero las evaluaciones "
          f"escritas suman {escrito} %")
    if total_tabla is not None and abs(total_tabla - total) > 1e-9:
        E(f"§8.2: el total de la tabla dice {total_tabla} %, pero los componentes "
          f"suman {total} %")
    # duración de las escritas: oración general, si la hay
    m = re.search(ce["duracion"], doc.texto) if ce.get("duracion") else None
    if m:
        for tramo in m.group(0).split(";"):
            mt = re.search(r"(\d+(?:\s*(?:,|y)\s*\d+)*)\D+?(\d+) minutos", tramo)
            if mt:
                for n in L.numeros(mt.group(1)):
                    for c in comps:
                        if c["escrita"] and c["n"] == n:
                            c["duracion"] = int(mt.group(2))
    return {"componentes": comps, "escrito": escrito, "total": total}


def analizar_rubrica(doc, cfg, E):
    cr = cfg["rubrica"]
    r = {"niveles": cr["niveles"], "criterios": None, "puntos": None, "comunes": []}
    m = re.search(cr["criterios"], doc.texto) if cr.get("criterios") else None
    if m:
        r["criterios"] = L.numero(m.group(1))
        if r["criterios"] is None:
            E(f"§8: no reconozco el número «{m.group(1)}» de criterios de la rúbrica")
    m = re.search(cr["puntos"], doc.texto) if cr.get("puntos") else None
    if m:
        r["puntos"] = int(m.group(1))
    if cr.get("comunes"):
        t = doc.tabla(cr["comunes"]["columnas"])
        if t is None:
            E("§8: no se encontró la tabla de criterios comunes de la rúbrica")
        else:
            for f in t.filas:
                r["comunes"].append({"nombre": _plano(f[0]), "niveles": f[1:]})
    return r


# --------------------------------------------------------------------- lecturas

def analizar_lecturas(doc, cfg, datos, S, n_sesiones, E):
    cl = cfg["lecturas"]
    t = doc.tabla(cfg["secciones"]["lecturas"]["columnas"])
    if t is None:
        return []
    carpeta = os.path.join(cfg["_raiz"], cl["carpeta"])
    apoyo = list(datos.get(cl["apoyo_desde"], [])) if cl.get("apoyo_desde") else None
    sobre = datos.get(cl["sobre_desde"], {}) if cl.get("sobre_desde") else None
    lecturas, i_apoyo = [], 0
    for reg in t.registros():
        clave_l = _plano(reg.get("clave", ""))
        sesiones = L.numeros(reg.get("sesiones", ""))
        temas = re.findall(r"\d+\.\d+", reg.get("temas", ""))
        extra = {k: v for k, v in reg.items()
                 if k not in ("clave", "titulo", "temas", "sesiones")}
        if clave_l == cl["apoyo"]:
            l = {"clave": clave_l, "titulo": _plano(reg.get("titulo", "")),
                 "sesiones": sesiones, "temas": temas, "extra": extra}
            if apoyo is not None:
                if i_apoyo >= len(apoyo):
                    E(f"§9.1: hay más lecturas de apoyo en la tabla que en "
                      f"{cl['apoyo_desde']} (datos)")
                    continue
                l.update(apoyo[i_apoyo])
                i_apoyo += 1
            lecturas.append(l)
            continue
        archivo = None
        for patron in (f"{clave_l}-*.md", f"{clave_l.lower()}-*.md", f"{clave_l.lower()}.md",
                       f"{clave_l}.md"):
            c = sorted(glob.glob(os.path.join(carpeta, patron)))
            if c:
                archivo = os.path.basename(c[0])
                break
        if archivo is None and cl.get("exigir_archivo"):
            E(f"§9.1: no existe {cl['carpeta']}/{clave_l}-*.md")
        proyecto = None
        validas = [s for s in sesiones if s in S]
        if validas:
            s_max = S[max(validas)]
            if s_max["tipo"] == "proyecto":
                proyecto = s_max["bloque"]
        for s in sesiones:
            if not 1 <= s <= n_sesiones:
                E(f"§9.1: la lectura {clave_l} menciona la sesión {s}, que no existe")
        l = {"clave": clave_l, "titulo": _plano(reg.get("titulo", "")), "archivo": archivo,
             "sesiones": sesiones, "temas": temas, "proyecto": proyecto, "extra": extra,
             "sobre": ""}
        if sobre is not None:
            if clave_l not in sobre:
                E(f"§9.1: falta «{clave_l}» en {cl['sobre_desde']} (datos)")
            l["sobre"] = sobre.get(clave_l, "")
        lecturas.append(l)
    if apoyo is not None and i_apoyo != len(apoyo):
        E(f"§9.1: hay menos lecturas de apoyo en la tabla que en {cl['apoyo_desde']}")
    for l in lecturas:
        l["corto"] = re.split(r":\s| \(", l["titulo"])[0].strip()
    return lecturas


# ------------------------------------------------ reglas declarativas del curso

TIPOS = {
    "entero": lambda v: int(v),
    "numero": lambda v: L.numero(v),
    "lista": lambda v: L.numeros(v),
    "texto": lambda v: v.strip(),
    "linea": lambda v: " ".join(v.split()),
}


def _poner(destino_dict, ruta, valor):
    partes = ruta.split(".")
    d = destino_dict
    for k in partes[:-1]:
        d = d.setdefault(k, {})
    if isinstance(d.get(partes[-1]), dict) and isinstance(valor, dict):
        d[partes[-1]].update(valor)
    else:
        d[partes[-1]] = valor


def _texto_regla(doc, regla, texto_base):
    if regla.get("seccion"):
        s = doc.seccion(regla["seccion"])
        return doc.texto_de(s) if s else None
    return texto_base


def aplicar_extraer(doc, reglas, texto_base, destino, E, contexto=""):
    for nombre, r in (reglas or {}).items():
        texto = _texto_regla(doc, r, texto_base)
        if texto is None:
            E(f"{contexto}extraer.{nombre}: no existe la sección {r['seccion']}")
            continue
        m = re.search(r["patron"], texto, re.M | re.S if r.get("multilinea") else re.M)
        if not m:
            if r.get("obligatorio", True):
                E(f"{contexto}{r.get('mensaje') or f'no se encontró el texto de «{nombre}»'} "
                  f"(regla extraer.{nombre} de curso.yml)")
            continue
        tipos = r.get("tipos", {})
        if m.groupdict():
            valor = {}
            for g, v in m.groupdict().items():
                if v is None:
                    continue
                conv = TIPOS.get(tipos.get(g, "linea"))
                try:
                    valor[g] = conv(v)
                except (ValueError, TypeError):
                    valor[g] = None
                if valor[g] is None:
                    E(f"{contexto}extraer.{nombre}: no entiendo «{v}» como {tipos.get(g)}")
        else:
            conv = TIPOS.get(r.get("tipo", "linea"))
            valor = conv(m.group(1) if m.groups() else m.group(0))
        _poner(destino, r.get("destino", nombre), valor)


def aplicar_tablas(doc, reglas, texto_base, destino, E, contexto="", proyectos=None):
    for nombre, r in (reglas or {}).items():
        base = _texto_regla(doc, r, texto_base)
        t = None
        if base is not None:
            for tb in doc.tablas(base):
                if tb.tiene(r["columnas"]):
                    t = tb
                    break
        if t is None:
            if r.get("obligatorio", True):
                E(f"{contexto}no se encontró la tabla «{' | '.join(r['columnas'])}» "
                  f"(regla tablas.{nombre} de curso.yml)")
            continue
        forma = r.get("forma", "registros")
        cols = r.get("columnas_salida")
        idx = [t.claves.index(L.clave(c)) for c in cols] if cols else range(len(t.claves))
        if forma == "filas":
            valor = [[_limpiar(f[i], r) for i in idx if i < len(f)] for f in t.filas]
        else:
            valor = []
            for reg in t.registros(r.get("renombrar")):
                valor.append({k: _limpiar(v, r, k) for k, v in reg.items()})
        if r.get("por_proyecto"):
            col = L.clave(r.get("columna_proyecto", "Proyecto"))
            por = {}
            for reg in valor:
                por[_plano(reg.get(col, ""))] = reg
            for p in proyectos or []:
                if p["id"] not in por:
                    if r.get("obligatorio", True):
                        E(f"{contexto}la tabla «{' | '.join(r['columnas'])}» no tiene la "
                          f"fila de {p['id']}")
                    continue
                _poner(p, r.get("destino", nombre), por[p["id"]])
        else:
            _poner(destino, r.get("destino", nombre), valor)


def _limpiar(v, regla, k=None):
    v = v.strip()
    if v in GUIONES and regla.get("guion_vacio", False):
        return None
    if regla.get("plano"):
        v = _plano(v)
    if k is not None and k in regla.get("minuscula_inicial", []):
        v = L.f_minuscula_inicial(v)
    return v


def aplicar_listas(doc, reglas, texto_base, destino, E, contexto=""):
    for nombre, r in (reglas or {}).items():
        base = _texto_regla(doc, r, texto_base)
        bloque = None
        if base is not None and r.get("despues_de"):
            e = _etiqueta(etiquetados(base), r["despues_de"])
            bloque = e[2] if e else None
        elif base is not None and r.get("desde"):
            md = re.search(r["desde"], base, re.M)
            if md:
                resto = base[md.end():]
                mh = re.search(r["hasta"], resto, re.M) if r.get("hasta") else None
                bloque = resto[:mh.start()] if mh else resto
        if bloque is None:
            if r.get("obligatorio", True):
                E(f"{contexto}no se encontró la lista «{nombre}» (regla listas.{nombre} "
                  "de curso.yml)")
            continue
        items, _ = _primer_grupo(parrafos(bloque), numerada if r.get("numerada")
                                 else vinetas)
        valor = []
        for it in items:
            if r.get("patron"):
                m = re.match(r["patron"], it)
                if not m:
                    E(f"{contexto}listas.{nombre}: no entendí «{it}»")
                    continue
                reg = {k: v.strip() for k, v in m.groupdict().items() if v is not None}
                reg.update(r.get("fijos", {}))
                valor.append(reg)
            else:
                valor.append(dict(r["fijos"], **{"texto": it}) if r.get("fijos") else it)
        if not valor and r.get("obligatorio", True):
            E(f"{contexto}la lista «{nombre}» está vacía")
        _poner(destino, r.get("destino", nombre), valor)


# ------------------------------------------------------------------- ensamble

def construir_modelo(cfg, recolectar=False):
    """recolectar=True: en vez de lanzar ErrorDeFuente, devuelve (ctx, errores) con todo
    lo que se pudo armar (lo usa programa-sitio revisar)."""
    E = Errores()
    ruta = os.path.join(cfg["_raiz"], cfg["fuente"])
    try:
        with open(ruta, encoding="utf-8") as f:
            texto = f.read()
    except FileNotFoundError:
        raise ErrorDeFuente(f"  · no existe la fuente {cfg['fuente']}")
    doc = Documento(texto)
    for e in doc.errores_datos + doc.errores_estructura:
        E(e)
    datos = cfg["_datos"]

    uea, grupos, _ = analizar_identificacion(doc, cfg, datos, E)
    base = periodo_base(uea, doc, E)
    periodo, con_bloque = armar_periodo(doc, base, E)
    fases_tabla = analizar_fases(doc, cfg, E)
    fases = [f["fase"] for f in fases_tabla]
    fase_entrega = cfg["vocabulario"].get("fase_entrega") or (fases[-1] if fases else None)

    S, filas, descansos_tabla = analizar_calendario(doc, cfg, fases, periodo, E)
    n_sesiones = len(S)
    if not con_bloque:
        # el periodo sale de §1 + la tabla
        # los días de clase: los del horario del grupo, si se entienden; si no, los que
        # se repiten en la tabla (así una fecha mal escrita no inventa un día de clase)
        dias_h = set()
        for g in grupos:
            texto_d = L.sin_acentos((g.get("dias") or g.get("horario") or "").lower())
            dias_h |= {DIA_NUM[d] for d in re.findall(r"[a-z]+", texto_d) if d in DIA_NUM}
        from collections import Counter
        cuenta = Counter(s["fecha"].weekday() for s in S.values() if s["fecha"])
        dias_tabla = sorted(d for d, c in cuenta.items() if c >= 2)
        horario_distinto = bool(dias_h) and bool(dias_tabla) and sorted(dias_h) != dias_tabla
        if horario_distinto:
            E(f"§1: el horario dice {L.f_y([L.DIAS[d] for d in sorted(dias_h)])}, pero las "
              f"sesiones de §7 son {L.f_y([L.DIAS[d] for d in dias_tabla])}")
        periodo["dias"] = dias_tabla if horario_distinto or not dias_h else sorted(dias_h)
        periodo["descansos"] = [{"fecha": d["fecha"], "nota": ""} for d in descansos_tabla
                                if d["fecha"]]
        if "primera_sesion" in periodo:
            periodo["_todas"], periodo["_efectivas"] = fechas_de_clase(periodo)
            ef = periodo["_efectivas"]
            fechas_S = [S[n]["fecha"] for n in sorted(S)]
            if len(ef) != len(fechas_S) or ef != fechas_S:
                dif = next(((i + 1, a, b) for i, (a, b) in enumerate(zip(fechas_S, ef))
                            if a != b), None)
                detalle = (f"; la primera diferencia es la sesión {dif[0]}: la tabla dice "
                           f"{L.f_dma(dif[1]) if dif[1] else '—'} y el periodo da "
                           f"{L.f_dma(dif[2])}") if dif else ""
                E(f"§7: las fechas de la tabla ({len(fechas_S)} sesiones) no coinciden con "
                  f"los {len(ef)} {' y '.join(L.DIAS[d] for d in periodo['dias'])} del "
                  f"periodo de clases menos los descansos de la tabla{detalle}")
    else:
        ef = periodo.get("_efectivas", [])
        if len(ef) != n_sesiones:
            E(f"§7: la tabla tiene {n_sesiones} sesiones numeradas, pero el periodo y los "
              f"descansos dan {len(ef)} fechas de clase")
        desc_bloque = periodo.get("descansos", [])
        if len(descansos_tabla) != len(desc_bloque):
            E(f"§7: la tabla muestra {len(descansos_tabla)} descansos, pero el bloque de "
              f"datos declara {len(desc_bloque)}")
    notas = [d.get("nota", "") for d in periodo.get("descansos", [])]
    for fc, nota in zip([f for f in filas if f.get("descanso")], notas):
        fc["nota"] = nota
    if "sesiones_declaradas" in periodo and periodo["sesiones_declaradas"] != n_sesiones:
        E(f"§1: el periodo de clases dice {periodo['sesiones_declaradas']} sesiones, pero "
          f"la tabla de §7 tiene {n_sesiones}")
    periodo.setdefault("fin_de_clases", _fin_de_clases(doc, periodo))
    mf = re.search(r"^\*?Fuente:?\*?:?\s*(.+?)\.?\s*$", doc.texto, re.M)
    periodo.setdefault("fuente", mf.group(1).strip() if mf else "")

    # proyectos
    patron = cfg["secciones"]["proyectos"]
    secciones_p = [(s, re.match(patron, s.titulo)) for s in doc.secciones]
    for s_, m_ in secciones_p:
        if not m_ and re.match(r"^Proyecto\b", s_.titulo):
            E(f"§{s_.numero or '6'}: el encabezado «{s_.titulo_completo}» no tiene la forma "
              "«Proyecto PN · Nombre» (o «Proyecto PN: Nombre»); el motor no lo reconoce "
              "como proyecto")
    secciones_p = [(s, m) for s, m in secciones_p if m]
    if not secciones_p:
        E("§6: no se encontró ninguna sección «Proyecto PN · Nombre»")
    ids = [m.group(1) for _, m in secciones_p]
    if len(set(ids)) != len(ids):
        E(f"§6: hay proyectos repetidos: {ids}")
    proyectos = [analizar_proyecto(doc, s, m.group(1), m.group(2).strip(), cfg, E)
                 for s, m in secciones_p]
    sintesis = analizar_sintesis(doc, cfg, ids, E)
    en_calendario = sorted({pid for s in S.values() for pid in s["proyectos"]})
    for pid in en_calendario:
        if pid not in ids:
            E(f"§7: el calendario tiene sesiones de {pid}, que no tiene sección en §6")

    ev = analizar_componentes(doc, cfg, ids, E)
    rub = analizar_rubrica(doc, cfg, E)

    curso = {"uea": uea, "grupos": grupos, "fases": fases_tabla,
             "evaluacion": ev, "rubrica": rub, "ia_etiquetas": cfg["ia_etiquetas"]}

    for p in proyectos:
        pid = p["id"]
        p["sintesis"] = sintesis.get(pid, "")
        ps = sorted((s for s in S.values() if pid in s["proyectos"]), key=lambda s: s["num"])
        if not ps:
            E(f"{pid}: no tiene sesiones en la tabla de §7")
            continue
        vistas = []
        for s in ps:
            v = dict(s)
            v["fase"] = s["fases"].get(pid)
            tab = p["_tabla_sesiones"].get(s["num"])
            if tab is None:
                E(f"{pid}: la sesión {s['num']} está en el calendario, pero no en la tabla "
                  "de sesiones del proyecto")
            else:
                if normalizar_fase(tab["fase"], fases) != v["fase"]:
                    E(f"{pid}: la sesión {s['num']} es «{v['fase']}» en el calendario y "
                      f"«{tab['fase']}» en la tabla del proyecto")
                if tab.get("fecha") and s["fecha"] and \
                        " ".join(tab["fecha"].split()) != L.f_corta(s["fecha"]):
                    E(f"{pid}: la sesión {s['num']} dice «{tab['fecha']}» en la tabla del "
                      f"proyecto y «{L.f_corta(s['fecha'])}» en el calendario")
                v["producto"] = tab["producto"]
                v["actividad_larga"] = tab["actividad"]
                if len(s["proyectos"]) == 1:
                    s["producto"] = tab["producto"]
                    s["actividad_larga"] = tab["actividad"]
            vistas.append(v)
        for n in p["_tabla_sesiones"]:
            if n not in {s["num"] for s in ps}:
                E(f"{pid}: la sesión {n} de su tabla no es de {pid} en el calendario")
        fases_p = [v["fase"] for v in vistas]
        if fases_p != fases:
            E(f"{pid}: la secuencia de fases es {fases_p}, no {fases}")
        p["sesiones"] = vistas
        p["nums"] = [v["num"] for v in vistas]
        p["por_fase"] = {v["fase"]: v for v in vistas if v["fase"]}
        p["primera"], p["ultima"] = vistas[0], vistas[-1]
        if vistas[0]["fecha"] and vistas[-1]["fecha"]:
            p["rango"] = L.f_rango(vistas[0]["fecha"], vistas[-1]["fecha"])
        comps = ev["componentes"]
        exp = next((c for c in comps if c.get("proyecto") == pid and not c["escrita"]), None)
        esc = next((c for c in comps if c.get("proyecto") == pid and c["escrita"]), None)
        if exp is None:
            E(f"{pid}: §8.2 no tiene la ponderación de su expediente")
        if esc is None:
            E(f"{pid}: §8.2 no tiene su evaluación escrita")
        if exp and esc:
            p["expediente_comp"], p["eval"], p["peso_exp"] = exp, esc, exp["peso"]
            entrega = p["por_fase"].get(fase_entrega)
            if entrega:
                exp["sesion"] = entrega["num"]
                exp["fecha"] = entrega["fecha"]
                _cuando_escrita(esc, entrega, periodo, pid, E)
            if "duracion" in p["evaluacion"] and "duracion" not in esc:
                esc["duracion"] = p["evaluacion"]["duracion"]
        # datos propios del sitio para este proyecto
        dp = (datos.get("proyectos") or {}).get(pid, {})
        for regla in cfg["proyecto"].get("alinear", []):
            lista = p.get(regla["lista"], [])
            valores = dp.get(regla["datos"], [])
            if len(lista) != len(valores):
                E(f"{pid}: {regla['lista']} tiene {len(lista)} elementos en la fuente, pero "
                  f"los datos declaran {len(valores)} en {regla['datos']}")
            for el, val in zip(lista, list(valores) + [None] * len(lista)):
                el[regla["campo"]] = val
        for k, v in dp.items():
            p.setdefault(k, v)
        aplicar_extraer(doc, cfg["proyecto"].get("extraer"), p["texto"], p, E, f"{pid}: ")
        reglas_t = {k: dict(v, obligatorio=v.get("obligatorio", False))
                    for k, v in (cfg["proyecto"].get("tablas") or {}).items()}
        aplicar_tablas(doc, reglas_t, p["texto"], p, E, f"{pid}: ")
        for nombre, r in (cfg["proyecto"].get("campos") or {}).items():
            e = _etiqueta(etiquetados(p["texto"]), r["etiqueta"])
            if e:
                _poner(p, r.get("destino", nombre), _una_linea(e[1]))
            elif r.get("obligatorio"):
                E(f"{pid}: no se encontró «**{r['etiqueta']}**»")
        del p["_tabla_sesiones"]

    for c in ev["componentes"]:
        c.pop("_fecha_texto", None)
    _contrastar_encabezados(proyectos, E)
    _contrastar_grupos(grupos, periodo, E)

    n_crit = rub["criterios"]
    for p in proyectos:
        total = len(p["criterios"]) + len(rub["comunes"])
        if n_crit and total != n_crit:
            E(f"§8: la rúbrica dice «{n_crit} criterios», pero {p['id']} tiene "
              f"{len(p['criterios'])} propios + {len(rub['comunes'])} comunes")

    curso["lecturas"] = analizar_lecturas(doc, cfg, datos, S, n_sesiones, E)

    # reglas propias del curso
    aplicar_extraer(doc, cfg.get("extraer"), doc.texto, curso, E)
    aplicar_tablas(doc, cfg.get("tablas"), doc.texto, curso, E, proyectos=proyectos)
    aplicar_listas(doc, cfg.get("listas"), doc.texto, curso, E)

    # datos del sitio: se agregan a «curso» sin pisar lo que dice la fuente
    for k, v in datos.items():
        if k == "proyectos":
            continue
        if k in curso and isinstance(curso[k], dict) and isinstance(v, dict):
            for kk, vv in v.items():
                curso[k].setdefault(kk, vv)
        else:
            curso.setdefault(k, v)

    holguras = [s for s in S.values() if s["tipo"] == "holgura"]
    intro = [s for s in S.values() if s["tipo"] == "intro"]
    todas = periodo.get("_todas", [])
    diag_fin = (periodo["primera_sesion"] - dt.timedelta(days=1)
                if periodo.get("primera_sesion") else None)
    cal = {"periodo": {k: v for k, v in periodo.items() if not k.startswith("_")},
           "diagnostico": {"inicio": periodo.get("trimestre_inicio"), "fin": diag_fin},
           "todas": todas}

    ctx = {
        "curso": curso, "cal": cal, "sesiones": S, "S": S, "proyectos": proyectos,
        "P": {p["id"]: p for p in proyectos}, "holguras": holguras, "intro": intro,
        "n_sesiones": n_sesiones, "n_lunmie": len(todas), "filas": filas,
        "fase_entrega": fase_entrega, "datos": datos,
    }

    # validaciones declaradas en curso.yml
    if not E:
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        env.filters.update(L.FILTROS)
        for i, regla in enumerate(cfg.get("validar") or []):
            try:
                ok = env.compile_expression(regla["que"])(**ctx)
            except jinja2.exceptions.UndefinedError as e:
                E(f"validar[{i}] ({regla['que']}): {e}")
                continue
            if not ok:
                E(env.from_string(regla.get("mensaje") or f"no se cumple: {regla['que']}")
                  .render(**ctx))
    ctx["_doc"] = doc
    ctx["_periodo"] = periodo
    if recolectar:
        return ctx, list(E)
    if E:
        raise ErrorDeFuente("\n".join("  · " + e for e in E))
    return ctx


DIA_NUM = {L.sin_acentos(d): i for i, d in enumerate(L.DIAS)}


def _contrastar_grupos(grupos, periodo, E):
    """Los días escritos en el horario de cada grupo deben ser los días de la tabla."""
    dias = set(periodo.get("dias") or [])
    for g in grupos:
        texto = L.sin_acentos((g.get("dias") or g.get("horario") or "").lower())
        escritos = {DIA_NUM[d] for d in re.findall(r"[a-z]+", texto) if d in DIA_NUM}
        if escritos and dias and escritos != dias:
            E(f"§1: el horario del grupo {g['id']} dice {', '.join(L.DIAS[d] for d in sorted(escritos))}, "
              f"pero las sesiones de §7 son {', '.join(L.DIAS[d] for d in sorted(dias))}")


def _contrastar_encabezados(proyectos, E):
    """Si un proyecto repite, al principio de su sección, sus sesiones («Sesiones: 3, 5…»)
    o sus ponderaciones («Ponderación: entregable, 10 %; examen escrito 1, 12 %»), deben
    coincidir con el calendario y con §8.2."""
    for p in proyectos:
        if "sesiones" not in p:
            continue
        cabeza = p["texto"].split("**")[0]
        m = re.search(r"^Sesiones:\s*(.+?)\.?\s*$", cabeza, re.M)
        if m:
            sin_notas = re.sub(r"\([^)]*\)", "", m.group(1))
            nums = sorted(set(L.numeros(sin_notas)))
            if " a " in sin_notas and len(nums) == 2:
                nums = list(range(nums[0], nums[1] + 1))
            if nums != sorted(p["nums"]):
                E(f"{p['id']}: su encabezado dice «Sesiones: {m.group(1).strip()}», pero en "
                  f"el calendario sus sesiones son {L.f_y(p['nums'])}")
        m = re.search(r"^.*Ponderación:\s*(.+)$", cabeza, re.M)
        if m and "eval" in p:
            dichos = [float(x.replace(",", ".")) for x in RE_PCT.findall(m.group(1))]
            reales = [p["peso_exp"], p["eval"]["peso"]]
            if len(dichos) == 2 and sorted(dichos) != sorted(float(x) for x in reales):
                E(f"{p['id']}: su encabezado dice «Ponderación: {m.group(1).strip()}», pero "
                  f"§8.2 da {p['peso_exp']} % al expediente y {p['eval']['peso']} % a la "
                  "evaluación escrita")


def _cuando_escrita(esc, entrega, periodo, pid, E):
    """La fecha de la evaluación escrita de un proyecto: la sesión de entrega, salvo que
    §8.2 la ubique en las evaluaciones globales. Si §8.2 dice una sesión o una fecha, se
    contrasta con el calendario."""
    if "sesion_declarada" in esc:
        if esc["sesion_declarada"] != entrega["num"]:
            E(f"§8.2: «{esc['nombre']}» dice sesión {esc['sesion_declarada']}, pero la "
              f"fase de entrega de {pid} es la sesión {entrega['num']}")
        esc["sesion"], esc["fecha"] = entrega["num"], entrega["fecha"]
        return
    texto = esc.pop("_fecha_texto", "")
    anio = (periodo.get("globales_inicio") or entrega["fecha"] or dt.date.today()).year
    rango = L.rango_texto(texto if re.search(r"\d{4}", texto) else f"{texto} de {anio}")
    un_dia = L.fecha_texto(texto, anio)
    g_ini, g_fin = periodo.get("globales_inicio"), periodo.get("globales_fin")
    if rango and g_ini and g_ini <= rango[0] and rango[1] <= g_fin:
        esc["en_globales"] = True
    elif re.search(r"global", texto, re.I) and not un_dia:
        esc["en_globales"] = True
    elif un_dia and g_ini and g_ini <= un_dia <= g_fin:
        esc["en_globales"] = True
    elif un_dia and entrega["fecha"] and un_dia == entrega["fecha"]:
        esc["sesion"], esc["fecha"] = entrega["num"], entrega["fecha"]
    elif un_dia:
        E(f"§8.2: «{esc['nombre']}» dice «{texto}», que no es la sesión de entrega de "
          f"{pid} ({L.f_dma(entrega['fecha'])}) ni cae en las evaluaciones globales")
    else:
        E(f"§8.2: no entiendo cuándo es «{esc['nombre']}» («{texto}»); escriba «Sesión N, "
          "día de mes» o las fechas de las evaluaciones globales")


def _fin_de_clases(doc, periodo):
    m = re.search(r"[Ll]as clases (?:concluyen|terminan) el (\d{1,2} de [a-záéíóú]+)",
                  doc.texto)
    if m and periodo.get("ultima_sesion"):
        d = L.fecha_texto(m.group(1), periodo["ultima_sesion"].year)
        if d:
            return d
    return periodo.get("ultima_sesion")
