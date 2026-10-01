"use client";

import { useEffect, useState } from "react";

import {
  getPushPublicKey,
  subscribeToTrainingNotifications,
  unsubscribeFromTrainingNotifications,
} from "@/lib/api/notifications";

import styles from "./TrainingNotificationsCard.module.css";

interface Props {
  accessToken: string;
}

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

export function TrainingNotificationsCard({ accessToken }: Props) {
  const [supported, setSupported] = useState(true);
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

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

        if (!cancelled) {
          setEnabled(Boolean(subscription) && Notification.permission === "granted");
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
  }, []);

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

      await subscribeToTrainingNotifications(accessToken, {
        endpoint: subscription.endpoint,
        keys: { p256dh, auth },
        timezone:
          Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      });

      setEnabled(true);
      setMessage("Attive: riceverai il promemoria la mattina dei giorni di allenamento.");
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
      setMessage("Promemoria allenamento disattivati su questo dispositivo.");
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

  return (
    <section className={styles.card}>
      <div className={styles.copy}>
        <div className={styles.titleRow}>
          <span className={styles.icon} aria-hidden="true">🔔</span>
          <div>
            <strong>Promemoria allenamento</strong>
            <span>Una notifica la mattina quando hai un allenamento pianificato.</span>
          </div>
        </div>

        <small>
          {enabled
            ? "Attive · ore 08:00 · fuso orario del dispositivo"
            : supported
              ? "Disattivate su questo dispositivo"
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

      <button
        type="button"
        className={enabled ? styles.disable : styles.enable}
        disabled={!supported || busy}
        onClick={() => {
          void (enabled ? disableNotifications() : enableNotifications());
        }}
      >
        {busy
          ? "Attendi…"
          : enabled
            ? "Disattiva"
            : "Attiva notifiche"}
      </button>
    </section>
  );
}
