import { apiRequest } from "./client";

import type {
  ConversationalMealPreviewItem,
} from "./meals";


export interface ConversationalDayMealAction {
  id: string;
  kind: "meal";
  date: string;
  text: string;
  meal_type: string;
  items: ConversationalMealPreviewItem[];
  totals: {
    calories: number;
    protein: number;
    carbs: number;
    fat: number;
  };
  needs_review: boolean;
  requires_confirmation: true;
}


export interface ConversationalDayActivityAction {
  id: string;
  kind: "activity";
  date: string;
  activity_name: string;
  activity_type: string;
  duration_seconds?: number | null;
  distance_meters?: number | null;
  burned_calories: number;
  calories_estimated: boolean;
  needs_review: boolean;
  requires_confirmation: true;
}


export interface ConversationalDayWeightAction {
  id: string;
  kind: "weight";
  date: string;
  weight_kg: number;
  needs_review: boolean;
  requires_confirmation: true;
}


export type ConversationalDayAction =
  | ConversationalDayMealAction
  | ConversationalDayActivityAction
  | ConversationalDayWeightAction;


export interface ConversationalDayPreview {
  status: "preview";
  original_text: string;
  actions: ConversationalDayAction[];
  needs_review: boolean;
  requires_confirmation: true;
}


export function previewConversationalDay(
  text: string,
  defaultMealType: string,
  referenceDate: string,
  accessToken?: string | null,
): Promise<ConversationalDayPreview> {
  return apiRequest<ConversationalDayPreview>(
    "/meals/conversational/day-preview",
    {
      method: "POST",
      accessToken,
      body: JSON.stringify({
        text,
        default_meal_type: defaultMealType,
        reference_date: referenceDate,
      }),
    },
  );
}
