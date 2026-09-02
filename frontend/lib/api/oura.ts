import { apiRequest } from "./client";

export interface OuraConnectionStatus {
  connected: boolean;
  connection: {
    scope?: string | null;
    connected_at?: string | null;
    updated_at?: string | null;
    last_synced_at?: string | null;
    expires_at?: string | null;
  } | null;
}

export function getOuraStatus(
  accessToken: string,
): Promise<OuraConnectionStatus> {
  return apiRequest<OuraConnectionStatus>(
    "/integrations/oura/status",
    {
      accessToken,
    },
  );
}

export function getOuraAuthorization(
  accessToken: string,
): Promise<{
  authorization_url: string;
}> {
  return apiRequest<{
    authorization_url: string;
  }>(
    "/integrations/oura/authorize",
    {
      accessToken,
    },
  );
}

export function exchangeOuraCode(
  accessToken: string,
  code: string,
  state: string,
): Promise<{
  connected: boolean;
}> {
  return apiRequest<{
    connected: boolean;
  }>(
    "/integrations/oura/exchange",
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
