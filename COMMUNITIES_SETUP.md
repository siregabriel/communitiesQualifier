# Communities Setup - 38 Communities Created

## Overview

Se han creado exitosamente **38 comunidades** con sus preguntas independientes. Cada comunidad tiene su propia copia de las preguntas que puede ser modificada de manera independiente.

## Estadísticas

- **Total de Comunidades**: 38
- **Total de Preguntas**: 152 (4 preguntas × 38 comunidades)
- **Preguntas por Comunidad**: 4

## Características Clave

### 1. Preguntas Independientes
Cada comunidad tiene sus propias copias de las preguntas. Esto significa que:
- ✅ Puedes modificar una pregunta para una comunidad sin afectar a las demás
- ✅ Cada pregunta tiene un ID único por comunidad
- ✅ Las preguntas mantienen una referencia al template original (`template_id`)

### 2. Gestión Flexible
- Los administradores pueden ver y gestionar todas las comunidades
- Los usuarios staff solo ven su comunidad asignada
- Las preguntas se pueden editar independientemente en el Question Manager

## Lista Completa de Comunidades

### Georgia (8 comunidades)
1. Kelley Place, Enterprise
2. Madison Heights Enterprise, Enterprise
3. Monark Grove Madison
4. Monark Grove Greystone
5. Legacy Ridge Trussville, Trussville
6. Madison at The Range, Madison
7. The Goldton at Athens
8. The Goldton at Jones Farm

### Florida (8 comunidades)
9. Madison at Clermont, Clermont
10. Madison at Ocoee, Ocoee
11. Madison at Oviedo, Oviedo
12. The Goldton at Venice, Venice
13. The Goldton at St. Petersburg, St. Petersburg
14. Lake Howard Heights, Winter Haven
15. The Canopy At Beacon Woods
16. The Goldton At Lake Nona

### North Carolina (8 comunidades)
17. Madison Heights Evans, Evans
18. Legacy at Savannah Quarters, Pooler
19. Legacy Reserve at Old Town, Columbus
20. Legacy Ridge at Alpharetta, Alpharetta
21. Legacy Ridge at Buckhead, Atlanta
22. Legacy Ridge at Marietta, Marietta
23. The Canopy at Westridge, McDonough
24. The Overlook at Suwanee, Suwanee

### Ohio (1 comunidad)
25. Legacy Reserve at Fritz Farm, Lexington

### Mississippi (2 comunidades)
26. The Goldton at Southaven, Southaven
27. The Goldton at Adelaide, Starkville

### South Carolina (4 comunidades)
28. Oakview Park, Greenville
29. Spring Park, Travelers Rest
30. Legacy Reserve Fairview Park, Simpsonville
31. Wildcat Senior Living, Summerville

### Tennessee (1 comunidad)
32. The Goldton at Spring Hill, Spring Hill

### Texas (2 comunidades)
33. The Oscar at Georgetown
34. The Oscar at Veramendi (June 2026)

### Maryland (2 comunidades)
35. Tribute at Black Hill
36. Tribute at Melford

### Virginia (2 comunidades)
37. Tribute at One Loudoun
38. Tribute at The Glen

## Usuarios de Ejemplo

Se han actualizado los usuarios de ejemplo para usar las nuevas comunidades:

```python
USERS_DB = {
    'john': {
        'password': 'pass123',
        'community': 'Kelley Place, Enterprise'
    },
    'maria': {
        'password': 'pass123',
        'community': 'Madison Heights Enterprise, Enterprise'
    },
    'carlos': {
        'password': 'pass123',
        'community': 'The Goldton at Athens'
    },
    'admin': {
        'password': 'admin123',
        'community': None  # Admin puede ver todas las comunidades
    }
}
```

## Estructura de Datos

### Formato de Pregunta
```json
{
    "id": "q_1778436221192_8491",
    "text": "Is the common area clean and well-maintained?",
    "photo_required": true,
    "communities": ["Kelley Place, Enterprise"],
    "created_at": "2026-05-18T10:30:00Z",
    "updated_at": "2026-05-18T10:30:00Z",
    "is_active": true,
    "template_id": "q_1705315800000_5678"
}
```

### Campos Importantes
- **id**: ID único para esta pregunta específica de la comunidad
- **communities**: Array con una sola comunidad (preguntas independientes)
- **template_id**: Referencia al template original (para tracking)
- **is_active**: Indica si la pregunta está activa

## Archivos Modificados

1. **app_mantenimiento/data/questions.json**
   - Actualizado con 152 preguntas (4 por comunidad × 38 comunidades)
   - Cada pregunta asignada a una sola comunidad

2. **app_mantenimiento/app.py**
   - `ALL_COMMUNITIES`: Lista actualizada con las 38 comunidades reales
   - `USERS_DB`: Usuarios de ejemplo actualizados con comunidades reales

3. **Scripts Creados**
   - `create_communities.py`: Script para crear las comunidades y preguntas
   - `verify_communities.py`: Script para verificar la configuración

## Cómo Usar

### Para Administradores
1. Login como `admin` / `admin123`
2. Acceder al Question Manager
3. Ver y editar preguntas de todas las comunidades
4. Crear nuevas preguntas y asignarlas a comunidades específicas

### Para Staff
1. Login con usuario asignado a una comunidad
2. Solo verán las preguntas de su comunidad
3. Pueden realizar inspecciones para su comunidad

### Modificar Preguntas Independientemente
1. En el Question Manager, buscar la pregunta de la comunidad específica
2. Hacer clic en "Edit"
3. Modificar el texto, requisitos de foto, etc.
4. Los cambios solo afectarán a esa comunidad

## Verificación

Para verificar que todo está configurado correctamente:

```bash
python3 verify_communities.py
```

Este script mostrará:
- Total de comunidades
- Total de preguntas
- Preguntas por comunidad
- Lista completa de comunidades por estado

## Próximos Pasos

1. ✅ Comunidades creadas
2. ✅ Preguntas asignadas independientemente
3. ✅ Backend actualizado
4. ✅ Sistema listo para uso

### Recomendaciones
- Crear usuarios adicionales según sea necesario
- Asignar usuarios a sus comunidades correspondientes
- Personalizar preguntas por comunidad según requisitos específicos
- Considerar implementar autenticación más robusta en producción

## Notas Técnicas

### Independencia de Preguntas
Cada pregunta tiene su propio ID único y está asignada a una sola comunidad. Esto permite:
- Modificaciones independientes sin afectar otras comunidades
- Tracking de cambios por comunidad
- Flexibilidad para requisitos específicos de cada ubicación

### Escalabilidad
El sistema está diseñado para:
- Agregar nuevas comunidades fácilmente
- Crear preguntas específicas por comunidad
- Mantener un historial de cambios (via `updated_at`)

---

**Fecha de Creación**: 18 de Mayo, 2026
**Versión**: 1.0
**Estado**: ✅ Completado y Verificado
