"""El ciclo completo: configuración → modelo → plan → páginas → auditoría → escritura."""

import jinja2

from . import config as C
from . import modelo as M
from . import salidas as X


class ErrorDeFuente(Exception):
    """La fuente, curso.yml o una plantilla no permiten generar el sitio. El mensaje
    lista todos los problemas encontrados, uno por renglón."""


def construir(raiz, modo="escribir"):
    """modo «escribir»: escribe lo que cambió y borra los huérfanos. «verificar»: no
    toca nada. Devuelve {salidas, distintos, huerfanos, avisos, modelo}."""
    try:
        cfg = C.cargar(raiz)
    except C.ErrorDeConfiguracion as e:
        raise ErrorDeFuente("  · " + str(e))
    try:
        ctx = M.construir_modelo(cfg)
    except M.ErrorDeFuente as e:
        raise ErrorDeFuente(str(e))
    try:
        plan = X.plan_de_salidas(ctx, cfg)
        salidas = X.generar(ctx, cfg, plan)
    except (ValueError, KeyError) as e:
        raise ErrorDeFuente(f"  · {e}")
    except jinja2.TemplateError as e:
        donde = getattr(e, "filename", None) or getattr(e, "name", None) or "plantilla"
        linea = getattr(e, "lineno", None)
        raise ErrorDeFuente(f"  · {donde}{f', línea {linea}' if linea else ''}: {e}")
    errores, avisos = X.auditar(ctx, cfg, salidas)
    from . import __version__
    pedida = str(cfg["_curso"].get("version_motor") or "")
    if pedida and pedida.split(".")[0] != __version__.split(".")[0]:
        errores.append(f"curso.yml pide el motor {pedida}, pero está instalado el "
                       f"{__version__}: actualice requirements.txt o curso.yml")
    elif pedida and pedida != __version__:
        avisos.append(f"curso.yml pide el motor {pedida}; está instalado el {__version__}")
    if errores:
        raise ErrorDeFuente("Auditoría de duplicación (una plantilla repite un dato de "
                            "la fuente como texto fijo):\n"
                            + "\n".join("  · " + e for e in errores))
    distintos, huerfanos = X.diferencias(cfg["_raiz"], salidas)
    if modo == "escribir":
        X.escribir(cfg["_raiz"], salidas, distintos, huerfanos)
    return {"salidas": salidas, "distintos": distintos, "huerfanos": huerfanos,
            "avisos": avisos, "modelo": ctx, "config": cfg}
