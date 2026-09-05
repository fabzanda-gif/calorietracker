"use client";

import {
  useEffect,
  useState,
} from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import {
  createRunningTrainingPlan,
  getTrainingPlans,
  type TrainingPlan,
} from "@/lib/api/activities";

import styles from "./RunningPlanBuilder.module.css";


function isoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(
    date.getMonth() + 1,
  ).padStart(2, "0");
  const day = String(
    date.getDate(),
  ).padStart(2, "0");

  return `${year}-${month}-${day}`;
}


function paceToSeconds(
  value: string,
): number | null {
  const match = value
    .trim()
    .match(/^(\d{1,2}):([0-5]\d)$/);

  if (!match) {
    return null;
  }

  return (
    Number(match[1]) * 60 +
    Number(match[2])
  );
}


function paceLabel(
  seconds: number,
): string {
  const minutes = Math.floor(
    seconds / 60,
  );
  const remainder =
    seconds % 60;

  return `${minutes}:${String(
    remainder,
  ).padStart(2, "0")}/km`;
}


export function RunningPlanBuilder({
  onCreated,
}: {
  onCreated?: () => void;
}) {
  const { accessToken } = useAuth();

  const [plans, setPlans] = useState<
    TrainingPlan[]
  >([]);

  const [currentDistance, setCurrentDistance] =
    useState("5");
  const [currentPace, setCurrentPace] =
    useState("6:00");

  const [targetDistance, setTargetDistance] =
    useState("21.1");
  const [targetPace, setTargetPace] =
    useState("5:00");

  const [sessionsPerWeek, setSessionsPerWeek] =
    useState("3");

  const [longRunWeekday, setLongRunWeekday] =
    useState("6");

  const [targetDate, setTargetDate] =
    useState(() => {
      const target = new Date();
      target.setMonth(
        target.getMonth() + 6,
      );
      return isoDate(target);
    });

  const [saving, setSaving] =
    useState(false);

  const [message, setMessage] =
    useState<string | null>(null);


  async function refreshPlans() {
    if (!accessToken) {
      return;
    }

    try {
      const response =
        await getTrainingPlans(
          accessToken,
        );

      setPlans(response.items);
    } catch {
      // The generic activity page remains usable
      // even if this optional block cannot load.
    }
  }


  useEffect(() => {
    void refreshPlans();
  }, [accessToken]);


  async function createPlan() {
    if (!accessToken) {
      return;
    }

    const currentPaceSeconds =
      paceToSeconds(currentPace);

    const targetPaceSeconds =
      paceToSeconds(targetPace);

    const currentDistanceKm =
      Number(currentDistance);

    const targetDistanceKm =
      Number(targetDistance);

    if (
      !currentPaceSeconds ||
      !targetPaceSeconds ||
      !currentDistanceKm ||
      !targetDistanceKm ||
      !targetDate
    ) {
      setMessage(
        "Controlla distanza, passo e data obiettivo.",
      );
      return;
    }

    const startDate =
      isoDate(new Date());

    const start =
      new Date(`${startDate}T00:00:00`);

    const target =
      new Date(`${targetDate}T00:00:00`);

    const weeks =
      (
        target.getTime() -
        start.getTime()
      ) /
      (7 * 24 * 60 * 60 * 1000);

    if (weeks < 8) {
      setMessage(
        "Servono almeno 8 settimane tra oggi e l’obiettivo.",
      );
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      const response =
        await createRunningTrainingPlan(
          {
            start_date: startDate,
            target_date: targetDate,
            current_distance_meters:
              currentDistanceKm * 1000,
            current_pace_seconds_per_km:
              currentPaceSeconds,
            target_distance_meters:
              targetDistanceKm * 1000,
            target_pace_seconds_per_km:
              targetPaceSeconds,
            sessions_per_week:
              Number(sessionsPerWeek),
            long_run_weekday:
              Number(longRunWeekday),
          },
          accessToken,
        );

      setMessage(
        `Piano creato: ${response.plan.total_weeks} settimane, ${response.session_count} sessioni.`,
      );

      await refreshPlans();

      onCreated?.();
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Non riesco a creare il piano.",
      );
    } finally {
      setSaving(false);
    }
  }


  const activePlan =
    plans.find(
      (item) =>
        item.status === "active" &&
        item.sport === "running",
    ) ?? null;


  return (
    <section className={styles.wrapper}>
      <div className={styles.heading}>
        <div>
          <p>RUNNING PLAN</p>
          <h2>
            Da dove parti. Dove vuoi arrivare.
          </h2>
          <span>
            SanoSync costruisce una progressione
            settimanale e la trasforma in attività
            pianificate.
          </span>
        </div>

        {activePlan ? (
          <div className={styles.activePlan}>
            <small>Piano attivo</small>
            <strong>
              {(
                activePlan.target_distance_meters /
                1000
              ).toLocaleString(
                "it-IT",
                {
                  maximumFractionDigits: 1,
                },
              )}{" "}
              km
            </strong>
            <span>
              {paceLabel(
                activePlan.target_pace_seconds_per_km,
              )}{" "}
              · {activePlan.total_weeks} settimane
            </span>
          </div>
        ) : null}
      </div>

      <div className={styles.columns}>
        <div className={styles.stateCard}>
          <div className={styles.cardTitle}>
            <span>01</span>
            <div>
              <strong>Stato iniziale</strong>
              <small>
                Cosa riesci a correre oggi.
              </small>
            </div>
          </div>

          <div className={styles.fields}>
            <label>
              Distanza attuale
              <div className={styles.unitInput}>
                <input
                  type="number"
                  min="1"
                  step="0.1"
                  value={currentDistance}
                  onChange={(event) =>
                    setCurrentDistance(
                      event.target.value,
                    )
                  }
                />
                <span>km</span>
              </div>
            </label>

            <label>
              Passo attuale
              <div className={styles.unitInput}>
                <input
                  value={currentPace}
                  placeholder="6:00"
                  onChange={(event) =>
                    setCurrentPace(
                      event.target.value,
                    )
                  }
                />
                <span>min/km</span>
              </div>
            </label>
          </div>
        </div>

        <div className={styles.goalCard}>
          <div className={styles.cardTitle}>
            <span>02</span>
            <div>
              <strong>Obiettivo</strong>
              <small>
                Dove vuoi arrivare.
              </small>
            </div>
          </div>

          <div className={styles.fields}>
            <label>
              Distanza obiettivo
              <div className={styles.unitInput}>
                <input
                  type="number"
                  min="1"
                  step="0.1"
                  value={targetDistance}
                  onChange={(event) =>
                    setTargetDistance(
                      event.target.value,
                    )
                  }
                />
                <span>km</span>
              </div>
            </label>

            <label>
              Passo obiettivo
              <div className={styles.unitInput}>
                <input
                  value={targetPace}
                  placeholder="5:00"
                  onChange={(event) =>
                    setTargetPace(
                      event.target.value,
                    )
                  }
                />
                <span>min/km</span>
              </div>
            </label>

            <label>
              Data obiettivo
              <input
                type="date"
                value={targetDate}
                onChange={(event) =>
                  setTargetDate(
                    event.target.value,
                  )
                }
              />
            </label>
          </div>
        </div>
      </div>

      <div className={styles.preferences}>
        <label>
          Corse a settimana
          <select
            value={sessionsPerWeek}
            onChange={(event) =>
              setSessionsPerWeek(
                event.target.value,
              )
            }
          >
            <option value="2">2</option>
            <option value="3">3</option>
            <option value="4">4</option>
            <option value="5">5</option>
          </select>
        </label>

        <label>
          Giorno del lungo
          <select
            value={longRunWeekday}
            onChange={(event) =>
              setLongRunWeekday(
                event.target.value,
              )
            }
          >
            <option value="0">Lunedì</option>
            <option value="1">Martedì</option>
            <option value="2">Mercoledì</option>
            <option value="3">Giovedì</option>
            <option value="4">Venerdì</option>
            <option value="5">Sabato</option>
            <option value="6">Domenica</option>
          </select>
        </label>

        <button
          type="button"
          disabled={saving}
          onClick={() => {
            void createPlan();
          }}
        >
          {saving
            ? "Costruisco il piano…"
            : "Crea piano di corsa"}
        </button>
      </div>

      {message ? (
        <p className={styles.message}>
          {message}
        </p>
      ) : null}
    </section>
  );
}
