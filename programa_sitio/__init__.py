"""programa-sitio: del programa analítico de una UEA a su sitio web.

Una sola fuente —el programa analítico en Markdown— se publica tal cual y, además, se
convierte en las páginas del sitio, el menú y el README del repositorio. Todo lo que el
sitio repite de la fuente se genera; nada se copia a mano."""

__version__ = "1.0.0"
# Repositorio del motor: de aquí instalan cada curso y GitHub Actions la versión fijada.
MOTOR_REPOSITORIO = "https://github.com/jzavalar/motor-uea"

from .nucleo import ErrorDeFuente, construir  # noqa: E402,F401
