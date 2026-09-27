#!/usr/bin/env bash
# Un solo comando para mantener el sitio de esta UEA (Fedora 44 o posterior).
#
#   ./sitio.sh preparar            instala lo necesario (pide la contraseña de sudo)
#   ./sitio.sh construir           regenera el sitio a partir de la fuente y lo valida
#   ./sitio.sh verificar           solo comprueba, sin escribir nada
#   ./sitio.sh auditar             muestra los avisos de la auditoría de duplicación
#   ./sitio.sh revisar             informe (revision.md) del programa analítico contra el
#                                  calendario escolar y el programa oficial, para corregirlo
#   ./sitio.sh servir              vista previa en http://127.0.0.1:8000 (se regenera al guardar)
#   ./sitio.sh publicar [--pr] [-m "mensaje"]
#                                  commit y push a main; con --pr, rama y Pull Request
#
# Todo pasa por la colección de Ansible jzavalar.programa_sitio, en la versión que fija
# requirements.yml; el motor de Python, en la que fija requirements.txt.
set -euo pipefail

aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$aqui"
accion="${1:-ayuda}"
[ $# -gt 0 ] && shift

ansible_minimo="2.16"
fedora_minimo="44"
export ANSIBLE_COLLECTIONS_PATH="$aqui/.ansible/collections"
export ANSIBLE_LOCALHOST_WARNING=false
export ANSIBLE_INVENTORY_UNPARSED_WARNING=false

ayuda() { sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; }

version_mayor_o_igual() {  # $1 >= $2
    printf '%s\n%s\n' "$2" "$1" | sort --check=quiet --version-sort
}

comprobar_sistema() {
    if [ -r /etc/os-release ]; then
        . /etc/os-release
        if [ "${ID:-}" = "fedora" ] && version_mayor_o_igual "${VERSION_ID:-0}" "$fedora_minimo"; then
            return 0
        fi
    fi
    if [ "${PROGRAMA_SITIO_OTRO_SISTEMA:-0}" = "1" ]; then
        echo "Aviso: este sistema no es Fedora $fedora_minimo o posterior; continúo porque PROGRAMA_SITIO_OTRO_SISTEMA=1." >&2
        return 0
    fi
    echo "Este repositorio está preparado para Fedora $fedora_minimo o posterior." >&2
    echo "Si de todos modos quiere intentarlo, ejecute con PROGRAMA_SITIO_OTRO_SISTEMA=1." >&2
    exit 1
}

comprobar_ansible() {
    if ! command -v ansible-playbook >/dev/null 2>&1; then
        echo "Falta Ansible. Instálelo con:  sudo dnf install ansible-core" >&2
        exit 1
    fi
    local v
    v="$(ansible-playbook --version 2>/dev/null | head -n1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -n1 || true)"
    if ! version_mayor_o_igual "$v" "$ansible_minimo"; then
        echo "Ansible $v es anterior al mínimo ($ansible_minimo). Actualícelo con:  sudo dnf upgrade ansible-core" >&2
        exit 1
    fi
}

instalar_coleccion() {
    local fijada instalada
    fijada="$(grep -E '^\s*version:' requirements.yml | head -n1 | awk '{print $2}' | tr -d '"')"
    instalada="$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' \
        "$ANSIBLE_COLLECTIONS_PATH/ansible_collections/jzavalar/programa_sitio/MANIFEST.json" 2>/dev/null | head -n1 || true)"
    if [ "v${instalada#v}" != "v${fijada#v}" ]; then
        echo "Instalando la colección jzavalar.programa_sitio ${fijada}…"
        ansible-galaxy collection install -r requirements.yml -p "$ANSIBLE_COLLECTIONS_PATH" --force >/dev/null
    fi
}

jugar() {
    local libro="$1"; shift
    local otro=()
    [ "${PROGRAMA_SITIO_OTRO_SISTEMA:-0}" = "1" ] && otro=(-e permitir_otro_sistema=true)
    ansible-playbook "jzavalar.programa_sitio.$libro" -e "repo=$aqui" "${otro[@]}" "$@"
}

case "$accion" in
    preparar)
        comprobar_sistema; comprobar_ansible; instalar_coleccion
        if [ "${PROGRAMA_SITIO_SIN_DNF:-0}" = "1" ]; then
            # paquetes ya instalados (o integración continua): no hace falta sudo
            jugar preparar -e omitir_dnf=true "$@"
        else
            jugar preparar --ask-become-pass "$@"
        fi ;;
    construir)
        comprobar_ansible; instalar_coleccion; jugar construir "$@" ;;
    publicar)
        comprobar_ansible; instalar_coleccion
        modo=directo; extra=()
        while [ $# -gt 0 ]; do
            case "$1" in
                --pr) modo=pr ;;
                -m) shift
                    # como JSON: «-e mensaje=dos palabras» partiría el mensaje en el espacio
                    extra+=(-e "$(python3 -c 'import json,sys; print(json.dumps({"mensaje": sys.argv[1]}))' "$1")") ;;
                *) extra+=("$1") ;;
            esac
            shift
        done
        jugar publicar -e "modo=$modo" "${extra[@]}" ;;
    verificar)
        exec "$aqui/.venv/bin/programa-sitio" construir --verificar "$@" ;;
    auditar)
        exec "$aqui/.venv/bin/programa-sitio" construir --auditar "$@" ;;
    revisar)
        exec "$aqui/.venv/bin/programa-sitio" revisar "$@" ;;
    servir)
        # --livereload explícito: en MkDocs 1.6 con Click 8.2 la recarga no se activa sola.
        exec "$aqui/.venv/bin/mkdocs" serve --livereload "$@" ;;
    ayuda|-h|--help) ayuda ;;
    *) echo "Acción desconocida: $accion" >&2; ayuda; exit 1 ;;
esac
