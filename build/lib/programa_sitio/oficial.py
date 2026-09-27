"""Contraste del programa analítico con el programa de estudios oficial de la UEA.

El programa oficial se usa en Markdown (convertido una sola vez del PDF, como
docs/curso/programa-oficial.md). Su formato varía de una UEA a otra —encabezado en
renglones «CLAVE: 221188» o en tabla, con o sin acentos—, así que se lee de manera
tolerante: se buscan sus apartados por nombre (OBJETIVO(S), CONTENIDO SINTÉTICO,
MODALIDADES DE CONDUCCIÓN, MODALIDADES DE EVALUACIÓN, BIBLIOGRAFÍA) y sus datos por
etiqueta.

Se comprueba:
  · ERROR: nombre, clave (la de seis dígitos del impreso se convierte a siete), plan,
    división, créditos, horas teóricas y prácticas, carácter, trimestre del plan y
    seriación de §1; cada objetivo y cada punto del contenido sintético aparece en el
    programa analítico; toda cita entre «» que el programa analítico atribuye al
    programa oficial está, tal cual, en el oficial.
  · AVISO: un dato que no se pudo leer del oficial; una obra de su bibliografía que no
    aparece (por apellido y año) en el programa analítico.
"""

import os
import re

from . import lexico as L


def normal(t):
    """Para comparar transcripciones: sin formato, sin acentos, sin mayúsculas, sin
    comillas ni puntuación final, con espacios simples."""
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"[*_`«»“”\"']", "", t)
    t = L.sin_acentos(t).lower()
    t = re.sub(r"\s*[-–—]\s*", "-", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip(" .;:,")


def clave7(c):
    """'221188' (formato impreso de seis dígitos) -> '2211088'."""
    c = re.sub(r"\D", "", c or "")
    return c[:4] + "0" + c[4:] if len(c) == 6 else c


def leer(texto):
    """Diccionario con los datos y apartados del programa oficial."""
    plano = re.sub(r"\*\*|__", "", texto)
    plano_sa = L.sin_acentos(plano)
    lineas = plano.split("\n")

    # apartados: renglones en mayúsculas que terminan en «:»
    marcas = []
    for i, l in enumerate(lineas):
        c = L.sin_acentos(l).strip().lstrip("#").strip()
        if not c or c != c.upper():   # los apartados van en mayúsculas
            continue
        for nombre, patron in (("objetivos", r"^OBJETIVO"), ("contenido", r"^CONTENIDO SINTETICO"),
                               ("conduccion", r"^MODALIDADES DE CONDUCCION"),
                               ("evaluacion", r"^MODALIDADES DE EVALUACION"),
                               ("bibliografia", r"^BIBLIOGRAFIA")):
            if re.match(patron, c.upper()):
                marcas.append((i, nombre))
    apartados = {}
    for j, (i, nombre) in enumerate(marcas):
        fin = marcas[j + 1][0] if j + 1 < len(marcas) else len(lineas)
        cuerpo = [l for l in lineas[i + 1:fin]
                  if not l.strip().startswith("|") and l.strip() != "---"]
        apartados[nombre] = "\n".join(cuerpo).strip()
    cabeza = "\n".join(lineas[:marcas[0][0]]) if marcas else plano
    cabeza_sa = L.sin_acentos(cabeza)
    cab_plana = re.sub(r"[|#]", " ", cabeza_sa)
    cab_plana = re.sub(r"\s+", " ", cab_plana)

    datos = {}
    m = re.search(r"CLAVE:?\s*(\d{6,7})", cab_plana) or \
        re.search(r"\b(\d{6,7})\b", cab_plana)
    if m:
        datos["clave"] = m.group(1)
    m = re.search(r"ENSENANZA-APRENDIZAJE:\s*([A-Z0-9 ,.-]+?)\s*(?:CLAVE|HORAS|$)", cab_plana) \
        or (re.search(rf"{datos.get('clave', '#')}\s+([A-Z][A-Z0-9 ,.-]+?)\s+\d{{1,2}}\b",
                      cab_plana) if datos.get("clave") else None)
    if m:
        datos["nombre"] = m.group(1).strip()
    m = re.search(r"CREDITOS:?\s*(\d{1,2})\b", cab_plana) or \
        (re.search(rf"{datos.get('clave', '#')}\s+[A-Z][A-Z0-9 ,.-]+?\s+(\d{{1,2}})\b", cab_plana)
         if datos.get("clave") else None)
    if m:
        datos["creditos"] = m.group(1)
    m = re.search(r"(?:HORAS TEORICAS|H\.?\s*TEOR\.?):?\s*(\d+(?:\.\d)?)", cab_plana)
    if m:
        datos["horas_teoricas"] = m.group(1)
    m = re.search(r"(?:HORAS PRACTICAS|H\.?\s*PRAC\.?):?\s*(\d+(?:\.\d)?)", cab_plana)
    if m:
        datos["horas_practicas"] = m.group(1)
    m = re.search(r"TIPO:?\s*([A-Z]+)", cab_plana)
    if m:
        datos["tipo"] = m.group(1)
    m = re.search(r"TRIMESTRE:\s*([IVX]+)\b", cab_plana) or \
        re.search(r"\b([IVX]{1,4})\s*$", cab_plana.strip())
    if m:
        datos["trimestre"] = m.group(1)
    m = re.search(r"SERIACION:?\s*(\d{6,7})?", cab_plana)
    if m is not None:
        ser = re.findall(r"\b(\d{6})\b", cab_plana)
        datos["seriacion"] = [s for s in ser if s != datos.get("clave")]
    m = re.search(r"PLAN:?\s*(LICENCIATURA [A-Z ]+?)(?:\s{2,}|\s+UNIDAD|\s+CLAVE|$)", cab_plana)
    if m:
        datos["plan"] = m.group(1).strip()
    m = re.search(r"DIVISION:?\s*([A-Z ]+?)(?:\s+NOMBRE|\s+1 / \d|\s{2,}|$)", cab_plana)
    if m:
        datos["division"] = m.group(1).strip()

    # objetivos: renglones con contenido que no son encabezados ni la frase introductoria
    objetivos = []
    for l in apartados.get("objetivos", "").split("\n"):
        t = l.strip().lstrip("-*·•").strip()
        c = L.sin_acentos(t).lower()
        if not t or c.startswith(("objetivo", "que al finalizar")) or t.startswith("#"):
            continue
        objetivos.append(t)
    # contenido sintético: puntos numerados y subpuntos con letra
    contenido = []
    for l in apartados.get("contenido", "").split("\n"):
        t = l.strip()
        m = re.match(r"^(?:\d+\.|[a-z]\.)\s+(.+?)[.:;]?$", t)
        if m:
            contenido.append(m.group(1).strip())
    # bibliografía: una obra por renglón (o viñeta)
    obras = [re.sub(r"^[-*·•]\s*", "", l.strip()) for l in
             apartados.get("bibliografia", "").split("\n") if re.search(r"\(\d{4}\)", l)]
    return {"datos": datos, "apartados": apartados, "objetivos": objetivos,
            "contenido": contenido, "bibliografia": obras,
            "texto_normal": normal(" ".join(apartados.values()))}


def contrastar(ctx, cfg):
    """(errores, avisos, oficial o None)."""
    co = cfg.get("programa_oficial") or {}
    ruta_rel = co.get("archivo")
    if not ruta_rel:
        return [], [], None
    ruta = os.path.join(cfg["_raiz"], ruta_rel)
    if not os.path.exists(ruta):
        msj = (f"no existe el programa oficial {ruta_rel} (en Markdown); sin él no se "
               "contrasta el programa analítico con el programa de estudios")
        return ([msj] if co.get("exigir") else []), ([] if co.get("exigir") else [msj]), None
    with open(ruta, encoding="utf-8") as f:
        of = leer(f.read())
    errores, avisos = [], []
    d = of["datos"]
    uea = ctx["curso"]["uea"]
    filas = uea.get("filas", {})
    fuente = ctx["_doc"]
    nombre_of = f"el programa oficial ({ruta_rel})"

    def comparar(etiqueta, del_analitico, del_oficial, normalizar=normal):
        if del_oficial is None:
            avisos.append(f"{nombre_of}: no pude leer «{etiqueta}»; no se contrastó")
            return
        if del_analitico is None:
            return
        if normalizar(str(del_analitico)) != normalizar(str(del_oficial)):
            errores.append(f"§1, {etiqueta}: el programa analítico dice «{del_analitico}» "
                           f"y {nombre_of}, «{del_oficial}»")

    comparar("nombre de la UEA", uea.get("nombre"), d.get("nombre"))
    comparar("clave", uea.get("clave"), clave7(d["clave"]) if d.get("clave") else None,
             lambda x: re.sub(r"\D", "", x))
    if uea.get("plan") and d.get("plan"):
        comparar("plan de estudios", uea.get("plan"), d.get("plan"))
    if uea.get("division") and d.get("division"):
        comparar("división", uea.get("division"),
                 re.sub(r"^DIVISION (DE )?", "", d["division"]))
    if "creditos" in filas:
        comparar("créditos", re.sub(r"\D", "", filas["creditos"]), d.get("creditos"))
    if "horas_semanales" in filas:
        horas = re.findall(r"\d+(?:\.\d)?", filas["horas_semanales"])
        if len(horas) >= 2:
            comparar("horas teóricas", horas[0], d.get("horas_teoricas"),
                     lambda x: f"{float(x):.1f}")
            comparar("horas prácticas", horas[1], d.get("horas_practicas"),
                     lambda x: f"{float(x):.1f}")
    if "caracter" in filas and d.get("tipo"):
        a, o = normal(filas["caracter"]), normal(d["tipo"])
        if not (a.startswith(o) or o.startswith(a)):
            errores.append(f"§1: el carácter es «{filas['caracter']}», pero {nombre_of} dice "
                           f"«{d['tipo']}»")
    if "trimestre_del_plan" in filas:
        comparar("trimestre del plan", filas["trimestre_del_plan"], d.get("trimestre"))
    if "seriacion" in filas and "seriacion" in d:
        del_analitico = sorted(set(re.findall(r"\b\d{7}\b", filas["seriacion"])))
        del_oficial = sorted({clave7(s) for s in d["seriacion"]})
        if del_analitico != del_oficial:
            errores.append(f"§1: la seriación es «{filas['seriacion']}», pero {nombre_of} "
                           f"da {', '.join(del_oficial) or 'ninguna'}")

    texto_analitico = normal(fuente.texto)

    def apartado(*titulos):
        """Texto normalizado del apartado donde se transcribe algo del programa oficial
        (el primero que exista); si no hay ninguno, todo el documento."""
        for t in titulos:
            s = fuente.seccion(t)
            if s is not None:
                return normal(fuente.texto_de(s)), f"§{s.numero or s.titulo}"
        return texto_analitico, "el programa analítico"

    texto_obj, donde_obj = apartado("Objetivos del programa oficial", "Objetivos")
    for o in of["objetivos"]:
        if normal(o) not in texto_obj:
            errores.append(f"{donde_obj}: el objetivo oficial «{o}» no aparece transcrito "
                           "tal cual")
    texto_cont, donde_cont = apartado("Contenido sintético del programa oficial",
                                      "Contenido sintético", "Contenido")
    for c in of["contenido"]:
        if normal(c) not in texto_cont:
            errores.append(f"{donde_cont}: el punto del contenido sintético «{c}» no aparece "
                           "transcrito tal cual")
    # citas atribuidas al programa oficial
    for p in re.split(r"\n\s*\n", fuente.texto):
        if not re.search(r"programa (oficial|de estudios)", p, re.I):
            continue
        for cita in re.findall(r"«([^»]{25,})»", p):
            if normal(cita) not in of["texto_normal"]:
                errores.append(f"la cita «{cita[:70]}…» se atribuye al programa oficial, "
                               "pero no está así en él")
    # bibliografía (aviso)
    s_bib = fuente.seccion("Bibliografía del programa oficial")
    texto_bib = normal(fuente.texto_de(s_bib)) if s_bib else texto_analitico
    for obra in of["bibliografia"]:
        anio = re.search(r"\((\d{4})\)", obra).group(1)
        # los nombres propios antes del año: basta con que uno de ellos y el año estén
        # en la bibliografía del programa (el orden nombre/apellido varía en el oficial)
        nombres = [normal(t) for t in re.findall(r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}",
                                                 obra[:obra.find("(")])]
        encontrado = any(re.search(rf"\b{re.escape(n)}\b[^\n]{{0,120}}\b{anio}\b", texto_bib)
                         for n in nombres)
        if not encontrado:
            avisos.append(f"bibliografía: la obra oficial «{obra[:60]}…» ({anio}) no aparece "
                          "en la bibliografía del programa analítico")
    return errores, avisos, {"archivo": ruta_rel, "datos": d, "objetivos": of["objetivos"],
                             "contenido": of["contenido"], "bibliografia": of["bibliografia"]}
