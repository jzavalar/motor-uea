"""Informe de revisión del programa analítico contra sus tres insumos.

Pensado para el ciclo de redacción con un asistente de IA: se genera, se le entrega al
asistente junto con el programa analítico, el asistente corrige, y se repite hasta que
el informe diga que el programa está listo. No escribe nada del sitio."""

import datetime as dt

from . import __version__
from . import calendario as K
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
        clave = (cfg.get("calendario") or {}).get("trimestre") or \
            K.clave_trimestre(uea.get("trimestre"))
        T = K.cargar(cfg).get(clave) if clave else None
        if T:
            L_.append(f"- **Calendario escolar**: {T['_calendario']}, trimestre {clave} "
                      f"({T.get('nombre', clave)})")
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
        clave = (cfg.get("calendario") or {}).get("trimestre") or \
            K.clave_trimestre(uea.get("trimestre"))
        T = K.cargar(cfg).get(clave) if clave else None
        if T:
            d = lambda x: L.f_dma(x)  # noqa: E731
            desc = [x for x in T["_descansos"] if T["trimestre"][0] <= x <= T["trimestre"][1]]
            L_ += [f"## Fechas oficiales del trimestre {clave}", "",
                   "| Concepto | Fecha |", "|---|---|",
                   f"| Trimestre | {d(T['trimestre'][0])} al {d(T['trimestre'][1])} |",
                   f"| Clases | del {L.f_larga(T['clases'][0])} al {L.f_larga(T['clases'][1])} "
                   f"de {T['clases'][1].year} |",
                   f"| Semanas lectivas | {len(T.get('semanas') or {})} "
                   f"({', '.join((T.get('semanas') or {}).keys())}) |",
                   "| Descansos obligatorios | " + (", ".join(L.f_larga(x) for x in desc)
                                                   or "ninguno") + " |",
                   f"| Evaluaciones globales | {d(T['globales'][0])} al {d(T['globales'][1])} |"]
            rec = T.get("recuperacion") or {}
            if rec.get("evaluaciones"):
                L_.append(f"| Evaluaciones de recuperación | {d(rec['evaluaciones'][0])} al "
                          f"{d(rec['evaluaciones'][1])} |")
            L_ += ["", f"*{T['_calendario']}. {T.get('_aprobacion', '')}*", ""]
    return "\n".join(L_).rstrip() + "\n", listo
