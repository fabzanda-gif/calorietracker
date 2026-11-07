import { apiRequest } from "./client";

export interface ExerciseMedia {
  media_type: "video" | "thumbnail" | "image";
  variant: "male" | "female" | "neutral";
  url: string;
  source: string;
  source_url: string | null;
  source_license: string | null;
  attribution: string | null;
  is_primary: boolean;
}

export interface ExerciseMuscle {
  key: string;
  name: string;
  role: "primary" | "secondary";
  contribution: number;
}

export interface ExerciseEquipment {
  key: string;
  name: string;
  role: "primary" | "required";
}

export interface ExerciseLibraryItem {
  id: string;
  slug: string;
  source: string;
  source_id: string;
  name_default: string;
  name: string;
  body_part: string | null;
  target_muscle: string | null;
  movement_pattern: string | null;
  mechanic: "compound" | "isolation" | null;
  laterality: "bilateral" | "unilateral" | "alternating";
  difficulty: "beginner" | "intermediate" | "advanced" | null;
  training_role: "primary" | "secondary" | "accessory" | null;
  fatigue_cost: "low" | "medium" | "high" | null;
  technical_complexity: "low" | "medium" | "high" | null;
  stability_requirement: "low" | "medium" | "high" | null;
  tracking_type:
    | "reps_load"
    | "reps_bodyweight"
    | "duration"
    | "distance";
  load_convention:
    | "reported"
    | "total"
    | "per_hand"
    | "bodyweight"
    | "bodyweight_plus_external"
    | "assistance";
  approved_for_generation: boolean;
  short_description: string | null;
  instructions: string | null;
  steps: string[];
  form_cues: string[];
  common_mistakes: string[];
  breathing: string | null;
  media: ExerciseMedia[];
  muscles: ExerciseMuscle[];
  equipment: ExerciseEquipment[];
  aliases: string[];
}

export interface ExerciseLibraryList {
  items: ExerciseLibraryItem[];
  count: number;
  limit: number;
  offset: number;
}

export function listExercises(
  accessToken: string,
  options: {
    search?: string;
    bodyPart?: string;
    equipment?: string;
    difficulty?: "beginner" | "intermediate" | "advanced";
    approvedOnly?: boolean;
    language?: string;
    limit?: number;
    offset?: number;
  } = {},
): Promise<ExerciseLibraryList> {
  const params = new URLSearchParams();

  if (options.search) {
    params.set("search", options.search);
  }
  if (options.bodyPart) {
    params.set("body_part", options.bodyPart);
  }
  if (options.equipment) {
    params.set("equipment", options.equipment);
  }
  if (options.difficulty) {
    params.set("difficulty", options.difficulty);
  }
  if (options.approvedOnly) {
    params.set("approved_only", "true");
  }
  if (options.language) {
    params.set("language", options.language);
  }
  if (options.limit) {
    params.set("limit", String(options.limit));
  }
  if (options.offset) {
    params.set("offset", String(options.offset));
  }

  const query = params.toString();
  return apiRequest<ExerciseLibraryList>(
    `/exercises${query ? `?${query}` : ""}`,
    { accessToken },
  );
}

export function getExercise(
  accessToken: string,
  identifier: string,
  language = "it",
): Promise<ExerciseLibraryItem> {
  return apiRequest<ExerciseLibraryItem>(
    `/exercises/${encodeURIComponent(identifier)}?language=${encodeURIComponent(language)}`,
    { accessToken },
  );
}

export type ExerciseRelationship =
  | "close_substitute"
  | "substitute"
  | "regression";

export interface ExerciseAlternative {
  exercise: ExerciseLibraryItem;
  relationship: ExerciseRelationship;
  similarity_score: number | null;
  rationale: string | null;
  requires_confirmation: true;
}

export interface ExerciseAlternativesResponse {
  items: ExerciseAlternative[];
  count: number;
}

/**
 * Suggestions only: the client must obtain user confirmation before
 * changing any planned or in-progress strength workout.
 */
export function getExerciseAlternatives(
  accessToken: string,
  identifier: string,
  options: {
    language?: string;
    equipment?: string;
    limit?: number;
  } = {},
): Promise<ExerciseAlternativesResponse> {
  const params = new URLSearchParams();
  if (options.language) params.set("language", options.language);
  if (options.equipment) params.set("equipment", options.equipment);
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  const query = params.toString();
  const url = `/exercises/${encodeURIComponent(identifier)}/alternatives${query ? `?${query}` : ""}`;
  return apiRequest<ExerciseAlternativesResponse>(url, { accessToken });
}
