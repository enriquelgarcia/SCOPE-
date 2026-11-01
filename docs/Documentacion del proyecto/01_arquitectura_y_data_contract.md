# SCOPE — Arquitectura de datos y Data Contract v0.1

**Documento narrativo n.º 01**
**Proyecto:** SCOPE — Sports Computational Outcome Prediction Engine
**Versión de datos que describe:** v0.1 (Premier League, 2021/22–2025/26)
**Documentos normativos de referencia:** `../contract/SCOPE_Data_Contract_v0.1.md` y `../DECISION_LOG.md`

---

## Tabla de contenidos

1. [Propósito del documento](#1-propósito-del-documento)
2. [Descripción general de SCOPE](#2-descripción-general-de-scope)
3. [Principios de diseño de datos](#3-principios-de-diseño-de-datos)
4. [Arquitectura general de datos](#4-arquitectura-general-de-datos)
5. [Unidad de observación](#5-unidad-de-observación)
6. [Identidad de partidos](#6-identidad-de-partidos)
7. [Identidad de equipos](#7-identidad-de-equipos)
8. [Clasificación temporal y funcional de variables](#8-clasificación-temporal-y-funcional-de-variables)
9. [Targets del proyecto](#9-targets-del-proyecto)
10. [Benchmark del mercado](#10-benchmark-del-mercado)
11. [Feature engineering definido por contrato](#11-feature-engineering-definido-por-contrato)
12. [Temporalidad y prevención de data leakage](#12-temporalidad-y-prevención-de-data-leakage)
13. [Reinicio por temporada](#13-reinicio-por-temporada)
14. [Elegibilidad para modelado](#14-elegibilidad-para-modelado)
15. [Multicolinealidad y representación de features](#15-multicolinealidad-y-representación-de-features)
16. [Alcance de SCOPE v0.1](#16-alcance-de-scope-v01)
17. [Limitaciones arquitectónicas conocidas](#17-limitaciones-arquitectónicas-conocidas)
18. [Escalabilidad futura](#18-escalabilidad-futura)
19. [Resumen de decisiones arquitectónicas](#19-resumen-de-decisiones-arquitectónicas)

---

## 1. Propósito del documento

Este documento explica cómo está organizada la información dentro de SCOPE y por qué se organizó de esa manera. Su objeto es la arquitectura de datos del proyecto y el conjunto de reglas que la gobiernan, recogidas en el *SCOPE Data Contract v0.1*.

El Data Contract es un documento **normativo**: establece qué datos existen, qué significan, en qué momento están disponibles, cómo deben serializarse y qué reglas no puede violar ninguna implementación. Está escrito para ser verificable, con tablas de columnas, dominios y reglas identificadas por códigos (T1–T10, M1–M4). Esa precisión es necesaria para implementar y validar el pipeline, pero hace que el contrato sea difícil de leer como explicación: dice *qué* debe cumplirse, pero rara vez se detiene en *por qué*.

Este texto cumple la función complementaria. No añade reglas, no las modifica y no las sustituye. Cuando ambos documentos parezcan decir cosas distintas, prevalece siempre el contrato técnico; este documento solo interpreta y justifica lo que allí ya está decidido. El *Decision Log* aporta la otra mitad del contexto: registra cada decisión, su origen (requisito de rúbrica, decisión del equipo o propuesta aprobada) y su estado (aprobada, provisional, pendiente o pospuesta).

Separar la versión narrativa de la normativa tiene una ventaja práctica: el contrato puede seguir siendo breve y exacto, mientras que la explicación puede desarrollarse con ejemplos y argumentos sin riesgo de introducir ambigüedad en las reglas. Además, este documento está pensado como base para el informe académico final del proyecto.

Quedan fuera de este documento la ejecución real del pipeline, sus validaciones, sus resultados y cualquier análisis exploratorio o de modelado; todo ello corresponde a documentos posteriores.

---

## 2. Descripción general de SCOPE

**SCOPE — Sports Computational Outcome Prediction Engine** es un sistema de análisis y predicción probabilística de resultados deportivos. No pretende "adivinar" quién ganará un partido, sino estimar, con información disponible antes del encuentro, la probabilidad de cada desenlace posible, y hacerlo de forma reproducible y metodológicamente defendible.

La versión v0.1 tiene un alcance deliberadamente acotado:

- **Competición:** Premier League inglesa.
- **Temporadas:** de 2021/22 a 2025/26, cinco temporadas completas de 380 partidos cada una.
- **Fuente:** Football-Data.co.uk.

El **problema principal de Machine Learning** es una clasificación multiclase sobre el resultado final del partido, con tres clases:

- `H` — victoria del equipo local;
- `D` — empate;
- `A` — victoria del equipo visitante.

Lo que se busca en última instancia no es solo la clase más probable, sino las tres probabilidades P(H), P(D) y P(A), que permiten evaluar el modelo con métricas probabilísticas y compararlo con el mercado de apuestas.

De forma complementaria, y en respuesta a los requisitos de Matemáticas Aplicadas a la Ciencia de Datos, se plantea un **problema de regresión lineal múltiple** cuya variable respuesta provisional es `goal_difference`, la diferencia de goles del partido. Este problema no sustituye al de clasificación; es un análisis estadístico relacionado que se apoya sobre los mismos datos y las mismas variables pre-partido.

Aunque el alcance sea pequeño, la arquitectura se diseñó desde el principio para poder crecer hacia otras ligas, otras fuentes y otros modelos sin rehacer su lógica central. Esa tensión entre un MVP manejable y un diseño escalable explica buena parte de las decisiones que se describen a continuación.

---

## 3. Principios de diseño de datos

Las decisiones del contrato no son independientes entre sí: derivan de un pequeño conjunto de principios. Entenderlos facilita entender todo lo demás.

### 3.1 RAW es inmutable

Los archivos descargados de la fuente original nunca se modifican, sobrescriben, limpian, eliminan ni sustituyen. Si contienen una anomalía, esta se documenta y se trata en una capa posterior, pero el archivo original se conserva tal cual. Su integridad se comprueba mediante un resumen criptográfico SHA-256 registrado en un manifiesto.

La razón es que RAW es la única evidencia de lo que la fuente entregó realmente. Si se corrigiera en su sitio, ya no sería posible distinguir entre un dato original y una intervención del equipo, ni repetir el proceso desde cero para comprobar que es correcto. Mantener RAW intacto convierte a toda la cadena posterior en algo que puede reconstruirse y auditarse.

### 3.2 Trazabilidad

Cada partido de las capas procesadas conserva una referencia al archivo y a la fila de RAW de la que procede. Así, cualquier valor sospechoso puede rastrearse hasta su origen y compararse con el dato entregado por la fuente. La trazabilidad es la contrapartida natural de la inmutabilidad: como RAW no se toca, siempre se puede volver a él.

### 3.3 Reproducibilidad

Con los mismos archivos RAW y las mismas reglas, el pipeline debe producir exactamente los mismos resultados. Por eso el contrato es tan preciso en aspectos que parecen menores, como el formato de las fechas, la representación de los números decimales, el orden de las filas o la forma de escribir un valor ausente. Un identificador de partido construido de forma determinista y unas convenciones de serialización fijas permiten que dos ejecuciones independientes generen archivos idénticos, lo que hace verificable cualquier afirmación sobre los datos.

### 3.4 Temporalidad estricta

Para predecir un partido solo puede utilizarse información que existiera antes de que empezara. Este principio es el más importante desde el punto de vista metodológico, porque su violación produce modelos que parecen excelentes durante el desarrollo y fracasan en cuanto se usan de verdad. Se desarrolla en detalle en la sección 12.

### 3.5 Separación entre hechos observados y variables de modelado

Un partido tiene hechos: quién jugó, cuándo, cuántos goles marcó cada equipo, cuántos tiros hizo. Esos hechos son estables y no dependen de ninguna decisión de modelado. Las *features*, en cambio, son construcciones: el promedio de puntos en los últimos cinco partidos, por ejemplo, depende de haber elegido una ventana de cinco y no de diez. SCOPE guarda ambas cosas en capas distintas. Si mañana se decide cambiar una feature, los hechos no se tocan; solo se genera una nueva versión de las features.

### 3.6 CANONICAL ≠ FEATURES ≠ base de datos relacional

Estas tres estructuras responden a preguntas diferentes y por eso no se confunden:

- **CANONICAL** responde a "¿qué ocurrió en cada partido?".
- **FEATURES** responde a "¿qué se sabía de cada equipo antes de cada partido, expresado como variables para un modelo?".
- **La base de datos relacional** responde a "¿cómo se almacena y consulta esta información de forma normalizada e íntegra?".

CANONICAL es una tabla analítica plana, con un partido por fila, cómoda para el análisis estadístico. Un esquema relacional, en cambio, separaría equipos, temporadas, partidos, estadísticas, cuotas, modelos y predicciones en entidades distintas. Ambos diseños son correctos para su propósito, pero no son intercambiables. El contrato solo identifica los conceptos que una futura base de datos tendría que representar; el diseño del esquema corresponde a la asignatura de Bases de Datos.

### 3.7 MVP pequeño pero escalable

Todo lo que no está en el contrato queda fuera de v0.1. Esto no es una forma de descartar ideas, sino de mantener un sistema que pueda terminarse, validarse y explicarse dentro del semestre. La escalabilidad no se consigue añadiendo componentes, sino diseñando bien las fronteras entre capas y las identidades de partidos y equipos, de manera que crecer después no obligue a rehacer lo ya construido.

---

## 4. Arquitectura general de datos

### 4.1 Flujo de capas

La información recorre siete etapas, cada una con una responsabilidad única:

```
            Fuente externa (Football-Data.co.uk)
                          │
                          ▼
┌──────────────────────────────────────────────────────┐
│ RAW            copia original, inmutable (SHA-256)   │
└──────────────────────────────────────────────────────┘
                          │  parseo, tipado, limpieza superficial
                          ▼
┌──────────────────────────────────────────────────────┐
│ INTERIM        temporadas unificadas, sin descartar  │
└──────────────────────────────────────────────────────┘
                          │  selección, renombrado, identidades, validación
                          ▼
┌──────────────────────────────────────────────────────┐
│ CANONICAL      1 fila = 1 partido · hechos observados│
└──────────────────────────────────────────────────────┘
                          │  desdoblamiento por equipo
                          ▼
┌──────────────────────────────────────────────────────┐
│ team_match_log 1 fila = 1 equipo en 1 partido        │
│                (artefacto auxiliar de cálculo)       │
└──────────────────────────────────────────────────────┘
                          │  acumulados y ventanas desplazados
                          ▼
┌──────────────────────────────────────────────────────┐
│ FEATURES       1 fila = 1 partido · variables previas│
└──────────────────────────────────────────────────────┘
                          │  entrenamiento con split temporal
                          ▼
┌──────────────────────────────────────────────────────┐
│ MODELS         modelos + metadatos + feature subset  │
└──────────────────────────────────────────────────────┘
                          │  inferencia
                          ▼
┌──────────────────────────────────────────────────────┐
│ PREDICTIONS    P(H), P(D), P(A) por partido y modelo │
└──────────────────────────────────────────────────────┘
```

De forma compacta:

`RAW → INTERIM → CANONICAL → team_match_log → FEATURES → MODELS → PREDICTIONS`

Cada flecha es una transformación que lee una capa y produce otra nueva. Ninguna capa modifica a la anterior.

### 4.2 RAW

RAW contiene una copia exacta de los archivos que entregó la fuente: en v0.1, un CSV por temporada descargado de Football-Data.co.uk, junto con la documentación oficial de columnas de la propia fuente. Funciona como **evidencia de origen**: es el punto de partida de toda reconstrucción y la referencia contra la que se comprueba que ninguna transformación alteró los datos.

Cada archivo queda registrado en un manifiesto con su huella SHA-256, de modo que cualquier cambio accidental, por mínimo que sea, puede detectarse.

**Qué no debe hacer RAW:** no se limpia, no se corrige, no se renombra, no se convierte a otro formato en su lugar ni se reemplaza por una versión "mejorada". Si un archivo RAW contiene un error, el error se documenta y se trata más adelante. Las copias en Excel que existen en el proyecto sirven solo para inspección manual y no forman parte de RAW como fuente de verdad.

### 4.3 INTERIM

INTERIM es una capa técnica de preparación. Aquí cada temporada se lee y se tipa correctamente, se eliminan problemas superficiales de formato (marcas de codificación al inicio del archivo, espacios sobrantes) y se unen todas las temporadas en una sola estructura.

Una particularidad de la fuente es que no todas las temporadas tienen las mismas columnas: el número de columnas varía entre archivos. INTERIM resuelve esta heterogeneidad conservando la **unión** de todas las columnas existentes, de modo que ninguna información se pierde; donde una temporada no tenía una columna, el valor queda ausente. Cada fila conserva además su archivo y posición de origen.

**Qué no debe hacer INTERIM:** no descarta columnas, no decide qué variables son relevantes, no traduce nombres a la nomenclatura de SCOPE ni calcula variables nuevas. Su función es dejar los datos legibles y uniformes, no interpretarlos.

### 4.4 CANONICAL

CANONICAL es la **representación oficial de un partido dentro de SCOPE**. A partir de INTERIM se seleccionan los campos que el proyecto considera estables y relevantes, se les asignan nombres propios del sistema, se fijan sus tipos y formatos y se resuelven las identidades internas de partidos y equipos.

Su contenido son **hechos observados**: identificación y trazabilidad del partido, fecha y hora, equipos, árbitro, goles finales y al descanso, estadísticas del encuentro (tiros, tiros a puerta, córneres, faltas, tarjetas), los dos targets y un bloque reducido de cuotas de mercado que se usa como benchmark. Solo pasan a CANONICAL los campos presentes y completos en las cinco temporadas, lo que garantiza que todos los partidos tengan la misma estructura.

Además, CANONICAL incluye un campo de avisos de calidad (`dq_flags`) que señala inconsistencias detectadas en los datos de origen —por ejemplo, más tiros a puerta que tiros totales— sin corregirlas. El dato se conserva tal como lo entregó la fuente y la anomalía queda marcada para que el análisis posterior decida cómo tratarla.

**Qué no debe hacer CANONICAL:** no contiene features, promedios históricos ni ninguna variable que dependa de una decisión de modelado. Tampoco contiene probabilidades implícitas del mercado ni las cuotas de casas de apuestas individuales, que permanecen en INTERIM. Y, sobre todo, el hecho de que un dato esté en CANONICAL no lo convierte en un predictor válido (sección 8).

### 4.5 team_match_log

`team_match_log` es un **artefacto auxiliar de cálculo**. Toma cada partido de CANONICAL y lo desdobla en dos filas: una con la perspectiva del equipo local y otra con la del visitante. Cada fila describe lo que le ocurrió a *un equipo* en *un partido*: si jugó en casa o fuera, cuándo, cuántos goles marcó y recibió, cuántos puntos obtuvo y cuántos tiros a puerta realizó.

Esta forma de organizar los datos existe porque las features describen el historial de un equipo, y ese historial mezcla partidos jugados como local y como visitante. Ordenando `team_match_log` por equipo y por fecha de inicio, calcular "lo que este equipo había hecho hasta ahora" se reduce a recorrer una secuencia ordenada, lo cual es más simple y menos propenso a errores que buscar en la tabla de partidos todas las apariciones del equipo en cualquiera de las dos columnas.

**Qué no debe hacer team_match_log:** no es una unidad de análisis ni sustituye a CANONICAL. No añade información que no derive de CANONICAL y no se usa directamente para entrenar modelos.

### 4.6 FEATURES

FEATURES es la tabla que consumen los modelos. Vuelve a tener **una fila por partido**, enlazada con CANONICAL a través de `match_id`, y contiene:

- variables **pre-partido** de cada equipo, calculadas solo con su historial anterior al encuentro;
- las diferencias entre local y visitante para esas variables;
- los dos targets (`result` y `goal_difference`), copiados de CANONICAL para facilitar el entrenamiento;
- un indicador de elegibilidad para el modelado;
- la versión del conjunto de features.

Las features están **versionadas**: si en el futuro cambian sus definiciones, se genera una nueva versión de FEATURES y CANONICAL permanece igual.

**Qué no debe hacer FEATURES:** no puede contener ninguna variable que use información del propio partido o de partidos posteriores, no puede incluir cuotas como predictores y no imputa los valores ausentes del inicio de temporada.

### 4.7 MODELS

MODELS almacena los modelos entrenados junto con todo lo necesario para entenderlos y reproducirlos: qué subconjunto de features usaron, con qué partición temporal se entrenaron y validaron, a partir de qué versión de los datos, con qué hiperparámetros y qué métricas obtuvieron.

Que cada modelo declare explícitamente su *feature subset* no es una formalidad: FEATURES contiene representaciones redundantes de la misma información (sección 15), y distintos modelos necesitan elegir entre ellas.

**Qué no debe hacer MODELS:** ningún ajuste —estandarización, selección de variables, hiperparámetros— puede usar información de los datos de validación o de prueba. Tampoco se acepta un modelo cuyas features o configuración no queden registradas.

### 4.8 PREDICTIONS

PREDICTIONS guarda las salidas finales: para cada partido y cada modelo, las probabilidades P(H), P(D) y P(A). En esta misma etapa se evaluará el benchmark de mercado con el mismo protocolo, de modo que la comparación entre modelo y mercado sea justa.

**Qué no debe hacer PREDICTIONS:** no debe mezclarse con los hechos observados ni retroalimentar las features. Una predicción es un resultado del sistema, no un dato del partido.

---

## 5. Unidad de observación

La unidad de observación indica qué representa cada fila de una tabla. En SCOPE cambia a lo largo del pipeline, y esos cambios son deliberados:

| Capa | Una fila representa |
|---|---|
| CANONICAL | un partido de liga |
| team_match_log | un equipo dentro de un partido (dos filas por partido) |
| FEATURES | un partido de liga |

CANONICAL y FEATURES comparten granularidad porque ambos describen partidos: el primero lo que ocurrió y el segundo lo que se sabía antes. Esa coincidencia permite relacionarlos de forma uno a uno mediante la clave `match_id` —no mediante la posición física de las filas en cada archivo— y garantiza que cada partido tenga exactamente una observación en el conjunto de modelado.

`team_match_log` cambia temporalmente la granularidad solo porque el cálculo lo requiere. Su existencia no implica que el proyecto analice "actuaciones de equipo" como observaciones independientes; una vez calculadas las variables históricas, los resultados se reconstruyen a una fila por partido. Si se usara `team_match_log` como tabla de análisis, cada partido aparecería dos veces y las observaciones dejarían de ser independientes de una forma difícil de controlar. Por eso el contrato insiste en que es un artefacto de cálculo y no una capa sustitutiva de CANONICAL.

---

## 6. Identidad de partidos

Un sistema que integra varias capas, y en el futuro varias fuentes, necesita una forma inequívoca de saber que dos registros se refieren al mismo partido. El contrato distingue para ello dos conceptos.

### 6.1 Clave natural

La clave natural es la combinación de atributos que, conceptualmente, identifica un partido:

`(competition_code, season, match_date, home_team_id, away_team_id)`

Es decir: en qué competición, en qué temporada, en qué fecha y entre qué local y qué visitante. Esta combinación debe ser única y así se valida.

Incluir la fecha puede parecer redundante en una liga donde cada pareja local–visitante se enfrenta una sola vez por temporada, pero no lo es si se piensa en el futuro: en copas, eliminatorias o en otras competiciones, los mismos equipos pueden enfrentarse más de una vez con la misma localía. Con la fecha, la clave sigue siendo válida en esos escenarios sin necesidad de rediseñarla.

### 6.2 `match_id`

A partir de la clave natural se construye un identificador interno, `match_id`, con el siguiente formato:

```
{competition_code}_{season}_{YYYYMMDD}_{home_team_id}_{away_team_id}
```

Un ejemplo real del contrato es:

```
EPL_2021-2022_20210813_brentford_arsenal
```

que corresponde al partido de la Premier League 2021/22 jugado el 13 de agosto de 2021 entre Brentford, como local, y Arsenal, como visitante.

Este diseño tiene varias propiedades importantes:

- **Es determinista y reproducible.** Se calcula exclusivamente a partir de datos del propio partido. Dos ejecuciones independientes del pipeline asignan siempre el mismo identificador al mismo partido.
- **No depende del orden físico de las filas.** No es un contador ni un número de fila. Si los archivos de origen llegaran en otro orden, o si se añadieran partidos, los identificadores existentes no cambiarían.
- **No necesita un registro central ni un hash.** Cualquier componente que conozca la clave natural puede construirlo.
- **Es legible.** Una persona puede reconocer el partido solo con leerlo, lo cual facilita la depuración.

El contrato define `match_id` como legible, determinista y reproducible. A eso se añade una recomendación de diseño que no es una regla contractual literal: como práctica de desacoplamiento, conviene que los componentes consumidores traten `match_id` como un **identificador opaco** y utilicen las columnas explícitas de fecha y equipos, en lugar de extraer información desde el texto del ID. Así, si algún día fuera necesario cambiar su formato —por ejemplo, añadiendo la hora—, la lógica que lo consume no tendría que modificarse.

En una base de datos relacional podrá añadirse una clave primaria entera subrogada, manteniendo `match_id` como columna única. Esa es una decisión de diseño de la base de datos, no del contrato.

### 6.3 Estabilidad y limitación conocida

Para datos históricos, `match_id` es completamente estable: los partidos ya jugados tienen una fecha definitiva que no cambiará.

La limitación aparece al pensar en partidos futuros. Si SCOPE predijera partidos todavía no disputados, un aplazamiento cambiaría la fecha y, con ella, el identificador. Resolverlo exigiría un registro de fixtures que asigne el identificador la primera vez que se conoce el partido. Esa situación está documentada en el contrato y queda explícitamente **fuera de v0.1**, que trabaja solo con temporadas históricas. El contrato también anticipa que, si en algún deporte dos equipos pudieran jugar dos veces el mismo día, bastaría con añadir la hora al formato; no es necesario ahora.

---

## 7. Identidad de equipos

El mismo equipo puede aparecer escrito de formas diferentes según la fuente. Football-Data.co.uk, por ejemplo, usa nombres abreviados como `Man City` o `Nott'm Forest`. Si SCOPE adoptara esos nombres como identidad, quedaría atado a las convenciones de un proveedor concreto, y cualquier fuente nueva con otra forma de escribirlos rompería la integración.

Por eso el contrato separa tres niveles:

```
(source, source_name)  →  team_id  →  display_name
```

- `(source, source_name)` es el **alias del proveedor**: cómo se llama el equipo en una fuente determinada.
- `team_id` es la **identidad interna** de SCOPE, independiente de cualquier fuente.
- `display_name` es el **nombre de presentación**, completo y legible.

La correspondencia está recogida en un archivo de mapeo con una fila por alias. Algunos ejemplos del mapeo vigente:

| Fuente | Alias en la fuente | `team_id` | `display_name` |
|---|---|---|---|
| football-data.co.uk | `Man City` | `manchester_city` | Manchester City |
| football-data.co.uk | `Man United` | `manchester_united` | Manchester United |
| football-data.co.uk | `Nott'm Forest` | `nottingham_forest` | Nottingham Forest |
| football-data.co.uk | `Wolves` | `wolverhampton_wanderers` | Wolverhampton Wanderers |

El caso de Nottingham Forest ilustra bien la decisión: el alias de la fuente contiene un apóstrofo y una abreviatura propia del proveedor; el `team_id` no hereda nada de eso.

Esta estructura permite que una fuente nueva utilice sus propios alias sin alterar la identidad de los equipos. Integrarla consiste en añadir filas al mapeo con otro valor de `source` que apunten a los `team_id` ya existentes. El equipo sigue siendo el mismo; solo se registra una nueva forma de nombrarlo.

La estabilidad de `team_id` es crítica porque forma parte del `match_id`. Cambiar un `team_id` cambiaría los identificadores de todos los partidos de ese equipo y rompería las referencias entre capas. Por eso los 27 `team_id` de v0.1 están congelados: un identificador ya usado no se modifica y, si en el futuro fuera imprescindible cambiarlo, tendría que hacerse mediante una migración explícita y versionada.

Conviene señalar una ambigüedad de nombres que el contrato resuelve explícitamente. En CANONICAL, el campo `source_name` indica la fuente del registro (`football-data.co.uk`); en el archivo de mapeo, el campo `source_name` es el alias del equipo, mientras que la fuente aparece en `source`. Son dos significados distintos del mismo nombre de columna, y la relación verificable es que la fuente del partido coincida con la fuente del alias, y que el nombre del equipo en RAW coincida exactamente con el alias registrado.

---

## 8. Clasificación temporal y funcional de variables

Cada campo de CANONICAL pertenece a una categoría que describe **cuándo** existe esa información y **para qué** puede usarse. Esta clasificación es la herramienta conceptual básica para prevenir el uso de información futura.

### META

Información de identificación y contexto: identificador del partido, competición, temporada, trazabilidad hacia RAW, fecha y hora de inicio, equipos, árbitro y avisos de calidad.

META es una categoría **funcional**, de metadatos, y no una garantía de disponibilidad temporal. Pertenecer a META no implica automáticamente que un dato estuviera disponible antes del partido. El caso más claro es `dq_flags`: el contrato lo clasifica como META porque es un campo de control de calidad, pero algunos de sus códigos se derivan de estadísticas POST, como la comparación entre tiros a puerta y tiros totales, que solo se conocen cuando el partido ha terminado. Lo que determina si una variable puede usarse como predictor no es únicamente su categoría, sino las reglas temporales T1–T10 (sección 12).

### POST

Información que se genera **durante o después** del partido: goles finales y al descanso, resultado al descanso, tiros, tiros a puerta, córneres, faltas y tarjetas. Ninguno de estos valores existe en el momento en que se haría una predicción.

### TARGET

Las variables que se pretende explicar o predecir: `result` para la clasificación y `goal_difference` para la regresión. Son, por definición, información posterior al partido.

### MARKET

Información del mercado de apuestas, en concreto las cuotas medias del mercado antes del cierre y al cierre. Se utiliza como referencia externa con la que comparar el modelo, no como insumo del modelo.

### Almacenar no es lo mismo que poder usar

> Que una variable POST se almacene en CANONICAL no significa que pueda utilizarse como predictor del propio partido.

CANONICAL guarda los tiros a puerta de un partido porque son un hecho observado valioso, y porque son necesarios para calcular el promedio de tiros a puerta que un equipo llevará a sus *siguientes* partidos. Pero si los tiros a puerta de un partido se usaran para predecir el resultado de ese mismo partido, el modelo estaría utilizando información que solo se conoce cuando el partido ya terminó. El resultado sería un modelo con un rendimiento aparentemente alto y sin ninguna utilidad real.

La clasificación META / POST / TARGET / MARKET hace explícita esta distinción en el propio esquema de datos. En lugar de confiar en que cada análisis recuerde qué variables son seguras, la categoría de cada campo deja claro desde el principio qué información está disponible antes del partido y cuál no.

---

## 9. Targets del proyecto

SCOPE tiene dos variables objetivo, relacionadas entre sí pero asociadas a problemas distintos.

### 9.1 `result`

`result` es una variable categórica con tres valores posibles: `H` (victoria local), `D` (empate) y `A` (victoria visitante). Es el **target principal de Machine Learning** y define un problema de clasificación multiclase.

El objetivo no se limita a acertar la clase. El modelo debe producir una distribución de probabilidad sobre las tres clases, porque es esa distribución la que permite evaluar con métricas probabilísticas y comparar con las probabilidades implícitas del mercado. Por construcción, `result` coincide con el signo de la diferencia de goles: positivo, victoria local; cero, empate; negativo, victoria visitante.

### 9.2 `goal_difference`

`goal_difference` se define como:

```
goal_difference = home_goals − away_goals
```

Es una variable **cuantitativa discreta**: toma valores enteros, positivos, negativos o cero. Se mantiene de forma **provisional** como variable respuesta de la regresión lineal múltiple requerida por Matemáticas.

El contrato justifica su elección por varios motivos: es interpretable, está directamente relacionada con el resultado H/D/A y puede explicarse con variables pre-partido sin recurrir a estadísticas del mismo encuentro, lo cual daría un modelo casi tautológico. Al mismo tiempo, deja constancia de sus limitaciones: al ser discreta, obliga a evaluar con cuidado supuestos del modelo lineal clásico como la normalidad de los residuos, y sus observaciones no son plenamente independientes, ya que los mismos equipos aparecen repetidamente y existe dependencia temporal. Por esa razón, un coeficiente de determinación bajo no se interpretará automáticamente como un fracaso del análisis, y la idoneidad de esta variable deberá validarse en el EDA de Matemáticas.

El contrato también delimita el uso de modelos de conteo: la distribución de Poisson se reserva para variables de conteo no negativas, como los goles de cada equipo o el total de goles, y no se aplica a `goal_difference`, que puede ser negativa.

### 9.3 Dos problemas relacionados, no equivalentes

Clasificación y regresión comparten datos y predictores, pero responden a preguntas diferentes. La clasificación pregunta *qué desenlace ocurrirá y con qué probabilidad*; la regresión pregunta *por cuántos goles de diferencia se resolverá el partido*. Conocer la diferencia de goles determina el resultado, pero un buen modelo de regresión no se traduce automáticamente en buenas probabilidades H/D/A, y viceversa.

Como explicación metodológica —no como regla del contrato— puede añadirse que el empate corresponde a un único valor de `goal_difference` (cero), y que una regresión lineal que estima el valor esperado de `goal_difference` no produce directamente una probabilidad específica de empate. Por eso ambos problemas se tratan por separado, con sus propios métodos de evaluación.

---

## 10. Benchmark del mercado

### 10.1 Qué se conserva

La fuente incluye cuotas de numerosas casas de apuestas y de varios mercados. CANONICAL conserva únicamente seis columnas, correspondientes a la **cuota decimal media del mercado** para cada resultado en dos momentos:

| Campo SCOPE | Origen en la fuente | Momento |
|---|---|---|
| `mkt_avg_pre_home` | `AvgH` | antes del cierre |
| `mkt_avg_pre_draw` | `AvgD` | antes del cierre |
| `mkt_avg_pre_away` | `AvgA` | antes del cierre |
| `mkt_avg_close_home` | `AvgCH` | cierre |
| `mkt_avg_close_draw` | `AvgCD` | cierre |
| `mkt_avg_close_away` | `AvgCA` | cierre |

Las cuotas previas al cierre son el **benchmark principal**; las de cierre, el **benchmark secundario**. Se eligieron los agregados medios porque representan un consenso del mercado y porque están completos en las cinco temporadas. Las cuotas de casas individuales, los valores máximos y los mercados de más/menos goles y hándicap asiático permanecen en INTERIM y no pasan a CANONICAL.

### 10.2 Por qué el mercado no es un predictor en v0.1

El contrato adopta lo que denomina **Estrategia C**: el modelo de SCOPE utiliza exclusivamente información deportiva histórica, y el mercado actúa como referencia externa con la que compararlo. La pregunta que guía esta decisión es:

> ¿Qué tan cerca está un modelo basado exclusivamente en información deportiva histórica del consenso probabilístico del mercado?

Las cuotas representan el consenso agregado del mercado y pueden incorporar información que no está representada en las features deportivas de SCOPE. Si se utilizaran como predictores, sería difícil separar cuánto rendimiento procede de las variables construidas por el proyecto y cuánto de la señal ya incorporada en el mercado. Mantenerlas fuera de las features permite medir lo que la información deportiva consigue por sí misma y usar el mercado como referencia externa e independiente.

Esto es coherente con la regla temporal T7, que prohíbe usar cuotas como features en v0.1, y con la categoría MARKET descrita en la sección 8.

### 10.3 Por qué no se almacenan probabilidades implícitas

Una cuota decimal no es directamente una probabilidad. Su inversa da una probabilidad "bruta", y la suma de las tres probabilidades brutas supera la unidad porque las casas de apuestas incluyen un margen. Para obtener probabilidades que sumen uno hay que normalizar ese margen, y existen varios métodos para hacerlo.

Como el resultado depende del método elegido, las probabilidades implícitas no son un hecho observado sino una transformación, y por eso no se guardan en CANONICAL. El contrato fija el método que se usará más adelante —una normalización proporcional, en la que cada inversa se divide entre la suma de las tres—, pero su aplicación pertenece a la **capa de evaluación**.

### 10.4 Comparación modelo–mercado

La comparación entre el modelo y el mercado corresponde a una etapa posterior. El contrato establece desde ahora algunas condiciones para que sea justa: ambos deberán evaluarse sobre exactamente el mismo conjunto de partidos, y no se asumirá que las cuotas de cierre contienen la misma información temporal que las predicciones de SCOPE, ya que la hora exacta en que la fuente captura esas cuotas no está documentada. Los detalles de la evaluación, como la formulación del Brier score multiclase, se definirán en la etapa de Machine Learning.

---

## 11. Feature engineering definido por contrato

### 11.1 Las ocho métricas por equipo

El contrato define un conjunto pequeño de métricas que describen el rendimiento previo de cada equipo dentro de la temporada:

| Métrica | Qué mide | Ventana |
|---|---|---|
| `n_prev_season` | número de partidos de liga ya jugados por el equipo en la temporada | season |
| `ppg_season` | puntos por partido | season |
| `gf_pg_season` | goles a favor por partido | season |
| `ga_pg_season` | goles en contra por partido | season |
| `ppg_last5` | puntos por partido en la forma reciente | last5 |
| `gf_pg_last5` | goles a favor por partido en la forma reciente | last5 |
| `ga_pg_last5` | goles en contra por partido en la forma reciente | last5 |
| `sot_pg_last5` | tiros a puerta propios por partido en la forma reciente | last5 |

Los puntos se calculan desde la perspectiva del equipo: tres por victoria, uno por empate y cero por derrota. En el caso de `sot_pg_last5`, se usan los tiros a puerta del propio equipo, ya hubiera jugado como local o como visitante, lo cual es posible precisamente gracias a la estructura de `team_match_log`.

Todas las métricas, salvo el conteo de partidos, se expresan como **tasas por partido** y no como totales. Esto es importante porque, por aplazamientos, dos equipos pueden llegar a un mismo partido con un número distinto de encuentros disputados; comparar totales favorecería artificialmente al que ha jugado más.

### 11.2 Ventana season

Para un equipo y un partido concreto, la ventana **season** está formada por todos los partidos de liga que ese equipo jugó **antes** dentro de la misma temporada. Describe el rendimiento acumulado del equipo hasta ese momento.

### 11.3 Ventana last5

La ventana **last5** está formada por los `min(5, n_prev_season)` partidos más recientes de la ventana season. Es decir, los cinco últimos partidos si el equipo ya jugó al menos cinco; si jugó menos, todos los que haya disputado. Describe la forma reciente y puede reaccionar más rápido que el acumulado a cambios de rendimiento. La longitud de cinco partidos es provisional y está pendiente de evaluarse en el EDA.

### 11.4 Perspectiva local y visitante

Cada partido tiene dos equipos, así que cada métrica se calcula dos veces y se materializa con un prefijo:

- `h_` para el equipo local (por ejemplo, `h_ppg_season`);
- `a_` para el equipo visitante (por ejemplo, `a_ppg_season`).

Se obtienen así dieciséis variables por partido.

### 11.5 Diferencias

Para siete de las ocho métricas se calcula además la diferencia entre local y visitante:

```
diff_x = h_x − a_x
```

Las diferencias ofrecen una representación compacta de la superioridad relativa de un equipo sobre otro: un valor positivo de `diff_ppg_season` indica que el local llega con mejor promedio de puntos que el visitante. Si cualquiera de los dos valores falta, la diferencia también falta.

El contrato no define una variable `diff_n_prev_season`: las siete diferencias se limitan a las métricas de rendimiento (Decision Log D20). Lo que sigue es una interpretación de esa decisión, no una justificación escrita en el contrato. `n_prev_season` se utiliza principalmente como variable de control: indica cuánto historial tiene disponible cada equipo, sustenta la regla de elegibilidad y sirve para estudiar la estabilidad de las features. Una diferencia entre los dos conteos podría reflejar también desigualdades de calendario o aplazamientos, más que una diferencia de rendimiento entre los equipos. Por ese motivo no forma parte del feature set v0.1.

### 11.6 Valores iniciales nulos y ausencia de imputación

En el primer partido de la temporada ningún equipo tiene historial previo, de modo que `n_prev_season` vale cero y no es posible calcular ninguna tasa: dividir entre cero partidos no tiene sentido. En esos casos las features quedan **ausentes** y el contrato prohíbe imputarlas.

La decisión es intencionada. Rellenar esos huecos con, por ejemplo, el promedio de la liga o los valores de la temporada anterior equivaldría a introducir información que el contrato no contempla y, en algunos casos, información de otras temporadas que la regla de reinicio excluye. En lugar de imputar, las filas sin historial suficiente se marcan como no elegibles para el modelado (sección 14), pero se conservan.

---

## 12. Temporalidad y prevención de data leakage

### 12.1 Qué es data leakage en SCOPE

Se habla de *data leakage* cuando un modelo utiliza, durante su construcción, información que no estaría disponible en el momento real de hacer una predicción. En un problema de predicción deportiva el riesgo es especialmente alto, porque la mayor parte de los datos disponibles describen el partido después de jugarse.

Las formas más habituales en SCOPE serían:

- **target leakage:** usar el resultado del propio partido, o variables derivadas de él, para predecirlo;
- **uso de estadísticas POST del mismo partido:** por ejemplo, predecir el resultado a partir de los tiros a puerta del propio encuentro;
- **look-ahead bias:** calcular variables con partidos posteriores, como un promedio de la temporada completa;
- **filtración en el ajuste del modelo:** estandarizar o seleccionar variables usando datos de validación o de prueba.

Un modelo con leakage suele obtener métricas muy buenas durante el desarrollo, y precisamente por eso es peligroso: el error no se manifiesta hasta que el modelo se enfrenta a partidos realmente futuros. El contrato dedica diez reglas temporales, T1 a T10, a impedirlo. A continuación se explica la lógica de cada grupo.

### 12.2 Solo partidos estrictamente anteriores

Las features de un partido solo pueden construirse con partidos cuyo momento de inicio sea **estrictamente anterior** al del partido que se predice (T1). La desigualdad estricta importa: un partido que empieza a la misma hora no puede formar parte del historial, porque su resultado tampoco se conocería en el momento de la predicción.

Además, en v0.1 solo cuentan partidos de liga de la **misma competición** (T2) y de la **misma temporada** (T3). La primera condición evita mezclar partidos de copas o de otras ligas, que no están en el alcance; la segunda refleja la decisión de reiniciar el historial cada temporada, que se explica en la sección 13.

### 12.3 Nada del propio partido

Ningún campo POST, TARGET o MARKET del partido que se predice puede participar en sus propias features (T4). Esta regla es la traducción directa de la clasificación de variables de la sección 8, pero conviene distinguir qué ocurre con cada categoría después de jugado el partido:

- los campos POST y los resultados observados del partido `t` —goles, estadísticas, puntos obtenidos— sí pueden contribuir a las features históricas de los partidos *posteriores* de esos equipos, pero nunca a las del propio `t`;
- los campos MARKET no participan en FEATURES en ningún caso: ni en las del propio partido ni en las de partidos posteriores. Las cuotas se reservan exclusivamente para el benchmark de mercado (T7 y Estrategia C, sección 10).

Esta idea se resume en una garantía que el contrato formula de manera muy clara: **modificar el resultado o las estadísticas de un partido no debe cambiar ninguna de las features usadas para predecirlo**; solo puede afectar a las features de partidos posteriores.

### 12.4 Una única frontera temporal: `kickoff_datetime`

El orden temporal lo define exclusivamente `kickoff_datetime`, la fecha y hora de inicio del partido (T5). No pueden usarse como frontera temporal:

- el orden físico de las filas en el archivo;
- la posición de la fila en RAW (`source_row`);
- la jornada del calendario;
- el orden auxiliar `match_seq_season`.

Cada una de estas alternativas falla por un motivo concreto. El orden de las filas depende de cómo la fuente organizó el archivo, no de cuándo se jugaron los partidos. La jornada no refleja el orden real cuando hay aplazamientos: un partido de la jornada 10 puede disputarse después de uno de la jornada 15. Y `match_seq_season`, aunque está ordenado por fecha de inicio, desempata los partidos que empiezan a la misma hora mediante el identificador alfabético, lo cual no implica que uno ocurriera antes que el otro. Solo `kickoff_datetime` expresa el momento real en que un partido comenzó.

### 12.5 Acumulados desplazados

Todos los acumulados y ventanas se calculan sobre `team_match_log`, ordenado por equipo y fecha de inicio, con un desplazamiento equivalente a `shift(1)` por equipo y temporada (T6). En términos prácticos, el valor asociado a un partido se calcula con los partidos anteriores y excluye siempre el propio partido. Después, los resultados se reconstruyen a una fila por partido a través de `match_id`.

Este desplazamiento es el mecanismo técnico que hace cumplir T1 y T4 al mismo tiempo: si un acumulado incluyera la fila actual, estaría incorporando el resultado del propio partido a su predicción.

### 12.6 Cuotas fuera de FEATURES

Las cuotas no son features en v0.1 (T7). Son información de mercado que se reserva para el benchmark, como se explicó en la sección 10.

### 12.7 Ajustes solo con datos de entrenamiento

La temporalidad no termina en el cálculo de las features: también afecta al entrenamiento. Toda transformación o decisión que se "aprenda" de los datos —el escalado de variables, la selección de features, los hiperparámetros— debe ajustarse exclusivamente con los datos de entrenamiento, y la validación principal debe ser temporal, nunca aleatoria (T8).

Una división aleatoria mezclaría partidos de distintas épocas entre entrenamiento y prueba, de modo que el modelo podría entrenarse con partidos posteriores a los que luego evalúa. Una división temporal reproduce la situación real: se entrena con el pasado y se evalúa con el futuro.

### 12.8 Prohibición de agregados de temporada completa

Queda prohibido usar como feature cualquier agregado calculado sobre la temporada completa o sobre periodos posteriores al partido (T9). Un ejemplo sería el promedio de goles de un equipo en toda la temporada: en la jornada 5 ese número todavía no existe, porque depende de partidos que no se han jugado. Es una de las formas de look-ahead bias más fáciles de introducir sin darse cuenta.

### 12.9 Partidos finalizados frente a partidos comenzados

En v0.1 todas las features usan el historial del **mismo equipo**, y como un equipo no juega dos partidos de liga a la vez, basta con exigir que sus partidos previos hayan empezado antes. El contrato anticipa, sin embargo, que en el futuro podrían definirse features que dependan de partidos de **otros** equipos, por ejemplo la posición en la tabla. En ese caso, haber comenzado antes no será suficiente: un partido que empezó una hora antes pero todavía se está jugando no tiene resultado conocido. La condición pasará a ser que esos partidos hayan **finalizado** antes del inicio del partido que se predice (T10).

Relacionada con esto, el contrato establece una hipótesis operativa: ningún equipo tiene dos partidos de liga simultáneos. Si apareciera un caso incompatible con ella —partidos suspendidos, abandonados o un equipo con dos partidos a la misma hora—, debería detectarse y bloquear la validación o documentarse explícitamente.

### 12.10 Ejemplo conceptual

El contrato ilustra estas reglas con un ejemplo sencillo. Supóngase que el Arsenal recibe al Chelsea el 20 de octubre y que se trata de su noveno partido de liga.

- `h_ppg_season` se calcula con los partidos 1 a 8 del Arsenal. El resultado del partido del 20 de octubre no interviene.
- Si el Chelsea tiene un partido aplazado y solo ha jugado 7, su `a_ppg_season` se calcula con esos 7. Como se trata de una tasa por partido, la comparación con el Arsenal sigue siendo equilibrada.
- `h_sot_pg_last5` promedia los tiros a puerta del Arsenal en sus partidos 4 a 8, los cinco más recientes.
- Los tiros a puerta y el resultado del propio partido del 20 de octubre solo aparecerán en las features del décimo partido del Arsenal.

Visto como una línea de tiempo:

```
Arsenal:  P1  P2  P3  P4  P5  P6  P7  P8  │ P9 (20/10)   P10
          └──────── season ────────────┘  │  partido
                      └──── last5 ─────┘  │  a predecir
                                          │
                        frontera: kickoff_datetime del P9
```

Todo lo que está a la izquierda de la frontera puede usarse; el propio P9 y todo lo que está a su derecha, no.

### 12.11 Disciplina sobre el conjunto de prueba

La temporalidad también tiene una dimensión metodológica más amplia. La temporada 2025/26 se reserva como conjunto de prueba final de v0.1. El contrato reconoce con honestidad que no es un test completamente ciego, ya que algunas estadísticas descriptivas agregadas de esa temporada se observaron antes de fijar esta política. Por ello establece una disciplina explícita: 2025/26 solo puede utilizarse en análisis descriptivos con fines de documentación, y nunca para tomar decisiones de diseño —seleccionar features, elegir el burn-in, escoger modelos, ajustar hiperparámetros o calibración— con el objetivo de mejorar los resultados sobre esa temporada. El análisis exploratorio que oriente decisiones de modelado debe usar únicamente las temporadas de desarrollo, de 2021/22 a 2024/25.

La construcción de FEATURES sigue una lógica secuencial compatible con una evaluación *walk-forward*. El protocolo final de entrenamiento, reentrenamiento y calibración se definirá durante la etapa de modelado. Conviene separar lo que ya está fijado de lo que todavía no:

**Ya definido por el contrato:**

- FEATURES se construye secuencialmente, partido a partido en orden de `kickoff_datetime`;
- cada partido utiliza únicamente la historia disponible antes de su inicio;
- dentro de una temporada de validación o prueba, los resultados de partidos ya jugados pueden actualizar las features de los partidos posteriores, igual que ocurriría en la realidad.

**Todavía provisional:**

- la partición exacta entre entrenamiento, validación y prueba (propuesta actual: entrenamiento 2021/22–2023/24, validación 2024/25 y prueba 2025/26; Decision Log P06, provisional);
- la frecuencia de reentrenamiento, si la hubiera;
- la estrategia de calibración;
- el protocolo final de actualización del modelo.

Que las features se actualicen con resultados ya conocidos no implica, por tanto, que el modelo se reentrene tras cada partido.

---

## 13. Reinicio por temporada

En v0.1 no se transporta ninguna información de una temporada a la siguiente. Al comenzar cada temporada se reinician:

- el número de partidos jugados;
- los puntos acumulados;
- las tasas por partido;
- las estadísticas acumuladas;
- las ventanas de forma reciente.

En la primera jornada todos los equipos parten de cero, como si no existiera historial previo.

Una consecuencia directa es que los **equipos ascendidos** reciben el mismo tratamiento que los demás. No hace falta buscar información externa, como sus resultados en la Championship, porque ningún equipo usa información de la temporada anterior. El tratamiento es homogéneo y no depende de fuentes adicionales.

Es importante subrayar que se trata de una **decisión del MVP** y no de una afirmación sobre el fútbol. Nadie sostiene que la temporada anterior sea irrelevante para predecir la siguiente; de hecho, la memoria entre temporadas y los sistemas de puntuación como Elo figuran entre las mejoras pospuestas, y Elo está señalado como una de las primeras candidatas. El reinicio se adopta porque simplifica las reglas, evita decidir cómo ponderar el pasado o cómo tratar a los equipos ascendidos, y deja un punto de partida claro con el que comparar mejoras futuras.

---

## 14. Elegibilidad para modelado

Las features de los primeros partidos de cada temporada se calculan con muy poco historial. Tras un único partido, el promedio de puntos de un equipo solo puede valer 0, 1 o 3; tras dos, sigue dependiendo casi por completo de uno o dos resultados aislados. Esos valores son legítimos, pero estas estimaciones presentan una variabilidad elevada y representan de forma poco estable el rendimiento del equipo cuando existe muy poco historial.

Para gestionarlo, el contrato introduce un periodo de *burn-in* mediante la siguiente regla:

```
is_modeling_eligible = min(h_n_prev_season, a_n_prev_season) ≥ 3
```

Un partido es elegible para el modelado solo si **ambos** equipos han jugado al menos tres partidos de liga previos en la temporada. Se usa el mínimo porque basta con que uno de los dos equipos tenga un historial insuficiente para que las features del partido sean poco fiables.

Varias precisiones son importantes:

- **Las filas no elegibles no se eliminan.** Permanecen en FEATURES y, por supuesto, en CANONICAL; simplemente se excluyen del entrenamiento y la evaluación mediante el indicador. Esto permite cambiar el criterio sin reconstruir ninguna capa.
- **El umbral de 3 está aprobado para v0.1 (D48).** Tras el análisis de estabilidad del EDA (E7), P01 quedó cerrada y el burn-in v0.1 es `k = 3`, por parsimonia y no como óptimo matemático. Se conserva `n_prev_season`, que permite análisis de sensibilidad con otros umbrales (k = 4/5) durante el modelado.
- **Esa comparación debe hacerse con datos de desarrollo.** La elección del umbral es una decisión de diseño y, como tal, no puede basarse en lo observado en la temporada de prueba 2025/26.

---

## 15. Multicolinealidad y representación de features

FEATURES contiene, a propósito, información redundante. Para un mismo concepto guarda la versión del local, la del visitante y su diferencia; y para varias métricas guarda tanto la ventana de temporada como la de forma reciente. Esta redundancia es útil, porque modelos distintos se benefician de representaciones distintas, pero exige reglas claras para no introducir problemas en los modelos lineales. El contrato las recoge en las reglas M1 a M4.

### 15.1 Dependencia lineal entre `h_x`, `a_x` y `diff_x`

Por definición:

```
diff_x = h_x − a_x
```

Esto significa que, conocidas dos de las tres variables, la tercera queda determinada exactamente. Si las tres se introducen a la vez en una regresión lineal, la matriz de diseño tiene columnas linealmente dependientes y los coeficientes no pueden estimarse de forma única: existen infinitas combinaciones que producen exactamente el mismo ajuste. Es un caso de **multicolinealidad perfecta**.

Por eso, en un modelo lineal hay que elegir una de dos representaciones: la **pareada** (`h_x` y `a_x`) o la de **diferencias** (`diff_x`), pero nunca las tres variables juntas (M1). El almacén de features puede conservarlas todas, porque la restricción afecta a la selección de variables de cada modelo, no al almacenamiento.

### 15.2 Por qué no se almacena `gd_pg`

Por el mismo motivo, no se guarda una diferencia de goles por partido: sería exactamente `gf_pg − ga_pg` y añadiría una nueva dependencia lineal perfecta con variables que ya existen (M2). Si un análisis necesitara esa variable, podría derivarla, pero entonces no podría convivir con los goles a favor y en contra en un mismo modelo lineal.

### 15.3 Coincidencia entre season y last5 al inicio

Mientras un equipo ha jugado cinco partidos o menos, su ventana last5 contiene exactamente los mismos partidos que su ventana season, de modo que cada feature de forma reciente es idéntica a su versión de temporada (M3). A partir del sexto partido empiezan a diferenciarse.

Esto tiene una consecuencia estadística: en esas filas la correlación entre ambas familias será perfecta, lo que inflará la correlación global entre ellas. El EDA deberá medirla, por ejemplo mediante el factor de inflación de la varianza (VIF) y estratificando por `n_prev_season`, y podría justificar conservar solo una de las dos familias en algunos modelos.

### 15.4 Feature subset explícito

Finalmente, cada modelo debe declarar de forma explícita qué subconjunto de features utiliza (M4). En el caso de la regresión lineal de Matemáticas, ese subconjunto debe evitar combinaciones linealmente dependientes. Esta regla convierte la gestión de la redundancia en una decisión documentada y verificable, en lugar de dejarla a criterio implícito de cada análisis.

Un ejemplo de esta lógica aparece en la propuesta para Complejidad Computacional, donde se plantean dos representaciones: una de cinco dimensiones basada en diferencias y otra de diez basada en las versiones separadas del local y el visitante. El contrato advierte que no contienen la misma información, porque la diferencia pierde los niveles absolutos de cada equipo, y que por tanto un cambio de rendimiento entre ambas no puede atribuirse únicamente al cambio de dimensionalidad. Esa propuesta es provisional y está sujeta al EDA.

---

## 16. Alcance de SCOPE v0.1

El contrato delimita expresamente lo que v0.1 incluye y lo que deja fuera. Esta delimitación forma parte del diseño tanto como las reglas positivas.

**Incluido en v0.1:**

- una única competición, la Premier League;
- cinco temporadas históricas, de 2021/22 a 2025/26;
- una única fuente, Football-Data.co.uk;
- historial reiniciado al comienzo de cada temporada;
- ocho métricas por equipo, sus versiones local y visitante y sus diferencias.

**Fuera de v0.1:**

- **Features y modelado:** Elo; posición en la tabla; enfrentamientos directos (H2H); ventanas de diez partidos; rendimiento separado como local y como visitante; días de descanso; efecto del árbitro; memoria entre temporadas; modelos de tipo Skellam.
- **Mercado:** cuotas como predictores; mercados de más/menos goles y hándicap asiático; cuotas de casas individuales en CANONICAL; estrategias de apuesta.
- **Datos externos:** xG; lesiones; alineaciones; datos de la Championship; deducciones de puntos; la fuente complementaria que se obtendrá mediante web scraping, todavía sin elegir.
- **Alcance temporal y geográfico:** la temporada 2026/27 y el registro de fixtures futuros; otras ligas, copas y deportes; zona horaria explícita.
- **Sistemas:** esquema SQL completo, APIs, automatización y despliegue.

Estar fuera del MVP no significa que estas variables o capacidades sean inútiles. Varias de ellas, como Elo, xG o la información sobre lesiones, son candidatas razonables a aportar información adicional, algo que tendría que comprobarse empíricamente en versiones futuras. Se posponen porque cada una añade fuentes, decisiones y riesgos de leakage que habría que validar, y el objetivo de v0.1 es disponer primero de un sistema pequeño, completo y reproducible sobre el que esas mejoras puedan medirse con rigor.

---

## 17. Limitaciones arquitectónicas conocidas

Conviene distinguir tres conceptos que a menudo se confunden:

- una **limitación** es una restricción conocida del diseño que se acepta conscientemente porque no afecta al alcance actual;
- una **decisión de alcance** es una elección deliberada de no incluir algo en esta versión;
- un **error** es un comportamiento que contradice lo que el sistema debería hacer.

Lo que se describe a continuación son limitaciones o decisiones de alcance documentadas, no errores.

| Aspecto | Tipo | Descripción |
|---|---|---|
| `match_id` depende de la fecha real | Limitación | Para datos históricos es estable, pero un partido futuro aplazado cambiaría de identificador. |
| Identidad de fixtures futuros | Limitación | Predecir partidos no jugados requeriría un registro de fixtures con identificador asignado la primera vez que se conoce el partido. Está fuera de v0.1. |
| Sin historia entre temporadas | Decisión de alcance | Al reiniciar el historial, las features del inicio de temporada no aprovechan lo ocurrido en la anterior. |
| Burn-in de 3 partidos | Decisión aprobada (D48) | Burn-in v0.1 = `k = 3`; P01 cerrada tras el EDA E7. Se permiten análisis de sensibilidad (k = 4/5) solo con datos de desarrollo. |
| Ventana last5 | Decisión provisional | Su longitud y su redundancia con la ventana de temporada se evaluarán en el EDA. |
| `goal_difference` como respuesta | Decisión provisional | Su idoneidad para la regresión lineal debe validarse metodológicamente. |
| Hora sin zona horaria | Decisión provisional | Suficiente con una sola liga y una sola fuente; deberá definirse una zona al incorporar otras. |
| Hora de captura de las cuotas de cierre | Limitación de la fuente | No está documentada, por lo que no se asume que el cierre tenga la misma información temporal que las predicciones. |
| Alcance del MVP | Decisión de alcance | Una liga, una fuente y un conjunto reducido de features. |

Ninguno de estos puntos invalida los resultados de v0.1 dentro de su alcance. Todos están identificados y tienen una vía de revisión prevista.

---

## 18. Escalabilidad futura

La escalabilidad de SCOPE no procede de haber construido ya componentes para el futuro, sino de cómo están definidas las fronteras de su arquitectura actual. Varias decisiones del contrato hacen posible crecer sin alterar la lógica central:

- **Cada fuente entra por su propia RAW e INTERIM.** Una fuente nueva, como la que se obtendrá mediante web scraping en R, se incorporaría con su propia copia inmutable y su propia capa de preparación, sin tocar las de Football-Data.
- **La integración se hace mediante identidades internas.** Los datos de una nueva fuente se enlazan con los existentes a través de `team_id` y de la clave natural del partido, no a través de nombres o códigos de un proveedor. Basta con añadir los alias de la nueva fuente al mapeo de equipos.
- **El sistema no depende de la nomenclatura de Football-Data.** A partir de CANONICAL, todos los nombres de campos y de equipos son propios de SCOPE. Cambiar o añadir fuentes no obliga a reescribir las capas posteriores.
- **Nuevas competiciones encajan en la clave existente.** La clave natural ya incluye la competición y la fecha, de modo que podría acoger otras ligas o copas sin rediseñarse.
- **Nuevos modelos consumen la misma capa.** Cualquier modelo futuro puede leer FEATURES, declarar su propio subconjunto de variables y registrarse en MODELS, sin modificar las capas de datos.
- **Las features están versionadas.** Añadir o redefinir variables genera una nueva versión de FEATURES y deja intactos los hechos observados de CANONICAL.

El contrato no define todavía una versión 0.2 ni el diseño concreto de ninguna de estas ampliaciones; lo que hace es asegurar que, cuando lleguen, puedan añadirse sobre lo existente en lugar de sustituirlo.

---

## 19. Resumen de decisiones arquitectónicas

La arquitectura de datos de SCOPE v0.1 se apoya en un conjunto reducido de decisiones que se refuerzan entre sí:

- **Separación por capas.** Cada etapa del pipeline tiene una única responsabilidad y produce una capa nueva sin modificar la anterior.
- **Inmutabilidad de RAW.** Los datos originales se conservan intactos y verificables, y actúan como evidencia de origen.
- **Trazabilidad.** Cada partido procesado puede rastrearse hasta el archivo y la fila de los que procede.
- **Identidad estable.** Partidos y equipos tienen identificadores internos deterministas e independientes de la fuente, congelados para esta versión.
- **Diferencia entre datos observados y features.** CANONICAL guarda lo que ocurrió; FEATURES guarda lo que se sabía antes, como resultado de decisiones de modelado versionadas.
- **Temporalidad estricta.** Solo se usa información de partidos iniciados estrictamente antes, con `kickoff_datetime` como única frontera temporal y acumulados desplazados que excluyen el propio partido.
- **Prevención de data leakage.** La clasificación de variables, las reglas T1–T10, el ajuste exclusivo sobre datos de entrenamiento y la disciplina sobre el conjunto de prueba cierran las vías por las que podría filtrarse información futura.
- **Separación entre mercado y predictores.** Las cuotas sirven como benchmark externo y no como entrada del modelo, lo que permite medir lo que aporta la información deportiva por sí sola.
- **Reproducibilidad.** Reglas de serialización y construcción deterministas permiten regenerar exactamente los mismos datos a partir de RAW.
- **Escalabilidad.** Nuevas fuentes, competiciones y modelos pueden incorporarse a través de las identidades internas y de capas propias, sin rehacer lo ya construido.

En conjunto, el Data Contract funciona como la **base metodológica** de SCOPE. Antes de explorar los datos, entrenar un modelo o diseñar una base de datos, define qué es un partido, qué es un equipo, qué se sabe en cada momento y qué no puede utilizarse nunca. Las fases posteriores del proyecto —el análisis exploratorio, la regresión de Matemáticas, los modelos de clasificación, los experimentos de Complejidad Computacional, la base de datos relacional y la aplicación en Java— se construyen sobre esas reglas, y la validez de sus resultados depende de que se respeten.
