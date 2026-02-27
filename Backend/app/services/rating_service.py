from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.course import Course
from app.models.rating import Rating


class RatingService:
    """
    Service class for handling rating-related operations.
    """

    def __init__(self, db: Session):
        self.db = db

    def upsert_rating(self, slug: str, device_id: str, score: int) -> Optional[Dict[str, Any]]:
        """
        Create or update a rating for a course.

        Args:
            slug: The course slug
            device_id: UUID of the device
            score: Rating score (1-5)

        Returns:
            Rating dict or None if course not found
        """
        course = (
            self.db.query(Course)
            .filter(Course.slug == slug)
            .filter(Course.deleted_at.is_(None))
            .first()
        )

        if not course:
            return None

        rating = (
            self.db.query(Rating)
            .filter(Rating.course_id == course.id)
            .filter(Rating.device_id == device_id)
            .filter(Rating.deleted_at.is_(None))
            .first()
        )

        if rating:
            rating.score = score
        else:
            rating = Rating(
                course_id=course.id,
                device_id=device_id,
                score=score
            )
            self.db.add(rating)

        self.db.commit()
        self.db.refresh(rating)

        return {
            "id": rating.id,
            "course_id": rating.course_id,
            "device_id": rating.device_id,
            "score": rating.score,
            "created_at": str(rating.created_at),
            "updated_at": str(rating.updated_at)
        }

    def get_course_rating_summary(self, slug: str, device_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get rating summary for a course.

        Args:
            slug: The course slug
            device_id: Optional device ID to get user's rating

        Returns:
            Rating summary dict or None if course not found
        """
        course = (
            self.db.query(Course)
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

        average_rating = round(float(rating_result.average_rating), 1) if rating_result.average_rating else None
        total_ratings = rating_result.total_ratings or 0

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
