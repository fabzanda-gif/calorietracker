import { apiRequest } from "./client";

export interface ProfileResponse {
  id: string;
  metadata: Record<string, unknown>;
}

export interface ProfileUpdate {
  onboarding_completed?: boolean | null;
  name?: string | null;
  gender?: string | null;
  birth_date?: string | null;
  height?: number | null;
  target_weight?: number | null;
  deficit_plan?: string | null;
  deficit_target_kcal?: number | null;
  goal_mode?: string | null;
  goal_adjustment_kcal?: number | null;
  protein_goal_enabled?: boolean | null;
  protein_goal_g?: number | null;
  language?: string | null;
  city?: string | null;
  office_lunch?: boolean | null;
  weekly_schedule?: Record<string, string> | null;
}

export function getProfile(
  accessToken?: string | null,
): Promise<ProfileResponse> {
  return apiRequest<ProfileResponse>(
    "/profile",
    {
      accessToken,
    },
  );
}

export function updateProfile(
  accessToken: string,
  payload: ProfileUpdate,
): Promise<ProfileResponse> {
  return apiRequest<ProfileResponse>(
    "/profile",
    {
      method: "PUT",
      accessToken,
      body: JSON.stringify(payload),
    },
  );
}

export function deleteAccount(
  accessToken: string,
): Promise<{ deleted: boolean }> {
  return apiRequest<{ deleted: boolean }>(
    "/profile/account",
    {
      method: "DELETE",
      accessToken,
    },
  );
}


export type WeeklyScheduleContext =
  | "home"
  | "office"
  | "free";

export interface WeeklyScheduleResponse {
  week_start: string;
  days: Record<string, WeeklyScheduleContext>;
  overrides: Record<string, WeeklyScheduleContext>;
}

export interface WeeklyScheduleDayUpdate {
  day_of_week: number;
  context: WeeklyScheduleContext;
}

export interface WeeklyScheduleUpdate {
  week_start: string;
  days: WeeklyScheduleDayUpdate[];
}

export function getWeeklySchedule(
  accessToken: string,
  weekStart: string,
): Promise<WeeklyScheduleResponse> {
  const query = new URLSearchParams({
    week_start: weekStart,
  });

  return apiRequest<WeeklyScheduleResponse>(
    `/weekly-schedule?${query.toString()}`,
    {
      accessToken,
    },
  );
}

export function updateWeeklySchedule(
  accessToken: string,
  payload: WeeklyScheduleUpdate,
): Promise<WeeklyScheduleResponse> {
  return apiRequest<WeeklyScheduleResponse>(
    "/weekly-schedule",
    {
      method: "PUT",
      accessToken,
      body: JSON.stringify(payload),
    },
  );
}
