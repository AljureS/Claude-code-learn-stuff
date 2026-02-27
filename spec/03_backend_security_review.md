# Security Review: Sistema de Ratings

Revision de seguridad del PR que implementa el sistema de ratings (1-5 estrellas) para cursos.

Archivos revisados:
- `app/models/rating.py` (nuevo)
- `app/services/rating_service.py` (nuevo)
- `app/services/course_service.py` (modificado)
- `app/main.py` (modificado)
- `app/db/seed.py` (modificado)
- `app/test_main.py` (modificado)

---

## Resultado: Sin vulnerabilidades de alta confianza

| Categoria | Estado | Razon |
|---|---|---|
| SQL Injection | Limpio | Todas las queries usan SQLAlchemy ORM con filtros parametrizados. No hay SQL crudo con input de usuario. |
| Command Injection | Limpio | No hay llamadas a subprocess ni ejecucion dinamica de codigo. |
| Auth/Authz Bypass | Por diseno | Identificacion por `device_id` sin autenticacion es intencional segun spec del proyecto ("Sin auth"). |
| Deserializacion insegura | Limpio | FastAPI maneja deserializacion JSON de forma segura via Pydantic. |
| Path Traversal | N/A | No hay operaciones de sistema de archivos en el codigo modificado. |
| XSS | N/A | API JSON pura, no renderiza HTML. |
| Secrets hardcodeados | Limpio | Solo datos de ejemplo/fixture en seed. |
| Exposicion de datos | Limpio | No se filtra PII a traves de los nuevos endpoints. |

---

## Observaciones informativas

Hallazgos por debajo del umbral de reporte pero documentados como referencia.

### 1. UniqueConstraint vs Soft Deletes

**Archivo:** `app/models/rating.py:21`
**Severidad:** Baja (integridad de datos, no seguridad)

El constraint `uq_ratings_course_device` no excluye filas soft-deleted. Si un rating se marca como eliminado (`deleted_at` se setea) y luego el mismo dispositivo intenta crear un nuevo rating para el mismo curso, la base de datos rechazara el insert con error 500 porque el constraint UNIQUE aplica sobre todas las filas, incluyendo las eliminadas.

```python
UniqueConstraint('course_id', 'device_id', name='uq_ratings_course_device'),
```

**Solucion propuesta:** Reemplazar por un indice unico parcial:
```python
Index(
    'uq_ratings_course_device',
    'course_id', 'device_id',
    unique=True,
    postgresql_where='deleted_at IS NULL'
)
```

### 2. Formato de device_id no validado

**Archivo:** `app/main.py:110`
**Severidad:** Baja (calidad de datos, no seguridad)

La validacion de `device_id` solo verifica string vacio y longitud maxima de 64 caracteres. El docstring del modelo dice "UUID del dispositivo" pero acepta cualquier string. No es un riesgo de seguridad porque el valor siempre pasa por queries parametrizadas de SQLAlchemy.

```python
if not device_id or len(device_id) > 64:
    raise HTTPException(status_code=422, detail="Invalid device_id")
```

**Solucion propuesta (opcional):** Agregar validacion de formato UUID si se quiere consistencia:
```python
import re
UUID_PATTERN = re.compile(r'^[a-f0-9\-]{1,64}$')
if not device_id or not UUID_PATTERN.match(device_id):
    raise HTTPException(status_code=422, detail="Invalid device_id")
```

### 3. Error de DB expuesto en health endpoint (pre-existente)

**Archivo:** `app/main.py:52` (codigo previo al PR)
**Severidad:** Baja

La linea `health_status["database_error"] = str(e)` podria filtrar detalles internos de conexion a la base de datos (hostname, puerto) en mensajes de error. Este codigo ya existia antes del PR de ratings y no fue introducido por estos cambios.

---

## CORS

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

- Origins restringido a `localhost:3000` (correcto para desarrollo)
- Metodos limitados a GET y POST (minimo necesario)
- **Nota para produccion:** Cambiar `allow_origins` al dominio real y considerar restringir `allow_headers`

---

## Recomendaciones para futuro

Estas no son vulnerabilidades actuales, son mejoras a considerar cuando el proyecto escale:

1. **Rate limiting en POST /courses/{slug}/ratings** - Sin auth, un actor puede enviar muchos ratings con diferentes `device_id` para manipular promedios. Considerar rate limiting por IP cuando se implemente en produccion.
2. **Autenticacion** - El sistema actual depende de `device_id` que es trivialmente spoofeable. Aceptable para desarrollo, pero requiere auth real para produccion.
3. **HTTPS** - Actualmente todo corre sobre HTTP. Configurar TLS antes de exponer a internet.
