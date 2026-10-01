"use client";

import { useEffect, useState } from "react";

import {
  getPushPublicKey,
  getTrainingNotificationSettings,
  subscribeToTrainingNotifications,
  unsubscribeFromTrainingNotifications,
} from "@/lib/api/notifications";

import styles from "./TrainingNotificationsCard.module.css";

interface Props {
  accessToken: string;
}

const REMINDER_HOURS = [6, 7, 8, 9, 10, 11] as const;

function urlBase64ToUint8Array(value: string): Uint8Array {
  const padding = "=".repeat((4 - (value.length % 4)) % 4);
  const base64 = (value + padding)
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  const raw = window.atob(base64);
  return Uint8Array.from(raw, (char) => char.charCodeAt(0));
}

function keyToBase64(value: ArrayBuffer | null): string {
  if (!value) {
    return "";
  }

  const bytes = new Uint8Array(value);
  let binary = "";

  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }

  return window
    .btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function browserSupportsPush(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

function hourLabel(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`;
}

export function TrainingNotificationsCard({ accessToken }: Props) {
  const [supported, setSupported] = useState(true);
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [reminderHour, setReminderHour] = useState(8);
  const [settingsOpen, setSettingsOpen] = useState(true);
  const [justEnabled, setJustEnabled] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function checkCurrentSubscription() {
      const hasSupport = browserSupportsPush();

      if (!hasSupport) {
        if (!cancelled) {
          setSupported(false);
        }
        return;
      }

      try {
        const registration = await navigator.serviceWorker.ready;
        const subscription = await registration.pushManager.getSubscription();
        const browserEnabled =
          Boolean(subscription) && Notification.permission === "granted";

        if (!cancelled) {
          setEnabled(browserEnabled);
          setSettingsOpen(!browserEnabled);
        }

        if (subscription && browserEnabled) {
          try {
            const settings = await getTrainingNotificationSettings(
              accessToken,
              subscription.endpoint,
            );
            if (!cancelled) {
              setEnabled(settings.enabled);
              setReminderHour(settings.reminder_hour || 8);
              setSettingsOpen(!settings.enabled);
            }
          } catch {
            // La subscription del browser resta comunque valida.
          }
        }
      } catch {
        if (!cancelled) {
          setSupported(false);
        }
      }
    }

    void checkCurrentSubscription();

    return () => {
      cancelled = true;
    };
  }, [accessToken]);

  async function saveSubscription(hour: number) {
    const registration = await navigator.serviceWorker.ready;
    const publicKey = await getPushPublicKey();
    let subscription = await registration.pushManager.getSubscription();

    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey) as BufferSource,
      });
    }

    const p256dh = keyToBase64(subscription.getKey("p256dh"));
    const auth = keyToBase64(subscription.getKey("auth"));

    if (!p256dh || !auth) {
      throw new Error("Il browser non ha restituito una subscription valida.");
    }

    return subscribeToTrainingNotifications(accessToken, {
      endpoint: subscription.endpoint,
      keys: { p256dh, auth },
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      reminder_hour: hour,
    });
  }

  async function enableNotifications() {
    if (!browserSupportsPush() || busy) {
      return;
    }

    setBusy(true);
    setMessage(null);

    try {
      const permission = await Notification.requestPermission();

      if (permission !== "granted") {
        setMessage(
          "Le notifiche sono bloccate nel browser. Abilitale dalle impostazioni del sito.",
        );
        return;
      }

      const settings = await saveSubscription(reminderHour);
      setReminderHour(settings.reminder_hour);
      setEnabled(true);
      setJustEnabled(true);
      setMessage(null);

      window.setTimeout(() => {
        setJustEnabled(false);
        setSettingsOpen(false);
      }, 1600);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Non è stato possibile attivare le notifiche.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function saveReminderHour() {
    if (!enabled || busy) {
      return;
    }

    setBusy(true);
    setMessage(null);

    try {
      const settings = await saveSubscription(reminderHour);
      setReminderHour(settings.reminder_hour);
      setMessage(`Orario salvato: ${hourLabel(settings.reminder_hour)}.`);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Non è stato possibile salvare l'orario.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function disableNotifications() {
    if (!browserSupportsPush() || busy) {
      return;
    }

    setBusy(true);
    setMessage(null);

    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();

      if (subscription) {
        await unsubscribeFromTrainingNotifications(
          accessToken,
          subscription.endpoint,
        );
        await subscription.unsubscribe();
      }

      setEnabled(false);
      setSettingsOpen(true);
      setMessage("Promemoria disattivati su questo dispositivo.");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Non è stato possibile disattivare le notifiche.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (enabled && !settingsOpen) {
    return (
      <section className={`${styles.card} ${styles.compactCard}`}>
        <button
          type="button"
          className={styles.compactButton}
          onClick={() => setSettingsOpen(true)}
        >
          <span className={styles.compactIcon} aria-hidden="true">🔔</span>
          <span className={styles.compactCopy}>
            <strong>Notifiche attive</strong>
            <small>{hourLabel(reminderHour)} · Modifica</small>
          </span>
        </button>
      </section>
    );
  }

  return (
    <section className={styles.card}>
      <div className={styles.copy}>
        <div className={styles.titleRow}>
          <span className={styles.icon} aria-hidden="true">🔔</span>
          <div>
            <strong>
              {justEnabled ? "Notifiche attive ✓" : "Promemoria allenamento"}
            </strong>
            <span>
              Una notifica nei giorni in cui hai un allenamento pianificato.
            </span>
          </div>
        </div>

        <label className={styles.timeRow}>
          <span>Orario</span>
          <select
            value={reminderHour}
            disabled={!supported || busy}
            onChange={(event) => setReminderHour(Number(event.target.value))}
          >
            {REMINDER_HOURS.map((hour) => (
              <option key={hour} value={hour}>
                {hourLabel(hour)}
              </option>
            ))}
          </select>
        </label>

        <small>
          {enabled
            ? `Attive · ${hourLabel(reminderHour)} · fuso orario del dispositivo`
            : supported
              ? "Scegli l'orario e attivale su questo dispositivo"
              : "Push non supportate in questo browser"}
        </small>

        {!supported && (
          <small>
            Su iPhone le notifiche web richiedono SanoSync installata nella schermata Home.
          </small>
        )}

        {message && (
          <small className={styles.message} role="status">
            {message}
          </small>
        )}
      </div>

      <div className={styles.actions}>
        {enabled ? (
          <>
            <button
              type="button"
              className={styles.enable}
              disabled={!supported || busy}
              onClick={() => void saveReminderHour()}
            >
              {busy ? "Attendi…" : "Salva orario"}
            </button>
            <button
              type="button"
              className={styles.disable}
              disabled={!supported || busy}
              onClick={() => void disableNotifications()}
            >
              Disattiva
            </button>
            <button
              type="button"
              className={styles.close}
              disabled={busy}
              onClick={() => setSettingsOpen(false)}
            >
              Chiudi
            </button>
          </>
        ) : (
          <button
            type="button"
            className={styles.enable}
            disabled={!supported || busy}
            onClick={() => void enableNotifications()}
          >
            {busy ? "Attendi…" : "Attiva notifiche"}
          </button>
        )}
      </div>
    </section>
  );
}
