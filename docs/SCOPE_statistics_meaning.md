

Sí. Esta duda es muy importante porque, si entiendes bien **qué representa cada tipo de dato**, prácticamente entiendes el corazón de SCOPE.

La forma más útil de verlo es separar nuestros datos en **4 grupos**:

1. datos que identifican el partido;
2. datos que describen lo que ocurrió en el partido;
3. datos que queremos predecir;
4. datos históricos que sí usaremos para predecir.

Y hay una distinción fundamental:

> **No todo lo que tenemos en el dataset se usa como predictor.**

Ese es probablemente el concepto más importante de todos.

---

## 1. Primero: ¿qué representa una fila?

En nuestros datos principales, una fila representa **un partido**.

Por ejemplo:

`Arsenal vs Chelsea Fecha: 15/03/2025 Local: Arsenal Visitante: Chelsea Marcador: 2-1 Resultado: H`

En SCOPE, H, D y A significan:

- H = Home win → gana el local
- D = Draw → empate
- A = Away win → gana el visitante

Entonces un registro real conceptualmente sería algo así:

|home_team|away_team|home_goals|away_goals|result|
|---|---|--:|--:|---|
|Arsenal|Chelsea|2|1|H|
|Liverpool|Everton|1|1|D|
|Wolves|Man City|0|3|A|

Esto es el punto de partida.

---

# 2. Datos de identificación

Tenemos información que sirve para saber **qué partido es**, pero no necesariamente para predecirlo.

Por ejemplo:

`match_id season match_date kickoff_datetime home_team_id away_team_id home_team_name away_team_name referee`

Podemos imaginar:

`match_id: EPL_2024-2025_20250315_arsenal_chelsea season: 2024-2025 home_team: Arsenal away_team: Chelsea`

Estos datos son importantes para:

- identificar el partido;
- ordenar cronológicamente;
- relacionar tablas;
- calcular estadísticas históricas;
- evitar utilizar información del futuro.

Pero **no porque una columna exista significa que la vamos a meter al modelo**.

Por ejemplo, match_id evidentemente no tiene sentido como predictor.

---

# 3. Datos POST: lo que ocurrió durante el partido

Aquí tenemos muchas de las columnas originales de Football-Data.

Por ejemplo:

### Goles

`home_goals away_goals`

Ejemplo:

`Arsenal 2 - Chelsea 1`

Entonces:

`home_goals = 2 away_goals = 1`

---

### Tiros

`home_shots away_shots`

Podríamos tener:

`Arsenal: 15 tiros Chelsea: 9 tiros`

---

### Tiros a puerta

`home_shots_on_target away_shots_on_target`

Por ejemplo:

`Arsenal: 6 Chelsea: 3`

---

### Otras estadísticas

También tenemos:

`corners fouls yellow cards red cards`

tanto para el local como para el visitante.

Conceptualmente:

`home_corners away_corners home_fouls away_fouls home_yellow_cards away_yellow_cards`

---

# 4. Pero aquí viene algo MUY importante

Estas estadísticas son **POST-match**.

Es decir:

> las conocemos después de que ocurrió el partido.

Por lo tanto, no podemos hacer esto:

`Quiero predecir Arsenal vs Chelsea Uso: home_goals = 2 home_shots = 15 home_shots_on_target = 6`

porque esos datos **todavía no existían antes de jugar el partido**.

Eso sería data leakage.

Sería prácticamente decir:

> “Voy a predecir quién ganó el partido utilizando el marcador del partido.”

No tendría sentido.

---

# 5. Entonces, ¿para qué conservamos esos datos?

Porque los partidos anteriores sí pueden generar información útil para partidos futuros.

Aquí empieza realmente SCOPE.

Supongamos que Arsenal va a jugar mañana.

Podemos mirar lo que Arsenal hizo **antes de mañana**.

Por ejemplo:

`Partidos anteriores de Arsenal Arsenal 3-1 ... Arsenal 2-0 ... Arsenal 1-1 ... Arsenal 2-2 ... Arsenal 4-0 ...`

A partir de eso calculamos estadísticas históricas.

Y esas sí son válidas antes del próximo partido.

---

# 6. Nuestras variables predictoras importantes

Esta es la parte que probablemente más te interesa para explicársela a tus profesores.

Actualmente tenemos **8 variables históricas por equipo**.

Para el equipo local:

`h_n_prev_season h_ppg_season h_gf_pg_season h_ga_pg_season h_ppg_last5 h_gf_pg_last5 h_ga_pg_last5 h_sot_pg_last5`

Y las mismas para el visitante:

`a_n_prev_season a_ppg_season a_gf_pg_season a_ga_pg_season a_ppg_last5 a_gf_pg_last5 a_ga_pg_last5 a_sot_pg_last5`

Vamos una por una porque entender esto es clave.

---

# 7. n_prev_season

Significa:

> ¿Cuántos partidos ha jugado este equipo antes del partido actual en esta temporada?

Por ejemplo:

`h_n_prev_season = 10`

significa:

> el equipo local ya jugó 10 partidos antes de este.

No mide directamente qué tan bueno es el equipo.

Nos dice **cuánta información histórica tenemos disponible**.

Por eso también es fundamental para el burn-in.

---

# 8. ppg_season

PPG significa:

**Points Per Game**  
Puntos por partido.

En fútbol:

`Victoria = 3 Empate = 1 Derrota = 0`

Supongamos que Arsenal ha jugado 5 partidos:

`W W D L W`

Sus puntos serían:

`3 + 3 + 1 + 0 + 3 = 10`

Entonces:

PPG=10/5=2.0PPG=10/5=2.0

Así:

`h_ppg_season = 2.0`

Nos da una idea de **rendimiento general en la temporada**.

---

# 9. gf_pg_season

GF = Goals For.

Significa:

> goles anotados por partido durante la temporada hasta ese momento.

Si un equipo lleva:

`10 partidos 18 goles`

entonces:

GF/PG=18/10=1.8GF/PG=18/10=1.8

Esto representa su capacidad ofensiva histórica.

---

# 10. ga_pg_season

GA = Goals Against.

Significa:

> goles recibidos por partido.

Si lleva:

`10 partidos 12 goles recibidos`

entonces:

GA/PG=12/10=1.2GA/PG=12/10=1.2

Esto nos da una aproximación de su comportamiento defensivo.

---

# 11. Las variables last5

Luego tenemos otra perspectiva.

En vez de mirar toda la temporada, miramos solamente los **últimos cinco partidos**.

Por ejemplo:

`ppg_last5 gf_pg_last5 ga_pg_last5 sot_pg_last5`

Esto intenta representar la **forma reciente**.

Podemos tener una situación así:

`Manchester City PPG temporada = 2.1 pero PPG últimos 5 = 1.2`

Eso podría indicar que históricamente lleva una buena temporada, pero recientemente está rindiendo peor.

Por eso tenemos ambas ventanas:

`season`

y

`last5`

---

# 12. sot_pg_last5

SOT = Shots On Target.

Es decir:

> tiros a puerta por partido durante los últimos cinco encuentros.

Ejemplo:

`últimos 5: 7, 5, 8, 3, 6 tiros a puerta`

SOT/PG=7+5+8+3+65=5.8SOT/PG=57+5+8+3+6​=5.8

Entonces:

`sot_pg_last5 = 5.8`

Nos da una medida aproximada de actividad ofensiva reciente.

---

# 13. Home y Away

Todas estas variables existen dos veces.

Por ejemplo:

`h_ppg_season a_ppg_season`

La h significa:

> home team.

La a:

> away team.

Entonces un partido podría verse así:

|variable|valor|
|---|--:|
|h_ppg_season|2.10|
|a_ppg_season|1.40|
|h_gf_pg_season|1.90|
|a_gf_pg_season|1.25|
|h_ga_pg_season|0.90|
|a_ga_pg_season|1.50|

Aquí ya empezamos a describir matemáticamente el enfrentamiento.

---

# 14. Y tenemos las variables diff_

Además calculamos la diferencia entre local y visitante.

Por ejemplo:

diff_ppg=h_ppg−a_ppgdiff_ppg=h_ppg−a_ppg

Si:

`h_ppg = 2.1 a_ppg = 1.4`

entonces:

`diff_ppg = 0.7`

Un valor positivo significa que, según esa métrica, el local tiene ventaja.

Un valor negativo significa que el visitante está mejor.

Tenemos diferencias para siete métricas:

`diff_ppg_season diff_gf_pg_season diff_ga_pg_season diff_ppg_last5 diff_gf_pg_last5 diff_ga_pg_last5 diff_sot_pg_last5`

No hacemos diff_n_prev porque la cantidad de historial tiene otra función.

---

# 15. Entonces, ¿qué queremos predecir?

Nuestro objetivo principal de Machine Learning es:

`result`

con tres categorías:

`H D A`

Por ejemplo, el modelo eventualmente podría decir:

`Arsenal vs Chelsea P(H) = 0.52 P(D) = 0.27 P(A) = 0.21`

No queremos simplemente:

> “Arsenal gana.”

Queremos probabilidades.

Ese es un punto muy bueno para explicar a un profesor.

---

# 16. ¿Y qué es goal_difference?

Tenemos otro target:

`goal_difference`

que se calcula:

home_goals−away_goalshome_goals−away_goals

Ejemplos:

`3-1 → +2 1-1 → 0 0-2 → -2`

Entonces:

`positivo → ganó local 0 → empate negativo → ganó visitante`

Este target será especialmente importante para Matemáticas Aplicadas.

Ahí nuestro problema cambia un poco.

En ML:

`result H / D / A`

es un problema de **clasificación**.

En Matemáticas:

`goal_difference`

es una variable numérica y podemos estudiarla mediante **regresión lineal múltiple**.

---

# 17. Draw no es una variable de entrada

Esto vale la pena aclararlo porque mencionaste “home, away, draw”.

Draw no es algo como:

`draw = 0.35`

en nuestros datos históricos.

Forma parte de la variable objetivo:

`result = D`

Es decir:

`H = ganó el local D = empate A = ganó el visitante`

Más adelante el modelo producirá:

`P(H) P(D) P(A)`

---

# 18. Tenemos también cuotas del mercado

En CANONICAL conservamos:

`mkt_avg_pre_home mkt_avg_pre_draw mkt_avg_pre_away mkt_avg_close_home mkt_avg_close_draw mkt_avg_close_away`

Son cuotas promedio.

Por ejemplo:

`Home = 1.80 Draw = 3.50 Away = 4.60`

Pero esto es otra distinción extremadamente importante:

> **Las cuotas NO serán predictors del modelo principal de SCOPE v0.1.**

Las vamos a utilizar como **benchmark**.

Queremos comparar:

`SCOPE vs Mercado`

No:

`Mercado → predictor de SCOPE`

porque entonces sería mucho más difícil saber qué capacidad predictiva proviene de nuestros datos deportivos y cuál simplemente estamos heredando de las casas de apuestas.

---

# 19. Entonces nuestro esquema mental completo es este

Podrías imaginártelo así:

`PARTIDOS HISTÓRICOS │ ├── goles ├── puntos ├── tiros a puerta │ ▼ HISTORIAL DEL EQUIPO │ ├── PPG temporada ├── GF/PG temporada ├── GA/PG temporada ├── PPG últimos 5 ├── GF/PG últimos 5 ├── GA/PG últimos 5 └── SOT/PG últimos 5 │ ▼ LOCAL vs VISITANTE │ ├── h_features ├── a_features └── diff_features │ ▼ MODELO │ ▼ P(H), P(D), P(A)`

Eso es básicamente **SCOPE en una imagen mental**.

---

# 20. ¿Cuáles son nuestros datos más importantes?

Si mañana un profesor te preguntara:

> “¿Con qué variables están trabajando?”

yo priorizaría estas:

|Tipo|Variables principales|Función|
|---|---|---|
|Identidad|equipos, fecha, temporada|identificar y ordenar partidos|
|Rendimiento temporada|PPG, GF/PG, GA/PG|nivel acumulado|
|Forma reciente|PPG, GF/PG, GA/PG últimos 5|rendimiento reciente|
|Ataque reciente|SOT/PG last5|actividad ofensiva|
|Comparación|diff_*|ventaja relativa local-visitante|
|Target ML|H/D/A|resultado a predecir|
|Target Matemáticas|goal difference|regresión|
|Mercado|cuotas 1X2|benchmark externo|

Esta tabla te sirve muchísimo para una explicación oral.

---

# 21. Una forma sencilla de explicárselo a los profesores

Puedes decir algo como:

> “SCOPE utiliza cinco temporadas históricas de la Premier League. De cada partido tenemos información como equipos, fecha, goles, tiros, tiros a puerta, córneres, faltas y tarjetas. Sin embargo, esas estadísticas del mismo partido no se utilizan para predecirlo porque eso provocaría data leakage. En su lugar, para cada partido calculamos el rendimiento que cada equipo tenía antes de jugarlo: puntos por partido, goles anotados y recibidos por partido, forma de los últimos cinco encuentros y tiros a puerta recientes. Estas métricas se calculan tanto para el local como para el visitante y también como diferencias entre ambos. A partir de ellas, posteriormente queremos estimar las probabilidades de victoria local, empate o victoria visitante.”

Si puedes explicar eso con seguridad, ya estás explicando una parte enorme del proyecto correctamente.

---

## Y fíjate en algo interesante

Por eso todo el trabajo que hicimos con RAW, INTERIM, CANONICAL y team_match_log tenía sentido.

No era solamente “limpiar datos”.

Era transformar:

`¿Qué ocurrió en los partidos?`

en:

`¿Qué se sabía de cada equipo ANTES de cada partido?`

Y esa segunda pregunta es la que necesitamos para poder predecir de forma válida.