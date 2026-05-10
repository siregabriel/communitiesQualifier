# 🏢 Assisted Living Maintenance App - Login & Photo Upload Setup

## ✅ Implementación Completada

Has instalado exitosamente:

### 1. **Portal de Login con Usuario y Contraseña**
- Página de login en `/login`
- Validación de credenciales
- Sesiones seguras con Flask
- Redireccionamiento automático al login si no está autenticado

### 2. **Detección Automática de Comunidad**
- Cuando un usuario ingresa su usuario y contraseña, la comunidad se detecta automáticamente
- Usuarios no-admin solo ven su comunidad asignada en el formulario
- Usuarios admin pueden ver todas las 38 comunidades
- La comunidad se muestra en la interfaz del usuario

### 3. **Carga y Almacenamiento de Fotografías**
- Carga correcta desde celulares (con `capture="environment"` para cámara trasera)
- Guardado seguro en carpetas organizadas por comunidad
- Validación de tipos de archivo (jpg, jpeg, png, gif, webp)
- Límite de tamaño: 16MB por imagen
- Nombres de archivo seguros con timestamp: `username_community_YYYYMMDD_HHMMSS.ext`

---

## 🔐 Credenciales de Prueba

### Usuarios Normales (con comunidad asignada):
```
👤 john     / 🔑 pass123  → Community A
👤 maria    / 🔑 pass123  → Community B
👤 carlos   / 🔑 pass123  → Community C
```

### Usuario Admin (ve todas las comunidades):
```
👤 admin    / 🔑 admin123 → Acceso a todas las 38 comunidades
```

---

## 🚀 Cómo Ejecutar

### 1. Instala Flask (si no lo tienes):
```bash
pip install flask
```

### 2. Navega a la carpeta del proyecto:
```bash
cd /Users/GabrielRosales/Projects/CommunitiesQualifier/app_mantenimiento
```

### 3. Ejecuta la aplicación:
```bash
python app.py
```

### 4. Abre tu navegador:
```
http://localhost:5001
```

---

## 📂 Estructura de Carpetas

```
app_mantenimiento/
├── app.py                          # Servidor Flask con autenticación
├── static/
│   └── uploads/                    # Carpeta para guardar fotos
│       ├── Community A/           # Fotos de Community A
│       ├── Community B/           # Fotos de Community B
│       └── ...
└── templates/
    ├── login.html                 # Página de login
    ├── reporte.html               # Formulario de reporte (con login integrado)
    └── dashboard.html             # Dashboard de admin
```

---

## 🔧 Flujo de Usuario

### Usuario Normal (ej: john)
1. ➡️ Va a `http://localhost:5001/login`
2. 🔑 Ingresa: `john` / `pass123`
3. ✅ Lo redirige al formulario `/`
4. 📋 Ve su comunidad asignada (Community A) pre-seleccionada
5. 📷 Llena el formulario y sube una foto
6. 💾 La foto se guarda en: `uploads/Community A/john_Community A_20260508_143022.jpg`

### Usuario Admin (ej: admin)
1. ➡️ Va a `http://localhost:5001/login`
2. 🔑 Ingresa: `admin` / `admin123`
3. ✅ Lo redirige al formulario `/`
4. 🌍 Puede seleccionar cualquiera de las 38 comunidades
5. 📷 Llena el formulario y sube una foto
6. 💾 La foto se guarda en: `uploads/[Community Seleccionada]/admin_[Community]_20260508_143022.jpg`

---

## 📸 Características de Carga de Imágenes

### ✨ Desde Celular:
- ✅ Acceso a cámara trasera automáticamente
- ✅ Puede tomar foto directamente o subir de galería
- ✅ Preview de la imagen antes de enviar
- ✅ Validación de tamaño (máx 16MB)

### 📁 Almacenamiento:
- ✅ Organizado por comunidad
- ✅ Nombres únicos con timestamp
- ✅ Prevención de sobrescritura
- ✅ Acceso seguro de archivos

---

## 🔄 Rutas de la Aplicación

| Ruta | Método | Descripción |
|------|--------|-------------|
| `/login` | GET | Página de login |
| `/api/login` | POST | Autenticación de usuario |
| `/` | GET | Formulario de reporte (requiere login) |
| `/dashboard` | GET | Dashboard de admin (requiere login) |
| `/api/submit-report` | POST | Envío de reporte con foto |
| `/api/user-info` | GET | Información del usuario actual |
| `/logout` | GET | Cerrar sesión |

---

## 🎨 Interfaz

### Página de Login
- Formulario limpio con validación en tiempo real
- Muestra credenciales de prueba
- Transiciones suaves y responsive

### Formulario de Reporte
- Muestra usuario y comunidad en el header
- Comunidad pre-seleccionada o selector para admin
- Radio buttons visuales (👍 Good / 👎 Needs Attention)
- Preview de imagen antes de enviar
- Feedback visual de envío exitoso

---

## ⚙️ Configuración en Producción

Para producción, cambiar:

1. **Secret Key** en `app.py`:
   ```python
   app.config['SECRET_KEY'] = 'genera-una-clave-segura-aleatoria'
   ```

2. **Base de datos**: Reemplazar `USERS_DB` con una base de datos real (PostgreSQL, MySQL, etc.)

3. **Autenticación de contraseña**: Usar hash seguro con werkzeug:
   ```python
   from werkzeug.security import generate_password_hash, check_password_hash
   ```

4. **SSL/HTTPS**: Configurar certificado SSL

---

## 📝 Notas

- La base de datos de usuarios es en memoria (USERS_DB). En producción, usar una BD real.
- Las fotos se guardan en `static/uploads/` - considerar usar un servicio de almacenamiento en la nube (S3, etc.)
- Las sesiones se almacenan en el filesystem. Para múltiples servidores, usar Redis o similar.

---

## 🆘 Solución de Problemas

### "Port 5001 already in use"
```bash
# Cambiar en app.py o usar un puerto diferente:
app.run(host='0.0.0.0', port=5002, debug=True)
```

### "Login no funciona"
- Verifica que ingresaste las credenciales correctas (revisar en USERS_DB en app.py)
- Limpia cookies del navegador
- Comprueba que Flask esté corriendo sin errores

### "Fotos no se guardan"
- Verifica permisos de carpeta `uploads/`
- Comprueba que haya espacio en disco
- Revisa los logs de Flask para errores

---

## 📞 Soporte

Si necesitas cambios adicionales o tienes preguntas, déjame saber:
- Agregar más usuarios
- Cambiar nombres de comunidades
- Modificar la interfaz
- Integrar base de datos real
