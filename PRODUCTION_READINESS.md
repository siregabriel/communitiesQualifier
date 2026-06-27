# Atlas Standards — Evaluación de preparación para producción

_Fecha: 27 de junio de 2026_

## Veredicto en una línea

La app **funciona bien y es razonablemente sólida**, pero todavía **no es "production-grade"** en tres frentes concretos: **respaldos de datos**, **algunas defensas de seguridad estándar**, y **un secreto expuesto sin rotar**. Ninguno es difícil de cerrar. "100% seguro" no existe, pero podemos llegar a un nivel profesional y confiable con un plan corto.

La migración de base de datos (tu pregunta original) **vale la pena, pero NO es lo más urgente** — los respaldos y la seguridad pesan más.

---

## 1. Capa de datos

### Hoy
Almacenamiento en archivos JSON (`data/*.json`), una sola instancia, 2 workers de gunicorn. Escrituras atómicas (temp + `os.replace`) y recarga-por-mtime. Para el volumen actual funciona.

### Riesgos reales
- **Sin respaldos automáticos.** Es el punto más débil. Si el disco de Lightsail falla, o una escritura mala se cuela, los datos se pierden. Hoy no hay copia.
- **Ventana de carrera entre procesos.** El lock protege dentro de un worker, pero entre los 2 workers de gunicorn solo está la recarga-por-mtime. Si dos personas guardan el MISMO archivo en el mismo instante, en teoría uno puede pisar al otro. Con tu volumen es muy improbable, pero existe.

### Opciones
- **Quedarse con JSON + respaldos** — lo más barato; cierra el riesgo de pérdida pero no la carrera entre procesos.
- **Migrar a SQLite** (recomendado a mediano plazo) — un solo archivo, **transacciones reales** (elimina la carrera), modo WAL para concurrencia, respaldo = copiar un archivo. Migración mediana (1 archivo de datos a la vez). Sigue siendo single-instance.
- **Migrar a Postgres** — solo si creces a varios servidores o miles de usuarios concurrentes. Hoy es sobre-ingeniería.

**Recomendación:** primero respaldos (rápido). SQLite cuando quieras endurecer la concurrencia. Postgres no hace falta por ahora.

---

## 2. Seguridad — hallazgos priorizados

### P0 — Crítico (hacer ya)
1. **Rotar la llave de acceso S3 expuesta.** Se compartió en texto plano. Mientras siga válida, cualquiera que la haya visto puede leer/borrar el bucket. Crear llave nueva en IAM, actualizar `atlas.env`, desactivar la vieja.
2. **Garantizar `SECRET_KEY` en producción.** Si la variable de entorno no está, la app arranca con una clave de desarrollo insegura y hardcodeada (solo avisa en el log). Con esa clave, las sesiones se pueden falsificar. Hay que confirmar que `SECRET_KEY` esté en `/etc/atlas/atlas.env` y, idealmente, hacer que la app **se niegue a arrancar** en producción sin ella.

### P1 — Importante (corto plazo)
3. **Sin protección CSRF.** Las sesiones por cookie sin token CSRF permiten que un sitio malicioso dispare acciones (crear usuarios, borrar datos) si un admin con sesión activa visita una página trampa. Solución: `Flask-WTF`/CSRFProtect o tokens manuales en los POST/PUT/DELETE.
4. **Cookies de sesión sin flags de seguridad.** No se configura `SESSION_COOKIE_SECURE`, `SAMESITE`. Con HTTPS ya activo, hay que poner `Secure=True`, `HttpOnly=True`, `SameSite='Lax'`.
5. **Sin rate limiting en el login.** Permite ataques de fuerza bruta sobre contraseñas. Solución: `Flask-Limiter` (p. ej. 5–10 intentos/min por IP) o un bloqueo simple por intentos fallidos.
6. **Headers de seguridad faltantes** en nginx/Flask: `Strict-Transport-Security` (HSTS), `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`.

### P2 — Deseable
7. **SES sigue en sandbox** — limita destinatarios de correo; ya tienes el caso de soporte en curso.
8. **`FLASK_DEBUG` por defecto en '1'** — solo afecta al arranque local con `python app.py` (producción usa gunicorn, que ignora ese bloque), pero conviene cambiar el default a '0'.
9. Endurecer `get_all_*` para devolver copias (ya lo hicimos en regiones; revisar otros servicios).

---

## 3. Confiabilidad y durabilidad

**Bien hoy:**
- `Restart=always` en systemd (se recupera de caídas).
- Swap añadido + 2 workers (estable en 512 MB).
- Datos vivos git-ignored → un deploy nunca los pisa.
- HTTPS funcionando (Certbot).

**Falta:**
- **Respaldos automáticos** (lo más importante de toda la lista). Mínimo: snapshot diario de Lightsail + un cron que copie `data/*.json` a S3 versionado.
- **Monitoreo/alertas** — hoy no te enteras si la app cae salvo que un usuario lo reporte. Un health-check externo (UptimeRobot, gratis) que avise por correo.
- **Plan de restauración probado** — tener respaldos sirve solo si sabes restaurarlos.

---

## 4. Roadmap recomendado (en orden)

**Esta semana (P0):**
1. Rotar la llave S3.
2. Confirmar/forzar `SECRET_KEY` en producción.
3. Activar respaldos: snapshot diario de Lightsail + cron de `data/` → S3.

**Próximas 1–2 semanas (P1):**
4. CSRF en todos los endpoints que modifican datos.
5. Flags seguros de cookie de sesión.
6. Rate limiting en login.
7. Headers de seguridad (HSTS, etc.) en nginx.

**Cuando haya tiempo (P2):**
8. Health-check externo + alerta.
9. Migrar a SQLite (concurrencia + respaldo trivial).
10. Cambiar default de `FLASK_DEBUG` a '0'; limpiar tests obsoletos.

---

## Conclusión

No estás lejos. Con los **3 puntos P0** (rotar llave, asegurar SECRET_KEY, respaldos) pasas de "frágil" a "seguro para el día a día". Con los **P1** llegas a un estándar profesional. La migración a SQLite es una mejora real de robustez, pero es P2 — no el cuello de botella.
