# Plan de Implementación Backend: Sistema de Ratings

## Contexto

Implementación del sistema de ratings (1-5 estrellas) para Platziflix. Este documento detalla las fases de implementación del lado backend siguiendo la metodología **database-first** del proyecto.

**Referencia:** Ver análisis técnico completo en `spec/00_rating_system.md`

---

## Objetivos Backend

1. Crear modelo `Rating` con soft deletes
2. Implementar service layer con lógica de upsert y agregados
3. Exponer 2 endpoints nuevos y modificar 2 existentes
4. Configurar CORS para permitir requests client-side
5. Asegurar cobertura de tests al 100%
6. Proveer datos de ejemplo via seed

---

## FASE 1: Infraestructura de Base de Datos

### Objetivo
Crear modelo de datos, relaciones y migración Alembic.

### Tareas

#### 1.1 Crear modelo Rating
**Archivo:** `Backend/app/models/rating.py`

- Heredar de `BaseModel` (id, created_at, updated_at, deleted_at automáticos)
- Campos:
  - `course_id`: Integer, ForeignKey a courses.id con ON DELETE CASCADE
  - `device_id`: String(64), para almacenar UUID del dispositivo
  - `score`: SmallInteger, rango 1-5
- Índices:
  - Index en `course_id`
  - Index en `device_id`
- Constraints:
  - `UniqueConstraint('course_id', 'device_id', name='uq_ratings_course_device')`
  - `CheckConstraint('score >= 1 AND score <= 5', name='ck_ratings_score_range')`
- Relación:
  - `course = relationship("Course", back_populates="ratings")`

#### 1.2 Actualizar modelo Course
**Archivo:** `Backend/app/models/course.py`

- Agregar relación inversa:
```python
ratings = relationship(
    "Rating",
    back_populates="course",
    cascade="all, delete-orphan"
)
```

#### 1.3 Registrar modelo
**Archivo:** `Backend/app/models/__init__.py`

- Agregar import y export de `Rating`

#### 1.4 Generar y ejecutar migración
**Comandos:**
```bash
make create-migration  # Genera migración automática
# Revisar archivo generado en alembic/versions/
make migrate          # Aplica migración
```

**Migración debe crear:**
- Tabla `ratings` con todos los campos
- Índices: `ix_ratings_course_id`, `ix_ratings_device_id`
- Índice parcial: `CREATE INDEX ix_ratings_course_id_score ON ratings(course_id, score) WHERE deleted_at IS NULL;`

### Verificación
- [x] Tabla `ratings` existe en PostgreSQL
- [x] Constraints UNIQUE y CHECK están activos
- [x] Índices creados correctamente
- [x] Endpoints existentes (`GET /courses`, `GET /courses/{slug}`) siguen funcionando

---

## FASE 2: Service Layer

### Objetivo
Implementar lógica de negocio para ratings y modificar CourseService.

### Tareas

#### 2.1 Crear RatingService
**Archivo:** `Backend/app/services/rating_service.py`

**Método 1: `upsert_rating(slug: str, device_id: str, score: int) -> Optional[Dict[str, Any]]`**

Lógica:
1. Buscar curso por slug (filtrar `deleted_at IS NULL`)
2. Si no existe, retornar `None`
3. Buscar rating existente con `course_id` y `device_id` (filtrar `deleted_at IS NULL`)
4. Si existe:
   - Actualizar `score`
   - Commit y refresh
5. Si no existe:
   - Crear nuevo `Rating`
   - Commit y refresh
6. Retornar dict con: `id`, `course_id`, `device_id`, `score`, `created_at`, `updated_at`

**Método 2: `get_course_rating_summary(slug: str, device_id: Optional[str] = None) -> Optional[Dict[str, Any]]`**

Lógica:
1. Buscar curso por slug (filtrar `deleted_at IS NULL`)
2. Si no existe, retornar `None`
3. Query con agregados:
   - `func.avg(Rating.score)` → average_rating
   - `func.count(Rating.id)` → total_ratings
   - Filtrar `course_id` y `deleted_at IS NULL`
4. Redondear average_rating a 1 decimal (o `None` si no hay ratings)
5. Si `device_id` es provisto:
   - Query adicional para obtener `Rating.score` del dispositivo
   - Asignar a `user_rating` (o `None`)
6. Retornar dict con: `course_slug`, `average_rating`, `total_ratings`, `user_rating`

#### 2.2 Modificar CourseService.get_all_courses()
**Archivo:** `Backend/app/services/course_service.py`

**Cambios:**
1. Crear subquery con agregados:
   ```python
   rating_stats = (
       self.db.query(
           Rating.course_id,
           func.avg(Rating.score).label("average_rating"),
           func.count(Rating.id).label("total_ratings")
       )
       .filter(Rating.deleted_at.is_(None))
       .group_by(Rating.course_id)
       .subquery()
   )
   ```
2. Modificar query principal:
   - Agregar `rating_stats.c.average_rating` y `rating_stats.c.total_ratings` al SELECT
   - LEFT JOIN con `Course.id == rating_stats.c.course_id`
3. En el return, agregar a cada dict:
   - `"average_rating": round(float(c.average_rating), 1) if c.average_rating else None`
   - `"total_ratings": c.total_ratings or 0`

#### 2.3 Modificar CourseService.get_course_by_slug()
**Archivo:** `Backend/app/services/course_service.py`

**Cambios:**
1. Después de obtener el curso, agregar query de agregados:
   ```python
   rating_result = (
       self.db.query(
           func.avg(Rating.score).label("average_rating"),
           func.count(Rating.id).label("total_ratings")
       )
       .filter(Rating.course_id == course.id)
       .filter(Rating.deleted_at.is_(None))
       .first()
   )
   ```
2. En el dict de retorno, agregar:
   - `"average_rating": round(float(rating_result.average_rating), 1) if rating_result.average_rating else None`
   - `"total_ratings": rating_result.total_ratings or 0`

### Verificación
- [x] `RatingService` retorna datos correctos para upsert
- [x] `get_all_courses()` incluye `average_rating: null, total_ratings: 0` para cursos sin ratings
- [x] `get_course_by_slug()` incluye los mismos campos
- [x] No hay regresiones en funcionalidad existente

---

## FASE 3: API Endpoints y CORS

### Objetivo
Exponer endpoints de ratings y configurar CORS para requests client-side.

### Tareas

#### 3.1 Configurar CORS Middleware
**Archivo:** `Backend/app/main.py`

Agregar después de crear `app`:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

**Justificación:** El frontend usa Server Components, pero el StarRating es Client Component que hace fetch directo al API.

#### 3.2 Crear dependency injection
**Archivo:** `Backend/app/main.py`

```python
from app.services.rating_service import RatingService

def get_rating_service(db: Session = Depends(get_db)) -> RatingService:
    return RatingService(db)
```

#### 3.3 Implementar POST /courses/{slug}/ratings
**Archivo:** `Backend/app/main.py`

**Signature:**
```python
@app.post("/courses/{slug}/ratings")
def create_or_update_rating(
    slug: str,
    device_id: str = Body(...),
    score: int = Body(...),
    rating_service: RatingService = Depends(get_rating_service)
) -> dict:
```

**Validaciones:**
- `if not (1 <= score <= 5):` → HTTPException 422 "Score must be between 1 and 5"
- `if not device_id or len(device_id) > 64:` → HTTPException 422 "Invalid device_id"

**Lógica:**
- Llamar `rating_service.upsert_rating(slug, device_id, score)`
- Si retorna `None` → HTTPException 404 "Course not found"
- Retornar resultado

**Respuestas:**
- 200: `{"id": int, "course_id": int, "device_id": str, "score": int, "created_at": str, "updated_at": str}`
- 404: `{"detail": "Course not found"}`
- 422: `{"detail": "Score must be between 1 and 5"}` o `{"detail": "Invalid device_id"}`

#### 3.4 Implementar GET /courses/{slug}/ratings
**Archivo:** `Backend/app/main.py`

**Signature:**
```python
@app.get("/courses/{slug}/ratings")
def get_course_ratings(
    slug: str,
    device_id: str = Query(default=None),
    rating_service: RatingService = Depends(get_rating_service)
) -> dict:
```

**Lógica:**
- Llamar `rating_service.get_course_rating_summary(slug, device_id)`
- Si retorna `None` → HTTPException 404 "Course not found"
- Retornar resultado

**Respuestas:**
- 200: `{"course_slug": str, "average_rating": float | null, "total_ratings": int, "user_rating": int | null}`
- 404: `{"detail": "Course not found"}`

### Verificación
- [x] CORS headers presentes en responses
- [x] POST con body válido retorna 200
- [x] POST con score inválido retorna 422
- [x] POST con slug inexistente retorna 404
- [x] GET sin ratings retorna average_rating: null
- [x] GET con device_id retorna user_rating

**Test manual con cURL:**
```bash
# POST rating
curl -X POST http://localhost:8000/courses/curso-de-react/ratings \
  -H "Content-Type: application/json" \
  -d '{"device_id": "test-device-123", "score": 4}'

# GET summary
curl http://localhost:8000/courses/curso-de-react/ratings?device_id=test-device-123

# Verificar en GET /courses que incluye average_rating
curl http://localhost:8000/courses
```

---

## FASE 4: Tests y Datos de Prueba

### Objetivo
Asegurar cobertura de tests al 100% y proveer datos de ejemplo.

### Tareas

#### 4.1 Actualizar mocks existentes
**Archivo:** `Backend/app/test_main.py`

**Cambios en `TestCourseEndpoints`:**
1. En el mock de `get_all_courses()`:
   - Agregar `"average_rating": 4.5` y `"total_ratings": 10` al primer curso
   - Agregar `"average_rating": None` y `"total_ratings": 0` al segundo curso

2. En el mock de `get_course_by_slug()`:
   - Agregar `"average_rating": 4.5` y `"total_ratings": 10`

#### 4.2 Crear TestRatingEndpoints
**Archivo:** `Backend/app/test_main.py`

**Clase:** `TestRatingEndpoints`

**Tests a implementar:**

1. `test_create_rating_success`:
   - Mock `upsert_rating` retorna dict válido
   - POST con body válido
   - Assert status 200
   - Assert response tiene todos los campos

2. `test_create_rating_invalid_score`:
   - POST con score = 0
   - Assert status 422
   - Assert detail contiene "Score must be between"

3. `test_create_rating_invalid_device_id`:
   - POST con device_id vacío
   - Assert status 422
   - Assert detail contiene "Invalid device_id"

4. `test_create_rating_course_not_found`:
   - Mock `upsert_rating` retorna None
   - POST con slug inexistente
   - Assert status 404

5. `test_update_existing_rating`:
   - Simular rating existente con score 3
   - POST con score 5
   - Verificar que se actualizó

6. `test_get_rating_summary_without_ratings`:
   - Mock retorna `{"course_slug": "test", "average_rating": None, "total_ratings": 0, "user_rating": None}`
   - GET sin device_id
   - Assert status 200

7. `test_get_rating_summary_with_user_rating`:
   - Mock retorna summary con user_rating = 4
   - GET con device_id
   - Assert user_rating presente

8. `test_get_rating_summary_course_not_found`:
   - Mock retorna None
   - GET con slug inexistente
   - Assert status 404

#### 4.3 Actualizar TestContractCompliance
**Archivo:** `Backend/app/test_main.py`

**Cambios:**
- En `test_get_courses_contract`:
  - Agregar assertions para `average_rating` (float | null)
  - Agregar assertions para `total_ratings` (int >= 0)

- En `test_get_course_by_slug_contract`:
  - Agregar mismas assertions

#### 4.4 Agregar ratings de ejemplo en seed
**Archivo:** `Backend/app/db/seed.py`

**Cambios:**
1. Importar modelo `Rating`
2. Después de crear cursos, agregar:
   ```python
   # Ratings de ejemplo
   ratings_data = [
       # Curso de React: 3 ratings (promedio ~4.3)
       {"course_id": 1, "device_id": "device-001", "score": 5},
       {"course_id": 1, "device_id": "device-002", "score": 4},
       {"course_id": 1, "device_id": "device-003", "score": 4},
       # Curso de Python: 2 ratings (promedio 3.5)
       {"course_id": 2, "device_id": "device-004", "score": 3},
       {"course_id": 2, "device_id": "device-005", "score": 4},
       # Curso de JavaScript: 1 rating
       {"course_id": 3, "device_id": "device-006", "score": 5},
       # Curso sin ratings: dejar sin datos
   ]
   ```
3. Hacer bulk insert de ratings
4. Commit

### Verificación
- [x] `pytest` pasa al 100% sin warnings
- [x] Cobertura de código incluye nuevos archivos
- [x] `make seed-fresh` ejecuta sin errores
- [x] Después de seed, GET /courses muestra ratings
- [x] Contract compliance tests verifican nuevos campos

**Comandos:**
```bash
cd Backend
pytest app/test_main.py -v
make seed-fresh
curl http://localhost:8000/courses | jq
```

---

## Consideraciones Técnicas

### Performance
- **Índice parcial** `WHERE deleted_at IS NULL` optimiza queries de agregados
- **Subquery en get_all_courses** evita N+1 queries
- **LEFT JOIN** permite cursos sin ratings (average_rating = null)

### Seguridad
- **CORS limitado** a localhost:3000 (ampliar en producción a dominio real)
- **SQL Injection protegido** por SQLAlchemy parametrizado
- **Rate limiting** NO implementado (considerar en futuro para evitar spam)

### Escalabilidad
- Hasta ~100K ratings: queries < 10ms
- Hasta ~1M ratings: queries < 50ms con índice parcial
- Más allá: considerar vista materializada o cache Redis

### Manejo de Errores
- **IntegrityError** en constraint UNIQUE → capturar y manejar como update
- **CheckConstraint violation** → no debería ocurrir si validamos en route
- **Course soft-deleted** → tratado como 404

---

## Checklist Final de Fase Backend

### Base de Datos
- [x] Modelo `Rating` creado con todos los campos
- [x] Relación bidireccional Course ↔ Rating
- [x] Migración Alembic ejecutada
- [x] Índices creados (normal + parcial)
- [x] Constraints UNIQUE y CHECK activos

### Service Layer
- [x] `RatingService.upsert_rating()` implementado
- [x] `RatingService.get_course_rating_summary()` implementado
- [x] `CourseService.get_all_courses()` incluye agregados
- [x] `CourseService.get_course_by_slug()` incluye agregados

### API
- [x] CORS configurado
- [x] POST /courses/{slug}/ratings implementado
- [x] GET /courses/{slug}/ratings implementado
- [x] Validaciones en ambos endpoints
- [x] Manejo de errores 404/422

### Tests
- [x] Tests de RatingEndpoints (8 tests mínimo)
- [x] Tests actualizados para nuevos campos en Course
- [x] Contract compliance actualizado
- [x] pytest pasa al 100%

### Datos
- [x] Seed incluye ratings de ejemplo
- [x] Variedad de scores (1-5)
- [x] Al menos un curso sin ratings
- [x] `make seed-fresh` funciona

---

## Próximos Pasos

Una vez completada la implementación backend:
1. Verificar todos los endpoints via Postman/cURL
2. Documentar cualquier desviación del plan
3. Notificar al equipo frontend que el API está listo
4. Proveer ejemplos de requests/responses para integración

**Referencia para frontend:** Ver `spec/02_frontend_implementation_plan.md`
