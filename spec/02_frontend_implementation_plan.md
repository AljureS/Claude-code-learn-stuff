# Plan de Implementación Frontend: Sistema de Ratings

## Contexto

Implementación del sistema de ratings (1-5 estrellas) para Platziflix. Este documento detalla las fases de implementación del lado frontend usando **Next.js 15 + React 19 + Server Components**.

**Referencia:** Ver análisis técnico completo en `spec/00_rating_system.md`

---

## Objetivos Frontend

1. Crear primer **Client Component** interactivo del proyecto (`"use client"`)
2. Implementar utilidad de `device_id` con localStorage
3. Actualizar tipos TypeScript con nuevos campos de rating
4. Integrar ratings en cards de cursos (read-only)
5. Integrar componente interactivo en página de detalle
6. Asegurar accesibilidad completa (teclado + screen readers)
7. Cobertura de tests con Vitest

---

## FASE 5: Tipos e Infraestructura

### Objetivo
Preparar tipos TypeScript y utilidad de device_id.

### Tareas

#### 5.1 Crear utilidad de device_id
**Archivo:** `Frontend/src/utils/deviceId.ts`

**Funcionalidad:**
```typescript
const STORAGE_KEY = "platziflix_device_id";

export function getDeviceId(): string {
  // Protección contra SSR
  if (typeof window === "undefined") return "";

  let deviceId = localStorage.getItem(STORAGE_KEY);
  if (!deviceId) {
    deviceId = crypto.randomUUID();
    localStorage.setItem(STORAGE_KEY, deviceId);
  }
  return deviceId;
}
```

**Consideraciones:**
- `typeof window === "undefined"` protege contra ejecución server-side
- `crypto.randomUUID()` es nativo en navegadores modernos (Chrome 92+, Firefox 95+, Safari 15.4+)
- Retorna string vacío en SSR (no lanza error)
- UUID se genera una sola vez y persiste

#### 5.2 Actualizar tipos TypeScript
**Archivo:** `Frontend/src/types/index.ts`

**Cambios en interface Course:**
```typescript
export interface Course {
  id: number;
  name: string;
  description: string;
  thumbnail: string;
  slug: string;
  average_rating: number | null;  // NUEVO
  total_ratings: number;          // NUEVO
}
```

**Nuevas interfaces:**
```typescript
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

### Verificación
- [ ] `getDeviceId()` funciona en browser
- [ ] No lanza error en SSR/build
- [ ] TypeScript compila sin errores
- [ ] Interfaces disponibles en toda la app

**Test manual:**
```typescript
// En consola del navegador
import { getDeviceId } from '@/utils/deviceId';
const id = getDeviceId();
console.log(id); // UUID
console.log(localStorage.getItem('platziflix_device_id')); // mismo UUID
```

---

## FASE 6: Componente StarRating

### Objetivo
Crear primer Client Component interactivo con estado y fetch directo al API.

### Tareas

#### 6.1 Crear componente StarRating
**Archivo:** `Frontend/src/components/StarRating/StarRating.tsx`

**Estructura:**
```typescript
"use client";

import { FC, useState, useEffect, useCallback } from "react";
import styles from "./StarRating.module.scss";
import { getDeviceId } from "@/utils/deviceId";

interface StarRatingProps {
  courseSlug: string;
  initialAverage: number | null;
  initialTotal: number;
}
```

**Estado del componente:**
- `averageRating`: number | null — promedio actual (se actualiza después de votar)
- `totalRatings`: number — total de votos
- `userRating`: number | null — rating del usuario actual (hidratado desde API)
- `hoveredStar`: number | null — estrella sobre la que está el mouse
- `isSubmitting`: boolean — indica si hay una petición en curso

**useEffect para hidratar user_rating:**
```typescript
useEffect(() => {
  const deviceId = getDeviceId();
  if (!deviceId) return;

  fetch(`http://localhost:8000/courses/${courseSlug}/ratings?device_id=${deviceId}`)
    .then((res) => res.json())
    .then((data: RatingSummary) => {
      if (data.user_rating !== null) setUserRating(data.user_rating);
      setAverageRating(data.average_rating);
      setTotalRatings(data.total_ratings);
    })
    .catch(() => {}); // Silent fail
}, [courseSlug]);
```

**Handler para calificar:**
```typescript
const handleRate = useCallback(async (score: number) => {
  if (isSubmitting) return;
  const deviceId = getDeviceId();
  if (!deviceId) return;

  setIsSubmitting(true);
  try {
    const res = await fetch(
      `http://localhost:8000/courses/${courseSlug}/ratings`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_id: deviceId, score })
      }
    );

    if (res.ok) {
      setUserRating(score);
      // Refrescar agregados
      const summaryRes = await fetch(
        `http://localhost:8000/courses/${courseSlug}/ratings?device_id=${deviceId}`
      );
      if (summaryRes.ok) {
        const summary: RatingSummary = await summaryRes.json();
        setAverageRating(summary.average_rating);
        setTotalRatings(summary.total_ratings);
      }
    }
  } catch (error) {
    // Manejo de error (opcional: mostrar toast)
  } finally {
    setIsSubmitting(false);
  }
}, [courseSlug, isSubmitting]);
```

**Render:**
```typescript
const displayRating = hoveredStar ?? userRating ?? 0;

return (
  <div className={styles.starRating}>
    <div className={styles.stars} role="radiogroup" aria-label="Calificación del curso">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          className={`${styles.star} ${star <= displayRating ? styles.filled : ""}`}
          onMouseEnter={() => setHoveredStar(star)}
          onMouseLeave={() => setHoveredStar(null)}
          onClick={() => handleRate(star)}
          disabled={isSubmitting}
          role="radio"
          aria-checked={userRating === star}
          aria-label={`${star} estrella${star > 1 ? "s" : ""}`}
        >
          &#9733;
        </button>
      ))}
    </div>
    <div className={styles.info}>
      {averageRating !== null ? (
        <span className={styles.average}>{averageRating.toFixed(1)}</span>
      ) : (
        <span className={styles.noRatings}>Sin calificaciones</span>
      )}
      <span className={styles.total}>
        ({totalRatings} {totalRatings === 1 ? "voto" : "votos"})
      </span>
    </div>
  </div>
);
```

**Consideraciones:**
- Directiva `"use client"` al inicio del archivo es **mandatoria**
- `displayRating` prioriza: hover > user rating > 0 (sin rating)
- `isSubmitting` previene clicks múltiples
- `useCallback` optimiza re-renders
- Manejo de error silencioso (no bloquea UI)

#### 6.2 Crear estilos del componente
**Archivo:** `Frontend/src/components/StarRating/StarRating.module.scss`

**Variables a usar de `vars.scss`:**
- `$color-primary` — para estrellas filled
- `$color-text-secondary` — para estrellas empty
- `$color-text-muted` — para info de votos
- `$spacing-sm`, `$spacing-md` — para gaps
- `$transition-base` — para hover effects

**Estructura de estilos:**
```scss
.starRating {
  display: flex;
  flex-direction: column;
  gap: $spacing-sm;
}

.stars {
  display: flex;
  gap: $spacing-xs;
}

.star {
  background: none;
  border: none;
  font-size: 2rem;
  color: $color-text-secondary;
  cursor: pointer;
  transition: $transition-base;
  padding: 0;

  &:hover:not(:disabled) {
    transform: scale(1.1);
  }

  &.filled {
    color: $color-primary; // Color dorado/amarillo
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  &:focus-visible {
    outline: 2px solid $color-primary;
    outline-offset: 2px;
  }
}

.info {
  display: flex;
  align-items: baseline;
  gap: $spacing-xs;
  font-size: 0.875rem;
}

.average {
  font-weight: 600;
  color: $color-text-primary;
  font-size: 1rem;
}

.noRatings {
  color: $color-text-muted;
  font-style: italic;
}

.total {
  color: $color-text-muted;
}
```

**Responsive:**
- En móvil: font-size de estrellas a 1.5rem
- Mantener touch target de mínimo 44x44px

### Verificación
- [ ] Componente renderiza 5 estrellas
- [ ] Hover muestra preview de rating
- [ ] Click envía POST al API
- [ ] Después de votar, user_rating se actualiza
- [ ] Promedio y total se actualizan después de votar
- [ ] Disabled state funciona durante submit
- [ ] Accesibilidad: navegable con teclado
- [ ] Accesibilidad: screen reader anuncia correctamente

**Test manual:**
1. Abrir página de detalle de curso
2. Verificar que las estrellas son visibles
3. Hover sobre estrellas → preview funciona
4. Click en estrella → POST enviado (ver Network tab)
5. Reload página → rating persiste (se hidrata desde API)
6. Click en otra estrella → rating se actualiza

---

## FASE 7: Integración en Páginas

### Objetivo
Integrar ratings en cards de cursos y página de detalle.

### Tareas

#### 7.1 Modificar componente Course (Card)
**Archivo:** `Frontend/src/components/Course/Course.tsx`

**Cambios:**
1. Actualizar props interface:
```typescript
interface CourseProps {
  course: {
    id: number;
    name: string;
    description: string;
    thumbnail: string;
    slug: string;
    average_rating: number | null;  // NUEVO
    total_ratings: number;          // NUEVO
  };
}
```

2. Agregar display de rating (read-only):
```typescript
// Dentro del return, después de description
{course.average_rating !== null ? (
  <div className={styles.rating}>
    <span className={styles.stars}>
      {renderStars(course.average_rating)}
    </span>
    <span className={styles.ratingText}>
      {course.average_rating.toFixed(1)} ({course.total_ratings})
    </span>
  </div>
) : (
  <div className={styles.rating}>
    <span className={styles.noRating}>Sin calificaciones</span>
  </div>
)}
```

3. Helper para renderizar estrellas visuales:
```typescript
function renderStars(rating: number) {
  const fullStars = Math.floor(rating);
  const hasHalfStar = rating % 1 >= 0.5;

  return (
    <>
      {[...Array(fullStars)].map((_, i) => (
        <span key={`full-${i}`}>★</span>
      ))}
      {hasHalfStar && <span>½</span>}
      {[...Array(5 - fullStars - (hasHalfStar ? 1 : 0))].map((_, i) => (
        <span key={`empty-${i}`}>☆</span>
      ))}
    </>
  );
}
```

**Nota:** Esto es display visual, NO interactivo (permanece Server Component).

#### 7.2 Actualizar estilos de Course
**Archivo:** `Frontend/src/components/Course/Course.module.scss`

**Agregar:**
```scss
.rating {
  margin-top: $spacing-sm;
  display: flex;
  align-items: center;
  gap: $spacing-xs;
  font-size: 0.875rem;
}

.stars {
  color: $color-primary;
  font-size: 1rem;
  letter-spacing: 2px;
}

.ratingText {
  color: $color-text-secondary;
}

.noRating {
  color: $color-text-muted;
  font-style: italic;
}
```

#### 7.3 Modificar componente CourseDetail
**Archivo:** `Frontend/src/components/CourseDetail/CourseDetail.tsx`

**Cambios:**
1. Importar StarRating:
```typescript
import { StarRating } from "@/components/StarRating/StarRating";
```

2. Actualizar props interface (agregar `average_rating` y `total_ratings`)

3. Agregar sección de rating en el layout:
```typescript
// Después de la descripción, antes de la lista de clases
<section className={styles.ratingSection}>
  <h2>Califica este curso</h2>
  <StarRating
    courseSlug={course.slug}
    initialAverage={course.average_rating}
    initialTotal={course.total_ratings}
  />
</section>
```

#### 7.4 Actualizar estilos de CourseDetail
**Archivo:** `Frontend/src/components/CourseDetail/CourseDetail.module.scss`

**Agregar:**
```scss
.ratingSection {
  margin: $spacing-lg 0;
  padding: $spacing-md;
  background: $color-surface;
  border-radius: $border-radius-base;

  h2 {
    margin-bottom: $spacing-md;
    font-size: 1.25rem;
  }
}
```

#### 7.5 Actualizar página principal
**Archivo:** `Frontend/src/app/page.tsx`

**Verificar que:**
- El fetch a `/courses` retorna `average_rating` y `total_ratings`
- Esos campos se pasan correctamente al componente `Course`

**Si hay transformación de datos, asegurarse de incluir:**
```typescript
const courses: Course[] = await res.json();
// courses ya incluye average_rating y total_ratings del API
```

### Verificación
- [ ] Cards en home muestran promedio de rating
- [ ] Cards sin rating muestran "Sin calificaciones"
- [ ] Página de detalle muestra componente interactivo
- [ ] Componente StarRating recibe props correctas
- [ ] Layout responsive no se rompe en móvil
- [ ] No hay errores de hidratación en consola
- [ ] Server Components siguen siendo Server Components (solo StarRating es Client)

**Test manual:**
1. `yarn dev`
2. Abrir `/` → verificar que cards muestran ratings
3. Abrir `/course/curso-de-react` → verificar componente interactivo
4. Verificar en DevTools que solo StarRating tiene bundle JS

---

## FASE 8: Tests

### Objetivo
Asegurar cobertura de tests del nuevo componente y actualizaciones.

### Tareas

#### 8.1 Crear tests de StarRating
**Archivo:** `Frontend/src/components/StarRating/__tests__/StarRating.test.tsx`

**Setup:**
```typescript
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { StarRating } from '../StarRating';

// Mock de fetch global
global.fetch = vi.fn();

// Mock de getDeviceId
vi.mock('@/utils/deviceId', () => ({
  getDeviceId: vi.fn(() => 'test-device-id')
}));
```

**Tests a implementar:**

1. **test_renders_five_stars:**
```typescript
it('renders 5 star buttons', () => {
  render(<StarRating courseSlug="test" initialAverage={null} initialTotal={0} />);
  const buttons = screen.getAllByRole('radio');
  expect(buttons).toHaveLength(5);
});
```

2. **test_displays_initial_average_and_total:**
```typescript
it('displays initial average rating and total votes', () => {
  render(<StarRating courseSlug="test" initialAverage={4.5} initialTotal={10} />);
  expect(screen.getByText('4.5')).toBeInTheDocument();
  expect(screen.getByText(/10 votos/)).toBeInTheDocument();
});
```

3. **test_displays_no_ratings_message:**
```typescript
it('displays "Sin calificaciones" when no ratings exist', () => {
  render(<StarRating courseSlug="test" initialAverage={null} initialTotal={0} />);
  expect(screen.getByText('Sin calificaciones')).toBeInTheDocument();
});
```

4. **test_fetches_user_rating_on_mount:**
```typescript
it('fetches user rating on mount', async () => {
  const mockSummary = {
    course_slug: 'test',
    average_rating: 4.2,
    total_ratings: 15,
    user_rating: 4
  };
  (global.fetch as any).mockResolvedValueOnce({
    json: async () => mockSummary
  });

  render(<StarRating courseSlug="test" initialAverage={4.2} initialTotal={15} />);

  await waitFor(() => {
    const button4 = screen.getByLabelText('4 estrellas');
    expect(button4).toHaveAttribute('aria-checked', 'true');
  });
});
```

5. **test_submits_rating_on_click:**
```typescript
it('submits rating when star is clicked', async () => {
  const user = userEvent.setup();

  (global.fetch as any)
    .mockResolvedValueOnce({ ok: true, json: async () => ({}) }) // POST response
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      course_slug: 'test',
      average_rating: 4.5,
      total_ratings: 1,
      user_rating: 5
    })}); // GET summary response

  render(<StarRating courseSlug="test" initialAverage={null} initialTotal={0} />);

  const button5 = screen.getByLabelText('5 estrellas');
  await user.click(button5);

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/courses/test/ratings',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ device_id: 'test-device-id', score: 5 })
      })
    );
  });
});
```

6. **test_disables_buttons_during_submission:**
```typescript
it('disables buttons during submission', async () => {
  const user = userEvent.setup();

  (global.fetch as any).mockImplementation(() =>
    new Promise(resolve => setTimeout(() => resolve({ ok: true, json: async () => ({}) }), 100))
  );

  render(<StarRating courseSlug="test" initialAverage={null} initialTotal={0} />);

  const button5 = screen.getByLabelText('5 estrellas');
  await user.click(button5);

  const buttons = screen.getAllByRole('radio');
  buttons.forEach(btn => expect(btn).toBeDisabled());
});
```

7. **test_handles_api_error_gracefully:**
```typescript
it('handles API error gracefully', async () => {
  const user = userEvent.setup();

  (global.fetch as any).mockRejectedValueOnce(new Error('Network error'));

  render(<StarRating courseSlug="test" initialAverage={null} initialTotal={0} />);

  const button5 = screen.getByLabelText('5 estrellas');
  await user.click(button5);

  // No debe romper la UI, botones deben volver a estar enabled
  await waitFor(() => {
    expect(button5).not.toBeDisabled();
  });
});
```

#### 8.2 Actualizar tests de Course
**Archivo:** `Frontend/src/components/Course/__tests__/Course.test.tsx`

**Nuevos tests:**

1. **test_displays_rating_when_available:**
```typescript
it('displays average rating and total votes', () => {
  const course = {
    id: 1,
    name: 'Test Course',
    description: 'Description',
    thumbnail: '/test.jpg',
    slug: 'test',
    average_rating: 4.5,
    total_ratings: 10
  };

  render(<Course course={course} />);

  expect(screen.getByText('4.5')).toBeInTheDocument();
  expect(screen.getByText(/10/)).toBeInTheDocument();
});
```

2. **test_displays_no_rating_message:**
```typescript
it('displays "Sin calificaciones" when no rating', () => {
  const course = {
    id: 1,
    name: 'Test Course',
    description: 'Description',
    thumbnail: '/test.jpg',
    slug: 'test',
    average_rating: null,
    total_ratings: 0
  };

  render(<Course course={course} />);

  expect(screen.getByText('Sin calificaciones')).toBeInTheDocument();
});
```

### Verificación
- [ ] Todos los tests pasan: `yarn test`
- [ ] Cobertura incluye StarRating (>80%)
- [ ] No hay warnings en ejecución de tests
- [ ] Tests son determinísticos (no flaky)

**Comandos:**
```bash
cd Frontend
yarn test                        # Ejecutar todos los tests
yarn test StarRating            # Solo tests de StarRating
yarn test --coverage            # Con cobertura
```

---

## Consideraciones Técnicas

### Server Components vs Client Components
- **Server Components:** Course cards (lectura de ratings)
- **Client Components:** StarRating (interacción y estado)
- **Beneficio:** Bundle JS solo para StarRating, resto es HTML puro

### Hidratación
- **SSR envía:** average_rating y total_ratings desde Server Component
- **Client hidrata:** user_rating específico del dispositivo en useEffect
- **Evita layout shift:** valores iniciales previenen reflow

### Manejo de Estado
- **No usar contexto global:** Rating es estado local del componente
- **Optimistic updates:** Opcional - actualizar UI inmediatamente antes de confirmar
- **Error handling:** Silent fail para no bloquear experiencia

### Performance
- **useCallback:** Evita recrear handler en cada render
- **Debounce:** NO necesario (click único, no input continuo)
- **Prefetch:** Considerar prefetch de rating summary en hover (futuro)

### Accesibilidad
- **role="radiogroup":** Grupo de opciones mutuamente excluyentes
- **role="radio":** Cada estrella es una opción
- **aria-checked:** Indica cuál está seleccionada
- **aria-label:** Texto descriptivo para cada estrella
- **Navegación:** Tab + Enter/Space para seleccionar

### Mobile
- **Touch targets:** Mínimo 44x44px (WCAG 2.5.5)
- **Hover states:** Adaptar para touch (usar onTouchStart si necesario)
- **Font size:** Aumentar en viewport pequeño

---

## Checklist Final de Fase Frontend

### Infraestructura
- [ ] Utilidad `getDeviceId()` creada y probada
- [ ] Tipos TypeScript actualizados
- [ ] Interfaces `RatingSummary` y `RatingResponse` creadas

### Componente StarRating
- [ ] Componente creado con directiva `"use client"`
- [ ] Estado manejado correctamente
- [ ] useEffect hidrata user_rating
- [ ] Handler handleRate funciona
- [ ] Estilos completos y responsivos
- [ ] Accesibilidad implementada

### Integración
- [ ] Course cards muestran rating read-only
- [ ] CourseDetail integra StarRating
- [ ] Props pasadas correctamente
- [ ] No hay errores de hidratación
- [ ] Layout responsive funciona

### Tests
- [ ] Tests de StarRating (7 tests mínimo)
- [ ] Tests de Course actualizados (2 tests nuevos)
- [ ] Todos los tests pasan
- [ ] Cobertura adecuada

### Calidad
- [ ] No hay console errors
- [ ] No hay TypeScript errors
- [ ] Build de producción funciona
- [ ] Lighthouse: Accesibilidad >90

---

## Próximos Pasos

Una vez completada la implementación frontend:
1. Test end-to-end manual en todos los navegadores
2. Test en móvil (iOS Safari + Android Chrome)
3. Verificar performance con Lighthouse
4. Documentar cualquier desviación del plan
5. Screenshot/video de la feature funcionando

**Integración completa:** Ver ratings en acción con backend en `http://localhost:3000`

**Referencia para backend:** Ver `spec/01_backend_implementation_plan.md`
