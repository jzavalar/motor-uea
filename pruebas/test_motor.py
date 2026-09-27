"""Pruebas del motor con el caso de Análisis de Decisiones (y, si se indica, con el
repositorio real de Informática: PROGRAMA_SITIO_INFORMATICA=/ruta/al/repo).

Cada prueba trabaja sobre una copia del caso en un directorio temporal."""

import datetime as dt
import os
import re
import shutil
import subprocess
import sys

import pytest

from programa_sitio import construir, ErrorDeFuente
from programa_sitio import lexico as L

CASOS = os.path.join(os.path.dirname(__file__), "casos")
AD = os.path.join(CASOS, "analisis-de-decisiones")
FUENTE = "docs/curso/programa-analitico.md"


@pytest.fixture
def curso(tmp_path):
    destino = tmp_path / "curso"
    shutil.copytree(AD, destino)
    construir(str(destino))
    return destino


def leer(curso, rel):
    return (curso / rel).read_text(encoding="utf-8")


def escribir(curso, rel, texto):
    (curso / rel).write_text(texto, encoding="utf-8")


def cambiar_fuente(curso, viejo, nuevo, veces=1):
    t = leer(curso, FUENTE)
    assert t.count(viejo) >= veces, f"no está «{viejo}» en la fuente"
    escribir(curso, FUENTE, t.replace(viejo, nuevo))


def generados(r):
    return r["salidas"]


# ------------------------------------------------------------------- básico

def test_construye_y_queda_al_dia(curso):
    r = construir(str(curso), "verificar")
    assert r["distintos"] == [] and r["huerfanos"] == []
    assert set(r["salidas"]) >= {"docs/index.md", "mkdocs.yml", "README.md",
                                 "docs/curso/calendario.md", "docs/curso/evaluacion.md",
                                 "docs/proyectos/p1-el-problema-bien-planteado/index.md"}


def test_modelo_del_segundo_curso(curso):
    m = construir(str(curso), "verificar")["modelo"]
    assert [p["id"] for p in m["proyectos"]] == ["P1", "P2", "P3"]
    assert [f["fase"] for f in m["curso"]["fases"]] == \
        ["Activista", "Reflexiva", "Teórica", "De cálculo", "Pragmática"]
    s8 = m["S"][8]
    assert s8["proyectos"] == ["P1", "P2"]
    assert s8["fases"] == {"P1": "Pragmática", "P2": "Activista"}
    pesos = {c["id"]: c["peso"] for c in m["curso"]["evaluacion"]["componentes"]}
    assert pesos == {"e1": 12, "e2": 15, "e3": 18, "exp1": 10, "exp2": 12, "exp3": 18,
                     "bit": 10, "par": 5}
    p1 = m["P"]["P1"]
    assert len(p1["criterios"]) == 6 and len(p1["expediente"]) == 8
    assert p1["eval"]["duracion"] == 60
    assert m["curso"]["uea"]["correo"] == "jzr@xanum.uam.mx"
    assert m["curso"]["grupos"][0]["id"] == "HE57"


def test_mkdocs_construye_estricto(curso):
    r = subprocess.run([sys.executable, "-m", "mkdocs", "build", "--strict", "--site-dir",
                        str(curso / "site")], cwd=curso, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]


# -------------------------------------------------------------- propagación

def test_un_cambio_en_la_fuente_llega_a_todas_las_paginas(curso):
    cambiar_fuente(curso, "| Correo de contacto | jzr@xanum.uam.mx |",
                   "| Correo de contacto | nuevo@xanum.uam.mx |")
    r = construir(str(curso))
    assert {"docs/index.md", "README.md", "mkdocs.yml"} <= set(r["distintos"])
    for rel in r["salidas"]:
        assert "jzr@xanum" not in leer(curso, rel), rel
    assert construir(str(curso), "verificar")["distintos"] == []


def test_renombrar_un_proyecto_muda_su_pagina_y_borra_la_vieja(curso):
    vieja = curso / "docs/proyectos/p2-el-precio-de-la-incertidumbre/index.md"
    assert vieja.exists()
    cambiar_fuente(curso, "### 6.2 Proyecto P2 · El precio de la incertidumbre",
                   "### 6.2 Proyecto P2 · El valor de la información")
    r = construir(str(curso))
    assert "docs/proyectos/p2-el-precio-de-la-incertidumbre/index.md" in r["huerfanos"]
    assert not vieja.parent.exists()
    assert (curso / "docs/proyectos/p2-el-valor-de-la-informacion/index.md").exists()
    assert "p2-el-valor-de-la-informacion" in leer(curso, "mkdocs.yml")
    assert "El precio de la incertidumbre" not in leer(curso, "docs/index.md")


MESES_L = ("enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|"
           "noviembre|diciembre")
MESES_A = "ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic"
RE_FECHAS = re.compile(
    # rango de un mismo mes: «7 al 11 de diciembre [de 2026]», «17 a 20 sep», «7–11 dic»
    rf"(?P<r1>\d{{1,2}})(?P<rsep>\s+al?\s+|–)(?P<r2>\d{{1,2}})(?P<resp> de | )"
    rf"(?P<rmes>{MESES_L}|{MESES_A})\b(?: de (?P<ranio>\d{{4}}))?"
    # fecha larga: «17 de septiembre [de 2026]»
    rf"|(?P<l1>\d{{1,2}}) de (?P<lmes>{MESES_L})(?: de (?P<lanio>\d{{4}}))?"
    # fecha corta de la tabla: «Lun 21 sep»
    rf"|(?:Lun|Mar|Mié|Jue|Vie|Sáb|Dom) (?P<c1>\d{{1,2}}) (?P<cmes>{MESES_A})\b")


def _desplazar(texto, dias):
    """Recorre todas las fechas del programa `dias` días (múltiplo de 7), en una sola
    pasada, como haría el profesor al preparar el trimestre siguiente."""
    def mas(anio, mes, dia):
        return dt.date(anio, L.MES_NUM[mes], int(dia)) + dt.timedelta(days=dias)

    def cambiar(m):
        g = m.groupdict()
        if g["r1"]:
            anio = int(g["ranio"]) if g["ranio"] else 2026
            a, b = mas(anio, g["rmes"], g["r1"]), mas(anio, g["rmes"], g["r2"])
            largo = len(g["rmes"]) > 3
            nombres = L.MESES if largo else L.MESES_C
            sep_mes = " de " if largo else " "
            ini = str(a.day) if a.month == b.month else f"{a.day}{sep_mes}{nombres[a.month]}"
            return (f"{ini}{g['rsep']}{b.day}{g['resp']}{nombres[b.month]}"
                    + (f" de {b.year}" if g["ranio"] else ""))
        if g["l1"]:
            d = mas(int(g["lanio"]) if g["lanio"] else 2026, g["lmes"], g["l1"])
            return f"{d.day} de {L.MESES[d.month]}" + (f" de {d.year}" if g["lanio"] else "")
        return L.f_corta(mas(2026, g["cmes"], g["c1"]))
    return RE_FECHAS.sub(cambiar, texto)


def test_cambio_de_trimestre(curso):
    t = leer(curso, FUENTE)
    t = _desplazar(t, 16 * 7).replace("26-Otoño", "27-Invierno")
    escribir(curso, FUENTE, t)
    r = construir(str(curso))
    m = r["modelo"]
    assert m["curso"]["uea"]["trimestre"] == "27-Invierno"
    assert m["S"][1]["fecha"] == dt.date(2027, 1, 11)
    assert m["cal"]["periodo"]["descansos"][0]["fecha"] == dt.date(2027, 2, 1)
    portada = leer(curso, "docs/index.md")
    assert "27-Invierno" in portada and "26-Otoño" not in portada
    assert "lunes 8 de febrero" in portada  # sesión 8, entrega de P1 (19 oct + 16 semanas)
    assert "Calendario" in leer(curso, "mkdocs.yml")


# ----------------------------------------------------------------- errores

def test_fuente_inconsistente_no_escribe_nada(curso):
    antes = {rel: leer(curso, rel) for rel in ("docs/index.md", "mkdocs.yml")}
    cambiar_fuente(curso, "| Bitácora de uso de IAG | Elaboración de fichas (individual) | 10 % |",
                   "| Bitácora de uso de IAG | Elaboración de fichas (individual) | 15 % |")
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "suman 105 %" in str(e.value)
    for rel, texto in antes.items():
        assert leer(curso, rel) == texto


def test_fecha_equivocada_en_el_calendario(curso):
    cambiar_fuente(curso, "| 9 | Mié 21 oct |", "| 9 | Mié 22 oct |")
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "22 de octubre de 2026 es jueves" in str(e.value)


def test_fase_fuera_de_orden(curso):
    cambiar_fuente(curso, "| 10 | Lun 26 oct | P2 | Teórica |", "| 10 | Lun 26 oct | P2 | Reflexiva |")
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "P2" in str(e.value) and "secuencia de fases" in str(e.value)


def test_plantilla_con_dato_fijo_se_rechaza(curso):
    (curso / "fuente/plantillas").mkdir(parents=True, exist_ok=True)
    escribir(curso, "fuente/plantillas/extra.md.j2", "Escríbeme a jzr@xanum.uam.mx.\n")
    cfg = leer(curso, "curso.yml") + "\nsalidas:\n  docs/extra.md: extra.md.j2\n"
    escribir(curso, "curso.yml", cfg)
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "jzr@xanum.uam.mx" in str(e.value) and "texto fijo" in str(e.value)
    escribir(curso, "fuente/plantillas/extra.md.j2",
             "Escríbeme a {{ curso.uea.correo }}, sesión {{ S[3].num }}.\n")
    r = construir(str(curso))
    assert "docs/extra.md" in r["salidas"]


def test_numero_de_sesion_fijo_se_rechaza(curso):
    (curso / "fuente/plantillas").mkdir(parents=True, exist_ok=True)
    escribir(curso, "fuente/plantillas/extra.md.j2", "Nos vemos en la sesión 5.\n")
    escribir(curso, "curso.yml", leer(curso, "curso.yml") +
             "\nsalidas:\n  docs/extra.md: extra.md.j2\n")
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "sesión 5" in str(e.value)


def test_clave_desconocida_en_curso_yml(curso):
    escribir(curso, "curso.yml", leer(curso, "curso.yml") + "\nprocesar: true\n")
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "claves desconocidas" in str(e.value)


# ------------------------------------------------------------ otros modelos

def test_pagina_generica_de_proyecto(curso):
    t = leer(curso, "curso.yml").replace("proyecto:\n  pagina: seccion",
                                         "proyecto:\n  pagina: plantilla")
    escribir(curso, "curso.yml", t)
    r = construir(str(curso))
    p1 = leer(curso, "docs/proyectos/p1-el-problema-bien-planteado/index.md")
    assert "# P1 · El problema bien planteado" in p1
    assert "## Sesión 7 · De cálculo" in p1
    assert "Examen escrito 1 (P1)" in p1
    assert "docs/proyectos/p1-el-problema-bien-planteado/index.md" in r["salidas"]


def test_nuevo_curso(tmp_path):
    from programa_sitio.nuevo import crear
    destino = tmp_path / "nueva-uea"
    mensajes = crear(str(destino), os.path.join(AD, FUENTE),
                     "https://ejemplo.github.io/nueva-uea/", "https://github.com/ejemplo/nueva-uea")
    assert any("Sitio generado" in m for m in mensajes), mensajes
    for rel in ("curso.yml", "sitio.sh", ".githooks/pre-commit", ".github/workflows/pages.yml",
                "requirements.txt", "requirements.yml", ".gitignore", "mkdocs.yml",
                "docs/index.md", "docs/curso/calendario.md"):
        assert (destino / rel).exists(), rel
    assert os.access(destino / "sitio.sh", os.X_OK)
    assert "{MOTOR" not in (destino / "requirements.txt").read_text()
    assert construir(str(destino), "verificar")["distintos"] == []


@pytest.mark.skipif(not os.environ.get("PROGRAMA_SITIO_INFORMATICA"),
                    reason="indique PROGRAMA_SITIO_INFORMATICA=/ruta/al/repo/informatica")
def test_informatica_real(tmp_path):
    destino = tmp_path / "informatica"
    shutil.copytree(os.environ["PROGRAMA_SITIO_INFORMATICA"], destino,
                    ignore=shutil.ignore_patterns(".git", ".venv", ".ansible", "site"))
    r = construir(str(destino), "verificar")
    assert r["distintos"] == [] and r["huerfanos"] == []


# ------------------------------------------- hallazgos de la revisión independiente

def test_renumerar_secciones_no_cambia_lo_que_muestra_cada_pagina(curso):
    t = leer(curso, FUENTE)
    t = t.replace("### 5.7 Uso de asistentes", "### 5.7 Plataforma del curso\n\nTexto nuevo.\n\n"
                  "### 5.8 Uso de asistentes").replace("### 5.8 Correspondencia",
                                                       "### 5.9 Correspondencia")
    escribir(curso, FUENTE, t)
    construir(str(curso))
    ia = leer(curso, "docs/curso/protocolo-ia.md")
    assert "Uso de asistentes" in ia and "Plataforma del curso" not in ia


def test_dos_secciones_con_el_mismo_numero(curso):
    cambiar_fuente(curso, "### 5.7 Uso de asistentes",
                   "### 5.7 Plataforma del curso\n\nTexto.\n\n### 5.7 Uso de asistentes")
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "dos secciones con el número 5.7" in str(e.value)


def test_lo_comentado_no_es_contenido(curso):
    cambiar_fuente(curso, "### 5.7 Uso de asistentes",
                   "<!--\n### 5.7 Versión vieja del protocolo\n\nNo va.\n-->\n\n### 5.7 Uso de asistentes")
    construir(str(curso))
    ia = leer(curso, "docs/curso/protocolo-ia.md")
    assert "Versión vieja" not in ia and "Uso de asistentes" in ia
    assert ia.count("-->") == 1  # solo el del aviso de archivo generado


def test_fecha_de_la_evaluacion_sin_la_palabra_sesion(curso):
    cambiar_fuente(curso, "| 12 % | Sesión 8, 19 de octubre |", "| 12 % | Lunes 19 de octubre |")
    m = construir(str(curso))["modelo"]
    e1 = next(c for c in m["curso"]["evaluacion"]["componentes"] if c["id"] == "e1")
    assert e1["sesion"] == 8 and "en_globales" not in e1


def test_sesion_de_la_evaluacion_que_no_es_la_de_entrega(curso):
    cambiar_fuente(curso, "| 12 % | Sesión 8, 19 de octubre |", "| 12 % | Sesión 9, 21 de octubre |")
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "sesión 9" in str(e.value) and "sesión 8" in str(e.value)


def test_fecha_equivocada_en_la_tabla_del_proyecto(curso):
    cambiar_fuente(curso, "| 5 | Lun 5 oct | Reflexiva |", "| 5 | Mar 6 oct | Reflexiva |")
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "«Mar 6 oct» en la tabla del proyecto" in str(e.value)


def test_un_anio_entre_parentesis_no_parte_el_expediente(curso):
    cambiar_fuente(curso, "(5) Análisis de dominación.",
                   "(5) Análisis de dominación según Taha (2004) y Hillier (2002).")
    m = construir(str(curso))["modelo"]
    assert len(m["P"]["P1"]["expediente"]) == 8


def test_la_pagina_generica_es_markdown_valido(curso):
    import markdown
    t = leer(curso, "curso.yml").replace("proyecto:\n  pagina: seccion",
                                         "proyecto:\n  pagina: plantilla")
    escribir(curso, "curso.yml", t)
    construir(str(curso))
    html = markdown.markdown(leer(curso, "docs/proyectos/p1-el-problema-bien-planteado/index.md"),
                             extensions=["tables"])
    assert html.count("<li>") == 6 + 4  # seis criterios y cuatro reactivos
    assert "Examen escrito 1 (P1)" in html


def test_enlaces_por_referencia_en_una_pagina_de_seccion(curso):
    cambiar_fuente(curso, "Se aplican las reglas siguientes:",
                   "Se aplican las reglas siguientes (ver el [programa oficial][po] y `[x](y)`):")
    escribir(curso, FUENTE, leer(curso, FUENTE) +
             "\n[po]: ../assets/2211092pe.pdf\n")
    construir(str(curso))
    ia = leer(curso, "docs/curso/protocolo-ia.md")
    assert "[po]: ../assets/2211092pe.pdf" in ia and "`[x](y)`" in ia


def test_horario_contra_calendario(curso):
    cambiar_fuente(curso, "| Horario | Lunes y miércoles,", "| Horario | Martes y jueves,")
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "horario del grupo HE57" in str(e.value)


def test_encabezado_del_proyecto_contra_la_evaluacion(curso):
    cambiar_fuente(curso, "| Examen escrito 1 (P1) | Evaluación periódica escrita individual | 12 % |",
                   "| Examen escrito 1 (P1) | Evaluación periódica escrita individual | 14 % |")
    cambiar_fuente(curso, "| 10 % | Cierre de cada proyecto |", "| 8 % | Cierre de cada proyecto |")
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "P1: su encabezado dice «Ponderación" in str(e.value)


def test_sintesis_con_guion(curso):
    cambiar_fuente(curso, "- P2 incorpora", "- P2 — incorpora")
    m = construir(str(curso))["modelo"]
    assert m["P"]["P2"]["sintesis"].startswith("incorpora")


def test_encabezado_de_proyecto_mal_escrito(curso):
    cambiar_fuente(curso, "### 6.2 Proyecto P2 · El precio", "### 6.2 Proyecto 2 · El precio")
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "no tiene la forma «Proyecto PN · Nombre»" in str(e.value)


def test_columna_agregada_al_calendario(curso):
    t = leer(curso, FUENTE)
    t = re.sub(r"^(\| Núm\. \| Fecha \|)", r"\1 Semana |", t, flags=re.M)
    t = re.sub(r"^(\|------------\|------------\|)(?=------------\|------------\|------------\|------------\|$)",
               r"\1------------|", t, flags=re.M)
    lineas = []
    en_tabla = False
    for l in t.split("\n"):
        if l.startswith("| Núm. |"):
            en_tabla = True
        elif en_tabla and l.startswith("|") and not l.startswith("|---"):
            partes = l.split("|")
            l = "|".join(partes[:3] + [" s "] + partes[3:])
        elif en_tabla and not l.startswith("|"):
            en_tabla = False
        lineas.append(l)
    escribir(curso, FUENTE, "\n".join(lineas))
    r = construir(str(curso))
    assert r["modelo"]["S"][8]["fases"] == {"P1": "Pragmática", "P2": "Activista"}


def test_descanso_con_otra_redaccion(curso):
    t = leer(curso, FUENTE).replace("| — | Lun 12 oct | — | — | Descanso obligatorio | — |",
                                    "| — | Lun 12 oct | — | — | Día de descanso obligatorio | — |")
    escribir(curso, FUENTE, t)
    m = construir(str(curso))["modelo"]
    assert m["cal"]["periodo"]["descansos"][0]["fecha"] == dt.date(2026, 10, 12)


def test_auditoria_fecha_sin_anio_y_lista_de_sesiones(curso):
    (curso / "fuente/plantillas").mkdir(parents=True, exist_ok=True)
    escribir(curso, "curso.yml", leer(curso, "curso.yml") +
             "\nsalidas:\n  docs/extra.md: extra.md.j2\n")
    escribir(curso, "fuente/plantillas/extra.md.j2", "Entrega el 19 de octubre.\n")
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "19 de octubre" in str(e.value)
    escribir(curso, "fuente/plantillas/extra.md.j2", "Repaso en las sesiones 18 y 19.\n")
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "sesiones 18 y 19" in str(e.value)


def test_pagina_a_mano_con_otro_correo(curso):
    (curso / "docs/recursos").mkdir(parents=True, exist_ok=True)
    escribir(curso, "docs/recursos/nota.md", "Escribir a viejo@xanum.uam.mx\n")
    r = construir(str(curso))
    assert any("viejo@xanum.uam.mx" in a for a in r["avisos"])


def test_huerfanos_de_otros_formatos(curso):
    (curso / "fuente/plantillas").mkdir(parents=True, exist_ok=True)
    escribir(curso, "fuente/plantillas/datos.yml.j2", "clave: {{ curso.uea.clave }}\n")
    base = leer(curso, "curso.yml")
    escribir(curso, "curso.yml", base + "\nsalidas:\n  docs/datos.yml: datos.yml.j2\n")
    construir(str(curso))
    assert (curso / "docs/datos.yml").exists()
    escribir(curso, "curso.yml", base)
    r = construir(str(curso))
    assert "docs/datos.yml" in r["huerfanos"] and not (curso / "docs/datos.yml").exists()


def test_gancho_no_mezcla_fuente_sin_agregar(curso):
    def git(*a):
        return subprocess.run(["git", *a], cwd=curso, capture_output=True, text=True)
    git("init", "-q", "-b", "main")
    git("config", "user.email", "prueba@example.com")
    git("config", "user.name", "Prueba")
    shutil.copytree(os.path.join(os.path.dirname(__file__), "..", "programa_sitio",
                                 "curso_base", ".githooks"), curso / ".githooks")
    git("add", "-A")
    assert git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "inicio").returncode == 0
    git("config", "core.hooksPath", ".githooks")
    cambiar_fuente(curso, "| Correo de contacto | jzr@xanum.uam.mx |",
                   "| Correo de contacto | otro@xanum.uam.mx |")
    escribir(curso, "notas.txt", "x\n")
    git("add", "notas.txt")
    r = git("commit", "-qm", "notas")
    assert r.returncode != 0 and "no están en el commit" in r.stderr
    git("add", FUENTE)
    r = git("commit", "-qm", "correo")
    assert r.returncode == 0, r.stderr
    assert "otro@xanum.uam.mx" in git("show", "HEAD:docs/index.md").stdout
    assert git("status", "--porcelain").stdout.strip() == ""


def test_nuevo_avisa_si_la_fuente_dice_otra_direccion(tmp_path):
    from programa_sitio.nuevo import crear
    m = crear(str(tmp_path / "x"), os.path.join(AD, FUENTE),
              "https://otra.github.io/x/", "https://github.com/otra/x")
    assert any("manda la fuente" in x for x in m)
