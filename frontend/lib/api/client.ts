import {
  getApiBaseUrl,
  getHeavyApiBaseUrl,
  isCoreApiPath,
} from "./config";

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
  route?: "auto" | "heavy";
};

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const {
    accessToken,
    headers,
    route = "auto",
    ...requestOptions
  } = options;

  const fetchOptions: RequestInit = {
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
  };

  const primaryBaseUrl =
    route === "heavy"
      ? getHeavyApiBaseUrl()
      : getApiBaseUrl(path);
  const method = String(
    requestOptions.method ?? "GET",
  ).toUpperCase();
  const canFallbackToHeavy =
    isCoreApiPath(path) &&
    (method === "GET" || method === "HEAD") &&
    primaryBaseUrl !== getHeavyApiBaseUrl();

  let response: Response;

  try {
    if (
      canFallbackToHeavy &&
      !fetchOptions.signal
    ) {
      const controller = new AbortController();
      const timeoutId = window.setTimeout(
        () => controller.abort(),
        5000,
      );

      try {
        response = await fetch(
          `${primaryBaseUrl}${path}`,
          {
            ...fetchOptions,
            signal: controller.signal,
          },
        );
      } finally {
        window.clearTimeout(timeoutId);
      }
    } else {
      response = await fetch(
        `${primaryBaseUrl}${path}`,
        fetchOptions,
      );
    }
  } catch (error) {
    if (!canFallbackToHeavy) {
      throw error;
    }

    console.warn(
      "[SanoSync API] Core backend unavailable/slow; retrying on heavy backend.",
      path,
    );

    response = await fetch(
      `${getHeavyApiBaseUrl()}${path}`,
      fetchOptions,
    );
  }

  if (
    canFallbackToHeavy &&
    [502, 503, 504].includes(response.status)
  ) {
    console.warn(
      `[SanoSync API] Core backend returned ${response.status}; retrying on heavy backend.`,
      path,
    );

    response = await fetch(
      `${getHeavyApiBaseUrl()}${path}`,
      fetchOptions,
    );
  }

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
