import { apiRequest } from "./client";
import type { ExerciseLibraryItem } from "./exercises";


export type StrengthGoal =
  | "hypertrophy"
  | "strength"
  | "general_fitness";

export type StrengthExperience =
  | "beginner"
  | "intermediate"
  | "advanced";

export type StrengthWorkoutStatus =
  | "planned"
  | "completed"
  | "skipped";

export interface StrengthPlan {
  id: string;
  user_id?: string;
  goal: StrengthGoal;
  experience_level: StrengthExperience;
  program_style:
    | "full_body"
    | "upper_lower"
    | "push_pull_legs";
  sessions_per_week: number;
  start_date: string;
  total_weeks: number;
  status:
    | "active"
    | "paused"
    | "completed"
    | "cancelled";
  created_at?: string;
  updated_at?: string;
}

export interface StrengthWorkoutExercise {
  id: string;
  user_id?: string;
  strength_workout_id: string;
  position: number;
  exercise_id?: string | null;
  exercise_key: string;
  exercise_name: string;
  movement_pattern: string;
  target_sets: number;
  target_reps_min: number;
  target_reps_max: number;
  target_rir: number | null;
  rest_seconds: number | null;
  prescribed_load_kg: number | null;
  is_user_added?: boolean;
  substituted_from_exercise_id?: string | null;
  prescription_source?: "plan" | "manual" | "substitution";
}

export interface StrengthWorkout {
  id: string;
  user_id?: string;
  strength_plan_id: string | null;
  scheduled_date: string;
  training_week: number | null;
  workout_index: number | null;
  title: string;
  focus: string;
  status: StrengthWorkoutStatus;
  workout_kind?: "planned" | "free";
  estimated_duration_minutes: number | null;
  exercises: StrengthWorkoutExercise[];
}

export interface StrengthPlanInput {
  start_date: string;
  goal: StrengthGoal;
  experience_level: StrengthExperience;
  sessions_per_week: 2 | 3 | 4;
  total_weeks: number;
  replace_active?: boolean;
}

export interface StrengthPlanPreviewResponse {
  preview: true;
  plan: {
    goal: StrengthGoal;
    experience_level: StrengthExperience;
    program_style: string;
    sessions_per_week: number;
    start_date: string;
    total_weeks: number;
    workout_count: number;
    workouts: Array<{
      scheduled_date: string;
      title: string;
      focus: string;
      training_week: number;
      workout_index: number;
      estimated_duration_minutes: number | null;
      exercises: Array<Omit<StrengthWorkoutExercise, "id" | "strength_workout_id">>;
    }>;
  };
}

export interface StrengthPlanListResponse {
  count: number;
  items: StrengthPlan[];
}

export interface StrengthPlanDetailResponse {
  plan: StrengthPlan;
  workout_count: number;
  workouts: StrengthWorkout[];
}

export type StrengthEffortFeeling =
  | "easy"
  | "right"
  | "hard"
  | "too_hard";

export interface StrengthSetLogInput {
  reps: number;
  load_kg: number;
  rir?: number | null;
  feeling?: StrengthEffortFeeling | null;
}

export interface StrengthWorkoutLogInput {
  performed_date: string;
  duration_minutes?: number | null;
  notes?: string | null;
  exercises: Array<{
    exercise_id: string;
    sets: StrengthSetLogInput[];
  }>;
}

export interface StrengthExerciseOutcome {
  exercise_id: string;
  exercise_key?: string | null;
  exercise_name?: string | null;
  outcome:
    | "under_target"
    | "on_target"
    | "over_target";
  message: string;
  target_sets: number;
  completed_sets: number;
  target_reps_min: number;
  target_reps_max: number;
  target_rir: number | null;
  average_reps: number | null;
  average_rir: number | null;
  volume_load: number;
}

export interface StrengthWorkoutOutcome {
  outcome:
    | "under_target"
    | "on_target"
    | "over_target";
  message: string;
  planned_exercise_count: number;
  logged_exercise_count: number;
  under_target_count: number;
  on_target_count: number;
  over_target_count: number;
  exercises: StrengthExerciseOutcome[];
}

export interface StrengthOutcomeResponse {
  status: "pending" | "evaluated";
  workout: StrengthWorkout;
  workout_log?: unknown;
  outcome: StrengthWorkoutOutcome | null;
  message?: string;
}

export interface StrengthProgressionProposal {
  exercise_id: string;
  exercise_key?: string | null;
  exercise_name?: string | null;
  movement_pattern?: string | null;
  outcome:
    | "under_target"
    | "on_target"
    | "over_target";
  action:
    | "increase_load"
    | "maintain"
    | "reduce_load";
  current_load_kg: number;
  proposed_load_kg: number;
  load_change_kg: number;
  message: string;
  next_exposure: {
    workout_id: string;
    scheduled_date: string;
    exercise_id: string;
    current_prescribed_load_kg:
      | number
      | null;
  } | null;
}

export interface StrengthHistorySet {
  set_index: number;
  reps: number;
  load_kg: number;
  rir: number | null;
}

export interface StrengthHistoryExercise
  extends StrengthWorkoutExercise {
  sets: StrengthHistorySet[];
}

export interface StrengthProgressionHistoryItem {
  id: string;
  source_workout_id: string;
  source_exercise_id: string;
  target_workout_id?: string;
  target_exercise_id: string;
  exercise_key: string;
  outcome:
    | "under_target"
    | "on_target"
    | "over_target";
  action:
    | "increase_load"
    | "maintain"
    | "reduce_load";
  observed_load_kg: number | null;
  before_load_kg: number | null;
  after_load_kg: number | null;
  created_at?: string;
}

export interface StrengthPlanHistoryItem {
  workout: StrengthWorkout;
  workout_log: {
    id: string;
    strength_workout_id: string;
    performed_date: string;
    duration_minutes: number | null;
    notes: string | null;
  };
  exercises: StrengthHistoryExercise[];
  outcome: StrengthWorkoutOutcome;
  progressions:
    StrengthProgressionHistoryItem[];
}

export interface StrengthPlanHistoryResponse {
  plan_id: string;
  count: number;
  items: StrengthPlanHistoryItem[];
}


export interface StrengthProgressionPreviewResponse {
  status: "pending" | "preview";
  workout: StrengthWorkout;
  workout_outcome?: string;
  proposal_count?: number;
  actionable_count?: number;
  proposals: StrengthProgressionProposal[];
  message?: string;
}


export function previewStrengthPlan(
  input: StrengthPlanInput,
  accessToken?: string | null,
): Promise<StrengthPlanPreviewResponse> {
  return apiRequest<StrengthPlanPreviewResponse>(
    "/strength/plans/preview",
    {
      method: "POST",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}


export function createStrengthPlan(
  input: StrengthPlanInput,
  accessToken?: string | null,
): Promise<unknown> {
  return apiRequest(
    "/strength/plans",
    {
      method: "POST",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}


export interface StrengthWorkoutRangeResponse {
  count: number;
  items: StrengthWorkout[];
}

export function getStrengthWorkouts(
  startDate: string,
  endDate: string,
  accessToken?: string | null,
): Promise<StrengthWorkoutRangeResponse> {
  const query = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
  });

  return apiRequest<StrengthWorkoutRangeResponse>(
    `/strength/workouts?${query.toString()}`,
    {
      accessToken,
    },
  );
}


export function getStrengthPlans(
  accessToken?: string | null,
): Promise<StrengthPlanListResponse> {
  return apiRequest<StrengthPlanListResponse>(
    "/strength/plans",
    {
      accessToken,
    },
  );
}


export function getStrengthPlanDetail(
  planId: string,
  accessToken?: string | null,
): Promise<StrengthPlanDetailResponse> {
  return apiRequest<StrengthPlanDetailResponse>(
    `/strength/plans/${planId}`,
    {
      accessToken,
    },
  );
}


export function getStrengthPlanHistory(
  planId: string,
  accessToken?: string | null,
): Promise<StrengthPlanHistoryResponse> {
  return apiRequest<StrengthPlanHistoryResponse>(
    `/strength/plans/${planId}/history`,
    {
      accessToken,
    },
  );
}


export function skipStrengthWorkout(
  workoutId: string,
  accessToken?: string | null,
): Promise<unknown> {
  return apiRequest(
    `/strength/workouts/${workoutId}/skip`,
    {
      method: "POST",
      accessToken,
    },
  );
}


export function cancelStrengthPlan(
  planId: string,
  accessToken?: string | null,
): Promise<unknown> {
  return apiRequest(
    `/strength/plans/${planId}/cancel`,
    {
      method: "POST",
      accessToken,
    },
  );
}


export function logStrengthWorkout(
  workoutId: string,
  input: StrengthWorkoutLogInput,
  accessToken?: string | null,
): Promise<unknown> {
  return apiRequest(
    `/strength/workouts/${workoutId}/log`,
    {
      method: "POST",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}


export function getStrengthWorkoutOutcome(
  workoutId: string,
  accessToken?: string | null,
): Promise<StrengthOutcomeResponse> {
  return apiRequest<StrengthOutcomeResponse>(
    `/strength/workouts/${workoutId}/outcome`,
    {
      accessToken,
    },
  );
}


export function getStrengthProgressionPreview(
  workoutId: string,
  accessToken?: string | null,
): Promise<StrengthProgressionPreviewResponse> {
  return apiRequest<StrengthProgressionPreviewResponse>(
    `/strength/workouts/${workoutId}/progression-preview`,
    {
      accessToken,
    },
  );
}


export function applyStrengthProgression(
  workoutId: string,
  exerciseId: string,
  accessToken?: string | null,
): Promise<unknown> {
  return apiRequest(
    (
      `/strength/workouts/${workoutId}` +
      `/progression/${exerciseId}/apply`
    ),
    {
      method: "POST",
      accessToken,
    },
  );
}


export interface StrengthSavedSet {
  id?: string;
  strength_workout_log_id: string;
  strength_workout_exercise_id: string;
  set_index: number;
  reps: number;
  load_kg: number;
  rir: number | null;
  feeling: StrengthEffortFeeling | null;
}

export interface StrengthSessionResponse {
  status: "draft";
  workout: StrengthWorkout;
  workout_log: {
    id: string;
    strength_workout_id: string;
    performed_date: string;
    duration_minutes: number | null;
    notes: string | null;
    status: "draft";
  };
  exercises: StrengthWorkoutExercise[];
  sets: StrengthSavedSet[];
}

export function startStrengthSession(
  workoutId: string,
  performedDate: string,
  accessToken?: string | null,
): Promise<StrengthSessionResponse> {
  return apiRequest<StrengthSessionResponse>(
    `/strength/workouts/${workoutId}/session`,
    {
      method: "POST",
      accessToken,
      body: JSON.stringify({
        performed_date: performedDate,
      }),
    },
  );
}

export function saveStrengthSet(
  workoutId: string,
  exerciseId: string,
  setIndex: number,
  input: {
    reps: number;
    load_kg: number;
    feeling?: StrengthEffortFeeling | null;
    rir?: number | null;
  },
  accessToken?: string | null,
): Promise<{
  saved: true;
  workout_log_id: string;
  set: StrengthSavedSet;
}> {
  return apiRequest(
    (
      `/strength/workouts/${workoutId}` +
      `/exercises/${exerciseId}/sets/${setIndex}`
    ),
    {
      method: "PUT",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}

export function deleteStrengthSet(
  workoutId: string,
  exerciseId: string,
  setIndex: number,
  accessToken?: string | null,
): Promise<{ deleted: true }> {
  return apiRequest(
    (
      `/strength/workouts/${workoutId}` +
      `/exercises/${exerciseId}/sets/${setIndex}`
    ),
    {
      method: "DELETE",
      accessToken,
    },
  );
}

export function completeStrengthSession(
  workoutId: string,
  input: {
    duration_minutes?: number | null;
    notes?: string | null;
  },
  accessToken?: string | null,
): Promise<unknown> {
  return apiRequest(
    `/strength/workouts/${workoutId}/complete`,
    {
      method: "POST",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}

export function createFreeStrengthWorkout(
  input: {
    title?: string;
    performed_date?: string;
  },
  accessToken?: string | null,
): Promise<{
  created: true;
  workout: StrengthWorkout;
}> {
  return apiRequest(
    "/strength/workouts/free",
    {
      method: "POST",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}

export function addStrengthWorkoutExercise(
  workoutId: string,
  input: {
    library_exercise_id: string;
    target_sets?: number;
    target_reps_min?: number;
    target_reps_max?: number;
    target_rir?: number | null;
    rest_seconds?: number | null;
  },
  accessToken?: string | null,
): Promise<{
  created: true;
  exercise: StrengthWorkoutExercise;
}> {
  return apiRequest(
    `/strength/workouts/${workoutId}/exercises`,
    {
      method: "POST",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}

export function getStrengthSubstitutions(
  workoutId: string,
  exerciseId: string,
  accessToken?: string | null,
): Promise<{
  items: Array<
    ExerciseLibraryItem & {
      substitution_score: number;
    }
  >;
  count: number;
}> {
  return apiRequest(
    (
      `/strength/workouts/${workoutId}` +
      `/exercises/${exerciseId}/substitutions`
    ),
    { accessToken },
  );
}

export function substituteStrengthExercise(
  workoutId: string,
  exerciseId: string,
  libraryExerciseId: string,
  accessToken?: string | null,
): Promise<{
  substituted: true;
  exercise: StrengthWorkoutExercise;
}> {
  return apiRequest(
    (
      `/strength/workouts/${workoutId}` +
      `/exercises/${exerciseId}/substitute`
    ),
    {
      method: "PUT",
      accessToken,
      body: JSON.stringify({
        library_exercise_id: libraryExerciseId,
      }),
    },
  );
}
