import { apiRequest } from "./client";

export type TrainingPushSubscription = {
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
  timezone: string;
};

export async function getPushPublicKey(): Promise<string> {
  const response = await apiRequest<{ public_key: string }>(
    "/notifications/vapid-public-key",
    { route: "heavy" },
  );

  return response.public_key;
}

export async function subscribeToTrainingNotifications(
  accessToken: string,
  subscription: TrainingPushSubscription,
): Promise<{
  enabled: boolean;
  timezone: string;
  reminder_hour: number;
}> {
  return apiRequest(
    "/notifications/training/subscribe",
    {
      method: "POST",
      accessToken,
      route: "heavy",
      body: JSON.stringify(subscription),
    },
  );
}

export async function unsubscribeFromTrainingNotifications(
  accessToken: string,
  endpoint: string,
): Promise<{ enabled: boolean }> {
  return apiRequest(
    "/notifications/training/unsubscribe",
    {
      method: "POST",
      accessToken,
      route: "heavy",
      body: JSON.stringify({ endpoint }),
    },
  );
}
