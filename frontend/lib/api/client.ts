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

// A dashboard navigation can start dozens of independent reads at once.
// Keep their peak server-side memory bounded without delaying writes.
const MAX_CONCURRENT_READS = 6;
let activeReads = 0;
const waitingReads: Array<() => void> = [];

function abortError(signal?: AbortSignal | null): unknown {
  return signal?.reason ?? new DOMException("Request aborted", "AbortError");
}

async function acquireReadSlot(signal?: AbortSignal | null): Promise<void> {
  if (signal?.aborted) throw abortError(signal);

  if (activeReads < MAX_CONCURRENT_READS) {
    activeReads += 1;
    return;
  }

  await new Promise<void>((resolve, reject) => {
    const resume = () => {
      signal?.removeEventListener("abort", abort);
      activeReads += 1;
      resolve();
    };
    const abort = () => {
      const index = waitingReads.indexOf(resume);
      if (index !== -1) waitingReads.splice(index, 1);
      reject(abortError(signal));
    };

    waitingReads.push(resume);
    signal?.addEventListener("abort", abort, { once: true });
    if (signal?.aborted) abort();
  });
}

function releaseReadSlot(): void {
  activeReads -= 1;
  waitingReads.shift()?.();
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const {
    accessToken,
    headers,
    ...requestOptions
  } = options;

  const isRead = !requestOptions.method || requestOptions.method.toUpperCase() === "GET";
  if (isRead) await acquireReadSlot(requestOptions.signal);

  try {
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
  } finally {
    if (isRead) releaseReadSlot();
  }
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
