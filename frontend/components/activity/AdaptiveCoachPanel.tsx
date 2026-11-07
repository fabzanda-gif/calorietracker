"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import {
  applyCoachAdjustment,
  dismissCoachAdjustment,
  reconcileTrainingCoach,
  type CoachAdjustment,
  type CoachLoadEvent,
} from "@/lib/api/coach";

import styles from "./AdaptiveCoachPanel.module.css";


type Props = {
  refreshKey?: number;
  onChanged?: () => void | Promise<void>;
};


function todayIso(): string {
  const now = new Date();

  const year = now.getFullYear();
  const month = String(
    now.getMonth() + 1,
  ).padStart(2, "0");
  const day = String(
    now.getDate(),
  ).padStart(2, "0");

  return year + "-" + month + "-" + day;
}


function formatDate(value: string): string {
  return new Date(
    value + "T00:00:00",
  ).toLocaleDateString(
    "it-IT",
    {
      weekday: "short",
      day: "numeric",
      month: "short",
    },
  );
}


function actionLabel(
  item: CoachAdjustment,
): string {
  if (item.action === "reduce_load") {
    return "Carico protetto";
  }

  if (item.action === "reduce_volume") {
    return "Volume ridotto";
  }

  if (
    item.action === "reduce_running_load"
  ) {
    return "Corsa alleggerita";
  }

  return "Seduta da ripianificare";
}


function intensityLabel(
  value: CoachLoadEvent["intensity"],
): string {
  if (value === "high") {
    return "alto";
  }

  if (value === "moderate") {
    return "moderato";
  }

  return "basso";
}


export function AdaptiveCoachPanel({
  refreshKey = 0,
  onChanged,
}: Props) {
  const { accessToken } = useAuth();

  const [loading, setLoading] =
    useState(false);
  const [error, setError] =
    useState<string | null>(null);
  const [events, setEvents] =
    useState<CoachLoadEvent[]>([]);
  const [adjustments, setAdjustments] =
    useState<CoachAdjustment[]>([]);
  const [busyId, setBusyId] =
    useState<string | null>(null);

  const load = useCallback(
    async () => {
      if (!accessToken) {
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const response =
          await reconcileTrainingCoach(
            todayIso(),
            accessToken,
          );

        setEvents(
          response.load_events,
        );
        setAdjustments(
          response.adjustments,
        );
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Coach non disponibile.",
        );
      } finally {
        setLoading(false);
      }
    },
    [accessToken],
  );

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const proposed = useMemo(
    () =>
      adjustments.filter(
        (item) =>
          item.decision === "proposed",
      ),
    [adjustments],
  );

  const automatic = useMemo(
    () =>
      adjustments.filter(
        (item) =>
          item.decision ===
          "auto_applied",
      ),
    [adjustments],
  );

  async function apply(
    adjustment: CoachAdjustment,
  ) {
    if (!accessToken) {
      return;
    }

    setBusyId(adjustment.id);
    setError(null);

    try {
      const response =
        await applyCoachAdjustment(
          adjustment.id,
          accessToken,
        );

      setAdjustments((current) =>
        current.map((item) =>
          item.id === adjustment.id
            ? response.adjustment
            : item,
        ),
      );

      if (onChanged) {
        await onChanged();
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco ad applicare la proposta.",
      );
    } finally {
      setBusyId(null);
    }
  }

  async function dismiss(
    adjustment: CoachAdjustment,
  ) {
    if (!accessToken) {
      return;
    }

    setBusyId(adjustment.id);
    setError(null);

    try {
      const response =
        await dismissCoachAdjustment(
          adjustment.id,
          accessToken,
        );

      setAdjustments((current) =>
        current.map((item) =>
          item.id === adjustment.id
            ? response.adjustment
            : item,
        ),
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a mantenere il piano.",
      );
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className={styles.card}>
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>
            Coach adattivo
          </span>
          <h3>
            Carico condiviso palestra + corsa
          </h3>
          <p>
            Bilanciato · guarda le ultime 72 ore
            e protegge le prossime sedute.
          </p>
        </div>

        <button
          type="button"
          className={styles.refresh}
          disabled={loading}
          onClick={() => {
            void load();
          }}
        >
          {loading ? "Analizzo…" : "Aggiorna"}
        </button>
      </header>

      {error ? (
        <div className={styles.error}>
          {error}
        </div>
      ) : null}

      {events.length ? (
        <div className={styles.eventStrip}>
          {events.slice(0, 4).map(
            (event) => (
              <div
                key={
                  event.source_kind +
                  "-" +
                  event.source_id
                }
                className={styles.event}
              >
                <strong>
                  {event.title ??
                    "Allenamento"}
                </strong>
                <span>
                  {formatDate(event.date)}
                  {" · carico "}
                  {intensityLabel(
                    event.intensity,
                  )}
                </span>
              </div>
            ),
          )}
        </div>
      ) : null}

      {!loading &&
      proposed.length === 0 &&
      automatic.length === 0 ? (
        <div className={styles.ok}>
          <strong>
            Nessun conflitto rilevante.
          </strong>
          <span>
            Le prossime sedute possono
            proseguire come programmate.
          </span>
        </div>
      ) : null}

      {automatic.map((item) => (
        <article
          key={item.id}
          className={styles.autoCard}
        >
          <div>
            <span>
              Applicato automaticamente
            </span>
            <strong>{item.title}</strong>
            <p>{item.message}</p>
          </div>
          <div className={styles.target}>
            <strong>
              {actionLabel(item)}
            </strong>
            <span>
              {formatDate(
                item.target_date,
              )}
            </span>
          </div>
        </article>
      ))}

      {proposed.map((item) => (
        <article
          key={item.id}
          className={styles.proposal}
        >
          <div>
            <span>
              Proposta Coach ·{" "}
              {item.severity === "high"
                ? "priorità alta"
                : "priorità media"}
            </span>
            <strong>{item.title}</strong>
            <p>{item.message}</p>
            <small>
              Target ·{" "}
              {formatDate(
                item.target_date,
              )}
            </small>
          </div>

          <div className={styles.actions}>
            <button
              type="button"
              className={
                styles.primaryButton
              }
              disabled={
                busyId === item.id
              }
              onClick={() => {
                void apply(item);
              }}
            >
              {busyId === item.id
                ? "Applico…"
                : "Applica"}
            </button>
            <button
              type="button"
              className={
                styles.secondaryButton
              }
              disabled={
                busyId === item.id
              }
              onClick={() => {
                void dismiss(item);
              }}
            >
              Mantieni piano
            </button>
          </div>
        </article>
      ))}
    </section>
  );
}
