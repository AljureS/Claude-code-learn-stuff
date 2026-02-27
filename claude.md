# Platziflix - Arquitectura del Sistema

Sistema **multi-plataforma** compuesto por 4 proyectos independientes que comparten un mismo backend API. Plataforma educativa estilo streaming para cursos online.

---

## Big Picture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENTES (Frontend)                         │
│                                                                     │
│  ┌──────────────┐   ┌──────────────────┐   ┌──────────────────┐    │
│  │   Next.js 15 │   │  Android (Kotlin) │   │   iOS (Swift)    │    │
│  │   React 19   │   │  Jetpack Compose  │   │    SwiftUI       │    │
│  │   TypeScript  │   │  Clean + MVI     │   │   Clean + MVVM   │    │
│  │   SSR/RSC    │   │  Retrofit/OkHttp  │   │   URLSession     │    │
│  └──────┬───────┘   └────────┬─────────┘   └────────┬─────────┘    │
│         │                    │                       │              │
└─────────┼────────────────────┼───────────────────────┼──────────────┘
          │ HTTP               │ HTTP                  │ HTTP
          │ :8000              │ :8000 (10.0.2.2)      │ :8000
          │                    │                       │
┌─────────▼────────────────────▼───────────────────────▼──────────────┐
│                         BACKEND (API)                               │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │              FastAPI (Python 3.11+)                        │     │
│  │                                                            │     │
│  │  Routes:                                                   │     │
│  │    GET /           → Welcome message                       │     │
│  │    GET /health     → Health check + DB status              │     │
│  │    GET /courses    → Lista de cursos                       │     │
│  │    GET /courses/{slug} → Detalle con teachers + classes    │     │
│  │                                                            │     │
│  │  Layers:                                                   │     │
│  │    main.py (Routes) → CourseService → SQLAlchemy ORM       │     │
│  └──────────────────────────────┬─────────────────────────────┘     │
│                                 │                                   │
│  ┌──────────────────────────────▼─────────────────────────────┐     │
│  │              PostgreSQL 15                                 │     │
│  │                                                            │     │
│  │  Tables:                                                   │     │
│  │    courses ──┐                                             │     │
│  │    lessons   ├── course_teachers (M:N) ── teachers         │     │
│  │              │                                             │     │
│  │  Soft deletes (deleted_at) en todos los modelos            │     │
│  │  Migrations via Alembic                                    │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                     │
│  Docker Compose (db + api) con hot reload                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Desglose por Proyecto

### 1. Backend - FastAPI + PostgreSQL

| Aspecto | Detalle |
|---------|---------|
| **Framework** | FastAPI (Python 3.11+) |
| **Base de datos** | PostgreSQL 15 via SQLAlchemy 2.0 |
| **Migraciones** | Alembic |
| **Infraestructura** | Docker Compose (2 servicios: `api` + `db`) |
| **Patrón** | Service Layer + Dependency Injection + Soft Deletes |
| **Testing** | pytest con mocks de servicios |
| **Paquetes** | uv (gestor de dependencias) |

**Modelo de datos:**
- `Course` (name, description, thumbnail, slug) -> tiene muchos `Lesson` y muchos `Teacher` (M:N via `course_teachers`)
- `Lesson` (name, description, slug, video_url, course_id)
- `Teacher` (name, email)
- Todos heredan campos: `id`, `created_at`, `updated_at`, `deleted_at`

**Estructura:**
```
Backend/
├── app/
│   ├── main.py                  # FastAPI app, routes, health check
│   ├── test_main.py             # Unit tests (pytest)
│   ├── core/config.py           # Pydantic Settings
│   ├── db/base.py               # SQLAlchemy engine + session
│   ├── db/seed.py               # Sample data
│   ├── models/                  # ORM: course, lesson, teacher, course_teacher
│   ├── services/course_service.py # Business logic
│   └── alembic/                 # Migrations
├── Dockerfile
├── docker-compose.yml
├── Makefile
└── pyproject.toml
```

**API Endpoints:**
- `GET /` — Welcome message
- `GET /health` — Health check con status de DB
- `GET /courses` — Lista cursos (sin teachers ni lessons)
- `GET /courses/{slug}` — Detalle con teacher_id[] y classes[]
- `GET /courses/:slug/classes/:id` — Definido en contrato, NO implementado aun

---

### 2. Frontend - Next.js 15 (App Router)

| Aspecto | Detalle |
|---------|---------|
| **Framework** | Next.js 15.3 + React 19 |
| **Lenguaje** | TypeScript (strict) |
| **Rendering** | Server Components (RSC) - sin estado cliente |
| **Estilos** | SCSS Modules + design tokens (`vars.scss`) |
| **Testing** | Vitest + Testing Library |
| **Bundler** | Turbopack (dev) |

**Estructura:**
```
Frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx               # Root layout (fonts, metadata)
│   │   ├── page.tsx                 # Home - grid de cursos
│   │   ├── course/[slug]/
│   │   │   ├── page.tsx             # Detalle del curso
│   │   │   ├── error.tsx            # Error boundary (Client Component)
│   │   │   ├── loading.tsx          # Loading skeleton
│   │   │   └── not-found.tsx        # 404
│   │   └── classes/[class_id]/
│   │       └── page.tsx             # Reproductor de video
│   ├── components/
│   │   ├── Course/Course.tsx        # Card de curso
│   │   ├── CourseDetail/CourseDetail.tsx
│   │   └── VideoPlayer/VideoPlayer.tsx
│   ├── styles/vars.scss             # Design tokens
│   ├── types/index.ts               # Interfaces TypeScript
│   └── test/setup.ts               # Vitest setup
├── package.json
├── next.config.ts                   # SCSS auto-import vars
├── tsconfig.json
└── vitest.config.ts
```

**Rutas:**
- `/` — Grid de cursos (fetch server-side a `/courses`)
- `/course/[slug]` — Detalle del curso con lista de clases
- `/classes/[class_id]` — Reproductor de video HTML5

**API Base URL:** `http://localhost:8000`

---

### 3. Android - Kotlin + Jetpack Compose

| Aspecto | Detalle |
|---------|---------|
| **Lenguaje** | Kotlin |
| **UI** | Jetpack Compose (declarativo) |
| **Arquitectura** | Clean Architecture + MVI |
| **Red** | Retrofit 2.9 + OkHttp3 |
| **Estado** | StateFlow + ViewModel |
| **Imágenes** | Coil |
| **DI** | Manual (AppModule singleton) |
| **Testing** | JUnit + Coroutines Test |

**Estructura:**
```
Mobile/PlatziFlixAndroid/app/src/main/java/com/espaciotiago/platziflixandroid/
├── MainActivity.kt
├── di/AppModule.kt                          # DI manual, flag USE_MOCK_DATA
├── data/
│   ├── network/NetworkModule.kt             # Retrofit config (10.0.2.2:8000)
│   ├── network/ApiService.kt               # GET /courses
│   ├── repositories/RemoteCourseRepository.kt
│   ├── repositories/MockCourseRepository.kt
│   ├── mappers/CourseMapper.kt              # DTO → Domain
│   └── entities/CourseDTO.kt
├── domain/
│   ├── repositories/CourseRepository.kt     # Interface
│   └── models/Course.kt
├── presentation/courses/
│   ├── viewmodel/CourseListViewModel.kt
│   ├── state/CourseListUiState.kt           # Loading/Success/Error
│   ├── screen/CourseListScreen.kt
│   └── components/CourseCard.kt, ErrorMessage.kt, LoadingIndicator.kt
└── ui/theme/Theme.kt, Color.kt, Type.kt, Spacing.kt
```

**Estado actual:** Solo pantalla de listado. Navegación a detalle pendiente (TODO).

---

### 4. iOS - Swift + SwiftUI

| Aspecto | Detalle |
|---------|---------|
| **Lenguaje** | Swift |
| **UI** | SwiftUI (declarativo) |
| **Arquitectura** | Clean Architecture + MVVM |
| **Red** | URLSession nativo (async/await) |
| **Estado** | @Published + @StateObject + Combine |
| **Imágenes** | AsyncImage (nativo) |
| **DI** | Constructor injection |
| **Accesibilidad** | VoiceOver completo |

**Estructura:**
```
Mobile/PlatziFlixiOS/PlatziFlixiOS/
├── PlatziFlixiOSApp.swift
├── ContentView.swift
├── Data/
│   ├── Mapper/CourseMapper.swift, TeacherMapper.swift, ClassMapper.swift
│   ├── Repositories/RemoteCourseRepository.swift, CourseAPIEndpoints.swift
│   └── Entities/CourseDTO.swift, TeacherDTO.swift, ClassDetailDTO.swift
├── Domain/
│   ├── Repositories/CourseRepositoryProtocol.swift
│   └── Models/Course.swift, Teacher.swift, Class.swift
├── Presentation/
│   ├── ViewModels/CourseListViewModel.swift
│   └── Views/CourseListView.swift, CourseCardView.swift, DesignSystem.swift
└── Services/
    ├── NetworkManager.swift, NetworkService.swift
    ├── NetworkError.swift, APIEndpoint.swift, HTTPMethod.swift
```

**Estado actual:** Solo pantalla de listado con búsqueda. Navegación a detalle pendiente (TODO).

---

## Patrones Compartidos

| Patrón | Backend | Frontend | Android | iOS |
|--------|---------|----------|---------|-----|
| **Clean Architecture** | Service Layer | RSC composition | Domain/Data/Presentation | Domain/Data/Presentation |
| **Repository** | CourseService | fetch directo | CourseRepository interface | CourseRepositoryProtocol |
| **Dependency Injection** | FastAPI Depends() | - | Manual singleton | Constructor injection |
| **Mapper/DTO** | Dict serialization | TypeScript interfaces | CourseMapper (DTO->Domain) | CourseMapper (DTO->Domain) |
| **Soft Deletes** | deleted_at column | - | - | - |
| **Error Handling** | HTTP exceptions | error.tsx boundary | UiState.Error | NetworkError enum |
| **UI State Machine** | - | loading.tsx/error.tsx | Loading/Success/Error | isLoading/error/courses |

---

## Flujo de Datos End-to-End

```
PostgreSQL → SQLAlchemy ORM → CourseService → FastAPI Route → JSON Response
                                                                    │
                    ┌───────────────────────────────────────────────┤
                    │                    │                          │
              Next.js SSR          Android Retrofit          iOS URLSession
              fetch() no-store     CourseDTO → Course        CourseDTO → Course
              Server Component     Mapper + StateFlow        Mapper + @Published
              Direct render        Compose recomposition     SwiftUI re-render
```

---

## Estado Actual y Pendientes

- **Backend**: Funcional con 2 endpoints de cursos + health check. Sin auth, sin CORS, sin middleware.
- **Frontend**: 3 rutas completas con SSR, error boundaries, y estilos. Sin estado client-side.
- **Android**: Solo pantalla de listado de cursos. Navegacion a detalle pendiente (TODO).
- **iOS**: Solo pantalla de listado de cursos con busqueda. Navegacion a detalle pendiente (TODO).
- **Endpoint faltante**: `GET /courses/:slug/classes/:id` definido en contrato pero no implementado en backend.

---

## Comandos de Desarrollo

### Backend
```bash
make start        # Docker Compose up
make stop         # Docker Compose down
make build        # Build images
make migrate      # Run Alembic migrations
make seed         # Load sample data
make seed-fresh   # Clear + reload sample data
```

### Frontend
```bash
yarn dev          # Next.js dev con Turbopack
yarn build        # Build produccion
yarn test         # Vitest
yarn lint         # ESLint
```
