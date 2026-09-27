"""El ciclo completo: configuración → modelo → contraste con el calendario escolar y el
programa oficial → plan → páginas → auditoría → escritura."""

import jinja2

from . import calendario as K
from . import config as C
from . import modelo as M
from . import oficial as O
from . import salidas as X


class ErrorDeFuente(Exception):
    """La fuente, curso.yml o una plantilla no permiten generar el sitio. El mensaje
    lista todos los problemas encontrados, uno por renglón."""


def _lista(errores):
    return "\n".join("  · " + e for e in errores)


def examinar(raiz):
    """Todo lo que se puede comprobar sin escribir, sin detenerse en el primer problema.
    Devuelve {cfg, ctx, errores: {origen: [...]}, avisos: [...], salidas}."""
    try:
        cfg = C.cargar(raiz)
    except C.ErrorDeConfiguracion as e:
        return {"cfg": None, "ctx": None, "errores": {"configuración": [str(e)]},
                "avisos": [], "salidas": {}}
    errores = {"estructura y consistencia": [], "calendario escolar": [],
               "programa oficial": [], "plantillas": []}
    avisos = []
    try:
        ctx, e_modelo = M.construir_modelo(cfg, recolectar=True)
    except M.ErrorDeFuente as e:
        return {"cfg": cfg, "ctx": None, "errores": {"estructura y consistencia": [str(e)]},
                "avisos": [], "salidas": {}}
    errores["estructura y consistencia"] += e_modelo
    for nombre, modulo, clave in (("calendario escolar", K, "calendario"),
                                  ("programa oficial", O, "oficial")):
        try:
            e, a, datos = modulo.contrastar(ctx, cfg)
        except Exception as ex:  # un insumo ilegible no debe ocultar lo demás
            e, a, datos = [f"no se pudo contrastar: {ex}"], [], None
        errores[nombre] += e
        avisos += a
        if clave == "calendario":
            ctx["cal"]["oficial"] = datos
        else:
            ctx["oficial"] = datos
    salidas = {}
    if not any(errores.values()):
        try:
            plan = X.plan_de_salidas(ctx, cfg)
            salidas = X.generar(ctx, cfg, plan)
            e_aud, a_aud = X.auditar(ctx, cfg, salidas)
            errores["plantillas"] += e_aud
            avisos += a_aud
        except (ValueError, KeyError) as e:
            errores["plantillas"].append(str(e))
        except jinja2.TemplateError as e:
            donde = getattr(e, "filename", None) or getattr(e, "name", None) or "plantilla"
            linea = getattr(e, "lineno", None)
            errores["plantillas"].append(f"{donde}{f', línea {linea}' if linea else ''}: {e}")
    from . import __version__
    pedida = str(cfg["_curso"].get("version_motor") or "")
    if pedida and pedida.split(".")[0] != __version__.split(".")[0]:
        errores["estructura y consistencia"].append(
            f"curso.yml pide el motor {pedida}, pero está instalado el {__version__}: "
            "actualice requirements.txt o curso.yml")
    elif pedida and pedida != __version__:
        avisos.append(f"curso.yml pide el motor {pedida}; está instalado el {__version__}")
    return {"cfg": cfg, "ctx": ctx, "errores": errores, "avisos": avisos,
            "salidas": salidas}


def construir(raiz, modo="escribir"):
    """modo «escribir»: escribe lo que cambió y borra los huérfanos. «verificar»: no
    toca nada. Devuelve {salidas, distintos, huerfanos, avisos, modelo, config}."""
    r = examinar(raiz)
    problemas = [e for lista in r["errores"].values() for e in lista]
    if problemas:
        partes = []
        for origen, lista in r["errores"].items():
            if lista:
                partes.append(f"[{origen}]\n{_lista(lista)}")
        raise ErrorDeFuente("\n".join(partes))
    cfg, salidas = r["cfg"], r["salidas"]
    distintos, huerfanos = X.diferencias(cfg["_raiz"], salidas)
    if modo == "escribir":
        X.escribir(cfg["_raiz"], salidas, distintos, huerfanos)
    return {"salidas": salidas, "distintos": distintos, "huerfanos": huerfanos,
            "avisos": r["avisos"], "modelo": r["ctx"], "config": cfg}
