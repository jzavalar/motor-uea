"""Del modelo al sitio: plan de salidas, páginas por sección, plantillas, menú,
auditoría de duplicación, escritura y borrado de huérfanos."""

import glob
import os
import posixpath
import re

import jinja2

from . import lexico as L

MOTOR_PLANTILLAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plantillas")
MARCA = "ARCHIVO GENERADO por programa-sitio"


def aviso(cfg, extension):
    texto = (f"{MARCA} a partir de {cfg['fuente']} y curso.yml. No lo edite: edite "
             "la fuente (o curso.yml y sus datos) y vuelva a generar.")
    return {".md": f"<!-- {texto} -->\n\n", ".yml": f"# {texto}\n\n"}.get(extension, "")


def entorno(cfg):
    carpetas = []
    propia = os.path.join(cfg["_raiz"], cfg["plantillas"])
    if os.path.isdir(propia):
        carpetas.append(propia)
    carpetas.append(MOTOR_PLANTILLAS)
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(carpetas),
        undefined=jinja2.StrictUndefined, trim_blocks=True, lstrip_blocks=True,
        keep_trailing_newline=True)
    env.filters.update(L.FILTROS)
    env.globals.update(L.GLOBALES)
    return env


# ------------------------------------------------------------------------ plan

def _plantilla_existe(cfg, nombre):
    return os.path.exists(os.path.join(cfg["_raiz"], cfg["plantillas"], nombre)) or \
        os.path.exists(os.path.join(MOTOR_PLANTILLAS, nombre))


def plan_de_salidas(ctx, cfg):
    """Lista de dicts: {destino, tipo: plantilla|seccion, plantilla | secciones, extra,
    menu, grupo}."""
    plan = []
    for destino, v in (cfg.get("salidas") or {}).items():
        if v is None:
            continue
        v = {"plantilla": v} if isinstance(v, str) else dict(v)
        plan.append({"destino": destino, "tipo": "plantilla", "plantilla": v["plantilla"],
                     "extra": {}, "menu": v.get("menu"), "grupo": v.get("grupo")})
    for pg in cfg.get("paginas") or []:
        plan.append({"destino": pg["destino"], "tipo": "seccion",
                     "secciones": [str(x) for x in pg["secciones"]],
                     "titulo": pg.get("titulo"), "menu": pg.get("menu"),
                     "grupo": pg.get("grupo", "El curso"), "extra": {}})
    cp = cfg["proyecto"]
    for p in ctx["proyectos"]:
        destino = cp["destino"].format(slug=p["slug"], id=p["id"].lower())
        p["pagina"] = None
        if cp["pagina"] == "ninguna":
            continue
        p["pagina"] = destino
        if cp["pagina"] == "seccion":
            plan.append({"destino": destino, "tipo": "seccion", "secciones": [p["seccion"]],
                         "titulo": None, "menu": f"{p['id']} · {p['nombre']}",
                         "grupo": "Proyectos", "extra": {"p": p}})
        else:
            propia = cp["plantilla"].format(id=p["id"].lower(), slug=p["slug"])
            nombre = propia if _plantilla_existe(cfg, propia) else "proyecto.md.j2"
            plan.append({"destino": destino, "tipo": "plantilla", "plantilla": nombre,
                         "extra": {"p": p}, "menu": f"{p['id']} · {p['nombre']}",
                         "grupo": "Proyectos"})
    destinos = [s["destino"] for s in plan]
    repetidos = sorted({d for d in destinos if destinos.count(d) > 1})
    if repetidos:
        raise ValueError(f"dos salidas escriben el mismo archivo: {repetidos}")
    return plan


def menu(ctx, cfg, plan):
    """Estructura del menú del sitio para la plantilla de mkdocs.yml del motor."""
    docs = "docs/"
    fuente_rel = cfg["fuente"][len(docs):] if cfg["fuente"].startswith(docs) else None
    grupos, orden = {}, []

    def agregar(grupo, titulo, ruta):
        if grupo not in grupos:
            grupos[grupo] = []
            orden.append(grupo)
        grupos[grupo].append({"titulo": titulo, "ruta": ruta})

    inicio = None
    for s in plan:
        if not s["destino"].startswith(docs):
            continue
        ruta = s["destino"][len(docs):]
        if ruta == "index.md":
            inicio = ruta
            continue
        # los proyectos se agregan después, en su orden; lo demás, si tiene etiqueta
        if s["grupo"] == "Proyectos" or not s.get("menu"):
            continue
        agregar(s.get("grupo") or "El curso", s["menu"], ruta)
    for p in ctx["proyectos"]:
        if p.get("pagina"):
            agregar("Proyectos", f"{p['id']} · {p['nombre']}", p["pagina"][len(docs):])
    carpeta = cfg["lecturas"]["carpeta"]
    for l in ctx["curso"]["lecturas"]:
        if l.get("archivo"):
            ruta = posixpath.join(carpeta, l["archivo"])
            if ruta.startswith(docs):
                agregar("Lecturas", f"{l['clave']} · {l['corto']}", ruta[len(docs):])
    for extra in cfg.get("menu_extra") or []:
        for titulo, ruta in extra.items():
            agregar("Más", titulo, ruta)
    nav = []
    if inicio:
        nav.append({"titulo": "Inicio", "ruta": inicio})
    for g in orden:
        nav.append({"titulo": g, "hijos": grupos[g]})
    if fuente_rel:
        nav.append({"titulo": "Programa analítico", "ruta": fuente_rel})
    return nav


# ------------------------------------------------------------- páginas-sección

RE_ENLACE = re.compile(r"(!?\[[^\]]*\]\()([^)\s]+)(\s+\"[^\"]*\")?\)")


def _reubicar_enlaces(texto, origen, destino):
    dir_o, dir_d = posixpath.dirname(origen), posixpath.dirname(destino)

    def cambiar(m):
        objetivo = m.group(2)
        if re.match(r"^(?:[a-z]+:|/)", objetivo):
            return m.group(0)
        ruta, _, ancla = objetivo.partition("#")
        if not ruta:  # ancla dentro del programa analítico: se apunta a la página completa
            nuevo = posixpath.relpath(origen, dir_d) + "#" + ancla
        else:
            absoluta = posixpath.normpath(posixpath.join(dir_o, ruta))
            nuevo = posixpath.relpath(absoluta, dir_d) + (("#" + ancla) if ancla else "")
        return f"{m.group(1)}{nuevo}{m.group(3) or ''})"
    return RE_ENLACE.sub(cambiar, texto)


def pagina_de_secciones(doc, cfg, s_plan):
    partes, nivel_base = [], None
    if s_plan.get("titulo"):
        partes.append(f"# {s_plan['titulo']}")
        nivel_obj = 2
    else:
        nivel_obj = 1
    for clave_s in s_plan["secciones"]:
        s = doc.seccion(clave_s)
        if s is None:
            raise ValueError(f"paginas: {s_plan['destino']} pide la sección «{clave_s}», "
                             "que no existe en la fuente")
        if nivel_base is None:
            nivel_base = s.nivel
        md = doc.markdown_de(s)
        delta = nivel_obj - nivel_base
        lineas, en_codigo = [], False
        for l in md.split("\n"):
            if l.lstrip().startswith(("```", "~~~")):
                en_codigo = not en_codigo
            m = re.match(r"^(#{1,6})(\s.*)$", l) if not en_codigo else None
            if m:
                n = min(6, max(1, len(m.group(1)) + delta))
                l = "#" * n + m.group(2)
            lineas.append(l)
        partes.append("\n".join(lineas).strip())
    texto = "\n\n".join(partes)
    texto = re.sub(r"<!--\s*fuente-datos:.*?-->\s*", "", texto, flags=re.S)
    return _reubicar_enlaces(texto, cfg["fuente"], s_plan["destino"])


# --------------------------------------------------------------------- render

def generar(ctx, cfg, plan):
    env = entorno(cfg)
    salidas = {}
    from . import MOTOR_REPOSITORIO, __version__
    ctx = dict(ctx, menu=menu(ctx, cfg, plan), config=cfg,
               motor={"url": MOTOR_REPOSITORIO, "version": __version__})
    for s in plan:
        if s["tipo"] == "seccion":
            texto = pagina_de_secciones(ctx["_doc"], cfg, s)
        else:
            texto = env.get_template(s["plantilla"]).render(**ctx, **s["extra"])
        texto = "\n".join(l.rstrip() for l in texto.split("\n"))
        while "\n\n\n" in texto:
            texto = texto.replace("\n\n\n", "\n\n")
        salidas[s["destino"]] = aviso(cfg, os.path.splitext(s["destino"])[1]) + \
            texto.strip() + "\n"
    return salidas


# ------------------------------------------------------------------ auditoría
#
# Un dato de la fuente escrito como texto fijo en una plantilla deja de actualizarse.
#   · ERROR (detiene): identificación de la UEA y de los grupos, nombre o carpeta de un
#     proyecto, título o archivo de una lectura, fecha del periodo, número de sesión.
#   · AVISO (no detiene): otras frases de la fuente (dos palabras o más, 12 caracteres
#     o más) repetidas en una plantilla; tramos de 12 palabras copiados de la fuente;
#     identificación de la UEA dentro de páginas escritas a mano.
# Una coincidencia legítima se declara en la plantilla:
#     {# auditoría: permitido «30 de septiembre de 2026» (fecha de una noticia) #}

RE_PERMITIDO = re.compile(r"\{#\s*auditoría:\s*permitido\s*«(.+?)»")
VENTANA = 12


def _texto_fijo(plantilla):
    t = re.sub(r"\{#.*?#\}", " ", plantilla, flags=re.S)
    t = re.sub(r"\{%.*?%\}", " ", t, flags=re.S)
    return re.sub(r"\{\{.*?\}\}", " \x00 ", t, flags=re.S)


def _buscar(valor, texto):
    return re.search(r"(?<![\w@.-])" + re.escape(valor) + r"(?![\w])", texto) is not None


def _palabras(texto):
    texto = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", texto)
    return re.findall(r"\w+", texto.lower())


def _hechos(ctx, cfg):
    criticos, otros = {}, {}
    u = ctx["curso"]["uea"]
    for k in ("nombre", "clave", "plan", "division", "institucion", "profesor", "correo",
              "telegram", "trimestre", "sitio", "repositorio", "unidad_corta"):
        if u.get(k) and len(str(u[k])) >= 3:
            criticos[str(u[k])] = f"curso.uea.{k}"
    for g in ctx["curso"]["grupos"]:
        for k in ("id", "sala"):
            if g.get(k):
                criticos[g[k]] = f"curso.grupos[].{k}"
    for p in ctx["proyectos"]:
        criticos[p["nombre"]] = f"nombre de {p['id']}"
        criticos[p["slug"]] = f"carpeta de {p['id']}"
    for l in ctx["curso"]["lecturas"]:
        if l.get("titulo"):
            criticos[l["titulo"]] = f"título de la lectura {l['clave']}"
        for k in ("archivo", "enlace"):
            if l.get(k) and not str(l[k]).startswith("http"):
                criticos[os.path.basename(l[k])] = f"archivo de la lectura {l['clave']}"
    per = ctx["cal"]["periodo"]
    fechas = list(ctx["cal"]["todas"]) + [v for v in per.values()
                                          if hasattr(v, "weekday")]
    for d in fechas:
        for f in (L.f_dma, L.f_larga, L.f_corta):
            criticos[f(d)] = "fecha del periodo lectivo"
    fijo = {f["fase"] for f in ctx["curso"]["fases"]} | set(cfg["rubrica"]["niveles"]) | \
        set(L.DIAS) | set(L.MESES) | {v for d in cfg["ia_etiquetas"].values()
                                       for v in d.values()}
    codigos = {"tipo", "ancla", "ia", "id", "bloque", "fase", "slug", "clave", "texto",
               "pagina", "seccion", "extra", "filas"}

    def recorrer(x, ruta):
        if isinstance(x, dict):
            for k, v in x.items():
                if k not in codigos:
                    recorrer(v, f"{ruta}.{k}")
        elif isinstance(x, (list, tuple)):
            for v in x:
                recorrer(v, f"{ruta}[]")
        elif isinstance(x, str):
            v = x.strip()
            if (len(v) >= 12 and len(v.split()) >= 2 and v not in fijo
                    and v not in criticos):
                otros.setdefault(v, ruta)
    recorrer({"curso": ctx["curso"], "proyectos": ctx["proyectos"]}, "")
    return criticos, otros


def auditar(ctx, cfg, generados):
    criticos, otros = _hechos(ctx, cfg)
    n_sesiones = ctx["n_sesiones"]
    errores, avisos = [], []
    pf = _palabras(ctx["_doc"].texto)
    ventanas = {" ".join(pf[i:i + VENTANA]) for i in range(len(pf) - VENTANA + 1)}
    raiz = cfg["_raiz"]
    carpeta = os.path.join(raiz, cfg["plantillas"])
    for ruta in sorted(glob.glob(os.path.join(carpeta, "**", "*.j2"), recursive=True)):
        nombre = os.path.relpath(ruta, raiz)
        crudo = open(ruta, encoding="utf-8").read()
        permitidos = set(RE_PERMITIDO.findall(crudo))
        fijo = _texto_fijo(crudo)
        for valor, origen in criticos.items():
            if valor not in permitidos and _buscar(valor, fijo):
                errores.append(f"{nombre}: contiene «{valor}» como texto fijo ({origen}); "
                               "use la variable correspondiente")
        for m in re.finditer(r"\b[Ss]esi[oó]n(?:es)? (\d+)\b", fijo):
            if 1 <= int(m.group(1)) <= n_sesiones and m.group(0) not in permitidos:
                errores.append(f"{nombre}: contiene «{m.group(0)}» como texto fijo; el "
                               "número de una sesión cambia con el calendario")
        for valor, origen in otros.items():
            if valor not in permitidos and _buscar(valor, fijo):
                avisos.append(f"{nombre}: repite «{valor[:60]}» ({origen})")
        p = _palabras(fijo.replace("\x00", " "))
        copiadas = {" ".join(p[i:i + VENTANA]) for i in range(len(p) - VENTANA + 1)}
        copiadas &= ventanas
        if copiadas:
            avisos.append(f"{nombre}: {len(copiadas)} tramo(s) de {VENTANA} palabras "
                          f"copiados de la fuente, p. ej. «{sorted(copiadas)[0]}»")
    no_manuales = set(generados) | {cfg["fuente"]}
    for ruta in sorted(glob.glob(os.path.join(raiz, "docs", "**", "*.md"), recursive=True)):
        rel = os.path.relpath(ruta, raiz)
        if rel in no_manuales:
            continue
        texto = open(ruta, encoding="utf-8").read()
        vistos = sorted({v for v, o in criticos.items()
                         if o.startswith("curso.uea") and _buscar(v, texto)})
        if vistos:
            avisos.append(f"{rel} (escrita a mano): contiene "
                          + ", ".join(f"«{v}»" for v in vistos)
                          + "; si cambian en la fuente, esta página no se actualiza sola")
    return errores, avisos


# ------------------------------------------------------------------ escritura

def generados_existentes(raiz):
    res = []
    for ruta in glob.glob(os.path.join(raiz, "docs", "**", "*.md"), recursive=True):
        with open(ruta, encoding="utf-8") as f:
            if MARCA in f.readline():
                res.append(os.path.relpath(ruta, raiz))
    return sorted(res)


def diferencias(raiz, salidas):
    distintos = []
    for destino, texto in salidas.items():
        ruta = os.path.join(raiz, destino)
        actual = open(ruta, encoding="utf-8").read() if os.path.exists(ruta) else None
        if actual != texto:
            distintos.append(destino)
    huerfanos = [g for g in generados_existentes(raiz) if g not in salidas]
    return distintos, huerfanos


def escribir(raiz, salidas, distintos, huerfanos):
    for destino in distintos:
        ruta = os.path.join(raiz, destino)
        os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(salidas[destino])
    docs = os.path.join(raiz, "docs")
    for h in huerfanos:
        ruta = os.path.join(raiz, h)
        os.remove(ruta)
        carpeta = os.path.dirname(ruta)
        while carpeta.startswith(docs) and carpeta != docs and not os.listdir(carpeta):
            os.rmdir(carpeta)
            carpeta = os.path.dirname(carpeta)
