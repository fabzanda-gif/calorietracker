export type ConfidenceState =
  | "confirmed"
  | "predicted"
  | "unknown";

export interface DaySignal<T> {
  value: T | null;
  state: ConfidenceState;
  source: string | null;
  confidence: number | null;
}

export interface DayActual {
  weight: number | null;
  steps: number | null;
}

export interface DayMealPrediction {
  state: string;
  source?: string | null;
  confidence?: number | null;
  [key: string]: unknown;
}

export interface DayResponse {
  date: string;
  context: DaySignal<string>;
  activity_plan: DaySignal<string>;
  actual: DayActual;
  meals: Record<string, DayMealPrediction>;
}

export type DecisionMode =
  | "auto"
  | "ready"
  | "cook"
  | "order"
  | "out";

export type DecisionLens =
  | "calorie"
  | "balanced"
  | "taste";

export interface MealCandidate {
  id?: string | null;
  source: string;
  source_id?: string | null;
  name: string;
  meal_type?: string;
  calories: number;
  protein_g?: number;
  carbs_g?: number;
  fat_g?: number;
  taste_score?: number;
  waste_risk?: string | null;
  decision_feedback_boost?: number;
  decision_feedback_reason?: string | null;
  [key: string]: unknown;
}

export interface RankedMealOption {
  lens: DecisionLens;
  label: string;
  candidate: MealCandidate;
  score: number;
  reason: string;
}

export interface DecisionPreferences {
  preferred_mode: string | null;
  preferred_lens: string | null;
  preferred_source: string | null;
  mode_learning_source?: string | null;
  lens_learning_source?: string | null;
  source_learning_source?: string | null;
  outcome_evidence?: {
    item_count: number;
    observed_count: number;
  };
}

export interface MealOptionsResponse {
  date: string;
  meal_slot: string;
  meal_type: string;
  mode: DecisionMode;
  mode_label: string;
  candidate_count: number;
  candidates: MealCandidate[];
  options: RankedMealOption[];
  decision_preferences: DecisionPreferences;
  empty_reason: string | null;
}
