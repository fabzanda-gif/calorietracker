import { apiRequest } from "./client";

export type DayHistoryProfile = {
  day_type: "office" | "home" | "free";
  days: number;
  average_burned_calories: number | null;
  median_burned_calories: number | null;
  min_burned_calories: number | null;
  max_burned_calories: number | null;
};

export type DayHistoryResponse = {
  lookback_days: number;
  start_date: string;
  end_date: string;
  profiles: {
    office: DayHistoryProfile;
    home: DayHistoryProfile;
    free: DayHistoryProfile;
  };
};

export function getDayHistory(
  accessToken?: string | null,
): Promise<DayHistoryResponse> {
  return apiRequest<DayHistoryResponse>(
    "/day-history/activity-profile",
    {
      accessToken,
    },
  );
}
