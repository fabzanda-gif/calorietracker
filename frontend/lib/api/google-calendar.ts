import { apiRequest } from "./client";

export interface GoogleCalendarConnectionStatus {
  connected: boolean;
  connection: {
    scope?: string | null;
    calendar_id?: string | null;
    connected_at?: string | null;
    updated_at?: string | null;
    last_synced_at?: string | null;
    expires_at?: string | null;
  } | null;
}

export interface GoogleCalendarSyncResponse {
  synced: boolean;
  created: number;
  updated: number;
  deleted: number;
}

export function getGoogleCalendarStatus(
  accessToken: string,
): Promise<GoogleCalendarConnectionStatus> {
  return apiRequest<GoogleCalendarConnectionStatus>(
    "/integrations/google-calendar/status",
    {
      accessToken,
    },
  );
}

export function getGoogleCalendarAuthorization(
  accessToken: string,
): Promise<{
  authorization_url: string;
}> {
  return apiRequest<{
    authorization_url: string;
  }>(
    "/integrations/google-calendar/authorize",
    {
      accessToken,
    },
  );
}

export function exchangeGoogleCalendarCode(
  accessToken: string,
  code: string,
  state: string,
): Promise<{
  connected: boolean;
}> {
  return apiRequest<{
    connected: boolean;
  }>(
    "/integrations/google-calendar/exchange",
    {
      method: "POST",
      accessToken,
      body: JSON.stringify({
        code,
        state,
      }),
    } as RequestInit & {
      accessToken: string;
    },
  );
}

export function syncGoogleCalendar(
  accessToken: string,
  startDate: string,
  endDate: string,
): Promise<GoogleCalendarSyncResponse> {
  const query = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
  });

  return apiRequest<GoogleCalendarSyncResponse>(
    `/integrations/google-calendar/sync?${query.toString()}`,
    {
      method: "POST",
      accessToken,
    } as RequestInit & {
      accessToken: string;
    },
  );
}

export function disconnectGoogleCalendar(
  accessToken: string,
): Promise<{
  connected: boolean;
}> {
  return apiRequest<{
    connected: boolean;
  }>(
    "/integrations/google-calendar/connection",
    {
      method: "DELETE",
      accessToken,
    } as RequestInit & {
      accessToken: string;
    },
  );
}
