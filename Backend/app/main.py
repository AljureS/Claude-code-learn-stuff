from fastapi import FastAPI, HTTPException, Depends, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.base import engine, get_db
from app.services.course_service import CourseService
from app.services.rating_service import RatingService

app = FastAPI(title=settings.project_name, version=settings.version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def get_course_service(db: Session = Depends(get_db)) -> CourseService:
    """
    Dependency to get CourseService instance
    """
    return CourseService(db)


def get_rating_service(db: Session = Depends(get_db)) -> RatingService:
    """
    Dependency to get RatingService instance
    """
    return RatingService(db)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Bienvenido a Platziflix API"}


@app.get("/health")
def health() -> dict[str, str | bool | int]:
    """
    Health check endpoint that verifies:
    - Service status
    - Database connectivity
    """
    health_status = {
        "status": "ok",
        "service": settings.project_name,
        "version": settings.version,
        "database": False,
    }

    # Check database connectivity and verify migration
    try:
        with engine.connect() as connection:
            # Execute COUNT on courses table to verify migration was executed
            result = connection.execute(text("SELECT COUNT(*) FROM courses"))
            row = result.fetchone()
            if row:
                count = row[0]
                health_status["database"] = True
                health_status["courses_count"] = count
            else:
                health_status["database"] = True
                health_status["courses_count"] = 0
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["database_error"] = str(e)

    return health_status


@app.get("/courses")
def get_courses(course_service: CourseService = Depends(get_course_service)) -> list:
    """
    Get all courses.
    Returns a list of courses with basic information: id, name, description, thumbnail, slug
    """
    return course_service.get_all_courses()


@app.get("/courses/{slug}")
def get_course_by_slug(slug: str, course_service: CourseService = Depends(get_course_service)) -> dict:
    """
    Get course details by slug.
    Returns course information including teachers and classes.
    """
    course = course_service.get_course_by_slug(slug)

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    return course


@app.post("/courses/{slug}/ratings")
def create_or_update_rating(
    slug: str,
    device_id: str = Body(...),
    score: int = Body(...),
    rating_service: RatingService = Depends(get_rating_service)
) -> dict:
    """
    Create or update a rating for a course.
    """
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
    """
    Get rating summary for a course.
    """
    result = rating_service.get_course_rating_summary(slug, device_id)

    if result is None:
        raise HTTPException(status_code=404, detail="Course not found")

    return result
