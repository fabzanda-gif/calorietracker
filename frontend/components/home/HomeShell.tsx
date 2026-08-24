"use client";

import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { confirmMealPrediction } from "@/lib/api/confirm";
import { commitMealDecision } from "@/lib/api/decision";
import {
  createMeal,
  getMealsForDate,
  type LoggedMeal,
} from "@/lib/api/meals";
import {
  getDay,
  getDayBudget,
  getMealOptions,
} from "@/lib/api/day";
import type {
  DayBudgetResponse,
  DayResponse,
  MealOptionsResponse,
  RankedMealOption,
} from "@/lib/api/types";

import styles from "./HomeShell.module.css";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function greeting(): string {
  const hour = new Date().getHours();

  if (hour < 12) {
    return "Buongiorno";
  }

  if (hour < 18) {
    return "Buon pomeriggio";
  }

  return "Buonasera";
}

function mealLabel(slot: string): string {
  return {
    breakfast: "Colazione",
    lunch: "Pranzo",
    dinner: "Cena",
  }[slot] ?? slot;
}

function roundNumber(value: number): string {
  return Math.round(value).toLocaleString("it-IT");
}

function optionLensLabel(
  option: RankedMealOption,
): string {
  if (option.label) {
    return option.label;
  }

  return {
    calorie: "Più leggera",
    balanced: "Più bilanciata",
    taste: "Più gusto",
  }[option.lens] ?? option.lens;
}

export function HomeShell() {
  const {
    user,
    accessToken,
    signOut,
  } = useAuth();

  const [day, setDay] =
    useState<DayResponse | null>(null);
  const [budgetResult, setBudgetResult] =
    useState<DayBudgetResponse | null>(null);
  const [dinnerOptions, setDinnerOptions] =
    useState<MealOptionsResponse | null>(null);
  const [loading, setLoading] =
    useState(true);
  const [committingIndex, setCommittingIndex] =
    useState<number | null>(null);
  const [confirmingSlot, setConfirmingSlot] =
    useState<string | null>(null);
  const [alternateSlot, setAlternateSlot] =
    useState<string | null>(null);
  const [alternateName, setAlternateName] =
    useState("");
  const [alternateCalories, setAlternateCalories] =
    useState("");
  const [alternateProtein, setAlternateProtein] =
    useState("");
  const [savingAlternate, setSavingAlternate] =
    useState(false);
  const [commitMessage, setCommitMessage] =
    useState<string | null>(null);
  const [actualDinner, setActualDinner] =
    useState<LoggedMeal | null>(null);
  const [actualMeals, setActualMeals] =
    useState<LoggedMeal[]>([]);
  const [error, setError] =
    useState<string | null>(null);

  const firstName = useMemo(() => {
    const metadataName =
      user?.user_metadata?.first_name ||
      user?.user_metadata?.name;

    if (
      typeof metadataName === "string" &&
      metadataName.trim()
    ) {
      return metadataName.trim();
    }

    if (user?.email) {
      return user.email.split("@")[0];
    }

    return "";
  }, [user]);

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    let active = true;

    async function load() {
      setLoading(true);
      setError(null);

      try {
        const date = todayIso();

        const [
          dayPayload,
          budgetPayload,
          dinnerPayload,
          mealsPayload,
        ] = await Promise.all([
          getDay(
            date,
            accessToken,
          ),
          getDayBudget(
            date,
            accessToken,
          ),
          getMealOptions(
            date,
            "dinner",
            "auto",
            accessToken,
          ),
          getMealsForDate(
            date,
            accessToken,
          ),
        ]);

        if (active) {
          setDay(dayPayload);
          setBudgetResult(budgetPayload);
          setDinnerOptions(dinnerPayload);
          setActualMeals(mealsPayload.items);
          setActualDinner(
            mealsPayload.items.find(
              (meal) => meal.meal_type === "Cena",
            ) ?? null,
          );
        }
      } catch (err) {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Impossibile caricare la giornata.",
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [accessToken]);

  const budget =
    budgetResult?.budget ?? null;

  const budgetProgress =
    budget && budget.daily_budget_kcal > 0
      ? Math.min(
          100,
          Math.max(
            0,
            (budget.consumed_kcal /
              budget.daily_budget_kcal) *
              100,
          ),
        )
      : 0;

  const proteinProgress =
    budget?.protein_target_g &&
    budget.protein_target_g > 0
      ? Math.min(
          100,
          Math.max(
            0,
            (budget.protein_consumed_g /
              budget.protein_target_g) *
              100,
          ),
        )
      : 0;

  async function refreshHome() {
    if (!accessToken) {
      return;
    }

    const date = todayIso();

    const [
      dayPayload,
      budgetPayload,
      dinnerPayload,
      mealsPayload,
    ] = await Promise.all([
      getDay(date, accessToken),
      getDayBudget(date, accessToken),
      getMealOptions(
        date,
        "dinner",
        "auto",
        accessToken,
      ),
      getMealsForDate(
        date,
        accessToken,
      ),
    ]);

    setDay(dayPayload);
    setBudgetResult(budgetPayload);
    setDinnerOptions(dinnerPayload);
    setActualMeals(mealsPayload.items);
    setActualDinner(
      mealsPayload.items.find(
        (meal) => meal.meal_type === "Cena",
      ) ?? null,
    );
  }

  function actualMealForSlot(
    slot: string,
  ): LoggedMeal | null {
    const type = mealLabel(slot);

    return (
      actualMeals.find(
        (meal) => meal.meal_type === type,
      ) ?? null
    );
  }

  function closeAlternateMeal() {
    setAlternateSlot(null);
    setAlternateName("");
    setAlternateCalories("");
    setAlternateProtein("");
  }

  async function saveAlternateMeal(
    slot: string,
  ) {
    if (!accessToken) {
      return;
    }

    const name = alternateName.trim();
    const calories = Number(alternateCalories);
    const protein = alternateProtein.trim()
      ? Number(alternateProtein)
      : 0;

    if (!name) {
      setError("Inserisci il nome del pasto.");
      return;
    }

    if (
      !Number.isFinite(calories) ||
      calories < 0
    ) {
      setError("Inserisci delle kcal valide.");
      return;
    }

    if (
      !Number.isFinite(protein) ||
      protein < 0
    ) {
      setError("Inserisci proteine valide.");
      return;
    }

    setSavingAlternate(true);
    setError(null);

    try {
      await createMeal(
        {
          date: todayIso(),
          meal_type: mealLabel(slot),
          name,
          calories: Math.round(calories),
          protein: Math.round(protein),
          carbs: 0,
          fat: 0,
        },
        accessToken,
      );

      closeAlternateMeal();
      await refreshHome();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a registrare il pasto.",
      );
    } finally {
      setSavingAlternate(false);
    }
  }

  async function confirmPredictedMeal(
    slot: string,
  ) {
    if (!accessToken) {
      return;
    }

    setConfirmingSlot(slot);

    try {
      await confirmMealPrediction(
        todayIso(),
        slot,
        accessToken,
      );

      await refreshHome();
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "";

      // Se nel frattempo il pasto era già stato
      // registrato, riallineiamo comunque la Home.
      if (message.includes("409")) {
        await refreshHome();
      } else {
        setError(
          message ||
            "Non riesco a confermare il pasto.",
        );
      }
    } finally {
      setConfirmingSlot(null);
    }
  }

  async function chooseDinner(
    option: RankedMealOption,
    optionIndex: number,
  ) {
    if (!accessToken || !dinnerOptions) {
      return;
    }

    setCommittingIndex(optionIndex);
    setCommitMessage(null);

    try {
      const result = await commitMealDecision(
        todayIso(),
        "dinner",
        {
          mode: dinnerOptions.mode,
          lens: option.lens,
          option_index: optionIndex,
          candidate: option.candidate,
          available_kcal:
            budget?.available_kcal ?? null,
          protein_remaining_g:
            budget?.protein_remaining_g ?? null,
        },
        accessToken,
      );

      setCommitMessage(
        result.already_committed
          ? "Cena già registrata."
          : "Cena registrata.",
      );

      await refreshHome();
    } catch (err) {
      setCommitMessage(
        err instanceof Error
          ? err.message
          : "Non riesco a registrare la cena.",
      );
    } finally {
      setCommittingIndex(null);
    }
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.brand}>
            SANOSYNC
          </p>
          <h1>
            {greeting()}
            {firstName
              ? `, ${firstName}`
              : ""}
          </h1>
        </div>

        <button
          type="button"
          className={styles.signOut}
          onClick={() => {
            void signOut();
          }}
        >
          Esci
        </button>
      </header>

      {loading ? (
        <section className={styles.card}>
          <p className={styles.muted}>
            Sto preparando la tua giornata…
          </p>
        </section>
      ) : null}

      {error ? (
        <section className={styles.errorCard}>
          <strong>
            Non riesco a caricare la giornata.
          </strong>
          <p>{error}</p>
        </section>
      ) : null}

      {day ? (
        <>
          <section className={styles.dayIntro}>
            <p className={styles.kicker}>
              Oggi
            </p>

            <h2>
              {day.context.value ||
                "Giornata da definire"}
            </h2>

            <p className={styles.subtitle}>
              {day.activity_plan.value
                ? `${day.activity_plan.value} prevista`
                : "Attività non ancora prevista"}
            </p>
          </section>

          {budget ? (
            <section className={styles.budgetHero}>
              <div className={styles.budgetTopline}>
                <span>Kcal disponibili</span>
                <span>
                  Budget{" "}
                  {roundNumber(
                    budget.daily_budget_kcal,
                  )}
                </span>
              </div>

              <div className={styles.budgetNumber}>
                {roundNumber(
                  budget.available_kcal,
                )}
              </div>

              <div className={styles.budgetUnit}>
                kcal
              </div>

              <div
                className={styles.progressTrack}
                aria-label="Calorie consumate"
              >
                <div
                  className={styles.progressFill}
                  style={{
                    width: `${budgetProgress}%`,
                  }}
                />
              </div>

              <div className={styles.budgetBreakdown}>
                <div>
                  <span>Consumate</span>
                  <strong>
                    {roundNumber(
                      budget.consumed_kcal,
                    )}
                  </strong>
                </div>

                <div>
                  <span>Pianificate</span>
                  <strong>
                    {roundNumber(
                      budget.planned_kcal,
                    )}
                  </strong>
                </div>

                <div>
                  <span>Non allocate</span>
                  <strong>
                    {roundNumber(
                      budget.unallocated_kcal,
                    )}
                  </strong>
                </div>
              </div>
            </section>
          ) : (
            <section className={styles.card}>
              <strong>
                Budget non disponibile
              </strong>
              <p className={styles.muted}>
                Completa il profilo per calcolare
                il budget energetico.
              </p>
            </section>
          )}

          <section
            className={styles.metricsGrid}
          >
            <article className={styles.metricCard}>
              <span>Peso</span>
              <strong>
                {day.actual.weight != null
                  ? `${day.actual.weight} kg`
                  : "—"}
              </strong>
            </article>

            <article className={styles.metricCard}>
              <span>Passi</span>
              <strong>
                {day.actual.steps != null
                  ? day.actual.steps.toLocaleString(
                      "it-IT",
                    )
                  : "—"}
              </strong>
            </article>
          </section>

          {budget?.protein_target_g != null ? (
            <section className={styles.proteinCard}>
              <div className={styles.proteinTop}>
                <div>
                  <span>Proteine</span>
                  <strong>
                    {roundNumber(
                      budget.protein_consumed_g,
                    )}{" "}
                    /{" "}
                    {roundNumber(
                      budget.protein_target_g,
                    )}{" "}
                    g
                  </strong>
                </div>

                <span className={styles.proteinRemaining}>
                  {roundNumber(
                    budget.protein_remaining_g ?? 0,
                  )}{" "}
                  g rimaste
                </span>
              </div>

              <div className={styles.proteinTrack}>
                <div
                  className={styles.proteinFill}
                  style={{
                    width: `${proteinProgress}%`,
                  }}
                />
              </div>
            </section>
          ) : null}

          <section className={styles.section}>
            <div className={styles.sectionHeader}>
              <div>
                <p className={styles.kicker}>
                  Routine prevista
                </p>
                <h2>I tuoi pasti</h2>
              </div>
            </div>

            <div className={styles.mealList}>
              {Object.entries(day.meals).map(
                ([slot, meal]) => (
                  <article
                    key={slot}
                    className={styles.mealCard}
                  >
                    <div
                      className={
                        styles.mealCardTop
                      }
                    >
                      <span
                        className={
                          styles.mealLabel
                        }
                      >
                        {mealLabel(slot)}
                      </span>

                      <span
                        className={
                          actualMealForSlot(slot)
                            ? styles.registeredMealBadge
                            : meal.state === "predicted"
                              ? styles.predictedBadge
                              : styles.unknownBadge
                        }
                      >
                        {actualMealForSlot(slot)
                          ? "Registrato"
                          : meal.state === "predicted"
                            ? "Previsto"
                            : "Da decidere"}
                      </span>
                    </div>

                    <strong
                      className={styles.mealName}
                    >
                      {actualMealForSlot(slot)?.name ||
                        meal.value ||
                        "Nessuna routine abbastanza forte"}
                    </strong>

                    {actualMealForSlot(slot) ? (
                      <p className={styles.mealMeta}>
                        {roundNumber(
                          actualMealForSlot(slot)!.calories,
                        )} kcal
                        {typeof actualMealForSlot(slot)!
                          .protein === "number"
                          ? ` · ${roundNumber(
                              actualMealForSlot(slot)!
                                .protein,
                            )} g proteine`
                          : ""}
                      </p>
                    ) : typeof meal.estimated_calories ===
                      "number" ? (
                      <p
                        className={
                          styles.mealMeta
                        }
                      >
                        {Math.round(
                          meal.estimated_calories,
                        )}{" "}
                        kcal
                        {typeof meal.estimated_protein_g ===
                        "number"
                          ? ` · ${Math.round(
                              meal.estimated_protein_g,
                            )} g proteine`
                          : ""}
                      </p>
                    ) : null}

                    {!actualMealForSlot(slot) &&
                    meal.state === "predicted" ? (
                      <>
                        <div className={styles.mealActions}>
                          <button
                            type="button"
                            className={styles.confirmMealButton}
                            disabled={
                              confirmingSlot !== null ||
                              savingAlternate
                            }
                            onClick={() => {
                              void confirmPredictedMeal(slot);
                            }}
                          >
                            {confirmingSlot === slot
                              ? "Confermo…"
                              : "Conferma"}
                          </button>

                          <button
                            type="button"
                            className={styles.alternateMealButton}
                            disabled={
                              confirmingSlot !== null ||
                              savingAlternate
                            }
                            onClick={() => {
                              setError(null);

                              if (alternateSlot === slot) {
                                closeAlternateMeal();
                              } else {
                                setAlternateSlot(slot);
                                setAlternateName("");
                                setAlternateCalories("");
                                setAlternateProtein("");
                              }
                            }}
                          >
                            Ho mangiato altro
                          </button>
                        </div>

                        {alternateSlot === slot ? (
                          <div className={styles.alternateMealForm}>
                            <label>
                              Cosa hai mangiato?
                              <input
                                type="text"
                                value={alternateName}
                                placeholder="Es. Piadina con pollo"
                                onChange={(event) => {
                                  setAlternateName(
                                    event.target.value,
                                  );
                                }}
                              />
                            </label>

                            <div className={styles.alternateMealNumbers}>
                              <label>
                                Kcal
                                <input
                                  type="number"
                                  min="0"
                                  inputMode="numeric"
                                  value={alternateCalories}
                                  placeholder="450"
                                  onChange={(event) => {
                                    setAlternateCalories(
                                      event.target.value,
                                    );
                                  }}
                                />
                              </label>

                              <label>
                                Proteine
                                <input
                                  type="number"
                                  min="0"
                                  inputMode="numeric"
                                  value={alternateProtein}
                                  placeholder="30"
                                  onChange={(event) => {
                                    setAlternateProtein(
                                      event.target.value,
                                    );
                                  }}
                                />
                              </label>
                            </div>

                            <div className={styles.alternateFormActions}>
                              <button
                                type="button"
                                className={styles.saveAlternateButton}
                                disabled={savingAlternate}
                                onClick={() => {
                                  void saveAlternateMeal(slot);
                                }}
                              >
                                {savingAlternate
                                  ? "Salvo…"
                                  : "Salva"}
                              </button>

                              <button
                                type="button"
                                className={styles.cancelAlternateButton}
                                disabled={savingAlternate}
                                onClick={closeAlternateMeal}
                              >
                                Annulla
                              </button>
                            </div>
                          </div>
                        ) : null}
                      </>
                    ) : null}
                  </article>
                ),
              )}
            </div>
          </section>

          {!actualDinner ? (
            <section className={styles.decisionSection}>
            <div className={styles.sectionHeader}>
              <div>
                <p className={styles.kicker}>
                  Stasera
                </p>
                <h2>Tre idee per cena</h2>
              </div>

              {dinnerOptions?.mode_label ? (
                <span className={styles.modeBadge}>
                  {dinnerOptions.mode_label}
                </span>
              ) : null}
            </div>

            {commitMessage ? (
              <p className={styles.commitMessage}>
                {commitMessage}
              </p>
            ) : null}

            {dinnerOptions?.options.length ? (
              <div className={styles.optionList}>
                {dinnerOptions.options.map(
                  (option) => (
                    <article
                      key={`${option.lens}-${option.candidate.id ?? option.candidate.name}`}
                      className={styles.optionCard}
                    >
                      <div className={styles.optionTop}>
                        <span className={styles.optionLens}>
                          {optionLensLabel(option)}
                        </span>

                        <span className={styles.optionSource}>
                          {option.candidate.source}
                        </span>
                      </div>

                      <h3>
                        {option.candidate.name}
                      </h3>

                      <p className={styles.optionNumbers}>
                        {roundNumber(
                          option.candidate.calories,
                        )}{" "}
                        kcal
                        {typeof option.candidate.protein_g ===
                        "number"
                          ? ` · ${roundNumber(
                              option.candidate.protein_g,
                            )} g proteine`
                          : ""}
                      </p>

                      <p className={styles.optionReason}>
                        {option.reason}
                      </p>

                      <button
                        type="button"
                        className={styles.chooseButton}
                        disabled={committingIndex !== null}
                        onClick={() => {
                          void chooseDinner(
                            option,
                            dinnerOptions.options.indexOf(option),
                          );
                        }}
                      >
                        {committingIndex ===
                        dinnerOptions.options.indexOf(option)
                          ? "Registro…"
                          : "Scelgo questa"}
                      </button>
                    </article>
                  ),
                )}
              </div>
            ) : (
              <article className={styles.emptyDecisionCard}>
                <strong>
                  Sto ancora imparando le tue cene.
                </strong>
                <p>
                  Registra qualche altra scelta e SanoSync
                  inizierà a proporti alternative più utili.
                </p>
              </article>
            )}
          </section>
          ) : null}
        </>
      ) : null}
    </main>
  );
}
