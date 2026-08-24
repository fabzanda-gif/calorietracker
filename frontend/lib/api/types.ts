export type ConfidenceState =
  | "confirmed"
  | "predicted"
  | "unknown";

export interface DayEvidence {
  observations?: number;
  matches?: number;
  recent_observations?: number;
  recent_matches?: number;
  change_detected?: boolean;
}

export interface DaySignal<T> {
  value: T | null;
  state: ConfidenceState;
  source: string | null;
  confidence: number | null;
  confidence_level?: string | null;
  evidence?: DayEvidence;
}

export interface DayActual {
  weight: number | null;
  steps: number | null;
}

export interface DayMealPrediction {
  meal_type?: string;
  value: string | null;
  state: string;
  source?: string | null;
  confidence?: number | null;
  confidence_level?: string | null;
  day_context?: string | null;
  estimated_calories?: number | null;
  estimated_protein_g?: number | null;
  estimated_carbs_g?: number | null;
  estimated_fat_g?: number | null;
  evidence?: DayEvidence;
  [key: string]: unknown;
}

export interface DayResponse {
  date: string;
  context: DaySignal<string>;
  activity_plan: DaySignal<string>;
  actual: DayActual;
  meals: Record<string, DayMealPrediction>;
}

export interface DayBudget {
  goal_mode: "loss" | "maintenance" | "gain";
  goal_adjustment_kcal: number;
  maintenance_kcal: number;
  daily_budget_kcal: number;
  consumed_kcal: number;
  planned_kcal: number;
  available_kcal: number;
  unallocated_kcal: number;
  protein_consumed_g: number;
  protein_target_g: number | null;
  protein_remaining_g: number | null;
}

export interface DayBudgetResponse {
  date: string;
  status: string;
  budget: DayBudget | null;
  actual: Record<string, unknown>;
  profile: Record<string, unknown>;
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
