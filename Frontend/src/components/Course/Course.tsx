import styles from "./Course.module.scss";
import { Course as CourseType } from "@/types";

type CourseProps = Omit<CourseType, "slug">;

/**
 * Helper function to render visual stars based on a rating value
 * @param rating - Rating value from 0 to 5
 * @returns JSX elements for stars (filled, half, empty)
 */
function renderStars(rating: number) {
  const fullStars = Math.floor(rating);
  const hasHalfStar = rating % 1 >= 0.5;
  const emptyStars = 5 - fullStars - (hasHalfStar ? 1 : 0);

  return (
    <span className={styles.stars}>
      {[...Array(fullStars)].map((_, i) => (
        <span key={`full-${i}`} aria-hidden="true">
          ★
        </span>
      ))}
      {hasHalfStar && (
        <span key="half" aria-hidden="true">
          ½
        </span>
      )}
      {[...Array(emptyStars)].map((_, i) => (
        <span key={`empty-${i}`} aria-hidden="true">
          ☆
        </span>
      ))}
    </span>
  );
}

export const Course = ({ name, thumbnail, average_rating, total_ratings }: CourseProps) => {
  return (
    <article className={styles.courseCard}>
      <div className={styles.thumbnailContainer}>
        <img src={thumbnail} alt={name} className={styles.thumbnail} />
      </div>
      <div className={styles.courseInfo}>
        <h2 className={styles.courseTitle}>{name}</h2>
        {average_rating !== null ? (
          <div className={styles.rating}>
            {renderStars(average_rating)}
            <span className={styles.ratingText}>
              {average_rating.toFixed(1)} ({total_ratings} {total_ratings === 1 ? "voto" : "votos"})
            </span>
          </div>
        ) : (
          <p className={styles.noRating}>Sin calificaciones</p>
        )}
      </div>
    </article>
  );
};
