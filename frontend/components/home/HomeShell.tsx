"use client";

import { AppNav } from "@/components/navigation/AppNav";
import { QuickAdd } from "@/components/home/QuickAdd";
import { RegisteredToday } from "@/components/home/RegisteredToday";
import { getActivitiesForDate, type Activity } from "@/lib/api/activities";

import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { confirmMealPrediction } from "@/lib/api/confirm";
import { commitMealDecision } from "@/lib/api/decision";
import {
  createMeal,
  deleteMeal,
  getMeal,
  getMealsForDate,
  updateMeal,
  type LoggedMeal,
  type StructuredMealIngredient,
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

function optionSourceLabel(
  source: string,
): string {
  return {
    recipe: "Ricetta",
    meal_history: "Dai tuoi pasti",
    meal_prep: "Già pronto",
    routine: "Dalla tua routine",
    restaurant: "Fuori casa",
    eating_out: "Fuori casa",
    generic_eating_out: "Idea fuori casa",
    takeaway: "Takeaway",
    delivery: "Delivery",
    generic_order: "Idea da ordinare",
  }[source] ?? source;
}

export function HomeShell() {
  const {
    user,
    accessToken,
  } = useAuth();

  const [day, setDay] =
    useState<DayResponse | null>(null);
  const [budgetResult, setBudgetResult] =
    useState<DayBudgetResponse | null>(null);
  const [dinnerOptions, setDinnerOptions] =
    useState<MealOptionsResponse | null>(null);
  const [
    showDinnerAlternatives,
    setShowDinnerAlternatives,
  ] = useState(false);
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
  const [alternateCarbs, setAlternateCarbs] =
    useState("");
  const [alternateFat, setAlternateFat] =
    useState("");
  const [savingAlternate, setSavingAlternate] =
    useState(false);
  const [commitMessage, setCommitMessage] =
    useState<string | null>(null);
  const [actualDinner, setActualDinner] =
    useState<LoggedMeal | null>(null);
  const [actualMeals, setActualMeals] =
    useState<LoggedMeal[]>([]);

  const [actualActivities, setActualActivities] =
    useState<Activity[]>([]);

  const [editingMealId, setEditingMealId] =
    useState<string | number | null>(null);

  const [mealEditIngredients, setMealEditIngredients] =
    useState<StructuredMealIngredient[]>([]);

  const [savingMealEdit, setSavingMealEdit] =
    useState(false);

  const [deletingMealId, setDeletingMealId] =
    useState<string | number | null>(null);
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
          activitiesPayload,
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
          getActivitiesForDate(
            date,
            accessToken,
          ),
        ]);

        if (active) {
          setDay(dayPayload);
          setBudgetResult(budgetPayload);
          setDinnerOptions(dinnerPayload);
          setActualMeals(mealsPayload.items);
          setActualActivities(
            activitiesPayload.items,
          );
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
      activitiesPayload,
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
      getActivitiesForDate(
        date,
        accessToken,
      ),
    ]);

    setDay(dayPayload);
    setBudgetResult(budgetPayload);
    setDinnerOptions(dinnerPayload);
    setActualMeals(mealsPayload.items);
    setActualActivities(
      activitiesPayload.items,
    );
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

  async function openMealEditor(
    meal: LoggedMeal,
  ) {
    if (
      !accessToken ||
      meal.id === null ||
      meal.id === undefined
    ) {
      return;
    }

    setError(null);

    try {
      const response = await getMeal(
        meal.id,
        accessToken,
      );

      const structured =
        response.item.structured_ingredients ?? [];

      if (!structured.length) {
        setError(
          "Questo pasto non ha ingredienti strutturati modificabili.",
        );
        return;
      }

      setEditingMealId(meal.id);
      setMealEditIngredients(
        structured.map((item) => ({
          ...item,
          original_quantity_g:
            Number(item.quantity_g) || 0,
        })),
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco ad aprire il pasto.",
      );
    }
  }

  function closeMealEditor() {
    setEditingMealId(null);
    setMealEditIngredients([]);
  }

  function updateMealIngredientQuantity(
    index: number,
    quantityG: number,
  ) {
    setMealEditIngredients((current) =>
      current.map((item, itemIndex) =>
        itemIndex === index
          ? {
              ...item,
              quantity: quantityG,
              quantity_g: quantityG,
            }
          : item,
      ),
    );
  }

  function mealEditNutrition() {
    return mealEditIngredients.reduce(
      (total, item) => {
        const currentQuantity =
          Math.max(
            0,
            Number(item.quantity_g) || 0,
          );

        const originalQuantity =
          Math.max(
            0,
            Number(
              item.original_quantity_g ??
                item.quantity_g,
            ) || 0,
          );

        const scale =
          originalQuantity > 0
            ? currentQuantity /
              originalQuantity
            : 0;

        return {
          calories:
            total.calories +
            (Number(item.calories) || 0) *
              scale,
          protein:
            total.protein +
            (Number(item.protein) || 0) *
              scale,
          carbs:
            total.carbs +
            (Number(item.carbs) || 0) *
              scale,
          fat:
            total.fat +
            (Number(item.fat) || 0) *
              scale,
        };
      },
      {
        calories: 0,
        protein: 0,
        carbs: 0,
        fat: 0,
      },
    );
  }

  async function saveMealEditor(
    meal: LoggedMeal,
  ) {
    if (
      !accessToken ||
      meal.id === null ||
      meal.id === undefined
    ) {
      return;
    }

    if (
      mealEditIngredients.length === 0 ||
      mealEditIngredients.some(
        (item) =>
          !Number.isFinite(
            Number(item.quantity_g),
          ) ||
          Number(item.quantity_g) <= 0,
      )
    ) {
      setError(
        "Inserisci grammature valide per tutti gli ingredienti.",
      );
      return;
    }

    setSavingMealEdit(true);
    setError(null);

    try {
      await updateMeal(
        meal.id,
        {
          name: meal.name,
          meal_type: meal.meal_type,
          structured_ingredients:
            mealEditIngredients.map(
              (item) => ({
                ingredient_id:
                  item.ingredient_id,
                quantity:
                  Number(item.quantity_g),
                unit: item.unit || "g",
                quantity_g:
                  Number(item.quantity_g),
              }),
            ),
        },
        accessToken,
      );

      closeMealEditor();
      await refreshHome();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a salvare il pasto.",
      );
    } finally {
      setSavingMealEdit(false);
    }
  }

  async function toggleRegisteredMealReusable(
    meal: LoggedMeal,
  ) {
    if (
      !accessToken ||
      meal.id === null ||
      meal.id === undefined
    ) {
      return;
    }

    setError(null);

    try {
      await updateMeal(
        meal.id,
        {
          is_reusable:
            meal.is_reusable === false,
        },
        accessToken,
      );

      await refreshHome();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco ad aggiornare i suggerimenti.",
      );
    }
  }

  async function deleteRegisteredMeal(
    meal: LoggedMeal,
  ) {
    if (
      !accessToken ||
      meal.id === null ||
      meal.id === undefined
    ) {
      return;
    }

    const confirmed = window.confirm(
      `Eliminare "${meal.name}"?`,
    );

    if (!confirmed) {
      return;
    }

    setDeletingMealId(meal.id);
    setError(null);

    try {
      await deleteMeal(
        meal.id,
        accessToken,
      );

      if (editingMealId === meal.id) {
        closeMealEditor();
      }

      await refreshHome();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a eliminare il pasto.",
      );
    } finally {
      setDeletingMealId(null);
    }
  }

  function closeAlternateMeal() {
    setAlternateSlot(null);
    setAlternateName("");
    setAlternateCalories("");
    setAlternateProtein("");
    setAlternateCarbs("");
    setAlternateFat("");
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
    const carbs = alternateCarbs.trim()
      ? Number(alternateCarbs)
      : 0;
    const fat = alternateFat.trim()
      ? Number(alternateFat)
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

    if (
      !Number.isFinite(carbs) ||
      carbs < 0
    ) {
      setError(
        "Inserisci carboidrati validi.",
      );
      return;
    }

    if (
      !Number.isFinite(fat) ||
      fat < 0
    ) {
      setError(
        "Inserisci grassi validi.",
      );
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
          carbs: Math.round(carbs),
          fat: Math.round(fat),
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
    <>
      <AppNav />

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

                    {slot === "dinner" &&
                    !actualMealForSlot(slot) &&
                    dinnerOptions?.recommended ? (
                      <div
                        className={
                          styles.replanningPreview
                        }
                      >
                        <div
                          className={
                            styles.replanningPreviewTop
                          }
                        >
                          <span
                            className={
                              styles.replanningBadge
                            }
                          >
                            {dinnerOptions.recommended
                              .strategy ===
                            "adapted_routine"
                              ? "Adattata alla tua giornata"
                              : dinnerOptions.recommended
                                    .strategy ===
                                  "routine"
                                ? "Già adatta alla giornata"
                                : "Oggi ti conviene cambiare"}
                          </span>
                        </div>

                        <strong
                          className={
                            styles.replanningMealName
                          }
                        >
                          {
                            dinnerOptions.recommended
                              .candidate.name
                          }
                        </strong>

                        <p
                          className={
                            styles.replanningNutrition
                          }
                        >
                          {dinnerOptions.recommended
                            .portion_multiplier !== 1
                            ? `${dinnerOptions.recommended.portion_multiplier} porz. · `
                            : ""}
                          {roundNumber(
                            dinnerOptions.recommended
                              .candidate.calories,
                          )}{" "}
                          kcal
                          {typeof dinnerOptions
                            .recommended.candidate
                            .protein_g === "number"
                            ? ` · ${roundNumber(
                                dinnerOptions.recommended
                                  .candidate.protein_g,
                              )} g proteine`
                            : ""}
                        </p>

                        <p
                          className={
                            styles.replanningReason
                          }
                        >
                          {
                            dinnerOptions.recommended
                              .reason
                          }
                        </p>
                      </div>
                    ) : null}

                    {actualMealForSlot(slot) ? (
                      <>
                        <div
                          className={
                            styles.registeredMealPrimaryActions
                          }
                        >
                          <button
                            type="button"
                            className={
                              styles.editRegisteredMealButton
                            }
                            disabled={
                              deletingMealId !== null
                            }
                            onClick={() => {
                              const actual =
                                actualMealForSlot(slot);

                              if (actual) {
                                if (
                                  editingMealId ===
                                  actual.id
                                ) {
                                  closeMealEditor();
                                } else {
                                  void openMealEditor(
                                    actual,
                                  );
                                }
                              }
                            }}
                          >
                            {editingMealId ===
                            actualMealForSlot(slot)?.id
                              ? "Chiudi modifica"
                              : "Modifica"}
                          </button>

                          <details
                            className={
                              styles.registeredMealActionMenu
                            }
                          >
                            <summary
                              className={
                                styles.registeredMealMoreButton
                              }
                              aria-label="Altre azioni"
                              title="Altre azioni"
                            >
                              •••
                            </summary>

                            <div
                              className={
                                styles.registeredMealMenuPanel
                              }
                            >
                              <button
                                type="button"
                                disabled={
                                  deletingMealId !== null ||
                                  savingMealEdit
                                }
                                onClick={(event) => {
                                  const actual =
                                    actualMealForSlot(slot);

                                  if (actual) {
                                    void toggleRegisteredMealReusable(
                                      actual,
                                    );
                                  }

                                  event.currentTarget
                                    .closest("details")
                                    ?.removeAttribute("open");
                                }}
                              >
                                {actualMealForSlot(slot)
                                  ?.is_reusable === false
                                  ? "Riusa nei suggerimenti"
                                  : "Non suggerire più"}
                              </button>

                              <button
                                type="button"
                                className={
                                  styles.registeredMealMenuDelete
                                }
                                disabled={
                                  deletingMealId !== null ||
                                  savingMealEdit
                                }
                                onClick={(event) => {
                                  const actual =
                                    actualMealForSlot(slot);

                                  if (actual) {
                                    void deleteRegisteredMeal(
                                      actual,
                                    );
                                  }

                                  event.currentTarget
                                    .closest("details")
                                    ?.removeAttribute("open");
                                }}
                              >
                                {deletingMealId ===
                                actualMealForSlot(slot)?.id
                                  ? "Elimino…"
                                  : "Elimina"}
                              </button>
                            </div>
                          </details>
                        </div>

                        {editingMealId ===
                        actualMealForSlot(slot)?.id ? (
                          <div
                            className={
                              styles.registeredMealEditor
                            }
                          >
                            {mealEditIngredients.map(
                              (ingredient, index) => (
                                <label
                                  key={
                                    String(
                                      ingredient.id ??
                                        ingredient.ingredient_id,
                                    ) + index
                                  }
                                >
                                  <span>
                                    {ingredient.name_snapshot ||
                                      "Ingrediente"}
                                  </span>

                                  <div
                                    className={
                                      styles.registeredMealQuantity
                                    }
                                  >
                                    <input
                                      type="number"
                                      min="1"
                                      step="1"
                                      value={
                                        ingredient.quantity_g
                                      }
                                      onChange={(event) => {
                                        updateMealIngredientQuantity(
                                          index,
                                          Number(
                                            event.target.value,
                                          ) || 0,
                                        );
                                      }}
                                    />
                                    <span>g</span>
                                  </div>
                                </label>
                              ),
                            )}

                            <div
                              className={
                                styles.registeredMealNutrition
                              }
                            >
                              <strong>
                                {Math.round(
                                  mealEditNutrition()
                                    .calories,
                                )} kcal
                              </strong>

                              <span>
                                {mealEditNutrition()
                                  .protein.toFixed(1)}{" "}
                                g proteine
                              </span>

                              <span>
                                {mealEditNutrition()
                                  .carbs.toFixed(1)}{" "}
                                g carbo
                              </span>

                              <span>
                                {mealEditNutrition()
                                  .fat.toFixed(1)}{" "}
                                g grassi
                              </span>
                            </div>

                            <div
                              className={
                                styles.registeredMealEditActions
                              }
                            >
                              <button
                                type="button"
                                className={
                                  styles.saveRegisteredMealButton
                                }
                                disabled={savingMealEdit}
                                onClick={() => {
                                  const actual =
                                    actualMealForSlot(slot);

                                  if (actual) {
                                    void saveMealEditor(
                                      actual,
                                    );
                                  }
                                }}
                              >
                                {savingMealEdit
                                  ? "Salvo…"
                                  : "Salva modifiche"}
                              </button>

                              <button
                                type="button"
                                className={
                                  styles.cancelRegisteredMealButton
                                }
                                disabled={savingMealEdit}
                                onClick={
                                  closeMealEditor
                                }
                              >
                                Annulla
                              </button>
                            </div>
                          </div>
                        ) : null}
                      </>
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

                          {slot === "dinner" ? (
                            <button
                              type="button"
                              className={
                                styles.alternativeIdeasButton
                              }
                              disabled={
                                confirmingSlot !== null ||
                                savingAlternate
                              }
                              onClick={() => {
                                setShowDinnerAlternatives(
                                  (current) => !current,
                                );
                              }}
                            >
                              {showDinnerAlternatives
                                ? "Nascondi idee"
                                : "Alternative"}
                            </button>
                          ) : null}

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
                                setAlternateCarbs("");
                                setAlternateFat("");
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


                              <label>
                                Carboidrati
                                <input
                                  type="number"
                                  min="0"
                                  inputMode="numeric"
                                  value={alternateCarbs}
                                  placeholder="45"
                                  onChange={(event) => {
                                    setAlternateCarbs(
                                      event.target.value,
                                    );
                                  }}
                                />
                              </label>

                              <label>
                                Grassi
                                <input
                                  type="number"
                                  min="0"
                                  inputMode="numeric"
                                  value={alternateFat}
                                  placeholder="15"
                                  onChange={(event) => {
                                    setAlternateFat(
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

          {!actualDinner &&
          showDinnerAlternatives ? (
            <section className={styles.decisionSection}>
            <div className={styles.sectionHeader}>
              <div>
                <p className={styles.kicker}>
                  Alternative
                </p>
                <h2>Tre idee per cena</h2>
              </div>

              {dinnerOptions?.mode_label ? (
                <span className={styles.modeBadge}>
                  {dinnerOptions.mode_label}
                </span>
              ) : null}
            </div>

            {dinnerOptions?.day_context ? (
              <div className={styles.dayDecisionContext}>
                <strong>
                  {dinnerOptions.day_context.title}
                </strong>
                <p>
                  {dinnerOptions.day_context.message}
                </p>
              </div>
            ) : null}

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
                          {optionSourceLabel(
                            option.candidate.source,
                          )}
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

          <QuickAdd
            date={todayIso()}
            accessToken={accessToken}
            onSaved={refreshHome}
          />

          <RegisteredToday
            meals={actualMeals}
            activities={actualActivities}
            accessToken={accessToken}
            onChanged={refreshHome}
          />

        </>
      ) : null}
      </main>
    </>
  );
}
