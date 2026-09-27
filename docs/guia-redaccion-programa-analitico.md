# Guía para redactar un programa analítico con un asistente de IA

Esta guía es para el asistente de IA —y para quien lo conduce— que redacta o actualiza
el programa analítico de una UEA de la UAM que después se publica con **programa-sitio**.
Entrégala al asistente al empezar, junto con los insumos.

## Los tres insumos

| Insumo | Qué fija | De dónde sale |
|---|---|---|
| **Programa de estudios oficial** de la UEA (`docs/curso/programa-oficial.md`) | Nombre, clave, créditos, horas, carácter, trimestre del plan, seriación, objetivos, contenido sintético, modalidades de conducción y de evaluación, bibliografía. **No se modifica.** | El PDF de la UAM, convertido una sola vez a Markdown. |
| **Calendario escolar** vigente | Inicio y fin del trimestre, periodo de clases, las semanas lectivas (11 + 11 bis), días de descanso obligatorio, evaluaciones globales, evaluaciones de recuperación. **No se modifica.** | El calendario que aprueba el Colegio Académico; el motor lo trae ya transcrito (`programa_sitio/calendarios/AAAA-AAAA.yml`). |
| **Programa analítico** (`docs/curso/programa-analitico.md`) | Todo lo demás: la propuesta del profesor para ese trimestre. | Se redacta con el asistente, a partir de los otros dos. |

El programa analítico **desarrolla** el oficial dentro del calendario: no cambia sus
objetivos, su contenido sintético ni sus modalidades de evaluación; los desglosa y los
asigna a sesiones fechadas.

## El ciclo de trabajo

1. El profesor le da al asistente esta guía, el programa oficial, las fechas del
   calendario escolar para el trimestre y, si existe, el programa analítico del
   trimestre anterior (o la plantilla vacía `plantilla-programa-analitico.md`).
2. El asistente redacta o actualiza el programa analítico **respetando la forma** que se
   describe abajo.
3. El profesor lo guarda en `docs/curso/programa-analitico.md` y ejecuta
   `./sitio.sh revisar`. Se genera `revision.md`, con cada discrepancia contra el
   calendario escolar, contra el programa oficial y contra la estructura común, y la
   tabla de fechas oficiales del trimestre.
4. El profesor le entrega `revision.md` al asistente, que corrige **solo** lo que el
   informe señala y devuelve el documento completo.
5. Se repite hasta que el informe diga «**El programa analítico está listo**». Entonces
   `./sitio.sh publicar` genera el sitio y lo sube.

## Reglas que el asistente debe cumplir

1. **Lo oficial se transcribe tal cual.** Los renglones de §1 que vienen del programa
   oficial (nombre, clave de siete dígitos, plan, división, carácter, trimestre del plan,
   créditos, horas, seriación), los objetivos (§3.1), el contenido sintético (§4.1) y
   toda cita entre «» que se atribuya al programa oficial deben coincidir palabra por
   palabra con él. La clave impresa de seis dígitos (221188) se escribe en el formato
   actual de siete (2211088) y se explica en el Anexo A.
2. **Las fechas salen del calendario escolar.** El trimestre lectivo y las evaluaciones
   globales de §1 son los del calendario. Ninguna sesión cae fuera del periodo de clases
   ni en día de descanso. Cada descanso que cae en un día de clase del grupo aparece en
   la tabla de §7 como renglón de descanso. Se aprovechan todos los días de clase.
3. **Un dato, un valor.** Si una fecha, una ponderación o un número de sesiones aparece
   en varios lugares del programa (§1, el encabezado de un proyecto, la tabla del
   proyecto, §7, §8.2), vale lo mismo en todos.
4. **La forma no se toca.** El motor lee el programa por su estructura; cambiar el texto
   de una celda es libre, cambiar la forma de una tabla o de un encabezado no.

## La forma que el motor lee

### Encabezado (antes de §1)

```markdown
# Programa Analítico

## Nombre de la UEA · UEA 2211088

Licenciatura en Administración · División de Ciencias Sociales y Humanidades

Universidad Autónoma Metropolitana, Unidad Iztapalapa

Trimestre 26-Otoño · Lunes y miércoles, de 14:00 a 16:00 h (grupo HA09)
```

El renglón `Trimestre NN-Periodo · …` es obligatorio: de él sale qué trimestre del
calendario escolar se usa (26-Otoño → 26-O, 27-Invierno → 27-I, 27-Primavera → 27-P).

### §1 Datos de identificación

Tabla `| Campo | Contenido |` con, al menos, estos renglones (el texto de la columna
Campo tal cual): Unidad de enseñanza-aprendizaje · Clave · Plan de estudios · División ·
Carácter · Trimestre del plan · Créditos · Horas semanales (`3.0 teóricas; 2.0
prácticas`) · Seriación · el grupo o los grupos · Trimestre lectivo (`17 de septiembre al
11 de diciembre de 2026`) · Periodo de clases (`21 de septiembre al 2 de diciembre de
2026 (20 sesiones)`) · Evaluaciones globales · Profesor · Correo de contacto.

Los grupos, de una de dos formas:

```markdown
| Grupo HA09 | Lunes y miércoles, de 14:00 a 16:00 h; Salón H214 - Sala C; 23 inscritos |
```
o
```markdown
| Grupo | HE57 |
| Horario | Lunes y miércoles, de 16:00 a 18:00 h |
```

Opcionales: Mensajería (`Telegram, [@usuario](https://t.me/usuario)`), Sitio del curso,
Repositorio, Modalidad de conducción.

### §3 y §4: lo transcrito del programa oficial

`### 3.1 Objetivos del programa oficial` con los objetivos entre «» y
`### 4.1 Contenido sintético del programa oficial` con los puntos del contenido sintético.

### §5 Estrategia didáctica

- `### 5.1 Organización por proyectos` con una viñeta por proyecto: `- **P1** síntesis del proyecto.`
- Una tabla de fases cuya primera columna se llama `Fase` y la segunda `Actividad`. Cada
  proyecto recorre **todas** esas fases, en ese orden.

### §6 Proyectos: uno por proyecto

```markdown
### 6.1 Proyecto P1 · Nombre del proyecto

**Propósito.** …

**Condiciones.** …          (o **Insumo.** …)

| Sesión | Fecha | Fase | Actividad | Producto de la sesión |
|---|---|---|---|---|
| 3 | Lun 28 sep | Activista | … | … |

**Expediente.** (1) Primer punto. (2) Segundo punto (insumo de P2). …

**Evaluación escrita 1.** Individual, en papel, 80 minutos. Reactivos sobre …: reactivo uno; reactivo dos; …

**Criterios de la rúbrica.** Criterio uno (nota); criterio dos; …
```

- También valen `**Contenido del expediente….**`, `**Examen escrito N.**` y los criterios
  como viñetas (`- Criterio (nota).`).
- Si el encabezado del proyecto repite `Sesiones: 3, 5, 6, 7 y 8` o
  `Ponderación: entregable, 10 %; examen escrito 1, 12 %`, debe coincidir con §7 y §8.2.

### §7 Programación de las sesiones

```markdown
| Núm. | Fecha | Bloque | Fase | Actividad | IAG |
|---|---|---|---|---|---|
| 1 | Lun 21 sep | Introducción | — | … | No |
| 3 | Lun 28 sep | P1 | Activista | … | No |
| — | Lun 12 oct | — | — | Descanso obligatorio | — |
| 8 | Lun 19 oct | P1 y P2 | Pragmática y activista | … | No |
| 18 | Mié 25 nov | Holgura 1 | — | Reserva; … | — |
| — | 7–11 dic | Evaluación global | — | Evaluación escrita 3 | No |
```

- Numeración consecutiva desde 1; fechas `Ddd DD mmm` con el día de la semana correcto.
- Columna IAG: `No`, `Sí, con bitácora`, `Demostración del profesor` o `—`.

### §8 Evaluación

- Tabla `| Componente | Forma prevista en el programa oficial | Ponderación | Fecha |`,
  con cada evaluación escrita (`Evaluación escrita 1 (P1)` o `Examen escrito 1 (P1)`), el
  renglón de expedientes (`10 % + 12 % + 18 % = 40 %`), los demás componentes y
  `**Total** | | **100 %**`. La fecha de cada escrita: `Sesión N, día de mes` o el
  rango de las evaluaciones globales.
- Las oraciones `Cada … se califica con N criterios` y `El puntaje máximo es de N puntos`.

### §9.1 Lecturas

Tabla `| Clave | Título | Temas | Sesiones |` (puede tener más columnas al final).

### Libre

Todo lo demás —presentación, temario detallado, alcance, justificaciones, bibliografía
complementaria, anexos— es prosa libre: se publica tal cual y no hay que cuidar su forma.
Lo que va dentro de `<!-- … -->` no se publica ni se lee.
