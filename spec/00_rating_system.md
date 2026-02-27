# Analisis Tecnico: Sistema de Ratings (1-5 Estrellas)

## Problema

Platziflix necesita un sistema de calificaciones por estrellas (1-5) que permita a los usuarios calificar cursos. Dado que el sistema **no tiene autenticacion**, la identidad del usuario se resuelve mediante un `device_id` generado en el cliente y persistido en `localStorage`.

### Restricciones

- **Sin autenticacion**: No existen modelos de usuario ni tokens. La unicidad del rating se garantiza por `device_id`.
- **Sin CORS configurado**: Se debera agregar middleware CORS en el backend para aceptar peticiones POST desde el frontend (actualmente solo hay GET y el frontend usa SSR con `fetch` server-side, pero los ratings requieren fetch client-side).
- **Sin Pydantic schemas**: El backend actual serializa a diccionarios manuales. Se mantiene la consistencia con el patron existente.
- **Frontend 100% Server Components**: No hay ningun client component. El rating sera el **primer componente interactivo** con estado client-side (`"use client"`).

---

## Impacto Arquitectural

- **Backend**: Nuevo modelo `Rating`, nuevo `RatingService`, 2 endpoints nuevos, modificacion de `CourseService` para incluir aggregates en respuestas existentes, CORS middleware, migracion Alembic.
- **Frontend**: Primer client component (`StarRating`), utility de `device_id` con `localStorage`, tipos TypeScript actualizados, integracion en cards y detalle de curso.
- **Base de datos**: Nueva tabla `ratings` con constraint UNIQUE `(course_id, device_id)`, CHECK constraint para score 1-5, indices para optimizacion de aggregates.

---

## Propuesta de Solucion

### 1. Diseno de Base de Datos

#### Tabla `ratings`

```sql
CREATE TABLE ratings (
    id              SERIAL PRIMARY KEY,
    course_id       INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    device_id       VARCHAR(64) NOT NULL,
    score           SMALLINT NOT NULL CHECK (score >= 1 AND score <= 5),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMP NULL,

    CONSTRAINT uq_ratings_course_device UNIQUE (course_id, device_id)
);

CREATE INDEX ix_ratings_course_id ON ratings(course_id);
CREATE INDEX ix_ratings_device_id ON ratings(device_id);
CREATE INDEX ix_ratings_course_id_score ON ratings(course_id, score)
    WHERE deleted_at IS NULL;
```

#### Justificacion de decisiones

| Decision | Razon |
|----------|-------|
| `SERIAL PRIMARY KEY` (id) | Consistencia con `BaseModel` existente que usa `Column(Integer, primary_key=True, index=True)` |
| `course_id` con `ON DELETE CASCADE` | Si un curso se elimina fisicamente, sus ratings tambien. Patron ya usado en `lessons` con `cascade="all, delete-orphan"` |
| `device_id VARCHAR(64)` | UUIDv4 tiene 36 caracteres con guiones. 64 caracteres da margen para cualquier formato futuro |
| `score SMALLINT CHECK(1..5)` | Constraint a nivel de DB. SMALLINT ocupa 2 bytes vs 4 de INTEGER |
| `UNIQUE(course_id, device_id)` | Un dispositivo solo puede calificar un curso una vez. Permite upsert (actualizar rating) |
| Indice parcial `WHERE deleted_at IS NULL` | Optimiza la consulta de promedio excluyendo ratings soft-deleted directamente en el indice |
| Hereda `BaseModel` | Consistencia con `id`, `created_at`, `updated_at`, `deleted_at` automaticos |

#### Modelo SQLAlchemy

```python
# Backend/app/models/rating.py

from sqlalchemy import Column, Integer, SmallInteger, String, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship
from .base import BaseModel


class Rating(BaseModel):
    __tablename__ = 'ratings'

    course_id = Column(Integer, ForeignKey('courses.id', ondelete='CASCADE'), nullable=False, index=True)
    device_id = Column(String(64), nullable=False, index=True)
    score = Column(SmallInteger, nullable=False)

    course = relationship("Course", back_populates="ratings")

    __table_args__ = (
        UniqueConstraint('course_id', 'device_id', name='uq_ratings_course_device'),
        CheckConstraint('score >= 1 AND score <= 5', name='ck_ratings_score_range'),
    )
```

#### Relacion inversa en Course

```python
# Agregar en Backend/app/models/course.py

ratings = relationship(
    "Rating",
    back_populates="course",
    cascade="all, delete-orphan"
)
```

---

### 2. API Contract

#### POST /courses/{slug}/ratings (NUEVO)

Crear o actualizar el rating de un dispositivo para un curso.

**Request**:
```
POST /courses/{slug}/ratings
Content-Type: application/json

{
    "device_id": "550e8400-e29b-41d4-a716-446655440000",
    "score": 4
}
```

**Validaciones**:
- `device_id`: string, requerido, longitud 1-64
- `score`: integer, requerido, rango 1-5 (inclusive)
- `slug`: debe corresponder a un curso existente y no eliminado

**Response 200**:
```json
{
    "id": 15,
    "course_id": 1,
    "device_id": "550e8400-e29b-41d4-a716-446655440000",
    "score": 4,
    "created_at": "2026-02-03T10:30:00",
    "updated_at": "2026-02-03T10:30:00"
}
```

**Response 404**:
```json
{ "detail": "Course not found" }
```

**Response 422**:
```json
{ "detail": "Score must be between 1 and 5" }
```

#### GET /courses/{slug}/ratings (NUEVO)

Obtener resumen de ratings de un curso y opcionalmente el rating del dispositivo actual.

**Request**:
```
GET /courses/{slug}/ratings?device_id=550e8400-e29b-41d4-a716-446655440000
```

**Response 200**:
```json
{
    "course_slug": "curso-de-react",
    "average_rating": 4.2,
    "total_ratings": 15,
    "user_rating": 4
}
```

- `average_rating`: float redondeado a 1 decimal, `null` si no hay ratings
- `total_ratings`: integer >= 0
- `user_rating`: integer 1-5 o `null` si el device_id no ha calificado o no se envio

**Response 404**:
```json
{ "detail": "Course not found" }
```

#### GET /courses (MODIFICADO)

Agregar `average_rating` y `total_ratings` a cada curso.

```json
[
    {
        "id": 1,
        "name": "Curso de React",
        "description": "Aprende React desde cero",
        "thumbnail": "https://via.placeholder.com/150",
        "slug": "curso-de-react",
        "average_rating": 4.2,
        "total_ratings": 15
    }
]
```

#### GET /courses/{slug} (MODIFICADO)

Agregar `average_rating` y `total_ratings` al detalle.

```json
{
    "id": 1,
    "name": "Curso de React",
    "description": "...",
    "thumbnail": "...",
    "slug": "curso-de-react",
    "teacher_id": [1, 2],
    "classes": [...],
    "average_rating": 4.2,
    "total_ratings": 15
}
```

---

### 3. Service Layer

#### RatingService

```python
# Backend/app/services/rating_service.py

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.course import Course
from app.models.rating import Rating


class RatingService:

    def __init__(self, db: Session):
        self.db = db

    def upsert_rating(self, slug: str, device_id: str, score: int) -> Optional[Dict[str, Any]]:
        course = (
            self.db.query(Course)
            .filter(Course.slug == slug)
            .filter(Course.deleted_at.is_(None))
            .first()
        )
        if not course:
            return None

        existing_rating = (
            self.db.query(Rating)
            .filter(Rating.course_id == course.id)
            .filter(Rating.device_id == device_id)
            .filter(Rating.deleted_at.is_(None))
            .first()
        )

        if existing_rating:
            existing_rating.score = score
            self.db.commit()
            self.db.refresh(existing_rating)
            rating = existing_rating
        else:
            rating = Rating(course_id=course.id, device_id=device_id, score=score)
            self.db.add(rating)
            self.db.commit()
            self.db.refresh(rating)

        return {
            "id": rating.id,
            "course_id": rating.course_id,
            "device_id": rating.device_id,
            "score": rating.score,
            "created_at": rating.created_at.isoformat(),
            "updated_at": rating.updated_at.isoformat()
        }

    def get_course_rating_summary(
        self, slug: str, device_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        course = (
            self.db.query(Course)
            .filter(Course.slug == slug)
            .filter(Course.deleted_at.is_(None))
            .first()
        )
        if not course:
            return None

        result = (
            self.db.query(
                func.avg(Rating.score).label("average_rating"),
                func.count(Rating.id).label("total_ratings")
            )
            .filter(Rating.course_id == course.id)
            .filter(Rating.deleted_at.is_(None))
            .first()
        )

        average_rating = round(float(result.average_rating), 1) if result.average_rating else None
        total_ratings = result.total_ratings or 0

        user_rating = None
        if device_id:
            user_rating_obj = (
                self.db.query(Rating.score)
                .filter(Rating.course_id == course.id)
                .filter(Rating.device_id == device_id)
                .filter(Rating.deleted_at.is_(None))
                .first()
            )
            if user_rating_obj:
                user_rating = user_rating_obj.score

        return {
            "course_slug": slug,
            "average_rating": average_rating,
            "total_ratings": total_ratings,
            "user_rating": user_rating
        }
```

#### Cambios en CourseService

**`get_all_courses()` — agregar subquery con LEFT JOIN:**

```python
from sqlalchemy import func
from app.models.rating import Rating

def get_all_courses(self) -> list[dict]:
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

    courses = (
        self.db.query(
            Course.id, Course.name, Course.description,
            Course.thumbnail, Course.slug,
            rating_stats.c.average_rating,
            rating_stats.c.total_ratings
        )
        .outerjoin(rating_stats, Course.id == rating_stats.c.course_id)
        .filter(Course.deleted_at.is_(None))
        .all()
    )

    return [
        {
            "id": c.id, "name": c.name, "description": c.description,
            "thumbnail": c.thumbnail, "slug": c.slug,
            "average_rating": round(float(c.average_rating), 1) if c.average_rating else None,
            "total_ratings": c.total_ratings or 0
        }
        for c in courses
    ]
```

**`get_course_by_slug()` — agregar query adicional de aggregates:**

```python
def get_course_by_slug(self, slug: str) -> dict | None:
    course = (
        self.db.query(Course)
        .options(joinedload(Course.teachers), joinedload(Course.lessons))
        .filter(Course.slug == slug)
        .filter(Course.deleted_at.is_(None))
        .first()
    )
    if not course:
        return None

    rating_result = (
        self.db.query(
            func.avg(Rating.score).label("average_rating"),
            func.count(Rating.id).label("total_ratings")
        )
        .filter(Rating.course_id == course.id)
        .filter(Rating.deleted_at.is_(None))
        .first()
    )

    return {
        "id": course.id, "name": course.name,
        "description": course.description,
        "thumbnail": course.thumbnail, "slug": course.slug,
        "teacher_id": [t.id for t in course.teachers],
        "classes": [
            {"id": l.id, "name": l.name, "description": l.description, "slug": l.slug}
            for l in course.lessons if l.deleted_at is None
        ],
        "average_rating": round(float(rating_result.average_rating), 1) if rating_result.average_rating else None,
        "total_ratings": rating_result.total_ratings or 0
    }
```

---

### 4. Rutas y CORS en main.py

```python
from fastapi.middleware.cors import CORSMiddleware
from app.services.rating_service import RatingService

# Despues de crear app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

def get_rating_service(db: Session = Depends(get_db)) -> RatingService:
    return RatingService(db)

@app.post("/courses/{slug}/ratings")
def create_or_update_rating(
    slug: str,
    device_id: str = Body(...),
    score: int = Body(...),
    rating_service: RatingService = Depends(get_rating_service)
) -> dict:
    if not (1 <= score <= 5):
        raise HTTPException(status_code=422, detail="Score must be between 1 and 5")
    if not device_id or len(device_id) > 64:
        raise HTTPException(status_code=422, detail="Invalid device_id")

    result = rating_service.upsert_rating(slug, device_id, score)
    if result is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return result

@app.get("/courses/{slug}/ratings")
def get_course_ratings(
    slug: str,
    device_id: str = Query(default=None),
    rating_service: RatingService = Depends(get_rating_service)
) -> dict:
    result = rating_service.get_course_rating_summary(slug, device_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return result
```

---

### 5. Diseno de Componentes Frontend

#### Estrategia para device_id

```typescript
// Frontend/src/utils/deviceId.ts

const STORAGE_KEY = "platziflix_device_id";

export function getDeviceId(): string {
  if (typeof window === "undefined") return "";
  let deviceId = localStorage.getItem(STORAGE_KEY);
  if (!deviceId) {
    deviceId = crypto.randomUUID();
    localStorage.setItem(STORAGE_KEY, deviceId);
  }
  return deviceId;
}
```

- `typeof window === "undefined"` protege contra ejecucion server-side
- `crypto.randomUUID()` soportado en Chrome 92+, Firefox 95+, Safari 15.4+

#### Tipos TypeScript

```typescript
// Agregar a Frontend/src/types/index.ts

// Agregar a interface Course:
//   average_rating: number | null;
//   total_ratings: number;

export interface RatingSummary {
  course_slug: string;
  average_rating: number | null;
  total_ratings: number;
  user_rating: number | null;
}

export interface RatingResponse {
  id: number;
  course_id: number;
  device_id: string;
  score: number;
  created_at: string;
  updated_at: string;
}
```

#### Componente StarRating (Client Component)

```typescript
// Frontend/src/components/StarRating/StarRating.tsx
"use client";

import { FC, useState, useEffect, useCallback } from "react";
import styles from "./StarRating.module.scss";
import { getDeviceId } from "@/utils/deviceId";

interface StarRatingProps {
  courseSlug: string;
  initialAverage: number | null;
  initialTotal: number;
}

export const StarRating: FC<StarRatingProps> = ({
  courseSlug, initialAverage, initialTotal,
}) => {
  const [averageRating, setAverageRating] = useState(initialAverage);
  const [totalRatings, setTotalRatings] = useState(initialTotal);
  const [userRating, setUserRating] = useState<number | null>(null);
  const [hoveredStar, setHoveredStar] = useState<number | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    const deviceId = getDeviceId();
    if (!deviceId) return;
    fetch(`http://localhost:8000/courses/${courseSlug}/ratings?device_id=${deviceId}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.user_rating !== null) setUserRating(data.user_rating);
        setAverageRating(data.average_rating);
        setTotalRatings(data.total_ratings);
      })
      .catch(() => {});
  }, [courseSlug]);

  const handleRate = useCallback(async (score: number) => {
    if (isSubmitting) return;
    const deviceId = getDeviceId();
    if (!deviceId) return;
    setIsSubmitting(true);
    try {
      const res = await fetch(
        `http://localhost:8000/courses/${courseSlug}/ratings`,
        { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ device_id: deviceId, score }) }
      );
      if (res.ok) {
        setUserRating(score);
        const summaryRes = await fetch(
          `http://localhost:8000/courses/${courseSlug}/ratings?device_id=${deviceId}`
        );
        if (summaryRes.ok) {
          const summary = await summaryRes.json();
          setAverageRating(summary.average_rating);
          setTotalRatings(summary.total_ratings);
        }
      }
    } catch {} finally { setIsSubmitting(false); }
  }, [courseSlug, isSubmitting]);

  const displayRating = hoveredStar ?? userRating ?? 0;

  return (
    <div className={styles.starRating}>
      <div className={styles.stars} role="radiogroup" aria-label="Calificacion del curso">
        {[1, 2, 3, 4, 5].map((star) => (
          <button key={star} type="button"
            className={`${styles.star} ${star <= displayRating ? styles.filled : ""}`}
            onMouseEnter={() => setHoveredStar(star)}
            onMouseLeave={() => setHoveredStar(null)}
            onClick={() => handleRate(star)}
            disabled={isSubmitting}
            role="radio"
            aria-checked={userRating === star}
            aria-label={`${star} estrella${star > 1 ? "s" : ""}`}
          >&#9733;</button>
        ))}
      </div>
      <div className={styles.info}>
        {averageRating !== null
          ? <span className={styles.average}>{averageRating.toFixed(1)}</span>
          : <span className={styles.noRatings}>Sin calificaciones</span>}
        <span className={styles.total}>
          ({totalRatings} {totalRatings === 1 ? "voto" : "votos"})
        </span>
      </div>
    </div>
  );
};
```

#### Flujo de datos

```
SSR (Server Component): page.tsx
  fetch("/courses") -> courses con average_rating, total_ratings
    -> Course card muestra average_rating (solo lectura, server-rendered)

SSR (Server Component): course/[slug]/page.tsx
  fetch("/courses/{slug}") -> course con average_rating, total_ratings
    -> CourseDetail recibe datos via props
      -> StarRating (CLIENT) recibe initialAverage, initialTotal
        -> useEffect: GET /courses/{slug}/ratings?device_id=X (hidrata user_rating)
        -> onClick: POST /courses/{slug}/ratings (envia score, refresca aggregate)
```

---

## Plan de Implementacion

### Fase 1: Backend — Modelo y Migracion

| Paso | Archivo | Accion | Depende de |
|------|---------|--------|------------|
| 1.1 | `Backend/app/models/rating.py` | Crear modelo Rating | - |
| 1.2 | `Backend/app/models/course.py` | Agregar relationship `ratings` | 1.1 |
| 1.3 | `Backend/app/models/__init__.py` | Registrar Rating en exports | 1.1 |
| 1.4 | Alembic migration | `make create-migration` + `make migrate` | 1.1, 1.2, 1.3 |

**Verificacion**: La tabla `ratings` existe en PostgreSQL. Endpoints existentes siguen funcionando.

### Fase 2: Backend — Service Layer

| Paso | Archivo | Accion | Depende de |
|------|---------|--------|------------|
| 2.1 | `Backend/app/services/rating_service.py` | Crear RatingService completo | Fase 1 |
| 2.2 | `Backend/app/services/course_service.py` | Modificar `get_all_courses` (subquery rating) | Fase 1 |
| 2.3 | `Backend/app/services/course_service.py` | Modificar `get_course_by_slug` (aggregate) | Fase 1 |

**Verificacion**: Endpoints existentes devuelven `average_rating: null, total_ratings: 0`.

### Fase 3: Backend — Rutas y CORS

| Paso | Archivo | Accion | Depende de |
|------|---------|--------|------------|
| 3.1 | `Backend/app/main.py` | Agregar CORSMiddleware | - |
| 3.2 | `Backend/app/main.py` | Agregar `get_rating_service` dependency | 2.1 |
| 3.3 | `Backend/app/main.py` | Agregar `POST /courses/{slug}/ratings` | 2.1, 3.2 |
| 3.4 | `Backend/app/main.py` | Agregar `GET /courses/{slug}/ratings` | 2.1, 3.2 |

**Verificacion**: Todos los endpoints responden via cURL.

### Fase 4: Backend — Tests y Seed

| Paso | Archivo | Accion | Depende de |
|------|---------|--------|------------|
| 4.1 | `Backend/app/test_main.py` | Actualizar mocks con `average_rating`/`total_ratings` | Fase 2 |
| 4.2 | `Backend/app/test_main.py` | Agregar `TestRatingEndpoints` y fixtures | Fase 3 |
| 4.3 | `Backend/app/test_main.py` | Actualizar `TestContractCompliance` | 4.1 |
| 4.4 | `Backend/app/db/seed.py` | Agregar ratings de ejemplo | Fase 1 |

**Verificacion**: `pytest` pasa al 100%. `make seed-fresh` carga ratings.

### Fase 5: Frontend — Utilidades y Tipos

| Paso | Archivo | Accion | Depende de |
|------|---------|--------|------------|
| 5.1 | `Frontend/src/utils/deviceId.ts` | Crear helper de device_id | - |
| 5.2 | `Frontend/src/types/index.ts` | Agregar campos a Course, crear RatingSummary, RatingResponse | - |

### Fase 6: Frontend — StarRating Component

| Paso | Archivo | Accion | Depende de |
|------|---------|--------|------------|
| 6.1 | `Frontend/src/components/StarRating/StarRating.tsx` | Crear client component | 5.1, 5.2 |
| 6.2 | `Frontend/src/components/StarRating/StarRating.module.scss` | Crear estilos | - |

### Fase 7: Frontend — Integracion

| Paso | Archivo | Accion | Depende de |
|------|---------|--------|------------|
| 7.1 | `Frontend/src/components/Course/Course.tsx` | Agregar display de `average_rating` | 5.2 |
| 7.2 | `Frontend/src/components/Course/Course.module.scss` | Estilos de rating en card | 7.1 |
| 7.3 | `Frontend/src/components/CourseDetail/CourseDetail.tsx` | Integrar StarRating | 6.1, 5.2 |
| 7.4 | `Frontend/src/components/CourseDetail/CourseDetail.module.scss` | Estilos ratingSection | 7.3 |
| 7.5 | `Frontend/src/app/page.tsx` | Pasar props de rating a Course | 5.2, 7.1 |

**Verificacion**: Frontend compila, estrellas visibles en detalle, promedio en cards.

### Fase 8: Frontend — Tests

| Paso | Archivo | Accion | Depende de |
|------|---------|--------|------------|
| 8.1 | `Frontend/src/components/StarRating/__tests__/StarRating.test.tsx` | Tests: render, click, fetch mock | 6.1 |
| 8.2 | Tests de Course card | Verificar que `average_rating` se renderiza | 7.1 |

---

## Consideraciones de Performance

| Area | Consideracion | Mitigacion |
|------|---------------|------------|
| Subquery en `get_all_courses` | LEFT JOIN computa aggregates en una sola query | O(n) en ratings, no O(n*m) |
| Indice para AVG/COUNT | Sin indice, full scan de ratings por request | Indice parcial `(course_id, score) WHERE deleted_at IS NULL` |
| Concurrencia en upsert | Race condition con mismo device_id simultaneo | Constraint UNIQUE lanza IntegrityError |
| Doble fetch en StarRating | useEffect GET despues de SSR | SSR data evita layout shift; GET hidrata user_rating |

**Escala estimada**: Hasta ~100K ratings con queries < 10ms. Hasta ~1M con queries < 50ms (con indice parcial). Mas alla: considerar vista materializada o cache Redis.

---

## Consideraciones de Seguridad

### Validaciones por capa

| Capa | Validacion |
|------|-----------|
| Frontend | Score 1-5 controlado por UI (5 botones) |
| Backend Route | `1 <= score <= 5`, `len(device_id) <= 64` |
| Backend Service | Course existe y `deleted_at IS NULL` |
| Database | `CHECK(score >= 1 AND score <= 5)`, `UNIQUE(course_id, device_id)` |

### Riesgos

| Vector | Riesgo | Mitigacion |
|--------|--------|------------|
| Spam de ratings con device_id aleatorios | Alto | Rate limiting por IP (futuro) |
| SQL Injection via device_id | Bajo | SQLAlchemy parametriza queries |
| CSRF en POST | Bajo | CORS limita origenes |

---

## Resumen de Archivos Afectados

### Backend: 3 nuevos, 5 modificados

| Archivo | Accion |
|---------|--------|
| `Backend/app/models/rating.py` | **NUEVO** |
| `Backend/app/services/rating_service.py` | **NUEVO** |
| `Backend/app/alembic/versions/xxx_add_ratings_table.py` | **NUEVO** (autogenerada) |
| `Backend/app/models/__init__.py` | MODIFICAR |
| `Backend/app/models/course.py` | MODIFICAR |
| `Backend/app/services/course_service.py` | MODIFICAR |
| `Backend/app/main.py` | MODIFICAR |
| `Backend/app/test_main.py` | MODIFICAR |
| `Backend/app/db/seed.py` | MODIFICAR |

### Frontend: 4 nuevos, 5 modificados

| Archivo | Accion |
|---------|--------|
| `Frontend/src/utils/deviceId.ts` | **NUEVO** |
| `Frontend/src/components/StarRating/StarRating.tsx` | **NUEVO** |
| `Frontend/src/components/StarRating/StarRating.module.scss` | **NUEVO** |
| `Frontend/src/components/StarRating/__tests__/StarRating.test.tsx` | **NUEVO** |
| `Frontend/src/types/index.ts` | MODIFICAR |
| `Frontend/src/components/Course/Course.tsx` | MODIFICAR |
| `Frontend/src/components/Course/Course.module.scss` | MODIFICAR |
| `Frontend/src/components/CourseDetail/CourseDetail.tsx` | MODIFICAR |
| `Frontend/src/components/CourseDetail/CourseDetail.module.scss` | MODIFICAR |
| `Frontend/src/app/page.tsx` | MODIFICAR |
