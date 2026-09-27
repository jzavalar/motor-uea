"""Carga de curso.yml combinada con la configuración predeterminada del motor."""

import copy
import os

import yaml

PREDETERMINADO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "predeterminado.yml")
ARCHIVO_CURSO = "curso.yml"


class ErrorDeConfiguracion(Exception):
    pass


def mezclar(base, encima):
    """Diccionarios: clave por clave, recursivamente. Todo lo demás: gana «encima»."""
    if isinstance(base, dict) and isinstance(encima, dict):
        r = copy.deepcopy(base)
        for k, v in encima.items():
            r[k] = mezclar(r.get(k), v) if k in r else copy.deepcopy(v)
        return r
    return copy.deepcopy(encima)


def cargar(raiz):
    """Devuelve la configuración efectiva del curso cuya raíz es «raiz»."""
    with open(PREDETERMINADO, encoding="utf-8") as f:
        base = yaml.safe_load(f)
    ruta = os.path.join(raiz, ARCHIVO_CURSO)
    if not os.path.exists(ruta):
        raise ErrorDeConfiguracion(f"no existe {ruta}: cada repositorio de UEA necesita "
                                   "un curso.yml en su raíz (vea programa-sitio nuevo)")
    try:
        with open(ruta, encoding="utf-8") as f:
            curso = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ErrorDeConfiguracion(f"{ARCHIVO_CURSO} no es YAML válido: {e}")
    if not isinstance(curso, dict):
        raise ErrorDeConfiguracion(f"{ARCHIVO_CURSO} debe ser un diccionario")
    desconocidas = sorted(set(curso) - set(base) - {"version_motor"})
    if desconocidas:
        raise ErrorDeConfiguracion(f"{ARCHIVO_CURSO}: claves desconocidas {desconocidas}; "
                                   f"las válidas son {sorted(base)}")
    cfg = mezclar(base, curso)
    cfg["_raiz"] = os.path.abspath(raiz)
    cfg["_curso"] = curso
    # datos: ruta a un YAML o diccionario en línea
    if isinstance(cfg.get("datos"), str):
        ruta_datos = os.path.join(raiz, cfg["datos"])
        try:
            with open(ruta_datos, encoding="utf-8") as f:
                cfg["_datos"] = yaml.safe_load(f) or {}
        except FileNotFoundError:
            raise ErrorDeConfiguracion(f"{ARCHIVO_CURSO}: datos apunta a {cfg['datos']}, "
                                       "que no existe")
        except yaml.YAMLError as e:
            raise ErrorDeConfiguracion(f"{cfg['datos']} no es YAML válido: {e}")
        cfg["_datos_archivo"] = cfg["datos"]
    else:
        cfg["_datos"] = cfg.get("datos") or {}
        cfg["_datos_archivo"] = None
    return cfg
