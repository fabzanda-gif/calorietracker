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
  confirmConversationalMeal,
  deleteMeal,
  getMeal,
  getMealsForDate,
  previewConversationalMeal,
  previewPhotoMeal,
  updateMeal,
  type ConversationalMealPreview,
  type LoggedMeal,
  type StructuredMealIngredient,
} from "@/lib/api/meals";
import {
  getDay,
  getDayBudget,
  getMealOptions,
  getNextMeal,
} from "@/lib/api/day";
import type {
  DayBudgetResponse,
  DayResponse,
  MealOptionsResponse,
  NextMealResponse,
  RankedMealOption,
} from "@/lib/api/types";

import { getLatestWeight } from "@/lib/api/weight";

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
  const [nextMealOptions, setNextMealOptions] =
    useState<MealOptionsResponse | null>(null);
  const [dinnerOptions, setDinnerOptions] =
    useState<MealOptionsResponse | null>(null);
  const [nextMeal, setNextMeal] =
    useState<NextMealResponse | null>(null);

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

  const [latestWeight, setLatestWeight] =
    useState<number | null>(null);

  const [editingMealId, setEditingMealId] =
    useState<string | number | null>(null);

  const [mealEditIngredients, setMealEditIngredients] =
    useState<StructuredMealIngredient[]>([]);

  const [savingMealEdit, setSavingMealEdit] =
    useState(false);

  const [simpleMealEdit, setSimpleMealEdit] =
    useState<LoggedMeal | null>(null);
  const [simpleMealQuantity, setSimpleMealQuantity] =
    useState(1);

  const [deletingMealId, setDeletingMealId] =
    useState<string | number | null>(null);
  const [error, setError] =
    useState<string | null>(null);

  const [conversationText, setConversationText] =
    useState("");
  const [conversationMode, setConversationMode] =
    useState<"text" | "photo">("text");
  const [conversationPhoto, setConversationPhoto] =
    useState<File | null>(null);
  const [
    conversationPhotoPreview,
    setConversationPhotoPreview,
  ] = useState<string | null>(null);
  const [conversationMealType, setConversationMealType] =
    useState("Pranzo");
  const [conversationPreview, setConversationPreview] =
    useState<ConversationalMealPreview | null>(null);
  const [conversationLoading, setConversationLoading] =
    useState(false);
  const [conversationError, setConversationError] =
    useState<string | null>(null);
  const [conversationConfirming, setConversationConfirming] =
    useState(false);
  const [conversationSuccess, setConversationSuccess] =
    useState<string | null>(null);


  const firstName = useMemo(() => {
    const metadataName =
      user?.user_metadata?.first_name ||
      user?.user_metadata?.name;

    if (
      typeof metadataName === "string" &&
      metadataName.trim()
    ) {
      return metadataName.trim().split(/\s+/)[0];
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
          nextMealPayload,
          mealsPayload,
          activitiesPayload,
          latestWeightPayload,
        ] = await Promise.all([
          getDay(
            date,
            accessToken,
          ),
          getDayBudget(
            date,
            accessToken,
          ),
          getNextMeal(
            date,
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
          getLatestWeight(
            accessToken,
          ),
        ]);

        const nextMealOptionsPayload =
          nextMealPayload.next_slot
            ? await getMealOptions(
                date,
                nextMealPayload.next_slot,
                "auto",
                accessToken,
              )
            : null;

        if (active) {
          setDay(dayPayload);
          setBudgetResult(budgetPayload);
          setNextMeal(nextMealPayload);
          setNextMealOptions(nextMealOptionsPayload);
          setDinnerOptions(
            nextMealPayload.next_slot === "dinner"
              ? nextMealOptionsPayload
              : null,
          );
          setActualMeals(mealsPayload.items);
          setActualActivities(
            activitiesPayload.items,
          );

          setLatestWeight(
            latestWeightPayload.item?.weight != null
              ? Number(latestWeightPayload.item.weight)
              : null,
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

  const burnedCalories = actualActivities.reduce(
    (total, activity) =>
      total + Number(activity.burned_calories || 0),
    0,
  );

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

  async function analyzeConversationMeal() {
    if (!accessToken || !conversationText.trim()) {
      return;
    }

    setConversationLoading(true);
    setConversationError(null);
    setConversationPreview(null);

    try {
      const preview = await previewConversationalMeal(
        conversationText.trim(),
        conversationMealType,
        accessToken,
      );

      setConversationPreview(preview);
    } catch (err) {
      setConversationError(
        err instanceof Error
          ? err.message
          : "Non riesco ad analizzare questo pasto.",
      );
    } finally {
      setConversationLoading(false);
    }
  }

  async function analyzePhotoMeal() {
    if (!accessToken || !conversationPhoto) {
      return;
    }

    setConversationLoading(true);
    setConversationError(null);
    setConversationPreview(null);
    setConversationSuccess(null);

    try {
      const dataUrl = await new Promise<string>(
        (resolve, reject) => {
          const reader = new FileReader();

          reader.onload = () => {
            if (typeof reader.result === "string") {
              resolve(reader.result);
              return;
            }

            reject(
              new Error(
                "Impossibile leggere la foto selezionata.",
              ),
            );
          };

          reader.onerror = () => {
            reject(
              new Error(
                "Impossibile leggere la foto selezionata.",
              ),
            );
          };

          reader.readAsDataURL(conversationPhoto);
        },
      );

      const separatorIndex = dataUrl.indexOf(",");

      if (separatorIndex < 0) {
        throw new Error(
          "Formato immagine non valido.",
        );
      }

      const imageBase64 = dataUrl.slice(
        separatorIndex + 1,
      );

      const preview = await previewPhotoMeal(
        imageBase64,
        conversationPhoto.type || "image/jpeg",
        conversationMealType,
        accessToken,
      );

      setConversationPreview(preview);
    } catch (err) {
      setConversationError(
        err instanceof Error
          ? err.message
          : "Non riesco ad analizzare questa foto.",
      );
    } finally {
      setConversationLoading(false);
    }
  }

  async function confirmConversationMeal() {
    if (
      !accessToken ||
      !conversationPreview ||
      !conversationPreview.requires_confirmation
    ) {
      return;
    }

    setConversationConfirming(true);
    setConversationError(null);
    setConversationSuccess(null);

    try {
      await confirmConversationalMeal(
        {
          date: todayIso(),
          meal_type: conversationPreview.meal_type,
          items: conversationPreview.items,
        },
        accessToken,
      );

      setConversationSuccess(
        "Pasto registrato. Ho aggiornato la tua giornata.",
      );

      setConversationText("");
      setConversationPreview(null);
      setConversationPhoto(null);
      setConversationPhotoPreview(null);

      await refreshHome();
    } catch (err) {
      setConversationError(
        err instanceof Error
          ? err.message
          : "Non riesco a registrare questo pasto.",
      );
    } finally {
      setConversationConfirming(false);
    }
  }

  async function refreshHome() {
    if (!accessToken) {
      return;
    }

    const date = todayIso();

    const [
      dayPayload,
      budgetPayload,
      nextMealPayload,
      mealsPayload,
      activitiesPayload,
    ] = await Promise.all([
      getDay(date, accessToken),
      getDayBudget(date, accessToken),
      getNextMeal(
        date,
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

    const nextMealOptionsPayload =
      nextMealPayload.next_slot
        ? await getMealOptions(
            date,
            nextMealPayload.next_slot,
            "auto",
            accessToken,
          )
        : null;

    setDay(dayPayload);
    setBudgetResult(budgetPayload);
    setNextMeal(nextMealPayload);
    setNextMealOptions(nextMealOptionsPayload);
    setDinnerOptions(
      nextMealPayload.next_slot === "dinner"
        ? nextMealOptionsPayload
        : null,
    );
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

  function actualMealsForSlot(
    slot: string,
  ): LoggedMeal[] {
    const type = mealLabel(slot);

    return actualMeals.filter(
      (meal) => meal.meal_type === type,
    );
  }

  function actualMealForSlot(
    slot: string,
  ): LoggedMeal | null {
    return actualMealsForSlot(slot)[0] ?? null;
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

      setEditingMealId(meal.id);

      if (!structured.length) {
        setMealEditIngredients([]);
        setSimpleMealEdit(response.item);
        setSimpleMealQuantity(
          Number(response.item.quantity) || 1,
        );
        return;
      }

      setSimpleMealEdit(null);
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
    setSimpleMealEdit(null);
    setSimpleMealQuantity(1);
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

  function simpleMealEditNutrition() {
    if (!simpleMealEdit) {
      return {
        calories: 0,
        protein: 0,
        carbs: 0,
        fat: 0,
      };
    }

    const factor = simpleMealEdit.is_per_100g
      ? simpleMealQuantity / 100
      : simpleMealQuantity;

    return {
      calories:
        Number(simpleMealEdit.base_calories ?? 0) *
        factor,
      protein:
        Number(simpleMealEdit.base_protein ?? 0) *
        factor,
      carbs:
        Number(simpleMealEdit.base_carbs ?? 0) *
        factor,
      fat:
        Number(simpleMealEdit.base_fat ?? 0) *
        factor,
    };
  }

  async function saveSimpleMealEditor(
    meal: LoggedMeal,
  ) {
    if (
      !accessToken ||
      meal.id === null ||
      meal.id === undefined ||
      !simpleMealEdit ||
      !Number.isFinite(simpleMealQuantity) ||
      simpleMealQuantity <= 0
    ) {
      return;
    }

    const nutrition = simpleMealEditNutrition();

    setSavingMealEdit(true);
    setError(null);

    try {
      await updateMeal(
        meal.id,
        {
          quantity: simpleMealQuantity,
          calories: nutrition.calories,
          protein: nutrition.protein,
          carbs: nutrition.carbs,
          fat: nutrition.fat,
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
      const replannedRecommendation =
        slot === nextMeal?.next_slot &&
        nextMealOptions?.recommended
          ? {
              name:
                nextMealOptions.recommended
                  .candidate.name,
              quantity:
                nextMealOptions.recommended
                  .recommended_quantity,
              calories:
                nextMealOptions.recommended
                  .candidate.calories,
              protein_g:
                nextMealOptions.recommended
                  .candidate.protein_g,
              carbs_g:
                nextMealOptions.recommended
                  .candidate.carbs_g,
              fat_g:
                nextMealOptions.recommended
                  .candidate.fat_g,
            }
          : null;

      await confirmMealPrediction(
        todayIso(),
        slot,
        accessToken,
        replannedRecommendation,
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

              <div className={styles.planMetrics}>
                <div className={styles.planMetric}>
                  <span>Peso</span>
                  <strong>
                    {latestWeight != null
                      ? `${latestWeight.toLocaleString(
                          "it-IT",
                          {
                            minimumFractionDigits: 1,
                            maximumFractionDigits: 1,
                          },
                        )} kg`
                      : "—"}
                  </strong>
                </div>

                <div className={styles.planMetric}>
                  <span>Kcal bruciate</span>
                  <strong>
                    {roundNumber(burnedCalories)} kcal
                  </strong>
                </div>

                <div
                  className={`${styles.planMetric} ${styles.planProtein}`}
                >
                  <div className={styles.planProteinTop}>
                    <span>Proteine</span>

                    {budget?.protein_target_g != null ? (
                      <small>
                        {roundNumber(
                          budget.protein_remaining_g ?? 0,
                        )} g rimaste
                      </small>
                    ) : null}
                  </div>

                  <strong>
                    {budget?.protein_target_g != null
                      ? `${roundNumber(
                          budget.protein_consumed_g,
                        )} / ${roundNumber(
                          budget.protein_target_g,
                        )} g`
                      : "—"}
                  </strong>

                  {budget?.protein_target_g != null ? (
                    <div className={styles.planProteinTrack}>
                      <div
                        className={styles.planProteinFill}
                        style={{
                          width: `${proteinProgress}%`,
                        }}
                      />
                    </div>
                  ) : null}
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

          <section className={styles.conversationCard}>
            <div className={styles.conversationHeader}>
              <div>
                <span className={styles.conversationEyebrow}>
                  SanoSync AI
                </span>
                <h2>
                  {conversationMode === "text"
                    ? "Raccontami cosa hai mangiato"
                    : "Fammi vedere cosa hai mangiato"}
                </h2>
                <p>
                  {conversationMode === "text"
                    ? "Scrivilo come lo diresti normalmente. "
                    : "Scatta una foto o scegline una dalla galleria. "}
                  Prima di registrare qualcosa ti mostro
                  sempre una preview.
                </p>
              </div>
            </div>

            <div className={styles.conversationModeSwitch}>
              <button
                type="button"
                className={
                  conversationMode === "text"
                    ? styles.conversationModeActive
                    : undefined
                }
                onClick={() => {
                  setConversationMode("text");
                  setConversationPreview(null);
                  setConversationError(null);
                  setConversationSuccess(null);
                }}
              >
                Testo
              </button>

              <button
                type="button"
                className={
                  conversationMode === "photo"
                    ? styles.conversationModeActive
                    : undefined
                }
                onClick={() => {
                  setConversationMode("photo");
                  setConversationPreview(null);
                  setConversationError(null);
                  setConversationSuccess(null);
                }}
              >
                Foto
              </button>
            </div>

            <div className={styles.conversationControls}>
              <select
                value={conversationMealType}
                onChange={(event) =>
                  setConversationMealType(
                    event.target.value,
                  )
                }
                aria-label="Tipo di pasto"
              >
                <option value="Colazione">
                  Colazione
                </option>
                <option value="Pranzo">
                  Pranzo
                </option>
                <option value="Cena">
                  Cena
                </option>
                <option value="Spuntino">
                  Spuntino
                </option>
              </select>

              {conversationMode === "text" ? (
                <>
                  <textarea
                    value={conversationText}
                    onChange={(event) =>
                      setConversationText(
                        event.target.value,
                      )
                    }
                    placeholder="Es. Ho mangiato una carbonara e una mela"
                    rows={3}
                  />

                  <button
                    type="button"
                    onClick={() => {
                      void analyzeConversationMeal();
                    }}
                    disabled={
                      conversationLoading ||
                      !conversationText.trim()
                    }
                  >
                    {conversationLoading
                      ? "Analizzo..."
                      : "Analizza"}
                  </button>
                </>
              ) : (
                <>
                  <label
                    className={styles.conversationPhotoPicker}
                  >
                    <span>
                      {conversationPhoto
                        ? conversationPhoto.name
                        : "Scatta o scegli una foto"}
                    </span>

                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      capture="environment"
                      onChange={(event) => {
                        const file =
                          event.target.files?.[0] ?? null;

                        setConversationPhoto(file);
                        setConversationPreview(null);
                        setConversationError(null);
                        setConversationSuccess(null);

                        if (!file) {
                          setConversationPhotoPreview(null);
                          return;
                        }

                        const reader = new FileReader();

                        reader.onload = () => {
                          if (
                            typeof reader.result ===
                            "string"
                          ) {
                            setConversationPhotoPreview(
                              reader.result,
                            );
                          }
                        };

                        reader.readAsDataURL(file);
                      }}
                    />
                  </label>

                  {conversationPhotoPreview ? (
                    <div
                      className={
                        styles.conversationPhotoPreview
                      }
                    >
                      <img
                        src={conversationPhotoPreview}
                        alt="Anteprima del pasto"
                      />
                    </div>
                  ) : null}

                  <button
                    type="button"
                    onClick={() => {
                      void analyzePhotoMeal();
                    }}
                    disabled={
                      conversationLoading ||
                      !conversationPhoto
                    }
                  >
                    {conversationLoading
                      ? "Analizzo..."
                      : "Analizza foto"}
                  </button>
                </>
              )}
            </div>

            {conversationError ? (
              <p className={styles.conversationError}>
                {conversationError}
              </p>
            ) : null}

            {conversationSuccess ? (
              <p className={styles.conversationSuccess}>
                {conversationSuccess}
              </p>
            ) : null}

            {conversationPreview ? (
              <div className={styles.conversationPreview}>
                <div className={styles.conversationPreviewTop}>
                  <strong>Ho capito così</strong>

                  {conversationPreview.needs_review ? (
                    <span>
                      Controlla le quantità stimate
                    </span>
                  ) : null}
                </div>

                <div className={styles.conversationItems}>
                  {conversationPreview.items.map(
                    (item, index) => (
                      <div
                        key={`${item.name}-${index}`}
                        className={styles.conversationItem}
                      >
                        <div>
                          <strong>{item.name}</strong>
                          <span>
                            {roundNumber(item.quantity)}{" "}
                            {item.unit}
                            {item.uncertainty
                              ? " · stimato"
                              : ""}
                          </span>
                        </div>

                        <span>
                          {roundNumber(item.calories)} kcal
                        </span>
                      </div>
                    ),
                  )}
                </div>

                <div className={styles.conversationTotals}>
                  <strong>
                    {roundNumber(
                      conversationPreview.totals.calories,
                    )}{" "}
                    kcal
                  </strong>

                  <span>
                    {roundNumber(
                      conversationPreview.totals.protein,
                    )}{" "}
                    g proteine ·{" "}
                    {roundNumber(
                      conversationPreview.totals.carbs,
                    )}{" "}
                    g carbo ·{" "}
                    {roundNumber(
                      conversationPreview.totals.fat,
                    )}{" "}
                    g grassi
                  </span>
                </div>

                <div
                  className={
                    styles.conversationPreviewActions
                  }
                >
                  <button
                    type="button"
                    onClick={() => {
                      void confirmConversationMeal();
                    }}
                    disabled={conversationConfirming}
                  >
                    {conversationConfirming
                      ? "Registro..."
                      : "Conferma e registra"}
                  </button>

                  <button
                    type="button"
                    onClick={() =>
                      setConversationPreview(null)
                    }
                  >
                    {conversationMode === "photo"
                      ? "Cambia foto"
                      : "Modifica testo"}
                  </button>
                </div>
              </div>
            ) : null}
          </section>

          <section className={`${styles.section} ${styles.mealsSection}`}>
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

                      {slot === nextMeal?.next_slot &&
                      !actualMealForSlot(slot) ? (
                        <span
                          className={styles.nextMealBadge}
                        >
                          Prossimo
                        </span>
                      ) : null}
                    </div>

                    {actualMealForSlot(slot) ? (
                      <>
                        <div className={styles.registeredMealList}>
                          {actualMealsForSlot(slot).map(
                            (registeredMeal) => (
                              <div
                                key={String(
                                  registeredMeal.id ??
                                    registeredMeal.name,
                                )}
                                className={
                                  styles.registeredMealRow
                                }
                              >
                                <div
                                  className={
                                    styles.registeredMealRowInfo
                                  }
                                >
                                  <strong>
                                    {registeredMeal.name}
                                  </strong>

                                  <span>
                                    {roundNumber(
                                      registeredMeal.calories,
                                    )}{" "}
                                    kcal
                                    {typeof registeredMeal.protein ===
                                    "number"
                                      ? ` · ${roundNumber(
                                          registeredMeal.protein,
                                        )} g proteine`
                                      : ""}
                                  </span>
                                </div>

                                <div
                                  className={
                                    styles.registeredMealRowActions
                                  }
                                >
                                  <button
                                    type="button"
                                    disabled={
                                      deletingMealId !== null ||
                                      savingMealEdit
                                    }
                                    onClick={() => {
                                      if (
                                        editingMealId ===
                                        registeredMeal.id
                                      ) {
                                        closeMealEditor();
                                      } else {
                                        void openMealEditor(
                                          registeredMeal,
                                        );
                                      }
                                    }}
                                  >
                                    ✎{" "}
                                    {editingMealId ===
                                    registeredMeal.id
                                      ? "Chiudi"
                                      : "Modifica"}
                                  </button>

                                  <button
                                    type="button"
                                    className={
                                      styles.registeredMealRowDelete
                                    }
                                    disabled={
                                      deletingMealId !== null ||
                                      savingMealEdit
                                    }
                                    onClick={() => {
                                      void deleteRegisteredMeal(
                                        registeredMeal,
                                      );
                                    }}
                                  >
                                    🗑{" "}
                                    {deletingMealId ===
                                    registeredMeal.id
                                      ? "Elimino…"
                                      : "Elimina"}
                                  </button>
                                </div>
                              </div>
                            ),
                          )}
                        </div>

                        {actualMealsForSlot(slot).length > 0 ? (
                          <div
                            className={
                              styles.registeredMealSlotTotal
                            }
                          >
                            <span>Totale {mealLabel(slot)}</span>

                            <strong>
                              {roundNumber(
                                actualMealsForSlot(slot).reduce(
                                  (total, registeredMeal) =>
                                    total +
                                    Number(
                                      registeredMeal.calories || 0,
                                    ),
                                  0,
                                ),
                              )}{" "}
                              kcal ·{" "}
                              {roundNumber(
                                actualMealsForSlot(slot).reduce(
                                  (total, registeredMeal) =>
                                    total +
                                    Number(
                                      registeredMeal.protein || 0,
                                    ),
                                  0,
                                ),
                              )}{" "}
                              g proteine
                            </strong>
                          </div>
                        ) : null}

                        {actualMealsForSlot(slot).some(
                          (registeredMeal) =>
                            registeredMeal.id === editingMealId,
                        ) ? (
                          <div
                            className={
                              styles.registeredMealEditor
                            }
                          >
                            {simpleMealEdit ? (
                              <>
                                <label>
                                  <span>
                                    {simpleMealEdit.is_per_100g
                                      ? "Grammi"
                                      : "Porzioni"}
                                  </span>

                                  <div
                                    className={
                                      styles.registeredMealQuantity
                                    }
                                  >
                                    <input
                                      type="number"
                                      min={
                                        simpleMealEdit.is_per_100g
                                          ? "1"
                                          : "0.25"
                                      }
                                      step={
                                        simpleMealEdit.is_per_100g
                                          ? "1"
                                          : "0.25"
                                      }
                                      value={simpleMealQuantity}
                                      onChange={(event) =>
                                        setSimpleMealQuantity(
                                          Number(
                                            event.target.value,
                                          ) || 0,
                                        )
                                      }
                                    />

                                    <span>
                                      {simpleMealEdit.is_per_100g
                                        ? "g"
                                        : "porz."}
                                    </span>
                                  </div>
                                </label>

                                <div
                                  className={
                                    styles.registeredMealNutrition
                                  }
                                >
                                  <strong>
                                    {Math.round(
                                      simpleMealEditNutrition()
                                        .calories,
                                    )} kcal
                                  </strong>

                                  <span>
                                    {simpleMealEditNutrition()
                                      .protein.toFixed(1)}{" "}
                                    g proteine
                                  </span>

                                  <span>
                                    {simpleMealEditNutrition()
                                      .carbs.toFixed(1)}{" "}
                                    g carbo
                                  </span>

                                  <span>
                                    {simpleMealEditNutrition()
                                      .fat.toFixed(1)}{" "}
                                    g grassi
                                  </span>
                                </div>
                              </>
                            ) : null}

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

                            {!simpleMealEdit ? (
                              <div
                                className={
                                  styles.registeredMealNutrition
                                }
                              >
                                <strong>
                                  {Math.round(
                                    mealEditNutrition().calories,
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
                            ) : null}

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
                                    actualMealsForSlot(slot).find(
                                      (registeredMeal) =>
                                        registeredMeal.id ===
                                        editingMealId,
                                    );

                                  if (actual) {
                                    if (simpleMealEdit) {
                                      void saveSimpleMealEditor(
                                        actual,
                                      );
                                    } else {
                                      void saveMealEditor(actual);
                                    }
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
                                onClick={closeMealEditor}
                              >
                                Annulla
                              </button>
                            </div>
                          </div>
                        ) : null}
                      </>
                    ) : (
                      <>
                        <strong
                          className={styles.mealName}
                        >
                          {meal.value ||
                            "Nessuna routine abbastanza forte"}
                        </strong>

                        {typeof meal.estimated_calories ===
                        "number" ? (
                          <p className={styles.mealMeta}>
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
                      </>
                    )}

                    {slot === nextMeal?.next_slot &&
                    !actualMealForSlot(slot) &&
                    nextMealOptions?.recommended ? (
                      nextMealOptions.recommended.strategy ===
                      "routine" ? (
                        <div
                          className={
                            styles.replanningCompact
                          }
                        >
                          <span
                            className={
                              styles.replanningCompactIcon
                            }
                            aria-hidden="true"
                          >
                            ✓
                          </span>

                          <div>
                            <strong>
                              {nextMealOptions
                                .replanning_context?.title ??
                                "Già adatta alla giornata"}
                            </strong>
                            <p>
                              {nextMealOptions
                                .replanning_context?.message ??
                                "Il tuo pasto abituale va bene così com'è oggi."}
                            </p>
                          </div>
                        </div>
                      ) : (
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
                              {nextMealOptions.recommended
                                .strategy ===
                              "adapted_routine"
                                ? "Adattata alla tua giornata"
                                : "Oggi ti conviene cambiare"}
                            </span>
                          </div>

                          <strong
                            className={
                              styles.replanningMealName
                            }
                          >
                            {
                              nextMealOptions.recommended
                                .candidate.name
                            }
                          </strong>

                          <p
                            className={
                              styles.replanningNutrition
                            }
                          >
                            {typeof nextMealOptions.recommended
                              .recommended_quantity === "number"
                              ? `${roundNumber(
                                  nextMealOptions.recommended
                                    .recommended_quantity,
                                )} porz. · `
                              : ""}
                            {roundNumber(
                              nextMealOptions.recommended
                                .candidate.calories,
                            )}{" "}
                            kcal
                            {typeof nextMealOptions
                              .recommended.candidate
                              .protein_g === "number"
                              ? ` · ${roundNumber(
                                  nextMealOptions.recommended
                                    .candidate.protein_g,
                                )} g proteine`
                              : ""}
                          </p>

                          <div>
                            {nextMealOptions
                              .replanning_context?.title ? (
                              <strong
                                className={
                                  styles.replanningContextTitle
                                }
                              >
                                {
                                  nextMealOptions
                                    .replanning_context.title
                                }
                              </strong>
                            ) : null}

                            <p
                              className={
                                styles.replanningReason
                              }
                            >
                              {nextMealOptions
                                .replanning_context?.message ??
                                nextMealOptions.recommended
                                  .reason}
                            </p>
                          </div>
                        </div>
                      )
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
