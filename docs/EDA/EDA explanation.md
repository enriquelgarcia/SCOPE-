Sí: **el EDA v0.1 de SCOPE ya está oficialmente terminado y aprobado**. Y como me lo pediste desde antes, ahora sí toca explicarte qué hicimos, por qué lo hicimos y qué significa todo esto para el proyecto, sin quedarnos únicamente con “Claude generó tablas y gráficas”.

## 1. ¿Qué era realmente el EDA de SCOPE?

EDA significa **Exploratory Data Analysis** o análisis exploratorio de datos.

En SCOPE no lo utilizamos simplemente para “ver gráficas”. El objetivo fue responder, antes de entrenar modelos:

> **¿Qué datos tenemos, qué tan confiables son, cómo están construidas nuestras features, qué relaciones existen entre ellas, qué decisiones metodológicas podemos justificar y qué problemas debemos dejar explícitamente abiertos para el modelado?**

Esto era especialmente importante porque SCOPE utiliza información temporal. Para predecir un partido \(t\), solo podemos usar información que existía **antes** de ese partido.

Por eso todo el EDA estuvo construido alrededor de una regla fundamental:

\[ \text{feature de }t \quad \text{solo usa partidos con kickoff}<kickoff(t) \]

Si violáramos esto, tendríamos **data leakage**: el modelo estaría “viendo el futuro”.

---

# 2. La base sobre la que hicimos todo

Partimos de 5 temporadas completas de Premier League:

\[ 5\times380=1900\text{ partidos} \]

y construimos el flujo:

\[ RAW \rightarrow INTERIM \rightarrow CANONICAL \rightarrow team\_match\_log \rightarrow FEATURES \]

RAW conserva exactamente lo que vino de Football-Data. INTERIM añade trazabilidad. CANONICAL reduce y normaliza el esquema. `team_match_log` transforma cada partido en dos observaciones, una por equipo. FEATURES contiene exclusivamente las variables que pueden utilizarse posteriormente para modelar.

Una de las mejores decisiones de todo el proyecto fue **congelar el pipeline antes del EDA** mediante D44. Así, durante E0–E11 no estuvimos cambiando los datos cada vez que encontrábamos algo interesante.

Eso hace que los resultados sean reproducibles.

---

# 3. Qué hicimos en cada fase

1. **E0 — Infraestructura del EDA.**  
    No analizamos fútbol todavía. Construimos los scopes, verificaciones de hashes y protecciones de escritura. Aquí definimos quién puede ver qué información. Por ejemplo, TRAIN puede utilizar targets para ciertos análisis; TEST puede describirse, pero nunca puede producir decisiones. Esto evita leakage metodológico.
    
2. **E1 — Estructura y calidad.**  
    Verificamos dimensiones, temporadas, equipos, missingness y flags. Descubrimos que los valores faltantes de FEATURES eran **estructurales**, no errores: al inicio de temporada un equipo todavía no tiene partidos previos. También comprobamos los 13 avisos de calidad y la irregularidad de calendario de 2023/24.
    
    Aquí empezamos a comprender que “missing” no significa automáticamente “dato malo”.
    
3. **E2 — Targets.**  
    Estudiamos qué intentará predecir SCOPE. En TRAIN, aproximadamente:
    
    \[ H=45.8\%,\quad D=22.5\%,\quad A=31.7\% \]
    
    El empate es la clase minoritaria, aunque no existe un desbalance extremo. También estudiamos `goal_difference`, goles y ventaja local. Vimos que los empates se solapan mucho con victorias locales y visitantes cuando observamos features individualmente. Esto ya nos anticipa que **Draw probablemente será la clase más complicada**, pero todavía no lo demostramos multivariadamente.
    
4. **E2m — Mercado de apuestas.**  
    Analizamos las cuotas únicamente como **benchmark externo**, no como predictors. Convertimos cuotas en probabilidades implícitas y eliminamos proporcionalmente el overround:
    
    \[ q_i=\frac1{o_i}, \qquad p_i=\frac{q_i}{\sum q_i} \]
    
    El mercado servirá después como punto de comparación: “¿qué tan buenas son las probabilidades de SCOPE frente al mercado?”. Pero el modelo v0.1 no recibe cuotas.
    
5. **E3 — Distribuciones de features.**  
    Estudiamos PPG, GF/PG, GA/PG, SOT/PG, season, last5, h/a y diff. Aquí apareció un fenómeno muy importante: **al inicio de temporada las tasas son mucho más inestables**. Una media calculada después de 3 partidos naturalmente fluctúa mucho más que después de 25.
    
    También vimos que `last5` es mucho más discreta, porque solo puede construirse con como máximo cinco partidos.
    
6. **E4 — Relaciones.**  
    Analizamos correlaciones predictor–predictor y, solo en TRAIN, predictor–target. Aquí vimos que PPG, GF y GA contienen información relacionada. Los `diff_*` mostraron asociaciones univariadas relativamente fuertes con `goal_difference`, llegando aproximadamente a:
    
    \[ |r|\approx0.41 \]
    
    Pero correlación no implica automáticamente que debamos seleccionar esa feature. Además, las distribuciones de H/D/A siguen solapándose considerablemente.
    
7. **E5 — M1 y dependencia h/a/diff.**  
    Esta fue una de las fases matemáticamente más importantes. Tenemos:
    
    \[ diff_x=h_x-a_x \]
    
    Así que si metemos simultáneamente `h_x`, `a_x` y `diff_x`, la tercera variable ya está determinada exactamente por las otras dos.
    
    Con las siete familias:
    
    \[ HADIFF: 21\text{ columnas},\quad rango=14 \]
    
    Tenemos una **dependencia lineal exacta**, no simplemente una correlación alta. El VIF se vuelve infinito para HADIFF.
    
    Esto originó **D46**: en modelos lineales no regularizados no utilizaremos HADIFF completo. HA y DIFF permanecen como representaciones distintas para experimentar posteriormente.
    
8. **E6 — M3, season vs last5.**  
    Demostramos algo que por construcción parecía obvio, pero necesitábamos formalizar:
    
    mientras un equipo tiene cinco partidos previos o menos,
    
    \[ season=last5 \]
    
    porque `last5` todavía contiene literalmente todo el historial disponible.
    
    Después del quinto partido empiezan a divergir. Fuera de esa zona mantienen correlaciones alrededor de 0.64–0.75, pero ya no son equivalentes.
    
    Para `diff` la condición es más interesante:
    
    \[ \max(h\_n\_prev,a\_n\_prev)\le5 \]
    
    porque ambos equipos tienen que seguir dentro de la zona de identidad.
    
    Esto se formalizó como **D47**.
    
9. **E7 — P01, burn-in.**  
    Esta fase respondió por qué exigimos un mínimo de partidos previos antes de permitir que una observación entre al modelado.
    
    Comparamos:
    
    \[ k=1,2,3,4,5,6 \]
    
    La estabilidad mejora mucho de 1→2 y todavía de manera material en 2→3. A partir de 3, las mejoras son más pequeñas e inciertas, mientras seguimos perdiendo aproximadamente otros 40 partidos DEVX por cada nivel adicional.
    
    Por eso formalizamos:
    
    \[ \min(h\_n\_prev,a\_n\_prev)\ge3 \]
    
    como **D48**.
    
    Esto no significa que 3 sea un número matemáticamente óptimo. Es un **compromiso por parsimonia y rendimientos decrecientes**.
    
10. **E8 — P02 y `last5`.**  
    Aquí ocurrió algo muy interesante porque los datos no confirmaron totalmente nuestra intuición.
    
    `last5` resulta aproximadamente **4 veces más responsiva** que `season`: cambia mucho más cuando llega un partido nuevo.
    
    Pero:
    
    \[ \text{más responsiva}\neq\text{más predictiva} \]
    
    En TRAIN, `season` mostró una asociación univariada mayor con el siguiente partido que `last5` para PPG y GF. Además:
    
    \[ last5-season \]
    
    casi no mostró persistencia en el siguiente partido.
    
    Esto sugiere que parte de lo que `last5` captura podría ser **variación transitoria o ruido**, no necesariamente “momentum”.
    
    Pero como todo E8 fue univariado, tampoco podemos decir que `last5` sea inútil. Podría aportar información adicional dentro de un modelo que ya conoce `season`.
    
    Por eso **P02 sigue abierta**. Durante modelado habrá que comparar:
    
    \[ season \quad\text{vs}\quad season+last5 \]
11. **E9 — Q01, anomalía AS/AST.**  
    Encontramos:
    
    \[ AS=8,\quad AST=9 \]
    
    lo cual viola:
    
    \[ AST\le AS \]
    
    El punto metodológico importante fue entender que esto **no demuestra que AST esté mal**. Podría estar equivocado AS, AST o ambos.
    
    La anomalía ya estaba en RAW, así que el pipeline no la creó. Solo afecta cinco partidos posteriores de West Ham mediante SOT last5, tres de ellos elegibles.
    
    Como no sabemos cuál es el valor verdadero, decidimos **no inventarlo**.
    
    Esto originó **D49**:
    
    > conservar valores fuente + flag, RAW inmutable.
    
    Es una gran lección de calidad de datos: detectar un dato incompatible no significa tener suficiente información para corregirlo.
    
12. **E10 — Drift temporal.**  
    Estudiamos si las distribuciones cambian entre temporadas usando principalmente SMD y KS.
    
    El **SMD** mide cuánto cambia la media respecto a la dispersión:
    
    \[ SMD=\frac{\bar x_B-\bar x_A}{s_{pooled}} \]
    
    El **KS** observa la mayor separación entre las distribuciones acumuladas:
    
    \[ KS=\max_x|F_A(x)-F_B(x)| \]
    
    Encontramos un nivel particularmente alto de GF/GA/SOT en 2023/24. TRAIN→VALIDATION presenta desplazamientos de medias muy pequeños:
    
    \[ |SMD|\le0.030 \]
    
    En cambio, 2025/26 presenta niveles más bajos y distribuciones más concentradas en varias features.
    
    Pero esto es fundamental:
    
    > **No cambiamos absolutamente nada debido a TEST.**
    
    Solo documentamos el drift para poder interpretar posteriormente el rendimiento final.
    
13. **E11 — Síntesis.**  
    Finalmente reunimos todo E0–E10 en un documento formal, tablas de trazabilidad y un handoff hacia ML.
    
    E11 no buscó resultados nuevos. Su función fue responder:
    
    > “Después de todo este trabajo, ¿qué sabemos, qué decidimos y qué sigue pendiente?”
    

---

# 4. Las cuatro decisiones principales que dejó el EDA

|Decisión|Qué resolvió|Resultado|
|---|---|---|
|**D46**|h/a/diff|No HADIFF completo en lineales no regularizados; HA y DIFF siguen candidatas|
|**D47**|season vs last5|Son idénticas solo en la zona inicial; después son distintas|
|**D48**|burn-in|`k=3` oficial para v0.1|
|**D49**|Q01|conservar fuente + flag; no inventar reparación|

Fíjate en algo importante: **ninguna de estas decisiones dice cuál será el mejor modelo**.

Son decisiones sobre la **validez metodológica de los datos y representaciones**.

---

# 5. Lo que todavía NO sabemos

El EDA terminó, pero SCOPE no terminó.

Siguen abiertas varias preguntas.

**P02** pregunta si `last5` aporta valor incremental. E8 no pudo resolverlo porque necesitamos comparar modelos.

**P04** trata los subconjuntos de features y dimensionalidades.

**P03** corresponde a `goal_difference` como respuesta de la regresión lineal de Matemáticas.

**P06** mantiene provisionalmente nuestro split temporal:

\[ TRAIN=21/22-23/24 \]\[ VALIDATION=24/25 \]\[ TEST=25/26 \]

**P07** sigue relacionada con la política de zona horaria.

Y C01–C06 son cuestiones que todavía dependen de confirmación docente.

Esto es bueno: un EDA serio **no tiene que cerrar absolutamente todas las preguntas**.

---

# 6. TRAIN, VALIDATION y TEST: una de las cosas más importantes que debes entender

Tenemos tres funciones distintas.

**TRAIN** sirve para aprender y tomar decisiones.

**VALIDATION** sirve para comparar opciones, representaciones, hiperparámetros, etc.

**TEST** debe representar el examen final.

Conceptualmente:

\[ TRAIN \rightarrow aprender \]\[ VALIDATION \rightarrow elegir \]\[ TEST \rightarrow evaluar una sola vez al final \]

Aunque durante el EDA describimos TEST, D42 prohíbe utilizar lo que vimos ahí para cambiar modelos, features o protocolo.

Por eso E10 podía decir:

> “2025/26 tiene distribuciones diferentes”.

Pero no:

> “entonces cambiemos esta feature”.

Ese límite protege la honestidad de la evaluación final.

---

# 7. Qué es el VIF y por qué apareció

El VIF intenta medir cuánto puede reconstruirse una variable usando las demás.

Conceptualmente:

\[ VIF_j=\frac{1}{1-R_j^2} \]

Si otra combinación de columnas reconstruye perfectamente una variable:

\[ R^2=1 \]

entonces:

\[ VIF=\infty \]

Eso pasó con HADIFF porque:

\[ h=a+diff \]

La información está repetida algebraicamente.

Esto importa especialmente en regresiones lineales porque los coeficientes dejan de tener una solución única.

---

# 8. Qué significa realmente `season` vs `last5`

Puedes pensar en ellas así.

`season` es una memoria larga:

\[ \frac{\text{todo lo ocurrido hasta ahora}}{n} \]

Cada nuevo partido pesa cada vez menos.

`last5` es una memoria corta:

\[ \frac{\text{últimos cinco partidos}}{5} \]

Cuando entra un partido nuevo, sale uno viejo.

Por eso last5 responde mucho más rápido.

Pero E8 nos enseñó una distinción fundamental:

> **Una señal que se mueve mucho no necesariamente sabe más.**

Puede estar siguiendo cambios reales, ruido, o una mezcla de ambos.

El modelado nos dirá si conocer `last5` además de `season` mejora realmente las probabilidades.

---

# 9. Qué significa el burn-in

Imagínate un equipo después de un único partido.

Si ganó 3-0:

\[ PPG=3 \]\[ GF/PG=3 \]\[ GA/PG=0 \]

¿Significa eso que es un equipo que promediará 3 puntos y 3 goles durante toda la temporada?

Probablemente no.

Tiene una muestra demasiado pequeña.

Conforme aumenta \(n\), la estimación se estabiliza.

El burn-in fue nuestra manera de decir:

> “No quiero que el modelo trate como fiables estimaciones construidas con prácticamente ningún historial.”

E7 mostró que exigir hasta 3 partidos ofrece una mejora importante, mientras que exigir 4 o 5 comienza a producir rendimientos decrecientes.

De ahí D48.

---

# 10. Qué aprendimos sobre los empates

Los draws representan aproximadamente 22.5 % de TRAIN.

Pero el problema no es únicamente que haya menos.

E4 mostró que, usando features individualmente, las distribuciones de los empates se superponen bastante con H y A.

Eso significa que no tenemos una regla simple tipo:

```
diff_ppg > X → Home
diff_ppg < Y → Away
en medio → Draw
```

que separe perfectamente las clases.

El verdadero reto se verá cuando combinemos features.

Por eso todavía no podemos afirmar cuánto más difícil será predecir empates hasta entrenar modelos y observar matrices de confusión, recall, probabilidades y calibración.

---

# 11. Por qué no seleccionamos features durante el EDA

Esto también fue deliberado.

Encontrar:

\[ corr(diff\_ppg,GD)=0.41 \]

no significa automáticamente:

> “diff_ppg es una de las mejores features”.

Una feature puede tener poca correlación individual y ser muy útil en combinación con otras.

O puede parecer muy buena individualmente y resultar redundante cuando el modelo ya tiene otra información.

Por eso el EDA caracterizó las features, pero **el modelado decidirá su utilidad predictiva**.

---

# 12. El mercado

El mercado tiene un papel muy concreto.

No queremos hacer:

\[ \text{modelo}(\text{odds}) \]

en v0.1.

Queremos algo como:

\[ P_{SCOPE}(H,D,A) \]

frente a:

\[ P_{market}(H,D,A) \]

Así tendremos un benchmark externo extremadamente relevante.

Si algún día SCOPE obtiene probabilidades razonables comparadas con el mercado, será mucho más informativo que simplemente decir:

> “mi accuracy es 52 %”.

---

# 13. Qué dejó preparado el EDA para Machine Learning

Ahora el modelado ya no empieza desde cero.

Tiene reglas.

Sabemos que debemos respetar temporalidad, usar `k=3`, no utilizar HADIFF ingenuamente en modelos lineales, comparar HA y DIFF, resolver P02 mediante experimentación, resolver P04, mantener MARKET fuera de predictors y no corregir Q01 silenciosamente.

Además, el profesor ha comunicado el requisito de **al menos cuatro modelos**, aunque la rúbrica documental correspondiente sigue pendiente bajo C06.

Y tendremos que evaluar no solo accuracy.

Como produciremos probabilidades:

\[ P(H),P(D),P(A) \]

nos interesarán también métricas como **log loss, Brier score y calibración**, además de precision, recall, F1 y matriz de confusión.

---

# 14. La idea más importante de todo el EDA

Si tuviera que resumirte estas semanas de trabajo en una sola frase sería:

> **El EDA convirtió decisiones que antes eran intuiciones en afirmaciones que ahora sabemos cuáles están demostradas, cuáles solo tienen evidencia parcial y cuáles todavía requieren modelado.**

Antes podíamos decir:

> “usemos last5 porque parece útil”.

Ahora sabemos:

> “last5 es estructuralmente distinta y más responsiva, pero todavía no hay evidencia suficiente de que aporte señal incremental”.

Antes:

> “usemos tres partidos de burn-in porque parece razonable”.

Ahora:

> “la estabilidad mejora mucho hasta tres partidos y después aparecen rendimientos decrecientes a un coste constante de observaciones”.

Antes:

> “no usemos h/a/diff juntos porque están correlacionados”.

Ahora:

> “existe dependencia algebraica exacta; HADIFF tiene 21 columnas pero rango 14”.

Ese salto de **intuición → evidencia** es probablemente el logro más importante del EDA.

---

## Cómo podrías explicárselo a un profesor

Si te preguntaran en clase qué hiciste en el EDA de SCOPE, una buena explicación oral sería:

> “Primero validamos la estructura y calidad de los datos y confirmamos que las features respetan temporalidad. Después analizamos la distribución del target, las variables predictoras y sus relaciones. Estudiamos problemas específicos de diseño, como la dependencia exacta entre h, a y diff, la relación season-last5 y cuánto historial necesitamos antes de considerar confiable una observación. También evaluamos la utilidad conceptual de last5, una anomalía de calidad de datos y el drift entre temporadas. Todo eso produjo decisiones formales sobre representación, burn-in y tratamiento de calidad, pero dejamos las preguntas de rendimiento predictivo para la etapa de Machine Learning. Finalmente documentamos el drift de TEST sin utilizarlo para cambiar ninguna decisión.”

Si puedes explicar **por qué** cada frase de ese párrafo es cierta, entonces ya entiendes la esencia del EDA de SCOPE.

Y ese es exactamente el punto en el que estamos ahora: **el análisis exploratorio terminó; el siguiente gran bloque es convertir todo este conocimiento en experimentos de Machine Learning sin romper las reglas que acabamos de construir.**