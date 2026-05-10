# Contexto del Proyecto: "Assisted Living Maintenance App"

Actúa como un Desarrollador Full-Stack experto en Python (Flask) y Frontend (HTML/CSS/Vanilla JS). 
Tu tarea es crear y estructurar un proyecto web completo para gestionar reportes de mantenimiento y limpieza en 38 comunidades de "Assisted Living". 

La interfaz de usuario (UI) de TODA la aplicación DEBE estar estrictamente en Inglés, ya que los usuarios finales están en Estados Unidos.

## Arquitectura y Tecnologías
- **Backend:** Python con el framework Flask.
- **Frontend:** HTML5, CSS3 puro (sin frameworks como Bootstrap) y JavaScript puro.
- **Estructura de carpetas requerida:**
  /app_mantenimiento
  ├── app.py
  ├── /static
  │   └── /uploads (para guardar las fotos en el futuro)
  └── /templates
      ├── reporte.html
      └── dashboard.html

## Pantalla 1: Formulario de Reporte Móvil (`reporte.html`)
Esta vista está diseñada para el personal de limpieza/mantenimiento usando teléfonos móviles.
- **UI:** En inglés. Diseño "Mobile-First" responsivo.
- **Campos del formulario:**
  1. `Select`: Para elegir la comunidad (incluir opciones como "Community 1", "Community 2", etc., simulando 38 comunidades).
  2. `Input (text)`: Ubicación específica (Ej: Hallway 3, Room 12).
  3. `Radio buttons (Custom UI)`: Sistema de calificación de la condición. **Obligatorio:** Ocultar los círculos de los radio buttons y usar botones grandes y táctiles con emojis: un botón de "👍" (Good) y un botón de "👎" (Needs Attention). Al seleccionar 👍 debe pintarse de verde, al seleccionar 👎 debe pintarse de rojo.
  4. `Textarea`: Descripción del problema.
  5. `Input (file)`: Botón para tomar/subir foto. **Crucial:** Debe incluir el atributo `accept="image/*" capture="environment"` para abrir la cámara trasera en móviles.
  6. `Button (submit)`: Para enviar el formulario.
- **Lógica actual:** Por ahora, interceptar el `submit` con JavaScript e imprimir un `alert()` con los datos recopilados para validar.

## Pantalla 2: Tablero de Administrador (`dashboard.html`)
Esta vista está diseñada para que los gerentes vean los reportes desde una computadora de escritorio.
- **UI:** En inglés. Diseño "Desktop-First" limpio y profesional.
- **Visualización:** Usar CSS Grid para crear una "Galería de Tarjetas" (Card Gallery). Cada tarjeta representa un reporte y debe mostrar:
  - Imagen del reporte en la parte superior.
  - Título (Nombre de la comunidad).
  - Ubicación específica.
  - Una "Badge" (etiqueta) visual del estado: Verde para "👍 Good" y Roja para "👎 Needs Attention".
  - Descripción del problema.
- **Datos Simples (Mock Data):** Dentro del JavaScript de este archivo, crea un array de objetos con 3 o 4 reportes falsos usando imágenes de prueba de Unsplash para poder visualizar el diseño.
- **Filtros (JavaScript):** En la parte superior de la galería, incluye 3 botones: "All Reports", "👍 Good Condition", "👎 Needs Attention". Al hacer clic en ellos, la galería debe filtrarse instantáneamente usando JavaScript sin recargar la página.

## Backend: Servidor Flask (`app.py`)
- Crear una aplicación básica de Flask.
- Configurar la ruta raíz `/` para que devuelva el archivo `reporte.html` usando `render_template`.
- Configurar la ruta `/dashboard` para que devuelva el archivo `dashboard.html` usando `render_template`.
- Ejecutar la aplicación en `host='0.0.0.0'` y `port=5000` con `debug=True`.

## Instrucciones de ejecución para el Agente:
1. Comienza creando la estructura de carpetas y el archivo `app.py`. Muestra el código.
2. Luego, genera el código completo para `templates/reporte.html`.
3. Finalmente, genera el código completo para `templates/dashboard.html`.
Asegúrate de que todo el código sea fácil de copiar y pegar, bien comentado en inglés, y que cumpla con los requisitos visuales de los pulgares (thumbs up/down).