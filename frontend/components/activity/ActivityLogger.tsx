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
import { useI18n } from "@/components/i18n/I18nProvider";

import styles from "./ActivityLogger.module.css";

type ActivityLoggerProps = {
  date: string;
  accessToken?: string | null;
  onSaved: (savedDate?: string) => void | Promise<void>;
  showMovement?: boolean;
  compact?: boolean;
};

const ACTIVITY_OPTIONS = [
  // Preferite / frequenti
  {
    value: "Padel",
    label: "🎾 Padel",
    kcalPerHour: 500,
    defaultMinutes: 90,
  },
  {
    value: "Bicicletta",
    label: "🚴 Bici",
    kcalPerHour: 420,
    defaultMinutes: 45,
  },
  {
    value: "Bici elettrica",
    label: "⚡ E-bike",
    kcalPerHour: 250,
    defaultMinutes: 45,
  },

  // Cardio
  {
    value: "Corsa",
    label: "🏃 Corsa",
    kcalPerHour: 650,
    defaultMinutes: 45,
  },
  {
    value: "Camminata",
    label: "🚶 Camminata",
    kcalPerHour: 280,
    defaultMinutes: 60,
  },
  {
    value: "Nuoto",
    label: "🏊 Nuoto",
    kcalPerHour: 520,
    defaultMinutes: 45,
  },
  {
    value: "Ellittica",
    label: "🏃 Ellittica",
    kcalPerHour: 430,
    defaultMinutes: 45,
  },
  {
    value: "Canottaggio",
    label: "🚣 Canottaggio",
    kcalPerHour: 500,
    defaultMinutes: 45,
  },

  // Forza
  {
    value: "Palestra",
    label: "🏋️ Palestra / pesi",
    kcalPerHour: 350,
    defaultMinutes: 60,
  },
  {
    value: "Circuit training",
    label: "💪 Circuit training",
    kcalPerHour: 500,
    defaultMinutes: 45,
  },

  // Sport
  {
    value: "Tennis",
    label: "🎾 Tennis",
    kcalPerHour: 480,
    defaultMinutes: 60,
  },
  {
    value: "Calcio",
    label: "⚽ Calcio",
    kcalPerHour: 600,
    defaultMinutes: 60,
  },
  {
    value: "Basket",
    label: "🏀 Basket",
    kcalPerHour: 550,
    defaultMinutes: 60,
  },

  // Outdoor / mobilità
  {
    value: "Escursionismo",
    label: "🥾 Escursionismo",
    kcalPerHour: 450,
    defaultMinutes: 90,
  },
  {
    value: "Yoga",
    label: "🧘 Yoga",
    kcalPerHour: 200,
    defaultMinutes: 60,
  },
  {
    value: "Pilates",
    label: "🧘 Pilates",
    kcalPerHour: 220,
    defaultMinutes: 60,
  },

  // Fallback
  {
    value: "Altro",
    label: "➕ Altra attività",
    kcalPerHour: 300,
    defaultMinutes: 60,
  },
];

const LOGGER_COPY = {
  it: { extra: "Allenamento extra", logActivity: "Registra attività", activityDate: "Data dell’attività", pastHint: "Puoi registrare anche un’attività passata.", activity: "Attività", minutes: "Durata in minuti", burned: "Calorie bruciate", suggestion: "Suggerimento", editable: "modificabile", logging: "Registrazione…", logWorkout: "Registra allenamento", dailyMovement: "Movimento quotidiano", dailySteps: "Passi della giornata", totalDetected: "Passi totali rilevati", stepsExample: "Es. 12000", updating: "Aggiornamento…", updateSteps: "Aggiorna passi", totalSteps: "Passi totali", included: "Inclusi negli allenamenti", netSteps: "Passi netti quotidiani", invalidName: "Inserisci il nome dell’attività.", invalidDuration: "Inserisci una durata valida.", invalidCalories: "Inserisci calorie valide.", saveFailed: "Non riesco a registrare l’attività.", invalidSteps: "Inserisci un numero di passi valido.", stepsUpdated: "Passi aggiornati.", stepsFailed: "Non riesco ad aggiornare i passi.", saved: "registrato.", labels: ["🎾 Padel", "🚴 Bici", "⚡ E-bike", "🏃 Corsa", "🚶 Camminata", "🏊 Nuoto", "🏃 Ellittica", "🚣 Canottaggio", "🏋️ Palestra / pesi", "💪 Circuit training", "🎾 Tennis", "⚽ Calcio", "🏀 Basket", "🥾 Escursionismo", "🧘 Yoga", "🧘 Pilates", "➕ Altra attività"] },
  en: { extra: "Extra workout", logActivity: "Log activity", activityDate: "Activity date", pastHint: "You can also log a past activity.", activity: "Activity", minutes: "Duration in minutes", burned: "Calories burned", suggestion: "Suggestion", editable: "editable", logging: "Logging…", logWorkout: "Log workout", dailyMovement: "Daily movement", dailySteps: "Daily steps", totalDetected: "Total steps detected", stepsExample: "E.g. 12000", updating: "Updating…", updateSteps: "Update steps", totalSteps: "Total steps", included: "Included in workouts", netSteps: "Net daily steps", invalidName: "Enter an activity name.", invalidDuration: "Enter a valid duration.", invalidCalories: "Enter valid calories.", saveFailed: "Unable to log the activity.", invalidSteps: "Enter a valid number of steps.", stepsUpdated: "Steps updated.", stepsFailed: "Unable to update steps.", saved: "logged.", labels: ["🎾 Padel", "🚴 Cycling", "⚡ E-bike", "🏃 Running", "🚶 Walking", "🏊 Swimming", "🏃 Elliptical", "🚣 Rowing", "🏋️ Gym / weights", "💪 Circuit training", "🎾 Tennis", "⚽ Football", "🏀 Basketball", "🥾 Hiking", "🧘 Yoga", "🧘 Pilates", "➕ Other activity"] },
  nl: { extra: "Extra training", logActivity: "Activiteit registreren", activityDate: "Datum van activiteit", pastHint: "Je kunt ook een eerdere activiteit registreren.", activity: "Activiteit", minutes: "Duur in minuten", burned: "Verbrande calorieën", suggestion: "Suggestie", editable: "aanpasbaar", logging: "Registreren…", logWorkout: "Training registreren", dailyMovement: "Dagelijkse beweging", dailySteps: "Stappen van vandaag", totalDetected: "Totaal gedetecteerde stappen", stepsExample: "Bijv. 12000", updating: "Bijwerken…", updateSteps: "Stappen bijwerken", totalSteps: "Totaal stappen", included: "Inbegrepen in trainingen", netSteps: "Netto dagelijkse stappen", invalidName: "Voer een activiteit in.", invalidDuration: "Voer een geldige duur in.", invalidCalories: "Voer geldige calorieën in.", saveFailed: "De activiteit kon niet worden geregistreerd.", invalidSteps: "Voer een geldig aantal stappen in.", stepsUpdated: "Stappen bijgewerkt.", stepsFailed: "De stappen konden niet worden bijgewerkt.", saved: "geregistreerd.", labels: ["🎾 Padel", "🚴 Fietsen", "⚡ E-bike", "🏃 Hardlopen", "🚶 Wandelen", "🏊 Zwemmen", "🏃 Crosstrainer", "🚣 Roeien", "🏋️ Sportschool / gewichten", "💪 Circuittraining", "🎾 Tennis", "⚽ Voetbal", "🏀 Basketbal", "🥾 Hiken", "🧘 Yoga", "🧘 Pilates", "➕ Andere activiteit"] },
  fr: { extra: "Entraînement supplémentaire", logActivity: "Enregistrer une activité", activityDate: "Date de l’activité", pastHint: "Vous pouvez aussi enregistrer une activité passée.", activity: "Activité", minutes: "Durée en minutes", burned: "Calories brûlées", suggestion: "Suggestion", editable: "modifiable", logging: "Enregistrement…", logWorkout: "Enregistrer l’entraînement", dailyMovement: "Mouvement quotidien", dailySteps: "Pas de la journée", totalDetected: "Nombre total de pas détectés", stepsExample: "Ex. 12000", updating: "Mise à jour…", updateSteps: "Mettre à jour les pas", totalSteps: "Nombre total de pas", included: "Inclus dans les entraînements", netSteps: "Pas quotidiens nets", invalidName: "Saisissez le nom de l’activité.", invalidDuration: "Saisissez une durée valide.", invalidCalories: "Saisissez des calories valides.", saveFailed: "Impossible d’enregistrer l’activité.", invalidSteps: "Saisissez un nombre de pas valide.", stepsUpdated: "Pas mis à jour.", stepsFailed: "Impossible de mettre à jour les pas.", saved: "enregistré.", labels: ["🎾 Padel", "🚴 Vélo", "⚡ Vélo électrique", "🏃 Course", "🚶 Marche", "🏊 Natation", "🏃 Vélo elliptique", "🚣 Aviron", "🏋️ Salle / musculation", "💪 Circuit training", "🎾 Tennis", "⚽ Football", "🏀 Basket", "🥾 Randonnée", "🧘 Yoga", "🧘 Pilates", "➕ Autre activité"] },
} as const;

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

function formatNumber(value: number, locale: string): string {
  return Math.round(value).toLocaleString(
    locale,
  );
}

export function ActivityLogger({
  date,
  accessToken,
  onSaved,
  showMovement = false,
  compact = false,
}: ActivityLoggerProps) {
  const { locale } = useI18n();
  const copy = LOGGER_COPY[locale];
  const numberLocale = locale === "it" ? "it-IT" : locale === "nl" ? "nl-NL" : locale === "fr" ? "fr-FR" : "en-GB";
  const [logDate, setLogDate] = useState(date);
  const [activityType, setActivityType] =
    useState("Padel");
  const [durationMinutes, setDurationMinutes] =
    useState("90");
  const [calories, setCalories] =
    useState("750");
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
    setLogDate(date);
  }, [date]);

  useEffect(() => {
    if (!caloriesEdited) {
      setCalories(String(automaticCalories));
    }
  }, [automaticCalories, caloriesEdited]);

  useEffect(() => {
    if (
      !showMovement ||
      !accessToken ||
      !logDate
    ) {
      return;
    }

    let active = true;

    async function loadMovement() {
      setLoadingMovement(true);

      try {
        const response =
          await getActivityMovement(
            logDate,
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
  }, [accessToken, logDate, showMovement]);

  async function saveActivity() {
    if (!accessToken) {
      return;
    }

    const minutes = Number(durationMinutes);
    const burned = Number(calories);
    const name = activityType;

    if (!name) {
      setError(copy.invalidName);
      return;
    }

    if (
      !Number.isFinite(minutes) ||
      minutes <= 0
    ) {
      setError(copy.invalidDuration);
      return;
    }

    if (
      !Number.isFinite(burned) ||
      burned < 0
    ) {
      setError(copy.invalidCalories);
      return;
    }

    setSavingActivity(true);
    setError(null);
    setMessage(null);

    try {
      const response = await createActivity(
        {
          date: logDate,
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

      setMessage(`${copy.labels[ACTIVITY_OPTIONS.findIndex((option) => option.value === name)]?.replace(/^\S+\s/, "") ?? name} ${copy.saved}`);
      await onSaved(logDate);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : copy.saveFailed,
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
        copy.invalidSteps,
      );
      return;
    }

    setSavingSteps(true);
    setError(null);
    setMessage(null);

    try {
      const response = await updateDailyLog(
        accessToken,
        logDate,
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
            logDate,
            accessToken,
          ),
        );
      }

      setMessage(copy.stepsUpdated);
      await onSaved(logDate);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : copy.stepsFailed,
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
            <span>{copy.extra}</span>
            <h3>{copy.logActivity}</h3>
          </div>
        </div>

        <label className={styles.dateInput}>
          <span>{copy.activityDate}</span>
          <input
            type="date"
            value={logDate}
            onChange={(event) => {
              setLogDate(event.target.value);
              setMessage(null);
              setError(null);
            }}
          />
          <small>
            {copy.pastHint}
          </small>
        </label>

        <div className={styles.formGrid}>
          <label>
            <span>{copy.activity}</span>
            <select
              value={activityType}
              onChange={(event) => {
                const nextType = event.target.value;
                const option = ACTIVITY_OPTIONS.find((item) => item.value === nextType);
                setActivityType(nextType);
                setDurationMinutes(String(option?.defaultMinutes ?? 60));
                setCaloriesEdited(false);
                setError(null);
              }}
            >
              {ACTIVITY_OPTIONS.map((option, index) => (
                <option
                  key={option.value}
                  value={option.value}
                >
                  {copy.labels[index]}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>{copy.minutes}</span>
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
            <span>{copy.burned}</span>
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
              {copy.suggestion}: {automaticCalories} kcal, {copy.editable}.
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
            ? copy.logging
            : copy.logWorkout}
        </button>
      </section>

      {showMovement ? (
        <section className={styles.movementPanel}>
          <div className={styles.panelHeading}>
            <div>
              <span>{copy.dailyMovement}</span>
              <h3>{copy.dailySteps}</h3>
            </div>
          </div>

          <label className={styles.stepsInput}>
            <span>{copy.totalDetected}</span>
            <input
              type="number"
              min="0"
              step="100"
              value={steps}
              placeholder={copy.stepsExample}
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
              ? copy.updating
              : copy.updateSteps}
          </button>

          {movement ? (
            <div className={styles.movementStats}>
              <div>
                <span>{copy.totalSteps}</span>
                <strong>
                  {formatNumber(
                    movement.total_steps, numberLocale,
                  )}
                </strong>
              </div>

              <div>
                <span>{copy.included}</span>
                <strong>
                  −
                  {formatNumber(
                    movement.applied_step_offset, numberLocale,
                  )}
                </strong>
              </div>

              <div className={styles.netSteps}>
                <span>{copy.netSteps}</span>
                <strong>
                  {formatNumber(
                    movement.net_daily_steps, numberLocale,
                  )}
                </strong>
                <small>
                  {formatNumber(
                    movement.step_calories, numberLocale,
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
