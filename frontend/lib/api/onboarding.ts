import { apiRequest } from "./client";

export type PrimaryGoal =
  | "hypertrophy"
  | "strength"
  | "general_fitness";

export type OnboardingNextStep =
  | "core"
  | "food_setup"
  | "training_setup"
  | null;

export interface OnboardingPreferences {
  onboarding_version?: number;
  primary_goal: PrimaryGoal | null;
  food_enabled: boolean;
  training_enabled: boolean;
  core_onboarding_completed: boolean;
  food_setup_completed: boolean;
  training_setup_completed: boolean;
  last_step?: string | null;
}

export interface NutritionProfile {
  weight_strategy: "loss" | "maintenance" | "gain" | null;
  target_weight_kg: number | null;
  calorie_adjustment_kcal: number | null;
  protein_target_mode: "automatic" | "manual" | "disabled";
  protein_target_g: number | null;
  macro_tracking_enabled: boolean;
}

export interface TrainingProfile {
  experience_level: "beginner" | "intermediate" | "advanced";
  sessions_per_week: number;
  session_duration_minutes: number;
  planning_horizon: "weekly" | "monthly";
  environment: "commercial_gym";
  coach_style: "conservative" | "balanced" | "ambitious";
  feedback_mode: "simple" | "advanced";
  schedule_flexibility: "fixed" | "flexible";
}

export interface OnboardingStatus {
  version: number;
  source: "v2" | "legacy";
  completed: boolean;
  next_step: OnboardingNextStep;
  preferences: OnboardingPreferences | null;
  nutrition_profile: NutritionProfile | null;
  training_profile: TrainingProfile | null;
  preferred_days: number[];
  priority_muscles: string[];
}

export function getOnboardingStatus(
  accessToken: string,
): Promise<OnboardingStatus> {
  return apiRequest<OnboardingStatus>(
    "/onboarding/status",
    { accessToken },
  );
}

export function saveOnboardingCore(
  accessToken: string,
  payload: {
    primary_goal: PrimaryGoal;
    food_enabled: boolean;
    training_enabled: boolean;
  },
): Promise<OnboardingStatus> {
  return apiRequest<OnboardingStatus>(
    "/onboarding/core",
    {
      method: "PUT",
      accessToken,
      body: JSON.stringify(payload),
    },
  );
}

export function saveNutritionSetup(
  accessToken: string,
  payload: {
    weight_strategy: "loss" | "maintenance" | "gain";
    target_weight_kg: number | null;
    calorie_adjustment_kcal: number;
    protein_target_mode: "automatic" | "manual" | "disabled";
    protein_target_g: number | null;
    macro_tracking_enabled: boolean;
  },
): Promise<OnboardingStatus> {
  return apiRequest<OnboardingStatus>(
    "/onboarding/nutrition",
    {
      method: "PUT",
      accessToken,
      body: JSON.stringify(payload),
    },
  );
}

export function saveTrainingSetup(
  accessToken: string,
  payload: {
    experience_level: "beginner" | "intermediate" | "advanced";
    sessions_per_week: number;
    session_duration_minutes: number;
    planning_horizon: "weekly" | "monthly";
    environment: "commercial_gym";
    coach_style: "conservative" | "balanced" | "ambitious";
    feedback_mode: "simple" | "advanced";
    schedule_flexibility: "fixed" | "flexible";
    preferred_days: number[];
    priority_muscles: string[];
  },
): Promise<OnboardingStatus> {
  return apiRequest<OnboardingStatus>(
    "/onboarding/training",
    {
      method: "PUT",
      accessToken,
      body: JSON.stringify(payload),
    },
  );
}
