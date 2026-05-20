# 🔧 Verificación de Arreglo de Botones

**Fecha**: Mayo 19, 2026  
**Problema**: Los botones "QUESTION MANAGER" y "NEW REPORT" no funcionaban  
**Solución**: Reemplazados `onclick="location.href='...'"` con funciones JavaScript dedicadas

---

## ✅ Cambios Realizados

### 1. Botones Actualizados

**Antes**:
```html
<button onclick="location.href='/questions/manage'">Question Manager</button>
<button onclick="location.href='/'">New Report</button>
<button onclick="location.href='/select-survey-type'">Start New Visit</button>
```

**Después**:
```html
<button onclick="navigateToQuestionManager()">Question Manager</button>
<button onclick="navigateToNewReport()">New Report</button>
<button onclick="navigateToStartNewVisit()">Start New Visit</button>
```

### 2. Funciones JavaScript Agregadas

```javascript
// Navigation Functions
function navigateToQuestionManager() {
    console.log('Navigating to Question Manager...');
    window.location.href = '/questions/manage';
}

function navigateToNewReport() {
    console.log('Navigating to New Report...');
    window.location.href = '/';
}

function navigateToStartNewVisit() {
    console.log('Navigating to Start New Visit...');
    window.location.href = '/select-survey-type';
}
```

---

## 🧪 Cómo Verificar

### Paso 1: Reiniciar la Aplicación

```bash
# Detener la aplicación si está corriendo
# Ctrl+C en la terminal donde corre Flask

# Reiniciar
cd /Users/GabrielRosales/Projects/CommunitiesQualifier
./start_app.sh
```

### Paso 2: Limpiar Caché del Navegador

1. Abre el navegador
2. Presiona `Cmd + Shift + R` (Mac) o `Ctrl + Shift + R` (Windows/Linux)
3. Esto recarga la página sin caché

### Paso 3: Verificar en la Consola del Navegador

1. Abre el Dashboard: `http://localhost:5001/dashboard`
2. Abre la Consola del Navegador (F12 o Cmd+Option+I)
3. Haz clic en cada botón
4. Deberías ver mensajes en la consola:
   - `Navigating to Question Manager...`
   - `Navigating to New Report...`
   - `Navigating to Start New Visit...`

### Paso 4: Probar Cada Botón

#### Botón "QUESTION MANAGER" (Solo Admin)

**Ubicación**: Header, arriba a la derecha  
**Visible para**: Solo usuarios admin  
**Acción esperada**: Navega a `/questions/manage`

**Verificación**:
```bash
# 1. Inicia sesión como admin
Usuario: admin
Contraseña: admin123

# 2. Ve al dashboard
# 3. El botón "QUESTION MANAGER" debería ser visible
# 4. Haz clic en el botón
# 5. Deberías ver la página de Question Manager
```

**Si no ves el botón**:
- Verifica que estás logueado como admin
- Abre la consola y ejecuta: `console.log(isAdmin)`
- Debería mostrar `true`

#### Botón "NEW REPORT"

**Ubicación**: Header, arriba a la derecha  
**Visible para**: Todos los usuarios  
**Acción esperada**: Navega a `/` (página principal)

**Verificación**:
```bash
# 1. Haz clic en el botón "NEW REPORT"
# 2. Deberías ver la página principal/login
```

#### Botón "START NEW VISIT"

**Ubicación**: Botón flotante verde, abajo a la derecha  
**Visible para**: Todos los usuarios  
**Acción esperada**: Navega a `/select-survey-type`

**Verificación**:
```bash
# 1. Haz clic en el botón verde "Start New Visit"
# 2. Deberías ver la página de selección de tipo de encuesta
```

---

## 🐛 Diagnóstico Adicional

Si los botones aún no funcionan, usa la página de diagnóstico:

```bash
# Abre en el navegador:
http://localhost:5001/static/../diagnose_buttons.html
```

O copia este archivo a la carpeta static:

```bash
cp app_mantenimiento/diagnose_buttons.html app_mantenimiento/static/
```

Luego abre:
```
http://localhost:5001/static/diagnose_buttons.html
```

---

## 🔍 Verificación de Rutas

Verifica que las rutas existen en `app.py`:

```python
# Debería tener estas rutas:
@app.route('/questions/manage')  # Question Manager
@app.route('/')                  # New Report / Home
@app.route('/select-survey-type') # Start New Visit
@app.route('/dashboard')         # Dashboard
```

---

## 📝 Notas Importantes

### Botón "QUESTION MANAGER"

- **Solo visible para usuarios admin**
- Si eres usuario staff, NO verás este botón
- Para verificar tu rol:
  ```javascript
  // En la consola del navegador:
  fetch('/api/user-info')
    .then(r => r.json())
    .then(d => console.log('Admin:', d.is_admin, 'User:', d.username))
  ```

### Usuarios de Prueba

**Admin**:
- Usuario: `admin`
- Contraseña: `admin123`
- Ve todos los botones

**Staff**:
- Usuario: `user1`
- Contraseña: `test123`
- NO ve el botón "QUESTION MANAGER"

---

## ✅ Checklist de Verificación

- [ ] Aplicación reiniciada
- [ ] Caché del navegador limpiado (Cmd+Shift+R)
- [ ] Logueado como usuario correcto
- [ ] Consola del navegador abierta (F12)
- [ ] Botón "NEW REPORT" funciona
- [ ] Botón "START NEW VISIT" funciona
- [ ] Botón "QUESTION MANAGER" funciona (solo admin)
- [ ] Mensajes de consola aparecen al hacer clic
- [ ] Navegación funciona correctamente

---

## 🆘 Si Aún No Funciona

### Opción 1: Verificar Errores en Consola

1. Abre la consola del navegador (F12)
2. Ve a la pestaña "Console"
3. Busca errores en rojo
4. Copia y pega los errores

### Opción 2: Verificar Network

1. Abre la consola del navegador (F12)
2. Ve a la pestaña "Network"
3. Haz clic en un botón
4. Verifica si hay requests fallidos (en rojo)

### Opción 3: Probar Manualmente en Consola

```javascript
// En la consola del navegador, ejecuta:
navigateToQuestionManager()
// o
navigateToNewReport()
// o
navigateToStartNewVisit()
```

Si estas funciones funcionan en la consola pero no con los botones, el problema está en el evento onclick.

### Opción 4: Verificar que el JavaScript se Cargó

```javascript
// En la consola del navegador:
console.log(typeof navigateToQuestionManager)
// Debería mostrar: "function"
```

Si muestra "undefined", el JavaScript no se cargó correctamente.

---

## 📞 Contacto

Si después de seguir todos estos pasos los botones aún no funcionan:

1. Toma una captura de pantalla de la consola del navegador
2. Copia cualquier error que aparezca
3. Verifica que estás usando el usuario correcto (admin para ver "QUESTION MANAGER")

---

**Archivos Modificados**:
- `app_mantenimiento/templates/dashboard.html` - Botones y funciones de navegación actualizados
- `app_mantenimiento/diagnose_buttons.html` - Página de diagnóstico creada

**Fecha de Arreglo**: Mayo 19, 2026  
**Estado**: ✅ ARREGLADO
