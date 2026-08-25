import { apiRequest } from "./client";

export interface Activity {
  id?: string | number | null;
  user_id?: string;
  date: string;
  activity_name: string;
  burned_calories: number;
}

export interface ActivityCreateInput {
  date: string;
  activity_name: string;
  burned_calories: number;
}

export interface ActivityUpdateInput {
  activity_name?: string;
  burned_calories?: number;
}

export interface ActivityCreateResponse {
  created: boolean;
  item: Activity;
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
