from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from app.models.course import Course
from app.models.lesson import Lesson
from app.models.teacher import Teacher
from app.models.rating import Rating


class CourseService:
    """
    Service class for handling course-related operations.
    Implements the contract specifications for course endpoints.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_all_courses(self) -> List[Dict[str, Any]]:
        """
        Get all courses with basic information and rating aggregates.

        Returns:
            List of course dictionaries with: id, name, description, thumbnail, slug,
            average_rating, total_ratings
        """
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
                Course,
                rating_stats.c.average_rating,
                rating_stats.c.total_ratings
            )
            .outerjoin(rating_stats, Course.id == rating_stats.c.course_id)
            .filter(Course.deleted_at.is_(None))
            .all()
        )

        return [
            {
                "id": course.id,
                "name": course.name,
                "description": course.description,
                "thumbnail": course.thumbnail,
                "slug": course.slug,
                "average_rating": round(float(average_rating), 1) if average_rating else None,
                "total_ratings": total_ratings or 0
            }
            for course, average_rating, total_ratings in courses
        ]

    def get_course_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Get course details by slug including teachers and lessons.
        
        Args:
            slug: The course slug
            
        Returns:
            Course dictionary with teachers and lessons, or None if not found
        """
        course = (
            self.db.query(Course)
            .options(
                joinedload(Course.teachers),
                joinedload(Course.lessons)
            )
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
            "id": course.id,
            "name": course.name,
            "description": course.description,
            "thumbnail": course.thumbnail,
            "slug": course.slug,
            "teacher_id": [teacher.id for teacher in course.teachers],
            "classes": [
                {
                    "id": lesson.id,
                    "name": lesson.name,
                    "description": lesson.description,
                    "slug": lesson.slug
                }
                for lesson in course.lessons
                if lesson.deleted_at is None
            ],
            "average_rating": round(float(rating_result.average_rating), 1) if rating_result.average_rating else None,
            "total_ratings": rating_result.total_ratings or 0
        } 