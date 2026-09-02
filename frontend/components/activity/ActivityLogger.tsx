"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  createActivity,
  getActivityMovement,
  type ActivityMovementSummary,
} from "@/lib/api/activities";
import { updateDailyLog } from "@/lib/api/day";

import styles from "./ActivityLogger.module.css";

type ActivityLoggerProps = {
  date: string;
  accessToken?: string | null;
  onSaved: () => void | Promise<void>;
  showMovement?: boolean;
  compact?: boolean;
};

const ACTIVITY_OPTIONS = [
  {
    value: "Padel",
    label: "🎾 Padel",
    kcalPerHour: 500,
  },
  {
    value: "Corsa",
    label: "🏃 Corsa",
    kcalPerHour: 650,
  },
  {
    value: "Tennis",
    label: "🎾 Tennis",
    kcalPerHour: 480,
  },
  {
    value: "Palestra",
    label: "🏋️ Palestra",
    kcalPerHour: 350,
  },
  {
    value: "Calcio",
    label: "⚽ Calcio",
    kcalPerHour: 600,
  },
  {
    value: "Nuoto",
    label: "🏊 Nuoto",
    kcalPerHour: 500,
  },
  {
    value: "Escursione",
    label: "🥾 Escursione",
    kcalPerHour: 400,
  },
  {
    value: "Camminata",
    label: "🚶 Camminata",
    kcalPerHour: 280,
  },
  {
    value: "Altro",
    label: "🔥 Altro",
    kcalPerHour: 300,
  },
];

function suggestedCalories(
  activityType: string,
  minutes: number,
): number {
  const option = ACTIVITY_OPTIONS.find(
    (item) => item.value === activityType,
  );

  return Math.round(
    Math.max(0, minutes) *
      (option?.kcalPerHour ?? 300) /
      60,
  );
}

function formatNumber(value: number): string {
  return Math.round(value).toLocaleString(
    "it-IT",
  );
}

export function ActivityLogger({
  date,
  accessToken,
  onSaved,
  showMovement = false,
  compact = false,
}: ActivityLoggerProps) {
  const [activityType, setActivityType] =
    useState("Padel");
  const [customName, setCustomName] =
    useState("");
  const [durationMinutes, setDurationMinutes] =
    useState("60");
  const [calories, setCalories] =
    useState("500");
  const [caloriesEdited, setCaloriesEdited] =
    useState(false);
  const [steps, setSteps] = useState("");
  const [movement, setMovement] =
    useState<ActivityMovementSummary | null>(
      null,
    );
  const [savingActivity, setSavingActivity] =
    useState(false);
  const [savingSteps, setSavingSteps] =
    useState(false);
  const [loadingMovement, setLoadingMovement] =
    useState(false);
  const [message, setMessage] =
    useState<string | null>(null);
  const [error, setError] =
    useState<string | null>(null);

  const duration = Number(durationMinutes);

  const automaticCalories = useMemo(
    () =>
      suggestedCalories(
        activityType,
        Number.isFinite(duration)
          ? duration
          : 0,
      ),
    [activityType, duration],
  );

  useEffect(() => {
    if (!caloriesEdited) {
      setCalories(String(automaticCalories));
    }
  }, [automaticCalories, caloriesEdited]);

  useEffect(() => {
    if (
      !showMovement ||
      !accessToken ||
      !date
    ) {
      return;
    }

    let active = true;

    async function loadMovement() {
      setLoadingMovement(true);

      try {
        const response =
          await getActivityMovement(
            date,
            accessToken,
          );

        if (active) {
          setMovement(response);
          setSteps(
            String(response.total_steps),
          );
        }
      } catch {
        if (active) {
          setMovement(null);
        }
      } finally {
        if (active) {
          setLoadingMovement(false);
        }
      }
    }

    void loadMovement();

    return () => {
      active = false;
    };
  }, [accessToken, date, showMovement]);

  async function saveActivity() {
    if (!accessToken) {
      return;
    }

    const minutes = Number(durationMinutes);
    const burned = Number(calories);
    const name =
      activityType === "Altro"
        ? customName.trim()
        : activityType;

    if (!name) {
      setError("Inserisci il nome dell’attività.");
      return;
    }

    if (
      !Number.isFinite(minutes) ||
      minutes <= 0
    ) {
      setError("Inserisci una durata valida.");
      return;
    }

    if (
      !Number.isFinite(burned) ||
      burned < 0
    ) {
      setError("Inserisci calorie valide.");
      return;
    }

    setSavingActivity(true);
    setError(null);
    setMessage(null);

    try {
      const response = await createActivity(
        {
          date,
          activity_name: name,
          activity_type: activityType,
          duration_seconds:
            Math.round(minutes * 60),
          burned_calories:
            Math.round(burned),
        },
        accessToken,
      );

      if (response.movement) {
        setMovement(response.movement);
      }

      setMessage(`${name} registrato.`);
      setCustomName("");
      await onSaved();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a registrare l’attività.",
      );
    } finally {
      setSavingActivity(false);
    }
  }

  async function saveSteps() {
    if (!accessToken) {
      return;
    }

    const totalSteps = Number(steps);

    if (
      !Number.isFinite(totalSteps) ||
      totalSteps < 0
    ) {
      setError(
        "Inserisci un numero di passi valido.",
      );
      return;
    }

    setSavingSteps(true);
    setError(null);
    setMessage(null);

    try {
      const response = await updateDailyLog(
        accessToken,
        date,
        {
          steps: Math.round(totalSteps),
        },
      );

      const nextMovement =
        response.movement as
          | ActivityMovementSummary
          | null
          | undefined;

      if (nextMovement) {
        setMovement(nextMovement);
      } else {
        setMovement(
          await getActivityMovement(
            date,
            accessToken,
          ),
        );
      }

      setMessage("Passi aggiornati.");
      await onSaved();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco ad aggiornare i passi.",
      );
    } finally {
      setSavingSteps(false);
    }
  }

  return (
    <div
      className={`${styles.logger} ${
        compact ? styles.compact : ""
      }`}
    >
      <section className={styles.activityPanel}>
        <div className={styles.panelHeading}>
          <div>
            <span>Allenamento extra</span>
            <h3>Registra attività</h3>
          </div>
        </div>

        <div className={styles.formGrid}>
          <label>
            <span>Attività</span>
            <select
              value={activityType}
              onChange={(event) => {
                setActivityType(
                  event.target.value,
                );
                setCaloriesEdited(false);
                setError(null);
              }}
            >
              {ACTIVITY_OPTIONS.map((option) => (
                <option
                  key={option.value}
                  value={option.value}
                >
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          {activityType === "Altro" ? (
            <label>
              <span>Nome attività</span>
              <input
                value={customName}
                placeholder="Es. Arrampicata"
                onChange={(event) =>
                  setCustomName(
                    event.target.value,
                  )
                }
              />
            </label>
          ) : null}

          <label>
            <span>Durata in minuti</span>
            <input
              type="number"
              min="1"
              step="5"
              value={durationMinutes}
              onChange={(event) =>
                setDurationMinutes(
                  event.target.value,
                )
              }
            />
          </label>

          <label>
            <span>Calorie bruciate</span>
            <input
              type="number"
              min="0"
              value={calories}
              onChange={(event) => {
                setCalories(event.target.value);
                setCaloriesEdited(true);
              }}
            />
            <small>
              Suggerimento: {automaticCalories} kcal,
              modificabile.
            </small>
          </label>
        </div>

        <button
          type="button"
          className={styles.saveButton}
          disabled={savingActivity}
          onClick={() => {
            void saveActivity();
          }}
        >
          {savingActivity
            ? "Registrazione…"
            : "Registra allenamento"}
        </button>
      </section>

      {showMovement ? (
        <section className={styles.movementPanel}>
          <div className={styles.panelHeading}>
            <div>
              <span>Movimento quotidiano</span>
              <h3>Passi della giornata</h3>
            </div>
          </div>

          <label className={styles.stepsInput}>
            <span>Passi totali rilevati</span>
            <input
              type="number"
              min="0"
              step="100"
              value={steps}
              placeholder="Es. 12000"
              onChange={(event) =>
                setSteps(event.target.value)
              }
            />
          </label>

          <button
            type="button"
            className={styles.secondaryButton}
            disabled={
              savingSteps || loadingMovement
            }
            onClick={() => {
              void saveSteps();
            }}
          >
            {savingSteps
              ? "Aggiornamento…"
              : "Aggiorna passi"}
          </button>

          {movement ? (
            <div className={styles.movementStats}>
              <div>
                <span>Passi totali</span>
                <strong>
                  {formatNumber(
                    movement.total_steps,
                  )}
                </strong>
              </div>

              <div>
                <span>Inclusi negli allenamenti</span>
                <strong>
                  −
                  {formatNumber(
                    movement.applied_step_offset,
                  )}
                </strong>
              </div>

              <div className={styles.netSteps}>
                <span>Passi netti quotidiani</span>
                <strong>
                  {formatNumber(
                    movement.net_daily_steps,
                  )}
                </strong>
                <small>
                  {formatNumber(
                    movement.step_calories,
                  )}{" "}
                  kcal
                </small>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {message ? (
        <p className={styles.success}>
          {message}
        </p>
      ) : null}

      {error ? (
        <p className={styles.error}>{error}</p>
      ) : null}
    </div>
  );
}
