# Frontend Architect Memory - Platziflix

## Project Structure Patterns

### Type Definitions (`/Frontend/src/types/index.ts`)
- Organized by feature domain with comment headers (e.g., `// Course types`, `// Rating types`)
- All interfaces exported at top level
- Related types grouped together (e.g., `Course`, `CourseDetail extends Course`)
- Pre-existing fields: `Course` already has `average_rating` and `total_ratings` (added in previous work)

### Utilities (`/Frontend/src/utils/`)
- Created for cross-cutting concerns (deviceId, etc.)
- SSR-safe patterns required: always check `typeof window === "undefined"`
- localStorage persistence pattern: check existing value before generating new

## Design Patterns

### Device ID Pattern (ratings without auth)
- Uses `crypto.randomUUID()` for unique browser identification
- Storage key: `"platziflix_device_id"`
- SSR guard: returns empty string during server render (no error throwing)
- Persists in localStorage for consistency across sessions

## TypeScript Configuration
- Project uses strict TypeScript mode
- Verify compilation with: `yarn tsc --noEmit`
- Test files may have pre-existing type issues (vitest globals not in tsconfig)
- Always verify new code compiles in isolation

## Rating System Types
- `RatingSummary`: aggregate stats + user's rating (nullable for unauthenticated)
- `RatingResponse`: backend response format with timestamps
- `Course.average_rating`: nullable (courses may have no ratings yet)

## StarRating Component - First Client Component

**Location**: `/Frontend/src/components/StarRating/`

### Client Component Pattern
- **MUST** have `"use client"` directive as FIRST line
- Only use when: useState, useEffect, event handlers, or browser APIs needed
- Export: `export const ComponentName: FC<Props> = ({...}) => {...}`

### State Management
- Local component state (no global context needed for ratings)
- State: `averageRating`, `totalRatings`, `userRating`, `hoveredStar`, `isSubmitting`
- Hydration: useEffect fetches user_rating on mount via GET with device_id query param
- Update: POST with `{device_id, score}` body, then refresh summary

### API Integration
- Base URL: `http://localhost:8000` (hardcoded, not relative)
- Silent error handling: `catch(() => {})` - don't block UI on failures
- Optimistic pattern: update userRating state immediately, then refresh aggregates

### Accessibility
- role="radiogroup" on container
- role="radio" on each star button
- aria-checked for selected state
- aria-label with descriptive text (e.g., "3 estrellas")
- Keyboard navigation: Tab + Enter/Space

### Styling
- Star character: `&#9733;` (HTML entity)
- Color filled: `color('primary')` - #ff2d2d
- Color empty: `color('text-secondary')` - #222
- Hover: scale(1.1) transform
- Mobile: reduce font-size to 1.5rem, ensure 44px touch targets

## SCSS Patterns

### Design Tokens Available (vars.scss)
```scss
color('primary')        // #ff2d2d
color('white')          // #fff
color('text-primary')   // #111
color('text-secondary') // #222
color('off-white')      // #fafafa
color('light-gray')     // #f2f2f2
```

**Note**: Spec may reference tokens that don't exist (e.g., `$spacing-sm`, `$color-text-muted`). Adapt by using inline values or available tokens.

### Module Pattern
- Import: `@import "../../styles/vars.scss";`
- Use color function: `color: color('primary');`
- BEM-like naming: `.star`, `.star.filled`
- Responsive: mobile-first with `@media (max-width: 768px)`

## Component Integration Patterns (Phase 7)

### Course Card (Server Component)
**Location**: `/Frontend/src/components/Course/Course.tsx`
- **Remains Server Component** - no "use client" needed
- Shows **read-only visual stars** using helper function `renderStars(rating)`
- Star characters: `★` (filled), `☆` (empty), `½` (half star)
- Format: `★★★★☆ 4.5 (10 votos)`
- Handles null ratings: shows "Sin calificaciones" message
- Props: receives `average_rating` and `total_ratings` from API

### CourseDetail (Server Component)
**Location**: `/Frontend/src/components/CourseDetail/CourseDetail.tsx`
- **Remains Server Component** - only StarRating child is Client Component
- Integration: imports and renders `<StarRating />` after description, before class list
- Props passed: `courseSlug`, `initialAverage`, `initialTotal`
- Section styling: separate `.ratingSection` with padding, border, background
- Layout: rating section is visually distinct from course info and class list

### Visual Star Display Pattern
```typescript
function renderStars(rating: number) {
  const fullStars = Math.floor(rating);
  const hasHalfStar = rating % 1 >= 0.5;
  const emptyStars = 5 - fullStars - (hasHalfStar ? 1 : 0);

  return (
    <span className={styles.stars}>
      {[...Array(fullStars)].map((_, i) => <span key={`full-${i}`}>★</span>)}
      {hasHalfStar && <span key="half">½</span>}
      {[...Array(emptyStars)].map((_, i) => <span key={`empty-${i}`}>☆</span>)}
    </span>
  );
}
```

### Testing Updates
- Course tests updated for new rating display format
- Use regex for flexible matching: `screen.getByText(/4\.5/)`
- Added test case for null ratings: verify "Sin calificaciones" message
- All tests passing: 8 passed across 3 test files
