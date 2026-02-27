from sqlalchemy import Column, String, Integer, SmallInteger, ForeignKey, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.orm import relationship
from .base import BaseModel


class Rating(BaseModel):
    """
    Rating model representing user ratings (1-5 stars) for courses.
    Uses device_id to identify users without authentication.
    """
    __tablename__ = 'ratings'

    course_id = Column(Integer, ForeignKey('courses.id', ondelete='CASCADE'), nullable=False, index=True)
    device_id = Column(String(64), nullable=False, index=True)
    score = Column(SmallInteger, nullable=False)

    # Many-to-one relationship with Course
    course = relationship("Course", back_populates="ratings")

    __table_args__ = (
        UniqueConstraint('course_id', 'device_id', name='uq_ratings_course_device'),
        CheckConstraint('score >= 1 AND score <= 5', name='ck_ratings_score_range'),
        Index('ix_ratings_course_id_score', 'course_id', 'score', postgresql_where='deleted_at IS NULL'),
    )

    def __repr__(self):
        return f"<Rating(id={self.id}, course_id={self.course_id}, device_id='{self.device_id}', score={self.score})>"
