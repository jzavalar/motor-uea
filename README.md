# programa-sitio

**Del programa analítico de una UEA, en Markdown, a su sitio web.** Una sola fuente —el
programa analítico— se publica tal cual y, además, se convierte en las páginas del
sitio, el menú y el README del repositorio. Todo lo que el sitio repite de la fuente se
genera; nada se copia a mano, así que un cambio en la fuente llega siempre a todas partes.

Sirve para cualquier UEA cuyo programa analítico tenga la estructura común que se
describe abajo (identificación, fases, proyectos, calendario, evaluación, lecturas), y
para cada trimestre nuevo de la misma UEA. Está pensado para Fedora 44 o posterior, con
Ansible, MkDocs Material y GitHub Pages.

### Los tres insumos

| Insumo | Dónde vive | Quién lo cambia |
|---|---|---|
| **Programa de estudios oficial** de la UEA | `docs/curso/programa-oficial.md` en el repositorio del curso (el PDF de la UAM convertido una vez a Markdown) | Nadie: es la referencia |
| **Calendario escolar** vigente | `programa_sitio/calendarios/AAAA-AAAA.json`, en este motor, un archivo por año escolar, con un formato validado por esquema ([`docs/formato-calendario-escolar.md`](docs/formato-calendario-escolar.md)) | Se actualiza cada año, o cuando el Colegio Académico lo modifique (ver *Calendario escolar*) |
| **Programa analítico** | `docs/curso/programa-analitico.md` en el repositorio del curso | El profesor, con su asistente de IA |

El programa analítico se redacta a partir de los otros dos, por iteraciones: el motor
lo contrasta con ambos (`./sitio.sh revisar`) y entrega un informe de discrepancias para
el asistente. Cuando el informe dice «listo», ese programa es la **fuente única** del sitio.
Para redactarlo: [`docs/guia-redaccion-programa-analitico.md`](docs/guia-redaccion-programa-analitico.md)
(se le entrega al asistente) y [`docs/plantilla-programa-analitico.md`](docs/plantilla-programa-analitico.md)
(el esqueleto vacío, con la forma que lee el motor).

Este repositorio contiene:

| Carpeta | Qué es |
|---|---|
| `programa_sitio/` | El motor (paquete de Python): analiza la fuente, valida, genera y audita. Incluye un complemento de MkDocs y la orden `programa-sitio`. |
| `programa_sitio/calendarios/` | El calendario escolar de cada año escolar, en JSON, y su esquema (`calendario-escolar.schema.json`). |
| `programa_sitio/plantillas/` | Las páginas predeterminadas: portada, menú (`mkdocs.yml`), README y página genérica de proyecto. |
| `programa_sitio/curso_base/` | Lo que recibe cada repositorio de curso: `sitio.sh`, el gancho pre-commit, la acción de GitHub y las versiones fijadas del motor. |
| `ansible/` | La colección de Ansible `jzavalar.programa_sitio`: preparar, construir, publicar y crear un curso nuevo. |
| `docs/` | La guía de redacción para el asistente de IA, la plantilla del programa analítico y el formato del calendario escolar. |
| `pruebas/` | Pruebas automáticas, con un caso completo (Análisis de Decisiones). |

---

## Uso diario, en el repositorio de una UEA

```bash
./sitio.sh preparar     # una vez por equipo: dnf, entorno virtual con el motor, gancho de git
./sitio.sh revisar      # contrasta el programa con el calendario y el programa oficial → revision.md
./sitio.sh servir       # vista previa en http://127.0.0.1:8000; se regenera al guardar la fuente
./sitio.sh construir    # regenera, valida y compila el sitio (sin tocar git)
./sitio.sh verificar    # solo comprueba; no escribe nada
./sitio.sh auditar      # muestra los avisos de la auditoría de duplicación
./sitio.sh publicar     # commit y push a main; GitHub Actions publica el sitio
./sitio.sh publicar --pr -m "Ajusta las fechas de P2"   # rama y Pull Request en su lugar
```

Se edita **solo** `docs/curso/programa-analitico.md` (y, si hace falta, `curso.yml`, los
datos del sitio o las plantillas propias). Cada archivo generado lo dice en su primera
línea: `ARCHIVO GENERADO por programa-sitio … No lo edite`.

### Redactar con el asistente de IA: `revisar`

`./sitio.sh revisar` escribe `revision.md` (no se sube a git) con: los insumos usados,
si el programa está listo, cada problema agrupado por su origen (calendario escolar,
programa oficial, estructura interna), los avisos, instrucciones para el asistente y la
tabla de fechas oficiales del trimestre. Se le entrega ese archivo al asistente, que
corrige solo lo señalado; se repite hasta que diga «El programa analítico está listo».
Termina con código 1 mientras no lo esté.

### Cuándo se propaga un cambio

1. **Al guardar**, con `./sitio.sh servir` abierto. Si la fuente queda a medio editar,
   la terminal dice qué falta y la vista previa conserva la última versión buena.
2. **Antes de cada commit.** El gancho `.githooks/pre-commit` regenera y agrega al commit
   las páginas que cambiaron —y quita las que ya no corresponden a nada, como la carpeta
   de un proyecto renombrado—. Si la fuente no es consistente, o si tiene cambios que no
   se agregaron a ese commit (las páginas no corresponderían a la fuente confirmada),
   detiene el commit y dice por qué.
3. **Al publicar.** `./sitio.sh publicar` regenera, valida, compila con
   `mkdocs build --strict` y sube.
4. **En GitHub Actions**, en cada push a `main`: si el repositorio tuviera páginas
   desactualizadas, publica de todos modos lo que resulta de la fuente y deja un aviso.

---

## Crear el sitio de una UEA nueva

Con el programa analítico en Markdown a la mano:

```bash
sudo dnf install ansible-core gh && gh auth login        # una vez
ansible-galaxy collection install \
    "git+https://github.com/jzavalar/motor-uea.git#/ansible/,v1.0.0"
ansible-playbook jzavalar.programa_sitio.nuevo \
    -e destino=~/cursos/mi-uea \
    -e fuente=~/Documentos/programa-analitico.md \
    -e nombre_repo=mi-uea \
    -e crear_en_github=true          # opcional: crea el repositorio y activa Pages
```

El playbook copia la fuente, escribe un `curso.yml` con lo que deduce de ella (qué
secciones volver páginas, la escala de la rúbrica), agrega `sitio.sh`, el gancho y la
acción de GitHub, genera el sitio y hace el primer commit. Si la fuente todavía no
cumple la estructura común, crea el repositorio igual y lista, uno por uno, los
problemas por resolver. Sin Ansible: `programa-sitio nuevo DIR --fuente … --sitio …
--repositorio …`.

---

## El algoritmo

Cada generación —la ordene quien la ordene: `sitio.sh`, el gancho, la vista previa o
GitHub Actions— sigue los mismos pasos, y **si cualquiera falla no se escribe nada**:

1. **Configuración.** Se combina `curso.yml` con la configuración predeterminada
   (`programa_sitio/predeterminado.yml`): lo que el curso no dice, se toma de ahí.
2. **Lectura estructural.** La fuente se descompone en secciones numeradas, tablas (por
   los nombres de sus columnas), listas, párrafos con etiqueta en negritas
   (`**Propósito.** …`) y bloques de datos ocultos (`<!-- fuente-datos: nombre … -->`).
   Todo lo que esté dentro de un comentario HTML se ignora. Nada se busca por posición
   en el texto; todo, por su forma.
3. **Modelo.** De esa estructura se extrae lo común a todo programa con aprendizaje
   basado en proyectos (ver abajo) y se aplican las reglas propias del curso
   (`extraer`, `tablas`, `listas` de `curso.yml`). Se agregan los datos que solo usa el
   sitio (`datos`), sin pisar nunca lo que dice la fuente.
4. **Contraste con el calendario escolar.** El trimestre del encabezado
   («26-Otoño» → `26-O`) elige el trimestre del calendario. Trimestre lectivo y
   evaluaciones globales de §1 iguales a los oficiales; ninguna sesión fuera del periodo
   de clases ni en día de descanso; cada descanso que cae en día de clase del grupo,
   presente en la tabla de §7, y ningún descanso inventado; aviso de días de clase sin
   sesión. Las fechas de recuperación pasan al sitio desde aquí.
5. **Contraste con el programa oficial.** Nombre, clave (la de seis dígitos se convierte
   a siete), plan, división, carácter, trimestre del plan, créditos, horas y seriación de
   §1; objetivos (§3.1) y contenido sintético (§4.1) transcritos tal cual; toda cita
   «…» atribuida al programa oficial, literal. La bibliografía oficial ausente solo
   produce avisos. Si falta el archivo del programa oficial, es un aviso (un error con
   `programa_oficial.exigir: true`).
6. **Validación interna.** Fechas contra el periodo y el día de la semana; días del horario de
   cada grupo contra los de las sesiones; numeración de sesiones; fases de cada proyecto
   en el orden de la tabla de fases; la tabla de cada proyecto (sesión, fecha y fase)
   contra el calendario; los renglones «Sesiones: …» y «Ponderación: …» del encabezado
   de un proyecto, si los tiene, contra el calendario y §8.2; la sesión o fecha de cada
   evaluación escrita contra la de entrega de su proyecto o las evaluaciones globales;
   ponderaciones que suman 100 %; subtotales y totales; criterios de la rúbrica; sesiones
   citadas por las lecturas; secciones con número repetido; y las comprobaciones propias
   del curso (`validar`). Se reúnen **todos** los errores antes de detenerse.
7. **Plan de salidas.** Portada, menú y README; las secciones que `paginas` pide como
   páginas; una página por cada proyecto que declare la sección 6 (su plantilla propia
   si existe, la genérica si no, o la sección tal cual); las plantillas propias del curso.
8. **Generación** con Jinja2, en modo estricto: una variable inexistente es un error, no
   un hueco silencioso.
9. **Auditoría de duplicación** de las plantillas del curso (ver abajo).
10. **Escritura** de lo que cambió y **borrado de huérfanos**: todo archivo de `docs/`,
   de cualquier formato, con la marca de generado en su primera línea que ya no
   corresponde a ninguna salida (por ejemplo, la carpeta de un proyecto que cambió de
   nombre). Nunca se borra un archivo escrito a mano.

### La estructura común que lee el motor

| Parte | Qué debe tener |
|---|---|
| Encabezado | La línea `Trimestre NN-Periodo · …` y, si se quiere en el pie del sitio, la línea `Universidad …, Unidad …`. |
| §1 Datos de identificación | Tabla `Campo \| Contenido` con los renglones Unidad de enseñanza-aprendizaje, Clave, Plan de estudios, División, Profesor, Correo de contacto, Trimestre lectivo («17 de septiembre al 11 de diciembre de 2026») y Periodo de clases («… (20 sesiones)»). Los grupos, como `Grupo HA09 \| Lunes y miércoles, de 14:00 a 16:00 h; sala; 23 inscritos` (uno por renglón) o como `Grupo \| HE57` más `Horario \| …`. Opcionales: Evaluaciones globales, Mensajería (enlace a `t.me`), Sitio del curso, Repositorio. |
| §5 Organización por proyectos | Una viñeta por proyecto: `- **P1** síntesis.` (negritas opcionales). |
| §5 Fases | Tabla `Fase \| Actividad \| …`: cada proyecto debe recorrer estas fases, en este orden. |
| §6 Proyectos | Un apartado por proyecto: `### 6.1 Proyecto P1 · Nombre` (o `P1: Nombre`), con los párrafos `**Propósito.**`, `**Condiciones…**` o `**Insumo.**`, la tabla `Sesión \| Fecha \| Fase \| Actividad \| Producto…`, `**Expediente.**` o `**Contenido del expediente…**` con puntos `(1) … (2) …`, `**Evaluación escrita N.**` o `**Examen escrito N.**` con sus reactivos (numerados o separados por «;») y `**Criterios … de la rúbrica.**` (viñetas o separados por «;»). |
| §7 Calendario | Tabla `Núm. \| Fecha \| Bloque \| Fase \| Actividad \| IAG`, con fechas `Lun 21 sep`; `Holgura N` en las reservas; `—` y «Descanso obligatorio» en los descansos. Admite sesiones compartidas (`P1 y P2` / `Pragmática y activista`). Opcional: el bloque oculto `fuente-datos: periodo`, contra el que se recalculan las fechas. |
| §8 Evaluación | Tabla `Componente \| … \| Ponderación \| Fecha`, con las evaluaciones escritas (`Evaluación escrita N` o `Examen escrito N`), el renglón de expedientes (`5 % + 5 % + 5 % = 15 %`, `10 % + 12 % + 18 % = 40 %` o `5 % cada uno`), y los demás componentes; la oración «se califica con N criterios» y «puntaje máximo es de N puntos». |
| §9.1 Lecturas | Tabla `Clave \| Título \| Temas \| Sesiones [\| …]`; cada lectura puede tener su archivo `docs/lecturas/<clave>-*.md`. |

Lo demás es texto libre: se publica tal cual en la página del programa y en las páginas
de sección, y nunca rompe la generación.

---

## `curso.yml`: lo que cambia de una UEA a otra

Todas las claves son opcionales; los valores predeterminados, comentados, están en
[`programa_sitio/predeterminado.yml`](programa_sitio/predeterminado.yml).

| Clave | Para qué |
|---|---|
| `version_motor` | Versión del motor para la que se escribió este archivo. |
| `fuente` | Ruta de la fuente (predeterminado: `docs/curso/programa-analitico.md`). |
| `calendario` | `archivo`: calendario escolar propio del curso, con prioridad sobre los del motor; `trimestre`: forzar un trimestre (`27-I`) en lugar del que dice el encabezado. |
| `programa_oficial` | `archivo` (predeterminado: `docs/curso/programa-oficial.md`); `exigir: true` convierte en error que falte. |
| `datos` | YAML (o diccionario) con lo que solo usa el sitio; se accede como `curso.<clave>` y, por proyecto, `datos.proyectos.P1.<clave>` se copia a `p.<clave>`. |
| `plantillas` | Carpeta de las plantillas propias (predeterminado: `fuente/plantillas`); se buscan antes que las del motor. |
| `sitio` | `url`, `repositorio`, `unidad_corta` cuando no están en la fuente. |
| `identificacion` | Qué texto de la columna Campo corresponde a cada dato, y cuáles son obligatorios. |
| `vocabulario` | Valores de la columna IAG, texto de los descansos, forma de las holguras, fase de entrega. |
| `ia_etiquetas` | Cómo se escribe cada código de IAG en las páginas. |
| `secciones` | Cómo reconocer cada parte (encabezados de tablas, forma del título de un proyecto). |
| `proyecto` | Etiquetas de los párrafos, página de cada proyecto (`plantilla`, `seccion` o `ninguna`), y reglas por proyecto: `alinear` (completar el expediente o los criterios con listas de `datos`), `tablas`, `campos`, `extraer`. |
| `evaluacion`, `rubrica`, `lecturas` | Formas de los componentes, niveles de la rúbrica, tabla de criterios comunes, carpeta y descripciones de las lecturas. |
| `extraer` | Datos que salen de una oración: `{patron: 'regex con (?P<grupo>…)', seccion, tipos: {grupo: entero\|numero\|lista\|texto\|linea}, destino}`. «numero» acepta «tres». |
| `tablas` | Tablas adicionales por sus columnas: `{columnas, seccion, forma: registros\|filas, columnas_salida, renombrar, destino, por_proyecto}`. |
| `listas` | Listas bajo una etiqueta (`despues_de`) o entre dos marcas (`desde`/`hasta`), con un `patron` por elemento. |
| `validar` | Comprobaciones propias: `{que: 'expresión de Jinja', mensaje: 'texto con {{ }}'}`. |
| `paginas` | Secciones de la fuente que también son páginas: `{destino, secciones: ['Uso de asistentes de inteligencia artificial generativa (IAG)'], menu, grupo}`. Conviene nombrar la sección por su **título** (así sigue siendo la misma aunque se renumeren las secciones); también se acepta el número (`'5.7'`). Si el nombre corresponde a más de una sección, se detiene. |
| `salidas` | Plantilla → archivo generado (`docs/index.md: sitio/index.md.j2`); `null` quita una salida del motor. |
| `menu_extra` | Páginas escritas a mano que se agregan al menú generado. |

Ejemplos completos: el `curso.yml` de [Informática](https://github.com/jzavalar/informatica)
(páginas didácticas propias y reglas sobre su prosa) y el de
[`pruebas/casos/analisis-de-decisiones`](pruebas/casos/analisis-de-decisiones/curso.yml)
(páginas por sección).

### Variables en las plantillas

`curso` (con `uea`, `grupos`, `fases`, `evaluacion`, `rubrica`, `lecturas` y lo que
agreguen `extraer`, `tablas`, `listas` y `datos`), `proyectos` y `P` (por id), `p` (en la
página de un proyecto), `sesiones`/`S` (por número), `filas` (renglones del calendario),
`cal` (`periodo`, `todas`, `diagnostico` y `oficial`: el trimestre del calendario escolar, con `inicio`, `fin`, `inicio_clases`, `fin_clases`, `globales`, `actas`, `inscripcion`, `recuperacion.inscripcion`, `recuperacion.evaluaciones`, `recuperacion.actas`, `semanas`, `descansos`; los conjuntos de días tienen `.inicio`, `.fin` y el filtro `dias`, que escribe «del 6 al 8 de enero de 2027» o «2, 3 y 6 de septiembre de 2027»), `oficial` (el programa de estudios leído, si existe), `intro`, `holguras`, `n_sesiones`, `menu`,
`config`, `motor`. Filtros: `corta`, `larga`, `dm`, `dma`, `palabra`, `y`, `nums`,
`punto`, `mayus`, `minuscula_inicial`, `sin_protocolo`, `yaml`, `slug`, `dias`; función `rango`.

### La auditoría de duplicación

Una plantilla que escribe como texto fijo un dato de la fuente es un dato que dejará de
actualizarse. En cada generación se revisa el texto fijo de las plantillas del curso:

- **Error** (detiene): datos de identificación (nombre y clave de la UEA, profesor,
  correo, Telegram, trimestre, sitio, grupos, días de clase y salas, o parte de ellas),
  nombre o carpeta de un proyecto, título o archivo de una lectura, una fecha del
  periodo lectivo (con o sin año, larga o corta), o un número de sesión («sesión 7»,
  «sesiones 12 y 13»).
- **Aviso** (no detiene, `./sitio.sh auditar`): otras frases de la fuente repetidas en una
  plantilla; tramos de 12 palabras copiados de la fuente; datos de identificación, o un
  correo o usuario de Telegram distinto del de la fuente, dentro de páginas escritas a
  mano; y rutas `docs/…` que la fuente menciona y que no existen en el sitio generado.

Si una coincidencia es legítima, se declara en la plantilla:
`{# auditoría: permitido «30 de septiembre de 2026» (fecha de una noticia) #}`.

---

## Calendario escolar

Un archivo JSON por cada calendario que aprueba el Colegio Académico en
`programa_sitio/calendarios/`: el ordinario de cada año escolar (hoy, de 2022-2023 a
2026-2027) y, si lo hay, el que lo modifica por causa de fuerza mayor (`modifica`). Se
transcribe día por día, con su simbología: descansos obligatorios y, por trimestre, periodo,
clases, semanas lectivas, inscripción/reinscripción, evaluaciones globales, actas y
recuperación, y los periodos del año: inter-trimestrales y vacaciones. Los sucesos se escriben como **listas explícitas de días**, nunca como rangos.
Cada archivo se valida contra su esquema y su coherencia, y todos se combinan: si dos
calendarios vigentes no coinciden sobre un trimestre, el trimestre queda en conflicto y no se
usa hasta que se transcriba el calendario modificado que lo resuelve.
Todo el detalle está en [`docs/formato-calendario-escolar.md`](docs/formato-calendario-escolar.md).

```bash
programa-sitio calendario                                  # valida todos los del motor
programa-sitio calendario 2027-2028.json --vista vista.html  # valida uno y lo dibuja con sus colores
programa-sitio calendario --plantilla 2027-2028 programa_sitio/calendarios/2027-2028.json
```

Se actualiza **cada año, o cuando el calendario se modifique**:

1. `programa-sitio calendario --plantilla AAAA-AAAA …`, llenar el esqueleto, validarlo y
   cotejar su vista con el calendario oficial.
2. `python3 -m pytest`, subir la versión del motor y publicar una etiqueta nueva
   (ver *Versiones*).
3. En cada curso, cambiar la etiqueta en `requirements.txt` y `requirements.yml`, y
   `./sitio.sh preparar`.

Si un curso necesita un calendario antes de que exista la versión nueva del motor, puede
usar su propia copia, que tiene prioridad:

```yaml
calendario:
  archivo: fuente/2027-2028.json   # mismo formato que los del motor
  trimestre: null                  # o forzar uno: 27-O
```

## Versiones

Cada curso fija la versión del motor en `requirements.txt` y la de la colección en
`requirements.yml` (las dos con la misma etiqueta, `v1.0.0`). Una mejora al motor se
publica con una etiqueta nueva; cada curso la adopta cuando quiere, cambiando esas dos
líneas. Para publicar una versión:

```bash
# 1. subir la versión en pyproject.toml, programa_sitio/__init__.py y ansible/galaxy.yml
python3 -m pytest
git commit -am "Versión 1.1.0" && git tag v1.1.0 && git push origin main v1.1.0
```

## Desarrollo

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[pruebas]'
python3 -m pytest                                           # pruebas
PROGRAMA_SITIO_INFORMATICA=~/informatica python3 -m pytest   # también contra Informática
```
