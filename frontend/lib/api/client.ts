import { getApiBaseUrl } from "./config";

export class ApiError extends Error {
  readonly status: number;
  readonly payload: unknown;

  constructor(
    message: string,
    status: number,
    payload: unknown,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

type ApiRequestOptions = RequestInit & {
  accessToken?: string | null;
};

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const {
    accessToken,
    headers,
    ...requestOptions
  } = options;

  const response = await fetch(
    `${getApiBaseUrl()}${path}`,
    {
      ...requestOptions,
      headers: {
        Accept: "application/json",
        ...(requestOptions.body
          ? { "Content-Type": "application/json" }
          : {}),
        ...(accessToken
          ? { Authorization: `Bearer ${accessToken}` }
          : {}),
        ...headers,
      },
      cache: "no-store",
    },
  );

  const payload = await readPayload(response);

  if (!response.ok) {
    throw new ApiError(
      `SanoSync API request failed (${response.status})`,
      response.status,
      payload,
    );
  }

  return payload as T;
}

async function readPayload(
  response: Response,
): Promise<unknown> {
  const contentType =
    response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response.text();
}
