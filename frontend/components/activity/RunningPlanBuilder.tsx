"use client";

import {
  useEffect,
  useState,
} from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import {
  createRunningTrainingPlan,
  deleteTrainingPlan,
  previewRunningTrainingPlan,
  getTrainingPlans,
  type PlannedActivity,
  type RunningTrainingPlanInput,
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

  const [deletingPlan, setDeletingPlan] =
    useState(false);

  const [message, setMessage] =
    useState<string | null>(null);

  const [previewSessions, setPreviewSessions] =
    useState<PlannedActivity[]>([]);

  const [previewWeeks, setPreviewWeeks] =
    useState<number | null>(null);

  const [previewInput, setPreviewInput] =
    useState<RunningTrainingPlanInput | null>(
      null,
    );


  function clearPreview() {
    setPreviewSessions([]);
    setPreviewWeeks(null);
    setPreviewInput(null);
  }


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


  function buildPlanInput():
    | RunningTrainingPlanInput
    | null {
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
      return null;
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
      return null;
    }

    return {
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
    };
  }


  async function generatePreview() {
    if (!accessToken) {
      return;
    }

    const input = buildPlanInput();

    if (!input) {
      return;
    }

    setSaving(true);
    setMessage(null);
    clearPreview();

    try {
      const response =
        await previewRunningTrainingPlan(
          input,
          accessToken,
        );

      setPreviewInput(input);
      setPreviewSessions(
        response.sessions,
      );
      setPreviewWeeks(
        response.total_weeks,
      );

      setMessage(
        "Anteprima pronta. Nulla è stato ancora aggiunto al calendario.",
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Non riesco a generare l’anteprima.",
      );
    } finally {
      setSaving(false);
    }
  }


  async function removeActivePlan(
    plan: TrainingPlan,
  ) {
    if (!accessToken) {
      return;
    }

    const confirmed =
      window.confirm(
        "Eliminare questo piano e tutte le sessioni collegate dal calendario?",
      );

    if (!confirmed) {
      return;
    }

    setDeletingPlan(true);
    setMessage(null);

    try {
      await deleteTrainingPlan(
        plan.id,
        accessToken,
      );

      clearPreview();

      await refreshPlans();

      setMessage(
        "Piano eliminato insieme alle sessioni collegate.",
      );

      onCreated?.();

    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Non riesco a eliminare il piano.",
      );
    } finally {
      setDeletingPlan(false);
    }
  }


  async function confirmPlan() {
    if (
      !accessToken ||
      !previewInput
    ) {
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      const response =
        await createRunningTrainingPlan(
          previewInput,
          accessToken,
          {
            replaceActive:
              Boolean(activePlan),
          },
        );

      const replaced =
        Boolean(
          response.replaced_plan_ids?.length,
        );

      setMessage(
        replaced
          ? `Piano sostituito: ${response.plan.total_weeks} settimane, ${response.session_count} nuove sessioni aggiunte al calendario.`
          : `Piano confermato: ${response.plan.total_weeks} settimane, ${response.session_count} sessioni aggiunte al calendario.`,
      );

      clearPreview();

      await refreshPlans();

      onCreated?.();
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Non riesco a salvare il piano.",
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

            <button
              type="button"
              className={styles.deletePlanButton}
              disabled={deletingPlan}
              onClick={() => {
                void removeActivePlan(
                  activePlan,
                );
              }}
            >
              {deletingPlan
                ? "Elimino…"
                : "Elimina piano"}
            </button>
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
                  onChange={(event) => {
                    setCurrentDistance(
                      event.target.value,
                    );
                    clearPreview();
                  }}
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
                  onChange={(event) => {
                    setCurrentPace(
                      event.target.value,
                    );
                    clearPreview();
                  }}
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
                  onChange={(event) => {
                    setTargetDistance(
                      event.target.value,
                    );
                    clearPreview();
                  }}
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
                  onChange={(event) => {
                    setTargetPace(
                      event.target.value,
                    );
                    clearPreview();
                  }}
                />
                <span>min/km</span>
              </div>
            </label>

            <label>
              Data obiettivo
              <input
                type="date"
                value={targetDate}
                onChange={(event) => {
                  setTargetDate(
                    event.target.value,
                  );
                  clearPreview();
                }}
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
            onChange={(event) => {
              setSessionsPerWeek(
                event.target.value,
              );
              clearPreview();
            }}
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
            onChange={(event) => {
              setLongRunWeekday(
                event.target.value,
              );
              clearPreview();
            }}
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
            void generatePreview();
          }}
        >
          {saving
            ? "Genero l’anteprima…"
            : "Genera anteprima"}
        </button>
      </div>

      {previewSessions.length &&
      previewWeeks ? (
        <div className={styles.preview}>
          <div className={styles.previewHeading}>
            <div>
              <small>
                ANTEPRIMA · NON ANCORA SALVATA
              </small>

              <h3>
                {previewWeeks} settimane ·{" "}
                {previewSessions.length} sessioni
              </h3>

              <p>
                Controlla le prime sessioni.
                Il calendario verrà modificato
                solo dopo la conferma.
              </p>
            </div>
          </div>

          {activePlan ? (
            <div className={styles.replaceWarning}>
              <strong>
                Hai già un piano attivo.
              </strong>

              <span>
                Se confermi, il piano attuale
                e tutte le sue sessioni future
                verranno sostituiti da questa
                nuova pianificazione.
              </span>
            </div>
          ) : null}

          <div className={styles.previewSessions}>
            {previewSessions
              .slice(0, 6)
              .map((session, index) => (
                <article
                  key={`${session.scheduled_date}-${index}`}
                >
                  <div>
                    <small>
                      Settimana{" "}
                      {session.training_week ?? "—"}
                    </small>

                    <strong>
                      {new Date(
                        `${session.scheduled_date}T00:00:00`,
                      ).toLocaleDateString(
                        "it-IT",
                        {
                          weekday: "short",
                          day: "numeric",
                          month: "short",
                        },
                      )}
                    </strong>
                  </div>

                  <div>
                    <small>
                      {session.session_kind ??
                        "corsa"}
                    </small>

                    <strong>
                      {session.title}
                    </strong>

                    <span>
                      {session.distance_meters
                        ? `${(
                            session.distance_meters /
                            1000
                          ).toLocaleString(
                            "it-IT",
                            {
                              maximumFractionDigits:
                                1,
                            },
                          )} km`
                        : ""}

                      {session.duration_minutes
                        ? ` · ${session.duration_minutes} min`
                        : ""}
                    </span>
                  </div>
                </article>
              ))}
          </div>

          {previewSessions.length > 6 ? (
            <p className={styles.previewMore}>
              + altre{" "}
              {previewSessions.length - 6} sessioni
            </p>
          ) : null}

          <div className={styles.previewActions}>
            <button
              type="button"
              className={styles.confirmButton}
              disabled={saving}
              onClick={() => {
                void confirmPlan();
              }}
            >
              {saving
                ? "Salvo il piano…"
                : activePlan
                  ? "Sostituisci piano attivo"
                  : "Conferma e aggiungi al calendario"}
            </button>

            <button
              type="button"
              className={styles.editButton}
              disabled={saving}
              onClick={() => {
                clearPreview();
                setMessage(null);
              }}
            >
              Modifica parametri
            </button>
          </div>
        </div>
      ) : null}

      {message ? (
        <p className={styles.message}>
          {message}
        </p>
      ) : null}
    </section>
  );
}
