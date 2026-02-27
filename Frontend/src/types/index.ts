// Course types
export interface Course {
  id: number;
  name: string;
  description: string;
  thumbnail: string;
  slug: string;
  average_rating: number | null;
  total_ratings: number;
}

// Class types
export interface Class {
  id: number;
  name: string;
  description: string;
  slug: string;
}

// Course Detail type
export interface CourseDetail extends Course {
  teacher_id: number[];
  classes: Class[];
}

// Progress types
export interface Progress {
  progress: number; // seconds
  user_id: number;
}

// Quiz types
export interface QuizOption {
  id: number;
  answer: string;
  correct: boolean;
}

export interface Quiz {
  id: number;
  question: string;
  options: QuizOption[];
}

// Favorite types
export interface FavoriteToggle {
  course_id: number;
}

// Rating types
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