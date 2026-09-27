"""Contraste del programa analítico con el calendario escolar vigente.

El calendario escolar lo aprueba el Colegio Académico para todo un año escolar y es el
mismo para todas las UEA: vive en el motor, un archivo por año escolar
(programa_sitio/calendarios/AAAA-AAAA.yml). Un curso puede usar su propia copia
(`calendario: {archivo: …}` en curso.yml) si el calendario cambia antes de que haya una
versión nueva del motor.

Lo que se comprueba —todo lo que el programa analítico dice sobre fechas debe caber en
el calendario—:

  · el trimestre lectivo y las evaluaciones globales de §1 son los del calendario;
  · ninguna sesión cae fuera del periodo de clases ni en un día de descanso obligatorio;
  · cada descanso obligatorio que cae en un día de clase del grupo aparece en la tabla
    de sesiones, y la tabla no marca como descanso un día que no lo es;
  · si hay bloque de datos del periodo, su fin de clases y sus globales coinciden;
  · aviso: días de clase del periodo que no se usan.
"""

import datetime as dt
import glob
import os
import re

import yaml

from . import lexico as L

CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calendarios")
ESTACIONES = {"otono": "O", "invierno": "I", "primavera": "P"}


def clave_trimestre(texto):
    """'26-Otoño' -> '26-O'; '26-O' -> '26-O'."""
    m = re.match(r"^(\d{2})-?([A-Za-zÁÉÍÓÚáéíóúñ]+)$", (texto or "").strip())
    if not m:
        return None
    est = L.sin_acentos(m.group(2)).lower()
    letra = ESTACIONES.get(est, est[:1].upper())
    return f"{m.group(1)}-{letra}"


def cargar(cfg):
    """{trimestre: datos}, más el nombre del calendario del que salió cada uno."""
    archivos = sorted(glob.glob(os.path.join(CARPETA, "*.yml")))
    propio = (cfg.get("calendario") or {}).get("archivo")
    if propio:
        archivos.append(os.path.join(cfg["_raiz"], propio))
    trimestres = {}
    for a in archivos:
        with open(a, encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        for k, t in (d.get("trimestres") or {}).items():
            t = dict(t)
            t["_calendario"] = d.get("calendario", os.path.basename(a))
            t["_aprobacion"] = d.get("aprobacion", "")
            t["_descansos"] = list(d.get("descansos") or [])
            trimestres[str(k)] = t
    return trimestres


def contrastar(ctx, cfg):
    """(errores, avisos, datos del trimestre o None)."""
    errores, avisos = [], []
    uea = ctx["curso"]["uea"]
    pedido = (cfg.get("calendario") or {}).get("trimestre")
    clave = pedido or clave_trimestre(uea.get("trimestre"))
    if not clave:
        return (["calendario escolar: no sé qué trimestre es «" + str(uea.get("trimestre"))
                 + "»; escriba en el encabezado «Trimestre 26-Otoño · …»"], [], None)
    trimestres = cargar(cfg)
    T = trimestres.get(clave)
    if T is None:
        return ([f"calendario escolar: el motor no tiene el trimestre {clave} (tiene "
                 f"{', '.join(sorted(trimestres)) or 'ninguno'}). Hace falta el calendario "
                 "escolar de ese año: agréguelo al motor o indique calendario.archivo en "
                 "curso.yml"], [], None)
    nombre = T["_calendario"]
    t_ini, t_fin = T["trimestre"]
    c_ini, c_fin = T["clases"]
    g_ini, g_fin = T["globales"]
    descansos = set(T["_descansos"])
    per = ctx.get("_periodo") or ctx["cal"]["periodo"]

    def fecha(d):
        return L.f_dma(d) if d else "—"

    # §1 contra el calendario
    if per.get("trimestre_inicio") and (per["trimestre_inicio"], per.get("trimestre_fin")) \
            != (t_ini, t_fin):
        errores.append(f"§1: el trimestre lectivo es del {fecha(per['trimestre_inicio'])} al "
                       f"{fecha(per.get('trimestre_fin'))}, pero el {nombre} dice del "
                       f"{fecha(t_ini)} al {fecha(t_fin)}")
    if per.get("globales_inicio") and (per["globales_inicio"], per.get("globales_fin")) \
            != (g_ini, g_fin):
        errores.append(f"§1: las evaluaciones globales son del {fecha(per['globales_inicio'])} "
                       f"al {fecha(per.get('globales_fin'))}, pero el {nombre} dice del "
                       f"{fecha(g_ini)} al {fecha(g_fin)}")
    fin_decl = per.get("fin_de_clases")
    if fin_decl and fin_decl != c_fin and fin_decl != per.get("ultima_sesion"):
        errores.append(f"§7: el fin de clases es el {fecha(fin_decl)}, pero el {nombre} "
                       f"dice el {fecha(c_fin)}")

    # sesiones
    S = ctx.get("S") or {}
    for n in sorted(S):
        d = S[n].get("fecha")
        if not d:
            continue
        if d < c_ini or d > c_fin:
            errores.append(f"§7: la sesión {n} ({fecha(d)}) cae fuera del periodo de clases "
                           f"del {nombre} ({fecha(c_ini)} al {fecha(c_fin)})")
        if d in descansos:
            errores.append(f"§7: la sesión {n} cae el {fecha(d)}, que es día de descanso "
                           f"obligatorio en el {nombre}")

    # descansos que tocan días de clase del grupo
    dias = set(per.get("dias") or {S[n]["fecha"].weekday() for n in S if S[n].get("fecha")})
    primera = per.get("primera_sesion") or c_ini
    ultima = per.get("ultima_sesion") or c_fin
    oficiales = sorted(d for d in descansos if primera <= d <= ultima and d.weekday() in dias)
    en_tabla = sorted(x["fecha"] for x in per.get("descansos", []) if x.get("fecha"))
    for d in oficiales:
        if d not in en_tabla:
            errores.append(f"§7: el {fecha(d)} es descanso obligatorio en el {nombre} y cae "
                           "en día de clase; falta como «Descanso obligatorio» en la tabla")
    for d in en_tabla:
        if d not in descansos:
            errores.append(f"§7: la tabla marca el {fecha(d)} como descanso, pero no lo es "
                           f"en el {nombre}")

    # días de clase disponibles que no se usan
    usados = {S[n]["fecha"] for n in S if S[n].get("fecha")}
    d = c_ini
    libres = []
    while d <= c_fin:
        if d.weekday() in dias and d not in descansos and d not in usados:
            libres.append(d)
        d += dt.timedelta(days=1)
    if libres and dias:
        avisos.append("calendario escolar: estos días de clase del grupo no tienen sesión: "
                      + ", ".join(L.f_larga(x) for x in libres))
    oficial = {
        "calendario": nombre, "aprobacion": T["_aprobacion"], "trimestre": clave,
        "nombre": T.get("nombre", clave), "inicio": t_ini, "fin": t_fin,
        "inicio_clases": c_ini, "fin_clases": c_fin, "globales": [g_ini, g_fin],
        "actas": T.get("actas"), "recuperacion": T.get("recuperacion") or {},
        "semanas": T.get("semanas") or {}, "descansos": sorted(descansos),
    }
    return errores, avisos, oficial
