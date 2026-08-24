"use client";

import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { commitMealDecision } from "@/lib/api/decision";
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
  const [commitMessage, setCommitMessage] =
    useState<string | null>(null);
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
        ]);

        if (active) {
          setDay(dayPayload);
          setBudgetResult(budgetPayload);
          setDinnerOptions(dinnerPayload);
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
    ] = await Promise.all([
      getDay(date, accessToken),
      getDayBudget(date, accessToken),
      getMealOptions(
        date,
        "dinner",
        "auto",
        accessToken,
      ),
    ]);

    setDay(dayPayload);
    setBudgetResult(budgetPayload);
    setDinnerOptions(dinnerPayload);
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
                          meal.state ===
                          "predicted"
                            ? styles.predictedBadge
                            : styles.unknownBadge
                        }
                      >
                        {meal.state ===
                        "predicted"
                          ? "Previsto"
                          : "Da decidere"}
                      </span>
                    </div>

                    <strong
                      className={styles.mealName}
                    >
                      {meal.value ||
                        "Nessuna routine abbastanza forte"}
                    </strong>

                    {typeof meal.estimated_calories ===
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
                  </article>
                ),
              )}
            </div>
          </section>

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
        </>
      ) : null}
    </main>
  );
}
