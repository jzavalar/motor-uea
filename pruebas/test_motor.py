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


CALENDARIO = os.path.join(os.path.dirname(__file__), "..", "programa_sitio", "calendarios",
                          "2026-2027.json")


def _calendario_real():
    import json
    return json.load(open(CALENDARIO, encoding="utf-8"))


def _guardar_calendario(curso, datos, nombre="cal.json"):
    import json
    (curso / nombre).write_text(json.dumps(datos, ensure_ascii=False, indent=1))
    escribir(curso, "curso.yml", leer(curso, "curso.yml") +
             f"\ncalendario: {{archivo: {nombre}}}\n")


def _mover_fechas(obj, dias):
    import json
    fecha = re.compile(r'"(\d{4}-\d{2}-\d{2})"')
    return json.loads(fecha.sub(lambda m: '"' + (dt.date.fromisoformat(m.group(1)) +
                                                 dt.timedelta(days=dias)).isoformat() + '"',
                                json.dumps(obj, ensure_ascii=False)))


def _calendario_desplazado(curso, dias, clave="27-I"):
    """Un calendario escolar hipotético: el del trimestre 26-O corrido `dias` días (con sus
    periodos intertrimestrales, vacaciones y descansos), recortado a una ventana que va del
    inicio de la cobertura al último día de su recuperación. (El 27-I real tiene otro número
    de sesiones y otros descansos; aquí se prueba la propagación.)"""
    real = _mover_fechas(_calendario_real(), dias)
    t26 = next(x for x in real["trimestres"] if x["clave"] == "26-O")
    ini = real["cobertura"]["inicio"]
    fin = t26["recuperacion"]["registro_de_calificaciones"][-1]

    def recortar(periodos):
        out = []
        for p in periodos:
            if p["fin"] >= ini and p["inicio"] <= fin:
                out.append(dict(p, inicio=max(p["inicio"], ini), fin=min(p["fin"], fin)))
        return out
    nuevo = dict(real, trimestres=[dict(t26, clave=clave, nombre="27-Invierno")],
                 cobertura={"inicio": ini, "fin": fin},
                 descansos=[x for x in real["descansos"] if ini <= x["fecha"] <= fin],
                 periodos_intertrimestrales=recortar(real["periodos_intertrimestrales"]),
                 vacaciones=recortar(real["vacaciones"]))
    _guardar_calendario(curso, nuevo)


def test_cambio_de_trimestre(curso):
    _calendario_desplazado(curso, 16 * 7)
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
    assert "el horario dice martes y jueves, pero las sesiones de §7 son lunes y miércoles" \
        in str(e.value)


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
    # el gancho busca programa-sitio en .venv/bin o en el PATH: se le da el del entorno
    # con que corren las pruebas, aunque no esté activado
    entorno = dict(os.environ, PATH=os.path.dirname(sys.executable) + os.pathsep +
                   os.environ.get("PATH", ""))

    def git(*a):
        return subprocess.run(["git", *a], cwd=curso, capture_output=True, text=True,
                              env=entorno)
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


# ------------------------------------------------------------ calendario escolar

def test_trimestre_contra_el_calendario_escolar(curso):
    cambiar_fuente(curso, "| Evaluaciones globales | 7 al 11 de diciembre de 2026 |",
                   "| Evaluaciones globales | 8 al 12 de diciembre de 2026 |")
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "[calendario escolar]" in str(e.value)
    assert "evaluaciones globales son del 8 de diciembre" in str(e.value)


def test_trimestre_que_el_motor_no_conoce(curso):
    cambiar_fuente(curso, "Trimestre 26-Otoño · Grupo HE57", "Trimestre 28-Otoño · Grupo HE57")
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "no tiene el trimestre 28-O" in str(e.value)


def test_descanso_oficial_que_falta_en_la_tabla(curso):
    real = _calendario_real()
    real["descansos"].append({"fecha": "2026-10-21"})   # un miércoles con sesión (la 9)
    real["descansos"].sort(key=lambda x: x["fecha"])
    _guardar_calendario(curso, real)
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "la sesión 9 cae el 21 de octubre de 2026, que es día de descanso" in str(e.value)


def test_calendario_disponible_en_las_plantillas(curso):
    m = construir(str(curso))["modelo"]
    rec = m["cal"]["oficial"]["recuperacion"]
    assert list(rec["evaluaciones"]) == [dt.date(2027, 1, 6), dt.date(2027, 1, 7),
                                         dt.date(2027, 1, 8)]
    assert rec["evaluaciones"].texto() == "del 6 al 8 de enero de 2027"
    assert len(m["cal"]["oficial"]["semanas"]) == 12
    portada = leer(curso, "docs/index.md")
    assert "| Evaluación de recuperación | — | Del 6 al 8 de enero de 2027 (inscripción: " \
           "4 de enero de 2027) |" in portada


# ------------------------------------------------- formato del calendario escolar

def _errores_de_calendario(datos, tmp_path):
    import json
    from programa_sitio import calendario_escolar as CE
    ruta = tmp_path / "c.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False))
    try:
        CE.leer(str(ruta))
    except CE.ErrorDeCalendario as e:
        return str(e)
    return ""


def _trimestre(datos, clave):
    return next(x for x in datos["trimestres"] if x["clave"] == clave)


def test_calendario_real_valido_y_vista_con_la_simbologia_oficial():
    from programa_sitio import calendario_escolar as CE
    cal = CE.leer(CALENDARIO)
    assert cal["avisos"] == []
    assert sorted(cal["trimestres"]) == ["26-O", "26-P", "27-I", "27-O", "27-P"]
    v = CE.vista(cal)
    # los renglones tal como están en la imagen oficial
    assert "| 4ⁱΦ | 5ⁱ• | 6ⁱ•® | 7ⁱ•®▲ | 8ⁱ•®▲ | 9 | 10 | IER/IR/ER/RCR |" in v
    assert "| 5 | 6 | 7< | 8* | 9* | 10 | 11 | 11 bis/EG |" in v
    assert "| 14ⁱ | **15** | **16** | 17> | 18 | 19 | 20 | 1 |" in v
    assert "| 30 |   |   |   |   |   |   | 11 bis |" in v
    # registro de calificaciones posterior al trimestre (verde en el original)
    assert "| 14ᶜ△ | 15ᶜ△ | 16ᶜ△ | 17ᶜ△ | 18ᶜ△ | 19 | 20 | RCA |" in v
    # vacaciones de fin de año y de verano (cuatro semanas)
    assert "| 21ᵛ | 22ᵛ | 23ᵛ | 24ᵛ | **25** | 26 | 27 |  |" in v
    assert "| Vacaciones | 21 al 31 de diciembre de 2026 (fin de año); 2 al 27 de agosto de 2027" in v
    # semanas recortadas: la primera empieza en jueves; la 11 bis de 27-I termina en miércoles
    assert "1: jue 17 a vie 18 sep" in v and "11 bis: lun 5 a mié 7 abr" in v


def test_dias_explicitos_y_su_texto():
    from programa_sitio.calendario_escolar import Dias
    d = dt.date
    assert Dias([d(2027, 9, 2), d(2027, 9, 3), d(2027, 9, 6)]).texto() == \
        "del 2 al 6 de septiembre de 2027"                  # solo salta el fin de semana
    assert Dias([d(2026, 11, 18), d(2026, 11, 20)]).texto() == "18 y 20 de noviembre de 2026"
    assert Dias([d(2027, 1, 4)]).texto() == "4 de enero de 2027"


def test_calendario_con_dia_inhabil_o_de_descanso(tmp_path):
    datos = _calendario_real()
    t = _trimestre(datos, "26-O")
    t["evaluaciones_globales"] = ["2026-12-07", "2026-12-12"]        # sábado
    t["recuperacion"]["evaluaciones"] = ["2027-01-01", "2027-01-06"]  # descanso
    err = _errores_de_calendario(datos, tmp_path)
    assert "hay evaluación global el sábado 12 de diciembre de 2026, que es sábado" in err
    assert "hay evaluación de recuperación el 1 de enero de 2027, que es día de descanso" in err


def test_calendario_con_fechas_desordenadas_o_semanas_mal(tmp_path):
    datos = _calendario_real()
    t = _trimestre(datos, "27-I")
    t["inscripcion_reinscripcion"] = ["2027-01-06", "2027-01-05"]
    t["semanas"][3]["inicio"] = "2027-02-09"                 # la semana 4 empieza el lunes 8
    t["semanas"][6].update(inicio="2027-03-08", fin="2027-03-12")   # salta la del 1 de marzo
    t["semanas"][0]["inicio"] = "2027-01-19"
    err = _errores_de_calendario(datos, tmp_path)
    assert "inscripcion_reinscripcion: las fechas no están en orden ascendente" in err
    assert "(semana 4): dice mar 9 a vie 12 feb, pero sus días de clase van del lunes 8 de " \
           "febrero al viernes 12 de febrero" in err
    assert "(semana 7): entre la semana 6 y esta queda la del 1 de marzo de 2027, sin " \
           "número; solo puede faltar número en vacaciones" in err
    assert "la primera semana empieza el 19 de enero de 2027, pero las clases empiezan el 18 " \
           "de enero de 2027" in err


def test_calendario_con_campo_mal_escrito_o_faltante(tmp_path):
    datos = _calendario_real()
    t = _trimestre(datos, "27-P")
    t["evaluaciones_global"] = t.pop("evaluaciones_globales")
    del t["clases"]["fin"]
    err = _errores_de_calendario(datos, tmp_path)
    assert "el campo «evaluaciones_global» no existe en el formato" in err
    assert "falta el campo «evaluaciones_globales»" in err
    assert "trimestres[3].clases: falta el campo «fin»" in err


def test_calendario_con_sucesos_fuera_de_orden(tmp_path):
    datos = _calendario_real()
    t = _trimestre(datos, "26-O")
    t["evaluaciones_globales"] = ["2026-12-03", "2026-12-04"]
    t["clave"], t["nombre"] = "26-O", "26-Invierno"
    err = _errores_de_calendario(datos, tmp_path)
    assert "deben empezar después de la terminación de clases" in err
    assert "el nombre «26-Invierno» no corresponde a la clave 26-O" in err


def test_trimestre_solo_parcial(curso):
    cambiar_fuente(curso, "Trimestre 26-Otoño · Grupo HE57", "Trimestre 27-Otoño · Grupo HE57")
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "solo muestra algunos días del trimestre 27-O" in str(e.value)


def test_calendarios_vecinos_que_no_coinciden(tmp_path):
    from programa_sitio import calendario_escolar as CE
    import json
    # un 2027-2028 hipotético y válido: el 2026-2027 corrido 53 semanas, con otras claves;
    # su 27-O empieza el 23 de septiembre y el 2026-2027 dice que el 20
    sig = _mover_fechas(_calendario_real(), 371)
    nombres = {"26-P": ("27-P", "27-Primavera"), "26-O": ("27-O", "27-Otoño"),
               "27-I": ("28-I", "28-Invierno"), "27-P": ("28-P", "28-Primavera"),
               "27-O": ("28-O", "28-Otoño")}
    for x in sig["trimestres"]:
        x["clave"], x["nombre"] = nombres[x["clave"]]
    sig["documento"].update(nombre="Calendario Escolar 2027-2028", anio_escolar="2027-2028",
                            aprobacion={"organo": "Colegio Académico", "sesion": 600,
                                        "fecha": "2027-02-25"})
    (tmp_path / "2027-2028.json").write_text(json.dumps(sig, ensure_ascii=False))
    completos, parciales, errores, avisos = CE.cargar_todos(
        [CALENDARIO, str(tmp_path / "2027-2028.json")])
    assert not errores, errores
    assert "27-O" in completos and completos["27-O"]["conflictos"]
    assert any("CONFLICTO en 27-O, inicio de clases: Calendario Escolar 2026-2027 (sesión 576): "
               "20 de septiembre de 2027; Calendario Escolar 2027-2028 (sesión 600): 23 de "
               "septiembre de 2027" in a for a in avisos), avisos
    # y el mismo día clasificado distinto por los dos documentos
    assert any(a.startswith("CONFLICTO: el 20 de septiembre de 2027 es trimestre según el "
                            "Calendario Escolar 2026-2027") for a in avisos), avisos


# ------------------------------------- historia real: 2022-2023 a 2026-2027 y modificaciones

def test_los_cinco_calendarios_reales_y_su_unico_conflicto():
    from programa_sitio import calendario_escolar as CE
    completos, parciales, errores, avisos = CE.cargar_todos(CE.del_motor())
    assert errores == []
    assert sorted(completos) == ["22-O", "23-I", "23-O", "23-P", "24-I", "24-O", "24-P",
                                 "25-I", "25-O", "25-P", "26-I", "26-O", "26-P", "27-I", "27-P"]
    en_conflicto = sorted(k for k, T in completos.items() if T["conflictos"])
    # el calendario 2023-2024 (s521) y el 2024-2025 (s540) no coinciden sobre 24-P y 24-O:
    # hubo un calendario modificado que no está transcrito
    assert en_conflicto == ["24-O", "24-P"]
    # lo que muestran dos documentos vecinos se combina: la inscripción de 25-O está en el
    # calendario 2024-2025 y el resto del trimestre en el 2025-2026
    T = completos["25-O"]
    assert T["inscripcion"].texto() == "del 18 al 29 de septiembre de 2025"
    assert T["_calendario"] == "Calendario Escolar 2025-2026"
    # recesos y semanas sin número (22-O, 24-O)
    assert completos["22-O"]["vacaciones"][0][:2] == (dt.date(2022, 12, 26), dt.date(2023, 1, 6))
    assert [s["etiqueta"] for s in completos["24-O"]["semanas"]][-2:] == ["10", "11"]


def test_trimestre_en_conflicto_no_se_usa():
    from programa_sitio import calendario as K
    clave, T, errores = K.trimestre({"calendario": {"trimestre": "24-P"}, "_raiz": "."}, {})
    assert T is None
    assert "los calendarios vigentes no coinciden sobre el trimestre 24-P" in errores[-1]
    assert "evaluaciones globales: Calendario Escolar 2023-2024 (sesión 521) dice del 19 al 25 " \
           "de julio de 2024 / Calendario Escolar 2024-2025 (sesión 540) dice del 1 al 4 de " \
           "octubre de 2024" in errores[-1]


def _modificado_2023_2024():
    """Un calendario modificado hipotético (caso de prueba, no real): 24-P recorrido por una
    suspensión, como lo muestra el calendario 2024-2025."""
    fechas = lambda a, m, *ds: [f"{a}-{m:02d}-{d:02d}" for d in ds]  # noqa: E731
    lunes = fechas(2024, 7, 15, 22, 29) + fechas(2024, 8, 5, 12, 19, 26) + \
        fechas(2024, 9, 2, 9, 16, 23)
    doc = _calendario_real()
    doc["documento"].update(nombre="Calendario Escolar 2023-2024 (modificado)",
                            anio_escolar="2023-2024",
                            aprobacion={"organo": "Colegio Académico", "sesion": 999,
                                        "fecha": "2024-06-28"},
                            modifica=[{"anio_escolar": "2023-2024", "sesion": 521}],
                            motivo="caso de prueba")
    doc["cobertura"] = {"inicio": "2024-07-01", "fin": "2024-10-31"}
    doc["descansos"] = [{"fecha": f} for f in fechas(2024, 9, 15, 16) + fechas(2024, 10, 12)]
    doc["periodos_intertrimestrales"] = [{"inicio": "2024-07-01", "fin": "2024-07-12"},
                                         {"inicio": "2024-10-07", "fin": "2024-10-18"}]
    doc["vacaciones"] = []
    doc["trimestres"] = [
        {"clave": "24-P", "nombre": "24-Primavera",
         "periodo": {"inicio": "2024-07-15", "fin": "2024-10-04"},
         "clases": {"inicio": "2024-07-15", "fin": "2024-09-27"},
         "semanas": [{"orden": i + 1, "etiqueta": str(i + 1), "inicio": x,
                      "fin": (dt.date.fromisoformat(x) + dt.timedelta(days=4)).isoformat()}
                     for i, x in enumerate(lunes)],
         "evaluaciones_globales": fechas(2024, 10, 1, 2, 3, 4),
         "registro_de_calificaciones": fechas(2024, 10, 1, 2, 3, 4),
         "recuperacion": {"inscripcion": fechas(2024, 10, 7),
                          "evaluaciones": fechas(2024, 10, 9, 10, 11),
                          "registro_de_calificaciones": fechas(2024, 10, 10, 11, 14)}},
        {"clave": "24-O", "nombre": "24-Otoño", "parcial": True,
         "tramo_visible": {"inicio": "2024-10-21", "fin": "2024-10-31"},
         "clases": {"inicio": "2024-10-21"},
         "semanas": [{"orden": 1, "etiqueta": "1", "inicio": "2024-10-21", "fin": "2024-10-25"},
                     {"orden": 2, "etiqueta": "2", "inicio": "2024-10-28", "fin": "2024-10-31"}],
         "inscripcion_reinscripcion": fechas(2024, 10, 8, 9, 10, 11, 14, 15, 16)}]
    return doc


def test_un_calendario_modificado_resuelve_el_conflicto(tmp_path):
    import json
    from programa_sitio import calendario_escolar as CE
    ruta = tmp_path / "2023-2024-s999.json"
    ruta.write_text(json.dumps(_modificado_2023_2024(), ensure_ascii=False))
    completos, _, errores, avisos = CE.cargar_todos(CE.del_motor() + [str(ruta)])
    assert errores == [], errores
    assert not [a for a in avisos if "CONFLICTO" in a], avisos
    T = completos["24-P"]
    assert T["globales"].texto() == "del 1 al 4 de octubre de 2024"
    assert T["_calendario"] == "Calendario Escolar 2023-2024 (modificado)"
    assert completos["24-I"]["_calendario"] == "Calendario Escolar 2023-2024"   # sigue vigente
    assert completos["24-O"]["clases"][0] == dt.date(2024, 10, 21)


def test_semanas_sin_numero_solo_en_vacaciones(tmp_path):
    import json
    from programa_sitio import calendario_escolar as CE
    datos = json.load(open(os.path.join(CE.CARPETA, "2022-2023.json"), encoding="utf-8"))
    del datos["vacaciones"][0]                   # las de fin de año, dentro de 22-O
    err = _errores_de_calendario(datos, tmp_path)
    assert "entre la semana 10 y esta queda la del 26 de diciembre de 2022, sin número" in err
    assert "queda la del 2 de enero de 2023" in err


def test_cada_dia_habil_en_un_solo_periodo(tmp_path):
    import json
    from programa_sitio import calendario_escolar as CE
    datos = json.load(open(os.path.join(CE.CARPETA, "2024-2025.json"), encoding="utf-8"))
    datos["periodos_intertrimestrales"][1] = {"inicio": "2025-01-27", "fin": "2025-02-03"}
    datos["vacaciones"][1] = {"inicio": "2025-08-11", "fin": "2025-09-12"}
    err = _errores_de_calendario(datos, tmp_path)
    assert "días hábiles sin periodo (4 al 7 de febrero de 2025)" in err
    assert "el 11 de agosto de 2025 está a la vez en trimestre y vacaciones" in err or \
        "hay evaluaciones globales fuera del trimestre" in err
    # la inscripción del 4 y el 6 de febrero ya no cae en un periodo intertrimestral
    assert "25-I: la inscripción/reinscripción cae fuera de un periodo intertrimestral " \
           "(4 y 6 de febrero de 2025)" in err


def test_vacaciones_de_verano_de_cuatro_semanas():
    from programa_sitio import calendario_escolar as CE
    for a in CE.del_motor():
        doc = CE.leer(a)
        assert not [x for x in doc["avisos"] if "vacaciones de verano" in x], a
    doc = CE.leer(os.path.join(CE.CARPETA, "2024-2025.json"))
    a, b, nota = doc["vacaciones"][1]
    assert (a, b) == (dt.date(2025, 8, 18), dt.date(2025, 9, 12)) and "cuatro semanas" in nota
    assert [p[:2] for p in doc["intertrimestrales"]] == [
        (dt.date(2024, 10, 7), dt.date(2024, 10, 18)), (dt.date(2025, 1, 27), dt.date(2025, 2, 7)),
        (dt.date(2025, 5, 12), dt.date(2025, 5, 23)), (dt.date(2025, 9, 17), dt.date(2025, 9, 30))]


def test_vista_con_la_simbologia_de_cada_documento():
    from programa_sitio import calendario_escolar as CE
    doc = CE.leer(os.path.join(CE.CARPETA, "2022-2023.json"))
    v = CE.vista(doc)
    assert "| 16*△ | 17*△ | 18*△ | 19*△ | 20*△ | 21 | 22 | EG/EA |" in v
    assert "| 23ⁱΦ | 24ⁱ• | 25ⁱ•® | 26ⁱ•®▲ | 27ⁱ•®▲ | 28 | 29 | IER/IR/ER/EAR |" in v
    assert "| 26ᵛ | 27ᵛ | 28ᵛ | 29ᵛ | 30ᵛ | 31 |   |  |" in v
    assert "artículo 21, RESUAM" in v
    assert "| Vacaciones dentro del trimestre | 26 de diciembre de 2022 al 6 de enero de 2023 |" in v
    h = CE.vista_html(doc)
    assert "<td class='intertrimestral'>23Φ</td>" in h
    assert "<td class='vacaciones'>26</td>" in h and "<td class='limite'>17&gt;</td>" in h


def test_plantilla_de_calendario_tiene_la_forma_del_esquema(tmp_path):
    import json
    from programa_sitio import calendario_escolar as CE
    err = _errores_de_calendario(json.loads(CE.plantilla("2027-2028")), tmp_path)
    assert err and "no existe en el formato" not in err and "falta el campo" not in err


# ------------------------------------------------------------- programa oficial

def test_contraste_con_el_programa_oficial(curso):
    r = construir(str(curso))
    assert r["modelo"]["oficial"]["datos"]["clave"] == "221192"
    cambiar_fuente(curso, "| Créditos | 8 |", "| Créditos | 9 |")
    cambiar_fuente(curso, "- «Buscar y ponderar información relevante en fuentes diversas.»",
                   "- «Buscar y valorar información relevante en fuentes diversas.»")
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    t = str(e.value)
    assert "[programa oficial]" in t and "créditos: el programa analítico dice «9»" in t
    assert "Buscar y ponderar" in t


def test_cita_del_programa_oficial_alterada(curso):
    cambiar_fuente(curso, "«Al menos dos evaluaciones periódicas escritas aplicadas",
                   "«Al menos tres evaluaciones periódicas escritas aplicadas")
    with pytest.raises(ErrorDeFuente) as e:
        construir(str(curso))
    assert "se atribuye al programa oficial" in str(e.value)


def test_sin_programa_oficial_solo_avisa(curso):
    os.remove(curso / "docs/curso/programa-oficial.md")
    r = construir(str(curso))
    assert any("no existe el programa oficial" in a for a in r["avisos"])


# ------------------------------------------------------------------ revisión

def test_informe_de_revision_listo(curso):
    from programa_sitio.revision import informe
    texto, listo = informe(str(curso))
    assert listo and "está listo" in texto
    assert "Fechas oficiales del trimestre 26-O" in texto
    assert "del 6 al 8 de enero de 2027" in texto   # recuperación


def test_informe_de_revision_con_problemas(curso):
    from programa_sitio.revision import informe
    cambiar_fuente(curso, "| Créditos | 8 |", "| Créditos | 9 |")
    cambiar_fuente(curso, "| Evaluaciones globales | 7 al 11 de diciembre de 2026 |",
                   "| Evaluaciones globales | 8 al 12 de diciembre de 2026 |")
    texto, listo = informe(str(curso))
    assert not listo
    assert "### Contra el calendario escolar" in texto
    assert "### Contra el programa de estudios oficial" in texto
    assert "## Instrucciones para el asistente de IA" in texto
    # no se escribió nada del sitio
    assert "8 al 12" not in leer(curso, "docs/index.md")


def test_orden_revisar(curso):
    r = subprocess.run([sys.executable, "-m", "programa_sitio.cli", "revisar", "--curso",
                        str(curso)], capture_output=True, text=True)
    assert r.returncode == 0 and (curso / "revision.md").exists()
