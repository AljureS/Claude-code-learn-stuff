"use client";

import { FC, useState, useEffect, useCallback } from "react";
import styles from "./StarRating.module.scss";
import { getDeviceId } from "@/utils/deviceId";
import { RatingSummary } from "@/types";

interface StarRatingProps {
  courseSlug: string;
  initialAverage: number | null;
  initialTotal: number;
}

export const StarRating: FC<StarRatingProps> = ({
  courseSlug,
  initialAverage,
  initialTotal,
}) => {
  const [averageRating, setAverageRating] = useState<number | null>(
    initialAverage
  );
  const [totalRatings, setTotalRatings] = useState<number>(initialTotal);
  const [userRating, setUserRating] = useState<number | null>(null);
  const [hoveredStar, setHoveredStar] = useState<number | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Hydrate user rating on mount
  useEffect(() => {
    const deviceId = getDeviceId();
    if (!deviceId) return;

    fetch(
      `http://localhost:8000/courses/${courseSlug}/ratings?device_id=${deviceId}`
    )
      .then((res) => res.json())
      .then((data: RatingSummary) => {
        if (data.user_rating !== null) setUserRating(data.user_rating);
        setAverageRating(data.average_rating);
        setTotalRatings(data.total_ratings);
      })
      .catch(() => {
        // Silent fail - don't block UI
      });
  }, [courseSlug]);

  // Handle rating submission
  const handleRate = useCallback(
    async (score: number) => {
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
            body: JSON.stringify({ device_id: deviceId, score }),
          }
        );

        if (res.ok) {
          setUserRating(score);
          // Refresh aggregates
          const summaryRes = await fetch(
            `http://localhost:8000/courses/${courseSlug}/ratings?device_id=${deviceId}`
          );
          if (summaryRes.ok) {
            const summary: RatingSummary = await summaryRes.json();
            setAverageRating(summary.average_rating);
            setTotalRatings(summary.total_ratings);
          }
        }
      } catch {
        // Silent error handling - don't disrupt user experience
      } finally {
        setIsSubmitting(false);
      }
    },
    [courseSlug, isSubmitting]
  );

  const displayRating = hoveredStar ?? userRating ?? 0;

  return (
    <div className={styles.starRating}>
      <div
        className={styles.stars}
        role="radiogroup"
        aria-label="Calificación del curso"
      >
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            type="button"
            className={`${styles.star} ${
              star <= displayRating ? styles.filled : ""
            }`}
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
          <>
            <span className={styles.average}>{averageRating.toFixed(1)}</span>
            <span className={styles.total}>
              ({totalRatings} {totalRatings === 1 ? "voto" : "votos"})
            </span>
          </>
        ) : (
          <span className={styles.noRatings}>Sin calificaciones</span>
        )}
      </div>
    </div>
  );
};
