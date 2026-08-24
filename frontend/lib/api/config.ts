const DEFAULT_API_BASE_URL = "http://localhost:8000";

export function getApiBaseUrl(): string {
  const value =
    process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ||
    DEFAULT_API_BASE_URL;

  return value.replace(/\/$/, "");
}
