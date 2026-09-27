"""Complemento de MkDocs: regenera el sitio a partir del programa analítico antes de
cada construcción, para que `mkdocs serve` y `mkdocs build` nunca muestren páginas
viejas. Se declara en mkdocs.yml (que el propio motor genera):

    plugins:
      - programa-sitio

· mkdocs serve: vigila también curso.yml, los datos y las plantillas del curso; cada vez
  que se guarda la fuente, regenera y recarga el navegador. Si la fuente queda a medio
  editar, muestra el error y conserva la última versión buena: el servidor no se cae.
· mkdocs build (y GitHub Actions): si la fuente no es consistente, la construcción falla
  con el mismo mensaje que daría `programa-sitio construir`.
· Si cambia mkdocs.yml (el menú), MkDocs ya había leído el anterior para esta
  construcción: se avisa, y la siguiente construcción ya lo toma.
"""

import logging
import os

from mkdocs.config import config_options
from mkdocs.exceptions import PluginError
from mkdocs.plugins import BasePlugin

from . import config as C
from .nucleo import ErrorDeFuente, construir

log = logging.getLogger("mkdocs.plugins.programa-sitio")


class ProgramaSitio(BasePlugin):
    config_scheme = (("curso", config_options.Type(str, default="")),)

    def on_startup(self, command, dirty):
        self.comando = command

    def _raiz(self, config):
        base = os.path.dirname(os.path.abspath(config.config_file_path))
        return os.path.join(base, self.config["curso"]) if self.config["curso"] else base

    def on_serve(self, server, config, builder):
        raiz = self._raiz(config)
        server.watch(os.path.join(raiz, C.ARCHIVO_CURSO))
        try:
            cfg = C.cargar(raiz)
            for rel in (cfg["plantillas"], cfg.get("_datos_archivo")):
                if rel and os.path.exists(os.path.join(raiz, rel)):
                    server.watch(os.path.join(raiz, rel))
        except C.ErrorDeConfiguracion:
            pass
        return server

    def on_pre_build(self, config):
        try:
            r = construir(self._raiz(config), "escribir")
        except ErrorDeFuente as e:
            mensaje = "La fuente no es internamente consistente:\n" + str(e)
            if getattr(self, "comando", "build") == "serve":
                log.error(mensaje + "\n(Se conserva la última versión generada del sitio.)")
                return
            raise PluginError(mensaje)
        for d in r["distintos"]:
            log.info(f"programa-sitio regeneró {d}")
        for h in r["huerfanos"]:
            log.info(f"programa-sitio borró {h} (ya no corresponde a nada en la fuente)")
        if "mkdocs.yml" in r["distintos"]:
            log.warning("mkdocs.yml cambió (menú o datos del sitio): esta construcción usa "
                        "la configuración anterior; vuelva a construir para ver el cambio.")
