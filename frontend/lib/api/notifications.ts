import { apiRequest } from "./client";

export type TrainingPushSubscription = {
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
  timezone: string;
  reminder_hour: number;
};

export type TrainingNotificationSettings = {
  enabled: boolean;
  timezone: string;
  reminder_hour: number;
};

export async function getPushPublicKey(): Promise<string> {
  const response = await apiRequest<{ public_key: string }>(
    "/notifications/vapid-public-key",
    { route: "heavy" },
  );

  return response.public_key;
}

export async function getTrainingNotificationSettings(
  accessToken: string,
  endpoint: string,
): Promise<TrainingNotificationSettings> {
  const params = new URLSearchParams({ endpoint });
  return apiRequest(
    `/notifications/training/settings?${params.toString()}`,
    {
      accessToken,
      route: "heavy",
    },
  );
}

export async function subscribeToTrainingNotifications(
  accessToken: string,
  subscription: TrainingPushSubscription,
): Promise<TrainingNotificationSettings> {
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
