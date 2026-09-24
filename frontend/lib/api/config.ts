const DEFAULT_API_BASE_URL = "http://localhost:8000";

const CORE_PREFIXES = [
  "/profile",
  "/weekly-schedule",
  "/pantry",
  "/daily-logs",
  "/weight",
  "/progress",
  "/meal-prep",
  "/day-history",
  "/insights",
] as const;

function cleanBaseUrl(
  value: string | undefined,
  fallback: string,
): string {
  return (value?.trim() || fallback).replace(/\/$/, "");
}

export function getHeavyApiBaseUrl(): string {
  return cleanBaseUrl(
    process.env.NEXT_PUBLIC_API_BASE_URL,
    DEFAULT_API_BASE_URL,
  );
}

export function getCoreApiBaseUrl(): string {
  return cleanBaseUrl(
    process.env.NEXT_PUBLIC_CORE_API_BASE_URL,
    getHeavyApiBaseUrl(),
  );
}

export function isCoreApiPath(path: string): boolean {
  return CORE_PREFIXES.some(
    (prefix) =>
      path === prefix ||
      path.startsWith(`${prefix}/`) ||
      path.startsWith(`${prefix}?`),
  );
}

export function getApiBaseUrl(
  path = "",
): string {
  if (isCoreApiPath(path)) {
    return getCoreApiBaseUrl();
  }

  return getHeavyApiBaseUrl();
}
