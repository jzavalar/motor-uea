"""Informe de revisión del programa analítico contra sus tres insumos.

Pensado para el ciclo de redacción con un asistente de IA: se genera, se le entrega al
asistente junto con el programa analítico, el asistente corrige, y se repite hasta que
el informe diga que el programa está listo. No escribe nada del sitio."""

import datetime as dt
import os

from . import __version__
from . import calendario as K
from . import calendario_escolar as CE
from . import lexico as L
from .nucleo import examinar

TITULOS = {
    "calendario escolar": "Contra el calendario escolar",
    "programa oficial": "Contra el programa de estudios oficial",
    "estructura y consistencia": "Estructura y consistencia interna del programa analítico",
    "plantillas": "Plantillas del sitio (no es del programa analítico)",
    "configuración": "Configuración del curso (curso.yml)",
}

INSTRUCCIONES = """\
1. Corrige **solo** el programa analítico. El calendario escolar y el programa de estudios
   oficial no se modifican: mandan ellos.
2. Toda fecha debe caber en el calendario escolar: sesiones dentro del periodo de
   clases, ningún día de descanso obligatorio con sesión, y cada descanso que caiga en
   día de clase del grupo como renglón «— | Ddd DD mmm | — | — | Descanso obligatorio | —»
   en la tabla de la sección 7.
3. Lo que el programa dice transcribir del programa oficial (datos de §1, objetivos,
   contenido sintético, citas entre «») debe quedar **idéntico** al oficial.
4. Conserva la **forma**: los encabezados de las tablas, los encabezados
   «### 6.N Proyecto PN · Nombre», los párrafos que empiezan con etiqueta en negritas
   (**Propósito.**, **Condiciones.** o **Insumo.**, **Expediente.**, **Evaluación
   escrita N.** o **Examen escrito N.**, **Criterios de la rúbrica.**), las fechas de las
   tablas como «Lun 21 sep» y el renglón «Trimestre NN-Periodo · …» del encabezado.
5. Si cambias un dato que aparece en más de un lugar del programa (una fecha, una
   ponderación, el número de sesiones), cámbialo en todos.
6. Entrega el programa analítico completo, corregido, en Markdown.
"""


def informe(raiz):
    """(texto_markdown, listo: bool)."""
    r = examinar(raiz)
    cfg, ctx = r["cfg"], r["ctx"]
    hoy = dt.date.today()
    uea = (ctx or {}).get("curso", {}).get("uea", {}) if ctx else {}
    titulo = f"{uea.get('nombre', 'UEA')} · Trimestre {uea.get('trimestre', '¿?')}"
    problemas = {k: v for k, v in r["errores"].items() if v}
    n = sum(len(v) for v in problemas.values())
    listo = n == 0
    L_ = [f"# Revisión del programa analítico · {titulo}", "",
          f"Generada el {L.f_dma(hoy)} por programa-sitio {__version__}.", ""]
    # insumos
    L_ += ["## Insumos", ""]
    if cfg:
        L_.append(f"- **Programa analítico** (la fuente): `{cfg['fuente']}`")
        of = (ctx or {}).get("oficial")
        archivo_of = (cfg.get("programa_oficial") or {}).get("archivo")
        L_.append(f"- **Programa de estudios oficial**: `{archivo_of}`" + ("" if of else
                  " — no se encontró o no se pudo leer; no se contrastó"))
        clave, T, _ = K.trimestre(cfg, uea)
        if T:
            L_.append(f"- **Calendario escolar**: {T['_calendario']} "
                      f"(`{os.path.basename(T['_archivo'])}`), trimestre {clave} ({T['nombre']})")
        else:
            L_.append(f"- **Calendario escolar**: no hay datos del trimestre {clave or '¿?'}")
    L_.append("")
    # resultado
    L_ += ["## Resultado", ""]
    if listo:
        L_ += ["**El programa analítico está listo**: es consistente consigo mismo, con el "
               "calendario escolar y con el programa oficial. Se puede generar y publicar "
               "el sitio.", ""]
    else:
        L_ += [f"**Hay {n} problema(s) por corregir** antes de generar el sitio.", ""]
        L_ += ["## Problemas por corregir", ""]
        for origen in ("calendario escolar", "programa oficial", "estructura y consistencia",
                       "configuración", "plantillas"):
            lista = problemas.get(origen)
            if not lista:
                continue
            L_ += [f"### {TITULOS[origen]}", ""]
            for e in lista:
                for linea in str(e).split("\n"):
                    linea = linea.strip().lstrip("·").strip()
                    if linea:
                        L_.append(f"- {linea}")
            L_.append("")
    def del_sitio(a):
        return a.startswith(("fuente/", "docs/")) and not a.startswith(cfg["fuente"]) \
            if cfg else False
    del_programa = [a for a in r["avisos"] if not del_sitio(a)]
    de_sitio = [a for a in r["avisos"] if del_sitio(a)]
    if del_programa:
        L_ += ["## Avisos sobre el programa analítico (no impiden generar el sitio)", ""]
        L_ += [f"- {a}" for a in del_programa] + [""]
    if not listo:
        L_ += ["## Instrucciones para el asistente de IA", "", INSTRUCCIONES]
    if de_sitio:
        L_ += ["<details><summary>Avisos sobre las plantillas y las páginas escritas a mano "
               f"del sitio ({len(de_sitio)}); no son del programa analítico</summary>", ""]
        L_ += [f"- {a}" for a in de_sitio] + ["", "</details>", ""]
    # referencia de fechas
    if cfg:
        clave, T, _ = K.trimestre(cfg, uea)
        if T:
            p, (ci, cf), rec = T["periodo"], T["clases"], T["recuperacion"]
            desc = [x for x in T["_descansos"] if p[0] <= x <= p[1]]
            L_ += [f"## Fechas oficiales del trimestre {clave}", "",
                   "| Concepto | Fechas |", "|---|---|",
                   f"| Trimestre | {CE.rango(*p)} |",
                   f"| Clases | {CE.rango_largo(ci, cf)} |",
                   f"| Semanas lectivas | {len(T['semanas'])}: " +
                   "; ".join(f"{s['etiqueta']}: {CE.rango_semana(s)}" for s in T["semanas"])
                   + " |",
                   "| Descansos obligatorios | " +
                   (", ".join(L.f_larga(x) for x in desc) or "ninguno") + " |",
                   ] + (["| Vacaciones dentro del trimestre (sin clases) | " +
                         "; ".join(CE.rango(a, b) for a, b, _ in T["vacaciones"]) + " |"]
                        if T["vacaciones"] else []) + [
                   f"| Evaluaciones globales | {T['globales'].texto()} |",
                   f"| Inscripción a recuperación | {rec['inscripcion'].texto()} |",
                   f"| Evaluaciones de recuperación | {rec['evaluaciones'].texto()} |",
                   "", f"*{T['_calendario']}. {T['_texto_aprobacion']}.*", ""]
    return "\n".join(L_).rstrip() + "\n", listo
