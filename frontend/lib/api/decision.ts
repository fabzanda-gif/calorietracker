import { apiRequest } from "./client";
import type {
  DecisionMode,
  MealCandidate,
} from "./types";

export interface DecisionCommitInput {
  mode: DecisionMode;
  lens: string;
  option_index: number;
  candidate: MealCandidate;
  available_kcal?: number | null;
  protein_remaining_g?: number | null;
}

export interface DecisionCommitResponse {
  committed: boolean;
  already_committed: boolean;
  selection: Record<string, unknown> | null;
  meal: Record<string, unknown>;
}

export function commitMealDecision(
  dayDate: string,
  mealSlot: string,
  input: DecisionCommitInput,
  accessToken?: string | null,
): Promise<DecisionCommitResponse> {
  return apiRequest<DecisionCommitResponse>(
    `/days/${encodeURIComponent(dayDate)}` +
      `/meals/${encodeURIComponent(mealSlot)}` +
      `/commit`,
    {
      method: "POST",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}
