# Propuesta: Módulo "Move-In Checklist" para Atlas Standards

_Borrador interno — 27 de junio de 2026_

## El problema que resuelve

Hoy, cuando entra un residente nuevo, el proceso de move-in se coordina con un binder físico: una checklist por fases que varios directores de departamento completan antes, durante y después de la mudanza (enfermería, dietary, mantenimiento, business office). El riesgo es que algo se pase por alto —un formato sin firmar, un paso de cumplimiento omitido— y nadie lo vea hasta que es tarde.

Greg pregunta si la app podría ofrecer una variante de esto para **asegurar que todo quede cubierto y ver los "blind spots"**. Sí se puede, y la plataforma ya tiene la mitad del camino hecho.

## Cómo encaja con lo que ya existe

La app ya es, en el fondo, un **motor de checklists con roles, evidencia y reportes**. Lo que reutilizaríamos casi tal cual:

- **Autenticación por rol** (admin / regional / staff) → aquí se mapea a directores de departamento.
- **Almacenamiento de adjuntos en S3** (privado, URLs firmadas) → para los formatos firmados del binder.
- **Emails transaccionales (SES)** → recordatorios y alertas.
- **Editor de checklists** (el Question Manager) → como base para editar la plantilla de move-in.
- **Exports CSV/Excel/PDF** → para auditoría y archivo.
- **Sistema de diseño y UI** ya consistente.

## Qué es nuevo (y por qué es un módulo, no solo otro "survey type")

El move-in tiene una "forma" distinta a las inspecciones de comunidad:

1. **Es por residente / por evento**, no por comunidad. Cada mudanza es una ficha propia (residente + comunidad + fecha objetivo de move-in).
2. **Es multi-fase y multi-rol a lo largo del tiempo**, no una sola visita. Distintos departamentos completan partes distintas en días/semanas diferentes.
3. **Los ítems no son Pass/Fail.** Son: completado ✓, fecha, iniciales de quien lo hizo, y opcionalmente un **formato adjunto**.
4. **Tiene candados de cumplimiento (gates).** Ej.: no se puede marcar "listo para move-in físico" sin el POC/1823 aprobado y el Medication form firmado.

## Estructura propuesta

**Plantilla (editable por admin)** — fases → ítems. Cada ítem define:
- Texto del paso.
- Departamento/rol responsable.
- Tipo: casilla simple · requiere fecha · requiere formato adjunto.
- Marca de "requerido para move-in" (gate).

**Fases (tomadas del binder de Greg):**
1. **Pre Move-In (Red Carpet · prep):** POC/1823 aprobado, evaluación de enfermería, **Medication form firmado (gate)**, seguro y farmacia confirmados.
2. **Día de Move-In (Tour-in):** letrero de bienvenida con nombre, foto del residente, formatos de residencia, escolta al apartamento, pendiente/sistema de llamado, preferencias de comedor, agenda de housekeeping.
3. **Welcome Home:** expediente financiero/ACH, placa con nombre ordenada, formatos firmados distribuidos a cada departamento, calendario mensual entregado.
4. **Seguimientos (Día 5, 1–2 semanas):** seguimiento en persona, check-in de dietary y de mantenimiento, encuesta de satisfacción, solicitar reseña de Google.

**Ficha por residente (instancia):** se crea cuando viene un residente nuevo; hereda la plantilla; los directores van completando sus ítems con fecha + iniciales + adjunto.

**Tablero de blind spots:** lista de move-ins activos con % de avance, ítems bloqueantes (gates sin cumplir cerca de la fecha), pendientes por departamento, y atrasados. Esto es exactamente el "ver que todo quede cubierto" que pide Greg.

## Roles

- **Directores de departamento:** ven y completan los ítems de su área.
- **Ejecutivo / ED / admin:** ven la ficha completa y el tablero de todos los move-ins.
- (Opcional) Alertas por email cuando un gate sigue sin cumplirse y la fecha de move-in se acerca.

## Enfoque por etapas (para no morder demasiado de un bocado)

- **MVP:** plantilla editable + ficha por residente + completar ítems (fecha/iniciales/adjunto) + tablero de avance básico. Esto ya entrega el 80% del valor.
- **Fase 2:** gates de cumplimiento + alertas por email + asignación por departamento.
- **Fase 3:** reportes/exports de move-ins, métricas (tiempo promedio de completar, departamentos más atrasados), historial por residente.

## Esfuerzo y riesgo

Es un módulo nuevo con su propio modelo de datos (por residente), así que **no es trivial** — pero **el andamiaje pesado ya está** (auth, storage, adjuntos, emails, exports, UI). El mayor trabajo nuevo es la ficha por residente, la plantilla por fases con metadatos de completado, y el tablero. Riesgo bajo para los datos existentes: vive como módulo aparte, no toca las inspecciones actuales.

## Recomendación

Vale la pena. Sugiero validar primero con Greg el alcance del **MVP** (plantilla + ficha + tablero), confirmar las fases/ítems exactos contra su binder real, y luego construir incremental. Empezar simple, probarlo con una comunidad piloto, y crecer.
