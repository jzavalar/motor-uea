# Formato del calendario escolar (formato 3)

Cada **calendario escolar aprobado** por el Colegio Académico se transcribe en su propio
archivo JSON en `programa_sitio/calendarios/`, con la forma que fija el esquema
[`calendario-escolar.schema.json`](../programa_sitio/calendarios/calendario-escolar.schema.json)
(JSON Schema, draft 2020-12):

| Documento | Archivo |
|---|---|
| El calendario ordinario de un año escolar | `AAAA-AAAA.json` (p. ej. `2025-2026.json`) |
| Un calendario que modifica a otro ya aprobado (huelga, contingencia…) | `AAAA-AAAA-sNNN.json`, con NNN = sesión que lo aprobó |

El motor trae transcritos los calendarios **2022-2023 a 2026-2027** (sesiones 505, 521, 540,
557 y 576).

## Cómo se lee un calendario escolar de la UAM

### Colores

Cada día hábil que no es de descanso tiene exactamente uno:

| Color | Significa | En el JSON |
|---|---|---|
| Azul | Trimestre | `trimestres[].periodo`, o `tramo_visible` si el trimestre es parcial |
| Amarillo | Periodo inter-trimestral: sin clases; inscripción/reinscripción y recuperación | `periodos_intertrimestrales` |
| Blanco (día hábil) | Vacaciones: las de fin de año y las de verano, de cuatro semanas obligatorias, antes del Otoño | `vacaciones` |
| Gris | Descanso obligatorio | `descansos` |
| Verde (2026-2027) o azul posterior al fin del trimestre (2022-2023, 2025-2026) | Registro de calificaciones posterior al último día del trimestre. El verde no está en la simbología del documento | Se deduce: los días de `registro_de_calificaciones` posteriores al `periodo` |
| Magenta con `>` / `<` | Inicio y terminación de clases | `clases.inicio`, `clases.fin` |

### La columna SEM

Trae una de dos cosas:
- **el número de la semana lectiva:** 1, 2 … 11, y a veces «11 bis», que equivale a una
  semana 12, a menudo recortada;
- **las siglas de los sucesos de esa semana**, cuando no es lectiva: «EG/RCA»,
  «IER/IR/ER/RCR».

A veces trae las dos: «11 bis/EG». En el JSON solo se guardan las semanas lectivas; las
siglas se deducen de los días marcados.

### Las semanas lectivas no siempre van de lunes a viernes

Cada semana se escribe con su **primer y último día de clases**:
- la primera semana empieza el día de inicio de clases. 26-O empieza en jueves: semana 1,
  jue 17 a vie 18 sep; 25-O empieza en miércoles: semana 1, mié 1 a vie 3 oct;
- la última semana termina el día de terminación de clases. La 11 bis de 27-I va del lun 5 al
  mié 7 abr; la 11 de 26-I, del lun 30 mar al mié 1 abr;
- los descansos obligatorios no recortan la semana;
- las vacaciones sí la interrumpen: en 22-O y 24-O las semanas de fin de año no llevan
  número.

### IR

Es el periodo de **inscripción** (alumnos de nuevo ingreso), que se hace a la vez que la
**reinscripción** (a partir del segundo trimestre de estudios). Se anota en el trimestre que
empieza después.

### Nombre de los trimestres

Se nombran por el **año natural** en que empiezan, en el orden **Invierno (AA-I),
Primavera (AA-P), Otoño (AA-O)**: el siguiente de 25-O es 26-I. Un año escolar enuncia un
Otoño y el Invierno y la Primavera del año natural siguiente.

## Lo que varía de un año a otro (y el formato admite)

| Rasgo | Ejemplos reales | Cómo se representa |
|---|---|---|
| Meses que muestra el documento | oct 2022–sep 2023; sep 2023–sep 2024; oct 2024–oct 2025 | `cobertura` |
| Documentos vecinos que se traslapan | sep 2023, oct 2025 y sep 2026 aparecen en dos calendarios | Se coteja cada día del traslape |
| Trimestre que cruza el año natural | 22-O (17 oct 2022–20 ene 2023), 24-O | `periodo` con fechas de dos años |
| Vacaciones de fin de año dentro del trimestre | 22-O: 26 dic–6 ene; 24-O: 23 dic–3 ene | `vacaciones`, traslapadas con el `periodo` |
| Vacaciones de verano, cuatro semanas | 14 ago–8 sep 2023; 29 jul–23 ago 2024; 18 ago–12 sep 2025; 3–28 ago 2026; 2–27 ago 2027 | `vacaciones` (aviso si no son 20 días hábiles) |
| Periodo inter-trimestral partido por vacaciones | 2023-2024: 22 dic, y 8–19 ene | Dos periodos |
| 11 o 12 semanas | 11 bis en 23-O, 24-I, 25-I, 26-O y 27-I | `semanas`: la 11 bis es `orden` 12 |
| Evaluaciones globales que empiezan la semana en que terminan las clases | 23-P: clases al jueves 3 de agosto, globales desde el viernes 4 | Conjunto de días explícito |
| Actas después del último día del trimestre | 23-P, 26-I, 26-P, 26-O, 27-I, 27-P | Se admite (color «cierre») |
| Nombre y sigla de las actas | «Entrega de actas (EA/EAR)» hasta 2024-2025; «Registro de calificaciones en actas (RCA/RCR)» desde 2025-2026 | `simbologia` del documento |
| Artículo del RESUAM de la inscripción | 21 (2022-2023), 22 (2023-2025), 27 (2025-2027) | `simbologia` del documento |
| Días de un trimestre en el calendario de otro año | la recuperación de 22-P, 23-P, 24-P y 26-P; la inscripción de 25-O; las primeras semanas de 23-O, 24-O, 25-O, 26-O y 27-O | Trimestres `"parcial": true` |
| Un calendario modificado | 24-P y 24-O: el calendario 2023-2024 (s521) y el 2024-2025 (s540) no coinciden | `documento.modifica`, y la regla de conflictos |

## Principios: por qué no hay ambigüedad

1. **Una sola forma de fecha:** la cadena `AAAA-MM-DD`. Si la fecha no existe, es un error.
2. **Dos tipos de dato de tiempo, y nada más:**

   | Tipo | Forma | Significa | Se usa para |
   |---|---|---|---|
   | periodo | `{"inicio", "fin"}` | Todos los días naturales entre ambos, **inclusive**. Empieza y termina en un día hábil de su color, no en un descanso | cobertura, trimestre, periodos inter-trimestrales, vacaciones, semanas |
   | conjunto de días | `["…", …]` | **Exactamente** esos días, en orden y sin repetir | inscripciones, evaluaciones y actas |

   Los sucesos nunca se escriben como rango. Dos ejemplos:
   - Las evaluaciones de recuperación de 25-I son el 14, el 16 y el 19 de mayo de 2025. El 15
     es día de descanso.
   - Las globales de 23-O son el 15, 18, 19, 20 y 21 de diciembre de 2023.
3. **Cobertura cerrada y sin huecos.** Dentro de `cobertura`, cada día hábil que no es de
   descanso está en exactamente un periodo: trimestre, inter-trimestral, vacaciones o registro
   de calificaciones posterior. Un día sin periodo, o en dos, es un error. Fuera de la
   cobertura, el documento no afirma nada.
4. **Un archivo, un documento, sin deducciones.** Se transcribe lo que el documento muestra,
   con su simbología. Los días que muestra de trimestres que no enuncia van en trimestres
   `"parcial": true`, con su `tramo_visible` en lugar de `periodo`.
5. **Orden explícito.** Los trimestres son una lista cronológica. Las semanas llevan `orden`
   1, 2, 3… sin saltos (la «11 bis» es la 12) y su primer y último día de clases.
6. **Nombres cerrados.** Un campo que no está en el esquema es un error.
7. **Nada se decide en silencio entre documentos.** Si dos documentos vigentes dan datos
   distintos para el mismo trimestre o clasifican distinto el mismo día, se informa como
   CONFLICTO, y un trimestre en conflicto no se usa (ver abajo).

## Correspondencia con la simbología oficial

| En el calendario | Campo del JSON |
|---|---|
| «Trimestre 24-O: del 21 de octubre de 2024 al 24 de enero de 2025» | `trimestres[].periodo` |
| Azul de un trimestre que el documento no enuncia | `trimestres[].tramo_visible` (trimestre parcial) |
| `>` inicio de clases | `trimestres[].clases.inicio` |
| `<` terminación de clases | `trimestres[].clases.fin` |
| Columna SEM con número (1 … 11, 11 bis) | `trimestres[].semanas[]`: `orden`, `etiqueta`, `inicio` y `fin` (primer y último día de clases) |
| Amarillo | `periodos_intertrimestrales[]` |
| Blanco en día hábil | `vacaciones[]` |
| Gris | `descansos[].fecha` |
| `•` IR (inscripción de nuevo ingreso y reinscripción, simultáneas) | `trimestres[].inscripcion_reinscripcion`, en el trimestre **que empieza después** |
| `*` EG | `trimestres[].evaluaciones_globales` |
| `△` EA o RCA | `trimestres[].registro_de_calificaciones` |
| `Φ` IER | `trimestres[].recuperacion.inscripcion`, en el trimestre **que se recupera**, que es el que acaba de terminar |
| `®` ER | `trimestres[].recuperacion.evaluaciones` |
| `▲` EAR o RCR | `trimestres[].recuperacion.registro_de_calificaciones` |
| Cuadro de simbología | `simbologia`: sigla y texto de cada suceso, como los imprime el documento |
| «Aprobado por el Colegio Académico en su sesión número N…» | `documento.aprobacion` |

## Calendarios modificados y conflictos

Un calendario modificado se transcribe como un documento más, con:

```json
"documento": {
  "nombre": "Calendario Escolar 2023-2024 (modificado)",
  "anio_escolar": "2023-2024",
  "aprobacion": {"organo": "Colegio Académico", "sesion": 999, "fecha": "2024-…"},
  "modifica": [{"anio_escolar": "2023-2024", "sesion": 521}],
  "motivo": "…"
}
```

Dentro de su `cobertura`, el documento modificado **sustituye** al que modifica:
- sus trimestres, periodos y descansos reemplazan a los del original;
- lo del original que queda fuera de esa cobertura sigue vigente. Por ejemplo, 24-I, si la
  modificación empezara después.

Así el motor combina todos los documentos:

1. **Datos de cada trimestre.** Cada trimestre toma sus datos de todos los documentos
   vigentes que lo muestran. La inscripción de 25-O está en el calendario 2024-2025, y el
   resto del trimestre en el 2025-2026.
2. **Conflictos.** Si dos documentos vigentes no coinciden, ese trimestre queda **en
   conflicto**. `programa-sitio calendario` lo informa, y un programa analítico de ese
   trimestre recibe un error que cita a ambos documentos.
3. **Resolución.** El conflicto se resuelve transcribiendo el documento que modificó al otro.
   El motor no elige por su cuenta.
4. **Copia propia de un curso.** La copia de un curso (`calendario.archivo` en `curso.yml`)
   se trata como una modificación de todos los calendarios del motor dentro de su cobertura.

**Hoy hay un solo conflicto, y es real:**

| | 24-P | 24-O |
|---|---|---|
| Calendario 2023-2024 (s521, 27 feb 2023) | globales del 19 al 25 de julio de 2024; recuperación del 28 al 30 de agosto | inicio de clases el 9 de septiembre de 2024 |
| Calendario 2024-2025 (s540, 26 feb 2024) | globales del 1 al 4 de octubre de 2024; recuperación del 9 al 11 de octubre | inicio de clases el 21 de octubre de 2024 |

El calendario 2023-2024 se modificó después de aprobarse. Esa modificación no está entre los
documentos transcritos.

## Qué comprueba el motor

**Capa 1, el esquema:**
- campos obligatorios, nombres, tipos;
- forma de las fechas, de las claves (`24-O`, `24-Otoño`, `11 bis`) y de las siglas.

**Capa 2, la coherencia de cada documento:**
- **Fechas y listas.** Toda fecha existe y cae en la cobertura. Toda lista está en orden y
  sin repetidos.
- **Periodos.** Cada día hábil que no es de descanso cae en exactamente un periodo. Los
  periodos inter-trimestrales y las vacaciones van en orden, no se traslapan, y empiezan y
  terminan en día hábil.
- **Dónde caen los sucesos.**
  - Inscripción/reinscripción, inscripción a recuperación, evaluaciones de recuperación y su
    registro caen en un periodo inter-trimestral.
  - Las evaluaciones globales caen en el trimestre.
  - Todos caen en día hábil, sin descanso.
- **Clases.** El inicio y la terminación de clases son días de clase (hábiles, sin descanso
  ni vacaciones) y caen en el trimestre.
- **Semanas.**
  - Cada una es de una sola semana de calendario.
  - Su `inicio` y su `fin` son su primer y último día de clases: de lunes a viernes,
    recortados por el inicio o la terminación de clases, por vacaciones o por el fin de la
    cobertura (en un trimestre parcial).
  - La primera empieza el día de inicio de clases; la última termina el de terminación.
  - Solo faltan números en semanas de vacaciones.
  - La «11 bis» es la 12 y sigue a la 11.
- **Orden de los sucesos:**
  1. inscripción/reinscripción;
  2. inicio de clases;
  3. terminación de clases;
  4. evaluaciones globales (dentro del trimestre);
  5. actas;
  6. inscripción a recuperación;
  7. evaluaciones de recuperación;
  8. actas de recuperación;
  9. inicio de clases del trimestre siguiente.
- **Trimestres.** Los del mismo documento no se traslapan.

**Capa 3, la combinación de documentos:**
- vigencia por `modifica`;
- cotejo de cada día hábil donde dos documentos se traslapan: descanso, trimestre,
  inter-trimestral, vacaciones o registro de calificaciones;
- cotejo de cada dato y de cada semana de cada trimestre entre todos los documentos que lo
  muestran.

**Avisos** (no impiden usar el documento, pero hay que confirmarlos en el original):
- un número de semanas distinto de 11 o 12;
- unas vacaciones de verano que no son de cuatro semanas (20 días hábiles);
- globales que no terminan el último día del trimestre;
- un trimestre cuyo año no coincide con su clave;
- un orden de trimestres distinto de I → P → O → I.

## Transcribir un calendario nuevo o modificado

```bash
programa-sitio calendario --plantilla 2027-2028 programa_sitio/calendarios/2027-2028.json
```

1. **Llenar el esqueleto.** Llena el esqueleto mes por mes con el calendario oficial:
   - la cobertura;
   - los descansos (gris);
   - los periodos inter-trimestrales (amarillo) y las vacaciones (blanco);
   - la simbología tal como la imprime el documento;
   - los trimestres del encabezado, con sus semanas de primer a último día de clases;
   - los trimestres parciales (lo que muestra del anterior y del siguiente).

   Borra lo que no aplique. Para un calendario modificado, agrega `modifica` y `motivo` en
   `documento` y nombra el archivo `AAAA-AAAA-sNNN.json`.
2. **Validar y dibujar:**
   `programa-sitio calendario programa_sitio/calendarios/2027-2028.json --vista /tmp/vista.html`.
   Corrige hasta que diga «válido».
3. **Cotejar la vista con el original.** La vista HTML dibuja cada mes con los colores, la
   simbología, la columna SEM y las siglas del documento, y resume cada trimestre y cada
   periodo en palabras. Un día rayado en rojo está sin periodo o en dos. Con `.md` la vista
   es texto: los colores van como letras (ⁱ inter-trimestral, ᵛ vacaciones, ᶜ registro
   posterior).
4. **Cotejar el conjunto:** `programa-sitio calendario`, sin argumentos, combina todos los
   documentos y muestra cualquier CONFLICTO con los años vecinos.
5. **Publicar.** Corre `python3 -m pytest`, publica una versión nueva del motor y cambia la
   etiqueta en los cursos.

Mientras tanto, un curso puede usar su propia copia (`calendario: {archivo: fuente/…json}` en
`curso.yml`), que prevalece sobre los calendarios del motor dentro de su cobertura.
