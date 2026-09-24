# Mapa de comunidades — borrador de spec

> Estado: **borrador**. Escrito para corregirse encima. Las decisiones marcadas
> con **⟡** son las que hay que resolver antes de escribir código.

---

## 1. Qué pregunta responde

> *"¿Dónde estamos flojos, geográficamente?"*

Es una vista de orientación, no de trabajo. Nadie va a abrir el mapa para
arreglar algo; lo va a abrir para decidir **dónde poner la atención esta
semana** antes de meterse a las listas.

De ahí se sigue todo lo demás: si un pin no ayuda a tomar esa decisión, sobra.

## 2. Qué NO es

**No es un mapa de calor.** Con 39 comunidades repartidas en diez estados, un
degradado de calor muestra **dónde hay más edificios**, no dónde están bajas
las calificaciones.

Ejemplo real: hay cuatro comunidades pegadas en el área de Tampa y una sola
cerca de Memphis. Si Tampa promedia 92 y Memphis 70, la mancha de Tampa se ve
más intensa de todos modos — la densidad le gana al puntaje, y el mapa dice lo
contrario de lo que queríamos saber.

Lo que sí dice la verdad con estos números son **pines de color individuales**.
Un punto rojo solo en Memphis salta a la vista precisamente porque está solo.

---

## 3. Los datos: coordenadas

### El problema

De los 39 nombres de comunidad:

- **25 traen la ciudad al final** — `The Goldton at Spring Hill, Spring Hill`
- **14 no la traen**, y de esos **9 nombran un fraccionamiento, no una ciudad**:

| Nombre | Dónde está de verdad |
|---|---|
| The Goldton At Lake Nona | distrito de Orlando, FL |
| Tribute at Melford | desarrollo en Bowie, MD |
| Tribute at One Loudoun | Ashburn, VA |
| The Oscar at Veramendi | New Braunfels, TX |
| The Goldton at Jones Farm | barrio de Huntsville, AL |

Y dos son ambiguos entre estados: **Athens** (GA / AL / TN) y **Madison**
(AL / MS / WI).

### La regla

**No se adivinan coordenadas en tiempo de ejecución.** Un mapa que coloca una
comunidad en el estado equivocado es peor que no tener mapa: se ve autoritativo
y nadie lo cuestiona.

### La forma

Un archivo nuevo, `data/community_places.json`, con una entrada por comunidad:

```json
{
  "The Goldton At Lake Nona": {
    "lat": 28.3772, "lng": -81.2519,
    "city": "Orlando", "state": "FL",
    "verificado_por": "gabriel.rosales",
    "verificado_el": "2026-09-25"
  }
}
```

- Se llena **una vez**. Yo propongo las 39 coordenadas; alguien que conozca las
  comunidades las revisa en el mapa y confirma.
- `verificado_por` existe para que se note cuáles siguen siendo una propuesta
  mía y cuáles ya pasaron por ojos humanos.
- No cambia cómo funcionan las comunidades hoy (siguen siendo texto dentro de
  `regions.json`); es una tabla lateral.

### Una comunidad sin coordenada

**No se dibuja, y se dice.** Un contador arriba del mapa: *"3 comunidades sin
ubicación"*, con la lista al abrirlo. Nunca se coloca en un punto aproximado
"mientras tanto" — eso es exactamente el error que estamos evitando.

**⟡ Decidir:** ¿quién confirma las coordenadas? Propongo que las proponga yo y
las revise una persona de operaciones que haya estado físicamente en varias.

---

## 4. Qué muestra un pin

### Color

Por **banda de calificación** de la última visita:

| Banda | Color | |
|---|---|---|
| 90–100 | verde | |
| 75–89 | ámbar | |
| menos de 75 | rojo | |
| sin visita reciente | **gris hueco** | "no sabemos" ≠ "bien" |

Esa última fila es importante. Una comunidad sin visitar en cuatro meses sigue
teniendo su última calificación guardada, y pintarla de verde dice algo que no
sabemos. Un pin hueco se lee distinto y es honesto.

**⟡ Decidir:** ¿cuántos días sin visita convierten un pin en gris? Propongo 60,
pero eso depende de la cadencia real que esperan de los regionales.

### Al pasar el cursor / tocar

Nombre, calificación, fecha de la última visita, cuántos items abiertos.

### Al hacer clic

Abre el **panel de comunidad que ya existe** — el mismo que se abre desde
Recent activity o desde Visits. Cero interfaz nueva.

**⟡ Decidir (para v2):** colorear por **tendencia** en vez de por puntaje
absoluto. El puntaje absoluto refleja sobre todo qué tan reciente fue la última
visita; *"bajó 8 puntos"* es una llamada telefónica, *"tiene 88"* no dice nada
por sí solo. Vale la pena como segundo modo, no como el primero.

---

## 5. Dónde vive

**Dentro de la vista Communities, como un interruptor Lista / Mapa.**

Razones:

- Esa vista ya contiene exactamente este conjunto de objetos y ya está acotada
  por rol. El mapa es otra forma de mirar lo mismo, no un lugar nuevo.
- No agrega una entrada al menú ni un concepto nuevo que explicar.
- La lista contesta *"¿cómo está esta?"* y el mapa contesta *"¿dónde están las
  que están mal?"*. Son la misma pregunta a distinto zoom.

**Por qué no una entrada propia en el menú:** un mapa no se visita todos los
días, y una entrada permanente en el menú promete más de lo que da. Si resulta
que la gente lo abre a diario, se gradúa a menú — pero que se lo gane.

**Por qué no una tarjeta del dashboard:** un mapa de diez estados en una tarjeta
chica no se lee. Cabría, pero no serviría.

### Quién ve qué

El mapa dibuja **lo que la sesión ya puede ver** — la función
`visible_communities()` que ya existe y ya decide eso en todos lados:

| Rol | Ve |
|---|---|
| admin | todas |
| corporativo | todas |
| regional | las de su región |
| ED | la suya |

Para un ED el mapa sería un solo pin, lo cual es inútil. **El interruptor de
Mapa solo aparece cuando la cuenta cubre más de una comunidad.**

Esto no es una decisión de diseño sino de alcance: el mapa no debe convertirse
en una forma nueva de ver comunidades que no te tocan.

---

## 6. Técnico

- **Leaflet + mapas de OpenStreetMap.** Gratis, sin llave de API, sin cuenta de
  facturación. Google Maps exige las dos cosas y para 39 pines no aporta nada.
- Una librería más, cargada solo en esa vista.
- Sin servicio de geocodificación en vivo: las coordenadas ya están guardadas,
  así que el mapa no depende de ningún tercero para funcionar.
- Un endpoint nuevo que devuelva, ya acotado por rol: nombre, lat, lng, banda,
  fecha de última visita, items abiertos. **Nunca la lista completa al cliente
  para que él filtre** — el filtrado por rol se hace en el servidor.

### Móvil

Un mapa de diez estados en una pantalla de teléfono no se usa igual. Propongo
que en móvil el interruptor exista pero el mapa abra en pantalla completa, y
que la lista siga siendo lo primero.

**⟡ Decidir:** o simplemente no ofrecer el mapa en móvil en v1. Es donde menos
falta hace: nadie decide dónde poner la atención de la semana desde el teléfono.

---

## 7. Fuera de alcance para la v1

- Mapa de calor / degradados.
- Agrupar pines (*clustering*). Con 39 no hace falta; con 200 sí.
- Filtros sobre el mapa (por región, por tipo de visita).
- Dibujar las regiones como polígonos.
- Exportar el mapa a imagen para una presentación.

---

## 8. Orden de trabajo propuesto

1. Generar las 39 coordenadas propuestas y que alguien las revise. **Esto no
   toca código y desbloquea todo lo demás.**
2. El archivo `community_places.json` y su lectura, con el contador de
   comunidades sin ubicación.
3. El endpoint acotado por rol.
4. El mapa en Communities, detrás del interruptor.
5. Pruebas: que un regional no reciba comunidades fuera de su región; que una
   comunidad sin coordenada no se dibuje y sí se cuente; que la banda de color
   respete el caso "sin visita reciente".

---

## 9. Lo que todavía no sé

- Si Greg y Wyman lo quieren para ver **estado actual** o **tendencia**. La
  respuesta cambia el color de los pines, que es la decisión central.
- Si alguien fuera de corporativo y regionales lo va a usar.
- Si 39 comunidades es el número estable o van a ser 200 el año que entra. Con
  200 el diseño de pines individuales empieza a fallar y ahí sí entra el
  agrupamiento.
