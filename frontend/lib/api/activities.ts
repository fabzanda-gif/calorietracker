import { apiRequest } from "./client";

export interface ActivityRoutePoint {
  latitude: number;
  longitude: number;
  elevation?: number;
  time?: string;
}

export interface ActivitySeriesPoint {
  index: number;
  time?: string;
  cadence?: number;
  heart_rate?: number;
}

export interface Activity {
  id?: string | number | null;
  user_id?: string;
  date: string;
  activity_name: string;
  burned_calories: number;
  source?: "manual" | "gpx";
  activity_type?: string | null;
  started_at?: string | null;
  duration_seconds?: number | null;
  distance_meters?: number | null;
  average_cadence?: number | null;
  average_heart_rate?: number | null;
  route_points?: ActivityRoutePoint[] | string;
  series_points?: ActivitySeriesPoint[] | string;
  original_point_count?: number | null;
  gpx_file_name?: string | null;
}

export interface ActivityCreateInput {
  date: string;
  activity_name: string;
  burned_calories: number;
  activity_type?: string;
  duration_seconds?: number;
}

export interface ActivityUpdateInput {
  activity_name?: string;
  burned_calories?: number;
}

export interface ActivityMovementSummary {
  total_steps: number;
  estimated_training_steps: number;
  applied_step_offset: number;
  net_daily_steps: number;
  step_calories: number;
}

export interface ActivityCreateResponse {
  created: boolean;
  item: Activity;
  movement?: ActivityMovementSummary;
}

export interface ActivityListResponse {
  count: number;
  items: Activity[];
}

export interface ActivityUpdateResponse {
  updated: boolean;
  item: Activity;
}

export function createActivity(
  input: ActivityCreateInput,
  accessToken?: string | null,
): Promise<ActivityCreateResponse> {
  return apiRequest<ActivityCreateResponse>(
    "/activities",
    {
      method: "POST",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}

export function getActivitiesForDate(
  date: string,
  accessToken?: string | null,
): Promise<ActivityListResponse> {
  return apiRequest<ActivityListResponse>(
    `/activities/${date}`,
    {
      accessToken,
    },
  );
}

export function updateActivity(
  id: string | number,
  input: ActivityUpdateInput,
  accessToken?: string | null,
): Promise<ActivityUpdateResponse> {
  return apiRequest<ActivityUpdateResponse>(
    `/activities/${id}`,
    {
      method: "PATCH",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}

export function deleteActivity(
  id: string | number,
  accessToken?: string | null,
): Promise<unknown> {
  return apiRequest(
    `/activities/${id}`,
    {
      method: "DELETE",
      accessToken,
    },
  );
}


export interface GpxActivityPreview
  extends Omit<Activity, "id" | "user_id" | "burned_calories"> {
  source: "gpx";
  original_point_count: number;
  estimated_calories?: number;
}

export interface GpxPreviewResponse {
  file_name: string;
  preview: GpxActivityPreview;
}

export interface GpxImportInput {
  file_name: string;
  content_base64: string;
  activity_name?: string;
  activity_type?: string;
  activity_date?: string;
  burned_calories?: number;
}

export interface ActivityRangeResponse
  extends ActivityListResponse {
  start_date: string;
  end_date: string;
}

export interface ActivityEnergyDay {
  date: string;
  state: "deficit" | "maintenance" | "surplus";
  balance_kcal: number;
}

export interface ActivityOverviewResponse extends ActivityRangeResponse {
  energy_days: ActivityEnergyDay[];
  summary: {
    workouts: number;
    duration_seconds: number;
    distance_meters: number;
    burned_calories: number;
  };
}

export function getActivityOverview(
  startDate: string,
  endDate: string,
  accessToken?: string | null,
): Promise<ActivityOverviewResponse> {
  const query = new URLSearchParams({ start_date: startDate, end_date: endDate });
  return apiRequest<ActivityOverviewResponse>(`/activities/overview?${query.toString()}`, { accessToken });
}

export function previewGpxActivity(
  input: {
    file_name: string;
    content_base64: string;
    activity_type?: string;
  },
  accessToken?: string | null,
): Promise<GpxPreviewResponse> {
  return apiRequest<GpxPreviewResponse>(
    "/activities/gpx/preview",
    {
      method: "POST",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}

export function importGpxActivity(
  input: GpxImportInput,
  accessToken?: string | null,
): Promise<ActivityCreateResponse> {
  return apiRequest<ActivityCreateResponse>(
    "/activities/gpx/import",
    {
      method: "POST",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}

export function getActivitiesForRange(
  startDate: string,
  endDate: string,
  accessToken?: string | null,
): Promise<ActivityRangeResponse> {
  const query = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
  });

  return apiRequest<ActivityRangeResponse>(
    `/activities/range?${query.toString()}`,
    {
      accessToken,
    },
  );
}


export function getActivityMovement(
  date: string,
  accessToken?: string | null,
): Promise<ActivityMovementSummary> {
  return apiRequest<ActivityMovementSummary>(
    `/activities/movement/${encodeURIComponent(date)}`,
    {
      accessToken,
    },
  );
}
