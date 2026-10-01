import { apiRequest } from "./client";


export async function notifyLogin(
  accessToken: string,
): Promise<void> {
  await apiRequest<{ status: string }>(
    "/auth-events/login",
    {
      method: "POST",
      accessToken,
    },
  );
}
