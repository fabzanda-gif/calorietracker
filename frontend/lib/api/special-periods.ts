import { apiRequest } from "./client";

export type SpecialPeriodType = "vacation" | "illness";

export interface SpecialPeriod {
  id: string;
  period_type: SpecialPeriodType;
  start_date: string;
  end_date: string;
  training_policy: "keep" | "suspend";
  activity_bias: "lower" | "normal" | "higher";
  nutrition_mode: "normal" | "flexible" | "recovery";
  meal_context: "normal" | "out_of_routine";
  notes?: string | null;
  created_at?: string;
  updated_at?: string;
}

export async function getSpecialPeriods(
  accessToken: string,
): Promise<{ count: number; items: SpecialPeriod[] }> {
  return apiRequest(
    "/special-periods",
    { accessToken, route: "heavy" },
  );
}

export async function createSpecialPeriod(
  accessToken: string,
  input: {
    period_type: SpecialPeriodType;
    start_date: string;
    end_date: string;
    notes?: string | null;
  },
): Promise<SpecialPeriod> {
  return apiRequest(
    "/special-periods",
    {
      method: "POST",
      accessToken,
      route: "heavy",
      body: JSON.stringify(input),
    },
  );
}

export async function deleteSpecialPeriod(
  accessToken: string,
  periodId: string,
): Promise<{ deleted: boolean; id: string }> {
  return apiRequest(
    `/special-periods/${encodeURIComponent(periodId)}`,
    {
      method: "DELETE",
      accessToken,
      route: "heavy",
    },
  );
}
