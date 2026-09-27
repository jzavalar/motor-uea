"""programa-sitio nuevo: arma el repositorio de una UEA a partir de su programa.

Copia la fuente a docs/curso/programa-analitico.md, escribe un curso.yml con lo que
logra deducir de la fuente (qué secciones existen para volverlas páginas, la escala de
la rúbrica), agrega sitio.sh, el gancho pre-commit, la acción de GitHub y las versiones
fijadas del motor, y genera el sitio por primera vez. Si la fuente todavía no cumple la
estructura común, el repositorio se crea igual y se listan los problemas por resolver."""

import os
import re
import shutil

from . import MOTOR_REPOSITORIO, __version__
from .markdown import Documento

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "curso_base")

# (título de la sección, al principio) -> (archivo del sitio, etiqueta del menú)
PAGINAS_HABITUALES = [
    ("Trabajo de campo", "docs/curso/trabajo-de-campo.md", "Trabajo de campo"),
    ("Uso de asistentes de inteligencia artificial", "docs/curso/protocolo-ia.md",
     "Uso de IA"),
    ("Programación de las sesiones", "docs/curso/calendario.md", "Calendario"),
    ("Evaluación", "docs/curso/evaluacion.md", "Evaluación"),
]


def _niveles(texto):
    m = re.search(r"escala por criterio es:\s*([^.]+)\.", texto)
    if not m:
        return None
    pares = re.findall(r"(\d+),\s*([a-záéíóúñ]+)", m.group(1))
    return [n for _, n in sorted(pares, key=lambda x: int(x[0]))] or None


def curso_yml(doc, sitio, repositorio, unidad):
    paginas = []
    for titulo, destino, menu in PAGINAS_HABITUALES:
        for s in doc.secciones:
            if s.numero and s.titulo.startswith(titulo) and (titulo != "Evaluación"
                                                              or "." not in s.numero):
                # por título, no por número: si se renumeran las secciones, la página
                # sigue mostrando la misma
                paginas.append(f"  - {{destino: {destino}, secciones: [\"{s.titulo}\"], "
                               f"menu: {menu}}}")
                break
    niveles = _niveles(doc.texto)
    lineas = [
        "# Configuración del curso para el motor programa-sitio. Todo lo que no se dice",
        "# aquí se toma de la configuración predeterminada del motor.",
        "",
        f'version_motor: "{__version__}"',
        "",
        "sitio:",
        f"  url: {sitio}",
        f"  repositorio: {repositorio}",
        f"  unidad_corta: {unidad}",
        "",
    ]
    if niveles:
        lineas += ["rubrica:", f"  niveles: [{', '.join(niveles)}]", ""]
    lineas += [
        "# Cada proyecto de la sección 6 se publica tal cual como su propia página.",
        "# (Con «pagina: plantilla» se usa en su lugar una plantilla didáctica.)",
        "proyecto:",
        "  pagina: seccion",
        "",
        "# Secciones de la fuente que también son páginas del sitio.",
        "paginas:",
    ] + (paginas or ["  []"]) + [""]
    return "\n".join(lineas)


def crear(destino, fuente, sitio, repositorio, unidad="UAM-Iztapalapa"):
    destino = os.path.abspath(os.path.expanduser(destino))
    if os.path.exists(os.path.join(destino, "curso.yml")):
        raise FileExistsError(f"{destino} ya tiene un curso.yml")
    with open(os.path.expanduser(fuente), encoding="utf-8") as f:
        texto = f.read()
    doc = Documento(texto)
    os.makedirs(os.path.join(destino, "docs", "curso"), exist_ok=True)
    shutil.copyfile(os.path.expanduser(fuente),
                    os.path.join(destino, "docs", "curso", "programa-analitico.md"))
    with open(os.path.join(destino, "curso.yml"), "w", encoding="utf-8") as f:
        f.write(curso_yml(doc, sitio, repositorio, unidad))
    for raiz, _, archivos in os.walk(BASE):
        for a in archivos:
            origen = os.path.join(raiz, a)
            rel = os.path.relpath(origen, BASE)
            rel = ".gitignore" if rel == "gitignore" else rel
            final = os.path.join(destino, rel)
            os.makedirs(os.path.dirname(final), exist_ok=True)
            with open(origen, encoding="utf-8") as f:
                contenido = f.read().replace("{MOTOR_REPOSITORIO}", MOTOR_REPOSITORIO) \
                    .replace("{MOTOR_VERSION}", __version__)
            with open(final, "w", encoding="utf-8") as f:
                f.write(contenido)
            # los permisos del paquete instalado no son confiables: se fijan aquí
            os.chmod(final, 0o755 if rel in ("sitio.sh", ".githooks/pre-commit") else 0o644)
    mensajes = [f"Curso creado en {destino}."]
    for etiqueta, dado in (("Sitio del curso", sitio), ("Repositorio", repositorio)):
        m = re.search(rf"^\|\s*{etiqueta}\s*\|\s*<?(https?://[^\s|>]+)", texto, re.M)
        if m and m.group(1).rstrip("/") != dado.rstrip("/"):
            mensajes.append(f"Aviso: la fuente dice «{etiqueta}: {m.group(1)}», distinto de "
                            f"{dado}; manda la fuente. Si el curso vive en otra dirección, "
                            "corrija ese renglón de §1.")
    from .nucleo import ErrorDeFuente, construir
    try:
        r = construir(destino, "escribir")
        mensajes.append(f"Sitio generado: {len(r['salidas'])} archivos.")
    except ErrorDeFuente as e:
        mensajes.append("La fuente todavía no cumple la estructura común; corrija esto y "
                        "ejecute ./sitio.sh construir:\n" + str(e))
    return mensajes
