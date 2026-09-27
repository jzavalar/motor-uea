"""programa-sitio — línea de órdenes.

    programa-sitio construir [--curso DIR] [--verificar] [--auditar] [--porcelana]
    programa-sitio nuevo DIR --fuente programa.md --sitio URL --repositorio URL
    programa-sitio version

construir   valida la fuente, regenera lo que cambió y borra las páginas huérfanas.
            --verificar  no escribe nada: sale con 1 si el sitio del repositorio no
                         coincide con la fuente (lo usan el gancho y GitHub Actions)
            --auditar    muestra también los avisos de la auditoría de duplicación
            --porcelana  escribe e imprime solo las rutas escritas o borradas
nuevo       arma el repositorio de una UEA nueva a partir de su programa analítico.
"""

import argparse
import difflib
import os
import sys

from . import __version__
from .nucleo import ErrorDeFuente, construir


def orden_construir(a):
    try:
        r = construir(a.curso, "verificar" if a.verificar else "escribir")
    except ErrorDeFuente as e:
        print("La fuente no es internamente consistente:\n" + str(e), file=sys.stderr)
        return 2
    if a.porcelana:
        for d in r["distintos"] + r["huerfanos"]:
            print(d)
        return 0
    raiz = r["config"]["_raiz"]
    if a.verificar:
        for destino in r["distintos"]:
            ruta = os.path.join(raiz, destino)
            actual = open(ruta, encoding="utf-8").read() if os.path.exists(ruta) else ""
            diff = difflib.unified_diff(actual.splitlines(), r["salidas"][destino].splitlines(),
                                        f"{destino} (en el repositorio)",
                                        f"{destino} (generado)", lineterm="", n=1)
            print("\n".join(list(diff)[:40]), file=sys.stderr)
        for h in r["huerfanos"]:
            print(f"{h}: fue generado, pero ya no corresponde a nada en la fuente",
                  file=sys.stderr)
        n = len(r["distintos"]) + len(r["huerfanos"])
        if n:
            print(f"\n{n} archivo(s) no coinciden con la fuente. Ejecute: "
                  "programa-sitio construir", file=sys.stderr)
            return 1
        print(f"Fuente consistente; {len(r['salidas'])} salidas al día.")
    else:
        print(f"Fuente consistente. Escritos {len(r['distintos'])} de "
              f"{len(r['salidas'])} archivos.")
        for d in r["distintos"]:
            print("  ·", d)
        for h in r["huerfanos"]:
            print("  · borrado:", h)
    if r["avisos"]:
        if a.auditar:
            print("\nAvisos de la auditoría de duplicación (no detienen la generación):")
            for x in r["avisos"]:
                print("  ·", x)
        else:
            print(f"{len(r['avisos'])} aviso(s) de auditoría; véalos con --auditar.")
    return 0


def orden_nuevo(a):
    from .nuevo import crear
    try:
        mensajes = crear(a.destino, a.fuente, a.sitio, a.repositorio, a.unidad)
    except (ValueError, FileExistsError, FileNotFoundError) as e:
        print(f"No se pudo crear el curso: {e}", file=sys.stderr)
        return 2
    for m in mensajes:
        print(m)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="programa-sitio", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="orden")
    c = sub.add_parser("construir", help="valida y regenera el sitio")
    c.add_argument("--curso", default=".", help="raíz del repositorio del curso")
    c.add_argument("--verificar", action="store_true")
    c.add_argument("--auditar", action="store_true")
    c.add_argument("--porcelana", action="store_true")
    n = sub.add_parser("nuevo", help="arma el repositorio de una UEA nueva")
    n.add_argument("destino")
    n.add_argument("--fuente", required=True, help="programa analítico en Markdown")
    n.add_argument("--sitio", required=True, help="URL del sitio (GitHub Pages)")
    n.add_argument("--repositorio", required=True, help="URL del repositorio en GitHub")
    n.add_argument("--unidad", default="UAM-Iztapalapa")
    sub.add_parser("version")
    a = ap.parse_args(argv)
    if a.orden == "construir":
        return orden_construir(a)
    if a.orden == "nuevo":
        return orden_nuevo(a)
    if a.orden == "version":
        print(__version__)
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
