# Colección jzavalar.programa_sitio

Playbooks para mantener el sitio de una UEA con el motor `programa-sitio`, en Fedora 44
o posterior. En un repositorio de curso se usan a través de `./sitio.sh`; directamente:

```bash
ansible-playbook jzavalar.programa_sitio.preparar -e repo=$PWD --ask-become-pass
ansible-playbook jzavalar.programa_sitio.construir -e repo=$PWD
ansible-playbook jzavalar.programa_sitio.publicar  -e repo=$PWD [-e modo=pr] [-e mensaje="…"]
ansible-playbook jzavalar.programa_sitio.nuevo -e destino=~/cursos/mi-uea \
    -e fuente=~/programa.md -e nombre_repo=mi-uea [-e crear_en_github=true]
```
