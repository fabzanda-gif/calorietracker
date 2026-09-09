"use client";

import { AppNav } from "@/components/navigation/AppNav";
import { WelcomeJourney } from "@/components/onboarding/WelcomeJourney";
import {
  DayPlanner,
  type DayType,
  type ActivityLevel,
} from "@/components/home/DayPlanner";

import {
  buildDayMessage,
  buildDayMessageContext,
} from "@/components/home/dayMessage";
import {
  getDayHistory,
  type DayHistoryResponse,
} from "@/lib/api/dayHistory";
import {
  createActivity,
  getActivitiesForDate,
  getPlannedActivities,
  type Activity,
  type PlannedActivity,
} from "@/lib/api/activities";

import {
  getStrengthPlanDetail,
  getStrengthPlans,
  type StrengthWorkout,
} from "@/lib/api/strength";

import {
  type DragEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { createPortal } from "react-dom";

import { useAuth } from "@/components/auth/AuthProvider";
import { confirmMealPrediction } from "@/lib/api/confirm";
import { commitMealDecision } from "@/lib/api/decision";
import {
  createMeal,
  logPantryMeal,
  confirmConversationalMeal,
  deleteMeal,
  getMeal,
  getMealHistory,
  getMealsForDate,
  previewConversationalMeal,
  previewPhotoMeal,
  updateMeal,
  type ConversationalMealPreview,
  type LoggedMeal,
  type StructuredMealIngredient,
} from "@/lib/api/meals";
import {
  previewConversationalDay,
  type ConversationalDayPreview,
} from "@/lib/api/conversation";
import {
  getRecipes,
  type Recipe,
} from "@/lib/api/recipes";
import {
  getIngredients,
  type Ingredient,
} from "@/lib/api/ingredients";
import {
  getPantry,
  type PantryItem,
} from "@/lib/api/pantry";
import {
  getMealPrepInventory,
  logMealPrepPortion,
  type MealPrepItem,
} from "@/lib/api/mealPrep";
import {
  getDay,
  getDayBriefing,
  getDayBudget,
  getMealOptions,
  getNextMeal,
  updateDailyLog,
} from "@/lib/api/day";
import type {
  DayBudgetResponse,
  DayResponse,
  MealOptionsResponse,
  NextMealResponse,
  RankedMealOption,
} from "@/lib/api/types";

import {
  nextMealType,
} from "@/lib/mealSlots";

import {
  createWeight,
  getLatestWeight,
  getWeightHistory,
  updateWeight,
  type WeightEntry,
} from "@/lib/api/weight";
import {
  getProfile,
  type ProfileResponse,
} from "@/lib/api/profile";

import { useExperienceMode } from "@/components/experience/ExperienceModeProvider";

import styles from "./HomeShell.module.css";

function localIsoDate(
  date: Date,
): string {
  const year = date.getFullYear();
  const month = String(
    date.getMonth() + 1,
  ).padStart(2, "0");
  const day = String(
    date.getDate(),
  ).padStart(2, "0");

  return `${year}-${month}-${day}`;
}


function todayIso(): string {
  return localIsoDate(new Date());
}


function futureIso(
  days: number,
): string {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  date.setDate(
    date.getDate() + days,
  );

  return localIsoDate(date);
}


function plannedTrainingDateLabel(
  value: string,
): string {
  if (value === todayIso()) {
    return "Oggi";
  }

  if (value === futureIso(1)) {
    return "Domani";
  }

  return new Date(
    `${value}T00:00:00`,
  ).toLocaleDateString(
    "it-IT",
    {
      weekday: "long",
      day: "numeric",
      month: "short",
    },
  );
}


function plannedTrainingKindLabel(
  value?: string | null,
): string {
  return {
    easy: "Facile",
    recovery: "Recupero",
    tempo: "Tempo",
    interval: "Intervalli",
    long: "Lungo",
    race: "Gara",
  }[value ?? ""] ?? "Corsa";
}

function strengthFocusLabel(
  value?: string | null,
): string {
  return {
    full_body: "Full body",
    upper: "Upper",
    lower: "Lower",
    push: "Push",
    pull: "Pull",
    legs: "Gambe",
  }[value ?? ""] ?? "Palestra";
}


function briefingMoment():
  "morning" | "afternoon" | "evening" {
  const hour = new Date().getHours();

  if (hour < 12) {
    return "morning";
  }

  if (hour < 18) {
    return "afternoon";
  }

  return "evening";
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
    snack: "Snack",
    dinner: "Cena",
  }[slot] ?? slot;
}

function mealIcon(slot: string): string {
  return {
    breakfast: "☕",
    lunch: "🍽️",
    snack: "🍎",
    dinner: "🍲",
  }[slot] ?? "🍴";
}

function normalizedMealSlot(value: string):
  "breakfast" | "lunch" | "dinner" | "snack" | "unknown" {
  const normalized = value.trim().toLocaleLowerCase("it");

  if (["colazione", "breakfast"].includes(normalized)) return "breakfast";
  if (["pranzo", "lunch"].includes(normalized)) return "lunch";
  if (["cena", "dinner"].includes(normalized)) return "dinner";
  if (["spuntino", "snack"].includes(normalized)) return "snack";
  return "unknown";
}

function mealFitsSlot(candidate: string, selected: string): boolean {
  const candidateSlot = normalizedMealSlot(candidate);
  const selectedSlot = normalizedMealSlot(selected);

  if (selectedSlot === "breakfast" || selectedSlot === "snack") {
    return candidateSlot === selectedSlot;
  }

  if (selectedSlot === "lunch" || selectedSlot === "dinner") {
    return candidateSlot === "lunch" || candidateSlot === "dinner";
  }

  return false;
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

function normalizeDayType(
  value: unknown,
): DayType {
  const normalized = String(value ?? "")
    .trim()
    .toLowerCase();

  if (
    normalized === "home" ||
    normalized.includes("casa")
  ) {
    return "home";
  }

  if (
    normalized === "free" ||
    normalized === "rest" ||
    normalized.includes("liber")
  ) {
    return "free";
  }

  return "office";
}

type DashboardWidgetSize = 4 | 8 | 12;

type DashboardWidgetId =
  | "meals"
  | "ai"
  | "dinner"
  | "quick-add"
  | "weight"
  | "goal"
  | "summary";

const DEFAULT_DASHBOARD_ORDER: DashboardWidgetId[] = [
  "meals",
  "ai",
  "dinner",
  "quick-add",
  "weight",
  "goal",
  "summary",
];

const DASHBOARD_ORDER_KEY =
  "sanosync-dashboard-widget-order";

const DASHBOARD_SIZE_KEY =
  "sanosync-dashboard-widget-sizes";

const DEFAULT_DASHBOARD_SIZES:
  Record<DashboardWidgetId, DashboardWidgetSize> = {
    meals: 8,
    ai: 4,
    dinner: 12,
    "quick-add": 12,
    weight: 8,
    goal: 4,
    summary: 12,
  };

function readDashboardOrder(): DashboardWidgetId[] {
  if (typeof window === "undefined") {
    return DEFAULT_DASHBOARD_ORDER;
  }

  try {
    const stored = JSON.parse(
      window.localStorage.getItem(
        DASHBOARD_ORDER_KEY,
      ) ?? "null",
    );

    if (
      Array.isArray(stored) &&
      DEFAULT_DASHBOARD_ORDER.every(
        (widget) => stored.includes(widget),
      )
    ) {
      return stored as DashboardWidgetId[];
    }
  } catch {
    // Usa l'ordine iniziale se il dato locale non è valido.
  }

  return DEFAULT_DASHBOARD_ORDER;
}

function readDashboardSizes():
  Record<DashboardWidgetId, DashboardWidgetSize> {
  if (typeof window === "undefined") {
    return DEFAULT_DASHBOARD_SIZES;
  }

  try {
    const stored = JSON.parse(
      window.localStorage.getItem(
        DASHBOARD_SIZE_KEY,
      ) ?? "null",
    );

    if (
      stored &&
      typeof stored === "object" &&
      DEFAULT_DASHBOARD_ORDER.every(
        (widget) =>
          stored[widget] === 4 ||
          stored[widget] === 8 ||
          stored[widget] === 12,
      )
    ) {
      return stored as Record<
        DashboardWidgetId,
        DashboardWidgetSize
      >;
    }
  } catch {
    // Usa le dimensioni iniziali.
  }

  return DEFAULT_DASHBOARD_SIZES;
}

type HomeSpeechRecognitionResult = {
  0?: {
    transcript: string;
  };
  length: number;
};

type HomeSpeechRecognitionEvent = {
  results: ArrayLike<HomeSpeechRecognitionResult>;
};

type HomeSpeechRecognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onresult:
    | ((event: HomeSpeechRecognitionEvent) => void)
    | null;
  onerror:
    | ((event: { error?: string }) => void)
    | null;
  onend: (() => void) | null;
};

type HomeSpeechRecognitionConstructor =
  new () => HomeSpeechRecognition;

export function HomeShell() {
  const {
    experienceMode,
    setExperienceMode,
  } = useExperienceMode();

  const [dashboardOrder, setDashboardOrder] =
    useState<DashboardWidgetId[]>(readDashboardOrder);
  const [dashboardSizes, setDashboardSizes] =
    useState<
      Record<DashboardWidgetId, DashboardWidgetSize>
    >(readDashboardSizes);
  const [
    customizingDashboard,
    setCustomizingDashboard,
  ] = useState(false);
  const [draggedWidget, setDraggedWidget] =
    useState<DashboardWidgetId | null>(null);

  const [dayPlannerSaving, setDayPlannerSaving] =
    useState(false);
  const [dayPlannerMessage, setDayPlannerMessage] =
    useState<string | null>(null);
  const [dayBriefing, setDayBriefing] =
    useState<string | null>(null);

  const [briefingHour, setBriefingHour] =
    useState(() => new Date().getHours());


  const {
    user,
    accessToken,
  } = useAuth();
  const [onboardingTestCompleted] = useState(
    () =>
      typeof window !== "undefined" &&
      window.sessionStorage.getItem(
        "sanosync-onboarding-test-token",
      ) === accessToken,
  );

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
  const [budgetExpanded, setBudgetExpanded] =
    useState(false);

  const maintenanceBudgetKcal =
    budgetResult?.budget
      ? budgetResult.budget.maintenance_kcal
      : 0;
  const [committingIndex, setCommittingIndex] =
    useState<number | null>(null);
  const [confirmingSlot, setConfirmingSlot] =
    useState<string | null>(null);
  const [alternateSlot, setAlternateSlot] =
    useState<string | null>(null);

  const [quickAddMealSlot, setQuickAddMealSlot] =
    useState<string | null>(null);
  const [quickAddMode, setQuickAddMode] =
    useState<"meal" | "activity" | "weight" | null>(null);

  const [quickActivityName, setQuickActivityName] =
    useState("");
  const [quickActivityCalories, setQuickActivityCalories] =
    useState("");
  const [
    quickActivityDurationMinutes,
    setQuickActivityDurationMinutes,
  ] = useState("");
  const [
    quickActivityDistanceKm,
    setQuickActivityDistanceKm,
  ] = useState("");
  const [quickActivitySaving, setQuickActivitySaving] =
    useState(false);

  const [pantryInventory, setPantryInventory] =
    useState<PantryItem[]>([]);
  const [
    pantryCookableRecipeCount,
    setPantryCookableRecipeCount,
  ] = useState(0);

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

  const [alternateSelectedKey, setAlternateSelectedKey] =
    useState<string | null>(null);

  const [alternateQuantity, setAlternateQuantity] =
    useState(1);

  const [knownAlternates, setKnownAlternates] = useState<Array<{
    key: string;
    name: string;
    mealType: string | null;
    mealSlots: string[] | null;
    calories: number;
    protein: number;
    carbs: number;
    fat: number;
    source:
      | "meal_prep"
      | "pantry"
      | "recipe"
      | "history"
      | "ingredient";
    ingredientId?: string;
    portionGrams?: number;
    pantryItemId?: string;
    pantryExpiresAt?: string | null;
    mealPrepBatchId?: string;
    mealPrepRemaining?: number;
    stockLabel?: string;
  }>>([]);
  const [savingAlternate, setSavingAlternate] =
    useState(false);
  const [commitMessage, setCommitMessage] =
    useState<string | null>(null);
  const [actualDinner, setActualDinner] =
    useState<LoggedMeal | null>(null);
  const [actualMeals, setActualMeals] =
    useState<LoggedMeal[]>([]);

  // HOME WEEK HISTORY V1
  // Reuse meal history already loaded for quick-add suggestions.
  // No additional Home request.
  const [weeklyMealHistory, setWeeklyMealHistory] =
    useState<LoggedMeal[]>([]);

  const [actualActivities, setActualActivities] =
    useState<Activity[]>([]);

  const [plannedActivities, setPlannedActivities] =
    useState<PlannedActivity[]>([]);

  const [
    nextRunningSession,
    setNextRunningSession,
  ] = useState<PlannedActivity | null>(
    null,
  );

  const [
    nextStrengthSession,
    setNextStrengthSession,
  ] = useState<StrengthWorkout | null>(
    null,
  );

  const [latestWeight, setLatestWeight] =
    useState<number | null>(null);
  const [latestWeightEntry, setLatestWeightEntry] =
    useState<WeightEntry | null>(null);

  const [weightQuickAddOpen, setWeightQuickAddOpen] =
    useState(false);
  const [weightQuickAddValue, setWeightQuickAddValue] =
    useState("");
  const [weightQuickAddSaving, setWeightQuickAddSaving] =
    useState(false);
  const [weightHistoryLoading, setWeightHistoryLoading] =
    useState(false);
  const [
    weightQuickAddEditingEntry,
    setWeightQuickAddEditingEntry,
  ] = useState<WeightEntry | null>(null);
  const [weightQuickAddMessage, setWeightQuickAddMessage] =
    useState<string | null>(null);

  const [profile, setProfile] =
    useState<ProfileResponse | null>(null);
  const [showWelcomeJourney, setShowWelcomeJourney] =
    useState(false);
  const [weightHistory, setWeightHistory] =
    useState<WeightEntry[]>([]);

  const [weightRange, setWeightRange] =
    useState<
      "14" | "30" | "90" | "180" | "365" | "all"
    >("30");

  const [dayHistory, setDayHistory] =
    useState<DayHistoryResponse | null>(null);

  const [editingMealId, setEditingMealId] =
    useState<string | number | null>(null);

  // Pannello "I tuoi pasti": mostra una sola fascia alla volta.
  const [selectedMealSlot, setSelectedMealSlot] =
    useState<string>("Colazione");
  const [mealEditType, setMealEditType] =
    useState("Colazione");
  const [
    mealEditRecipeServings,
    setMealEditRecipeServings,
  ] = useState(1);

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
  const [conversationListening, setConversationListening] =
    useState(false);
  const speechRecognitionRef =
    useRef<HomeSpeechRecognition | null>(null);

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
  const [
    conversationDayPreview,
    setConversationDayPreview,
  ] = useState<ConversationalDayPreview | null>(null);
  const [conversationLoading, setConversationLoading] =
    useState(false);
  const [conversationError, setConversationError] =
    useState<string | null>(null);
  const [conversationConfirming, setConversationConfirming] =
    useState(false);
  const [conversationSuccess, setConversationSuccess] =
    useState<string | null>(null);

  const pantryHomeSummary = useMemo(() => {
    const pantryItems =
      knownAlternates.filter(
        (item) => item.source === "pantry",
      );

    const breakfastSnack =
      pantryItems.filter((item) =>
        item.mealSlots?.some(
          (slot) =>
            slot === "breakfast" ||
            slot === "snack",
        ),
      ).length;

    const lunchDinner =
      pantryItems.filter((item) =>
        item.mealSlots?.some(
          (slot) =>
            slot === "lunch" ||
            slot === "dinner",
        ),
      ).length;

    return {
      breakfastSnack,
      lunchDinner,
    };
  }, [knownAlternates]);

  const recommendedMealType = useMemo(
    () =>
      nextMealType(
        actualMeals.map(
          (meal) => meal.meal_type,
        ),
      ),
    [actualMeals],
  );

  useEffect(() => {
    if (!accessToken) return;
    let active = true;

    Promise.allSettled([
      getRecipes(accessToken),
      getMealHistory(accessToken),
      getIngredients(accessToken),
      getPantry(accessToken),
      getMealPrepInventory(accessToken, true),
    ]).then(([
      recipesResult,
      historyResult,
      ingredientsResult,
      pantryResult,
      mealPrepResult,
    ]) => {
      if (!active) return;

      const recipes =
        recipesResult.status === "fulfilled"
          ? recipesResult.value.items
          : [];

      const history =
        historyResult.status === "fulfilled"
          ? historyResult.value.items
          : [];

      setWeeklyMealHistory(history);

      const ingredients =
        ingredientsResult.status === "fulfilled"
          ? ingredientsResult.value.items
          : [];

      const pantry =
        pantryResult.status === "fulfilled"
          ? pantryResult.value.items
          : [];

      const mealPrep =
        mealPrepResult.status === "fulfilled"
          ? mealPrepResult.value.items
          : [];

      setPantryInventory(pantry);

      const availableGramsByIngredient =
        new Map<string, number>();

      pantry.forEach((item) => {
        let grams = 0;

        if (item.quantity_mode === "portion") {
          grams =
            Number(item.quantity || 0) *
            Number(item.grams_per_portion || 0);
        } else {
          const quantity =
            Number(item.quantity || 0);

          const unit =
            String(item.unit || "")
              .trim()
              .toLowerCase();

          if (
            unit === "kg" ||
            unit === "kilogram" ||
            unit === "kilograms"
          ) {
            grams = quantity * 1000;
          } else if (
            unit === "g" ||
            unit === "gr" ||
            unit === "gram" ||
            unit === "grams"
          ) {
            grams = quantity;
          }
        }

        if (grams <= 0) {
          return;
        }

        const key =
          String(item.ingredient_id);

        availableGramsByIngredient.set(
          key,
          (availableGramsByIngredient.get(key) ?? 0) +
            grams,
        );
      });

      const cookableRecipeCount =
        recipes.filter((recipe: Recipe) => {
          const components =
            recipe.structured_ingredients ?? [];

          if (components.length === 0) {
            return false;
          }

          return components.every((component) => {
            const required =
              Number(component.quantity_g || 0);

            const available =
              availableGramsByIngredient.get(
                String(component.ingredient_id),
              ) ?? 0;

            return (
              required > 0 &&
              available >= required
            );
          });
        }).length;

      setPantryCookableRecipeCount(
        cookableRecipeCount,
      );

      const seen = new Set<string>();

      const ingredientPortionGrams = (
        ingredient: Ingredient,
      ): number => {
        const defaultQuantity =
          Number(ingredient.default_quantity);

        const gramsPerUnit =
          Number(ingredient.grams_per_unit);

        if (
          ingredient.default_unit !== "g" &&
          Number.isFinite(defaultQuantity) &&
          defaultQuantity > 0 &&
          Number.isFinite(gramsPerUnit) &&
          gramsPerUnit > 0
        ) {
          return defaultQuantity * gramsPerUnit;
        }

        if (
          ingredient.default_unit === "g" &&
          Number.isFinite(defaultQuantity) &&
          defaultQuantity > 0
        ) {
          return defaultQuantity;
        }

        if (
          Number.isFinite(gramsPerUnit) &&
          gramsPerUnit > 0
        ) {
          return gramsPerUnit;
        }

        return 100;
      };

      const pantryAlternates = [...pantry]
        .sort((left, right) => {
          const leftExpiry =
            left.expires_at ?? "9999-12-31";
          const rightExpiry =
            right.expires_at ?? "9999-12-31";

          return leftExpiry.localeCompare(rightExpiry);
        })
        .flatMap((pantryItem) => {
          const ingredient = ingredients.find(
            (candidate: Ingredient) =>
              String(candidate.id) ===
              String(pantryItem.ingredient_id),
          );

          if (!ingredient) {
            return [];
          }

          const storedPortionGrams =
            pantryItem.quantity_mode === "portion"
              ? Number(
                  pantryItem.grams_per_portion || 0,
                )
              : 0;

          const portionGrams =
            storedPortionGrams > 0
              ? storedPortionGrams
              : ingredientPortionGrams(
                  ingredient,
                );

          const factor = portionGrams / 100;

          return [{
            key: `pantry:${pantryItem.id}`,
            name:
              pantryItem.ingredient_name ||
              ingredient.name,
            mealType: null,
            mealSlots: ingredient.meal_slots ?? [],
            calories:
              Number(
                ingredient.calories_per_100g || 0,
              ) * factor,
            protein:
              Number(
                ingredient.protein_per_100g || 0,
              ) * factor,
            carbs:
              Number(
                ingredient.carbs_per_100g || 0,
              ) * factor,
            fat:
              Number(
                ingredient.fat_per_100g || 0,
              ) * factor,
            source: "pantry" as const,
            ingredientId: ingredient.id,
            portionGrams,
            pantryItemId: String(pantryItem.id),
            pantryExpiresAt: pantryItem.expires_at,
            stockLabel:
              pantryItem.quantity_mode === "portion"
                ? `${pantryItem.quantity} ${
                    Number(pantryItem.quantity) === 1
                      ? "porzione"
                      : "porzioni"
                  }`
                : `${pantryItem.quantity} ${pantryItem.unit}`,
          }];
        });

      const mealPrepAlternates =
        mealPrep.flatMap(
          (batch: MealPrepItem) => {
            const recipe = recipes.find(
              (candidate: Recipe) =>
                String(candidate.id) ===
                String(batch.recipe_id),
            );

            if (!recipe) {
              return [];
            }

            return [{
              key: `meal-prep:${batch.id}`,
              name: batch.name,
              mealType:
                recipe.meal_type || null,
              mealSlots: null,
              calories: Number(
                batch.calories_per_portion || 0,
              ),
              protein: Number(
                batch.protein_per_portion || 0,
              ),
              carbs: Number(
                batch.carbs_per_portion || 0,
              ),
              fat: Number(
                batch.fat_per_portion || 0,
              ),
              source: "meal_prep" as const,
              mealPrepBatchId:
                String(batch.id),
              mealPrepRemaining:
                Number(
                  batch.portions_remaining || 0,
                ),
              stockLabel:
                `${batch.portions_remaining} ${
                  batch.portions_remaining === 1
                    ? "porzione"
                    : "porzioni"
                }`,
            }];
          },
        );

      const items = [
        ...mealPrepAlternates,
        ...pantryAlternates,

        ...recipes.map((recipe: Recipe) => {
          const servings = Math.max(
            1,
            Number(recipe.recipe_servings) || 1,
          );

          return {
            key: `recipe:${recipe.id}`,
            name: recipe.name,
            mealType: recipe.meal_type || "Pranzo",
            mealSlots: null,
            calories:
              Number(recipe.calories || 0) / servings,
            protein:
              Number(recipe.protein || 0) / servings,
            carbs:
              Number(recipe.carbs || 0) / servings,
            fat:
              Number(recipe.fat || 0) / servings,
            source: "recipe" as const,
          };
        }),

        ...history.map((meal) => {
          const quantity = Math.max(
            0.01,
            Number(meal.quantity) || 1,
          );

          const factor = meal.is_per_100g
            ? 100 / quantity
            : 1 / quantity;

          return {
            key:
              `history:${
                meal.id ??
                `${meal.date}:${meal.name}`
              }`,
            name: meal.base_name || meal.name,
            mealType:
              meal.meal_type || "Pranzo",
            mealSlots: null,
            calories: Number(
              meal.base_calories ??
                Number(meal.calories || 0) *
                  factor,
            ),
            protein: Number(
              meal.base_protein ??
                Number(meal.protein || 0) *
                  factor,
            ),
            carbs: Number(
              meal.base_carbs ??
                Number(meal.carbs || 0) *
                  factor,
            ),
            fat: Number(
              meal.base_fat ??
                Number(meal.fat || 0) *
                  factor,
            ),
            source: "history" as const,
          };
        }),

        ...ingredients.map(
          (ingredient: Ingredient) => {
            const portionGrams =
              ingredientPortionGrams(
                ingredient,
              );

            const factor =
              portionGrams / 100;

            return {
              key: `ingredient:${ingredient.id}`,
              name: ingredient.name,
              mealType: null,
              mealSlots: ingredient.meal_slots ?? [],
              ingredientId: ingredient.id,
              portionGrams,
              calories:
                Number(
                  ingredient.calories_per_100g ||
                    0,
                ) * factor,
              protein:
                Number(
                  ingredient.protein_per_100g ||
                    0,
                ) * factor,
              carbs:
                Number(
                  ingredient.carbs_per_100g ||
                    0,
                ) * factor,
              fat:
                Number(
                  ingredient.fat_per_100g ||
                    0,
                ) * factor,
              source: "ingredient" as const,
            };
          },
        ),
      ].filter((item) => {
        const key = `${item.source}:${item.name
          .trim()
          .toLocaleLowerCase("it")}`;

        if (!item.name.trim() || seen.has(key)) {
          return false;
        }

        seen.add(key);
        return true;
      });

      setKnownAlternates(items);
    });

    return () => { active = false; };
  }, [accessToken]);

  useEffect(() => {
    if (
      conversationPreview ||
      conversationDayPreview ||
      conversationText.trim() ||
      conversationPhoto
    ) {
      return;
    }

    setConversationMealType(
      recommendedMealType,
    );
  }, [
    recommendedMealType,
    conversationPreview,
    conversationDayPreview,
    conversationText,
    conversationPhoto,
  ]);


  function resizeDashboardWidget(
    widget: DashboardWidgetId,
    direction: -1 | 1,
  ) {
    const allowedSizes: DashboardWidgetSize[] =
      widget === "ai" || widget === "goal"
        ? [4, 8, 12]
        : [8, 12];

    const currentSize = dashboardSizes[widget];
    const currentIndex = allowedSizes.indexOf(
      currentSize,
    );
    const safeIndex =
      currentIndex >= 0 ? currentIndex : 0;
    const nextIndex = Math.min(
      allowedSizes.length - 1,
      Math.max(0, safeIndex + direction),
    );

    if (nextIndex === safeIndex) {
      return;
    }

    const nextSizes = {
      ...dashboardSizes,
      [widget]: allowedSizes[nextIndex],
    };

    setDashboardSizes(nextSizes);
    window.localStorage.setItem(
      DASHBOARD_SIZE_KEY,
      JSON.stringify(nextSizes),
    );
  }

  function saveDashboardOrder(
    nextOrder: DashboardWidgetId[],
  ) {
    setDashboardOrder(nextOrder);

    window.localStorage.setItem(
      DASHBOARD_ORDER_KEY,
      JSON.stringify(nextOrder),
    );
  }

  function moveDashboardWidget(
    widget: DashboardWidgetId,
    direction: -1 | 1,
  ) {
    const currentIndex = dashboardOrder.indexOf(widget);
    const nextIndex = currentIndex + direction;

    if (
      currentIndex < 0 ||
      nextIndex < 0 ||
      nextIndex >= dashboardOrder.length
    ) {
      return;
    }

    const nextOrder = [...dashboardOrder];
    [
      nextOrder[currentIndex],
      nextOrder[nextIndex],
    ] = [
      nextOrder[nextIndex],
      nextOrder[currentIndex],
    ];

    saveDashboardOrder(nextOrder);
  }

  function dashboardWidgetProps(
    widget: DashboardWidgetId,
  ) {
    return {
      draggable: customizingDashboard,
      style: {
        order: dashboardOrder.indexOf(widget),
      },
      "data-widget-size":
        dashboardSizes[widget],
      "aria-grabbed":
        customizingDashboard
          ? draggedWidget === widget
          : undefined,
      onDragStart: () => {
        if (customizingDashboard) {
          setDraggedWidget(widget);
        }
      },
      onDragOver: (
        event: DragEvent<HTMLElement>,
      ) => {
        if (customizingDashboard) {
          event.preventDefault();
        }
      },
      onDrop: () => {
        if (
          !customizingDashboard ||
          !draggedWidget ||
          draggedWidget === widget
        ) {
          return;
        }

        const nextOrder = dashboardOrder.filter(
          (item) => item !== draggedWidget,
        );
        const targetIndex =
          nextOrder.indexOf(widget);

        nextOrder.splice(
          targetIndex,
          0,
          draggedWidget,
        );

        saveDashboardOrder(nextOrder);
        setDraggedWidget(null);
      },
      onDragEnd: () => setDraggedWidget(null),
    };
  }

  function dashboardWidgetControls(
    widget: DashboardWidgetId,
    label: string,
  ) {
    if (!customizingDashboard) {
      return null;
    }

    const position = dashboardOrder.indexOf(widget);

    return (
      <div className={styles.widgetControls}>
        <span>Trascina {label}</span>

        <div className={styles.widgetControlActions}>
          <div className={styles.widgetSizeControls}>
            <button
              type="button"
              aria-label={`Riduci ${label}`}
              disabled={
                dashboardSizes[widget] <=
                (
                  widget === "ai" ||
                  widget === "goal"
                    ? 4
                    : 8
                )
              }
              onClick={() =>
                resizeDashboardWidget(widget, -1)
              }
            >
              −
            </button>

            <span>
              {dashboardSizes[widget] === 4
                ? "Compatto"
                : dashboardSizes[widget] === 8
                ? "Medio"
                : "Largo"}
            </span>

            <button
              type="button"
              aria-label={`Allarga ${label}`}
              disabled={dashboardSizes[widget] >= 12}
              onClick={() =>
                resizeDashboardWidget(widget, 1)
              }
            >
              +
            </button>
          </div>

          <button
            type="button"
            aria-label={`Sposta ${label} prima`}
            disabled={position <= 0}
            onClick={() =>
              moveDashboardWidget(widget, -1)
            }
          >
            ↑
          </button>

          <button
            type="button"
            aria-label={`Sposta ${label} dopo`}
            disabled={
              position >= dashboardOrder.length - 1
            }
            onClick={() =>
              moveDashboardWidget(widget, 1)
            }
          >
            ↓
          </button>
        </div>
      </div>
    );
  }

  useEffect(() => {
    let timeoutId: ReturnType<
      typeof setTimeout
    >;

    function scheduleNextHour() {
      const now = new Date();
      const nextHour = new Date(now);

      nextHour.setHours(
        now.getHours() + 1,
        0,
        0,
        50,
      );

      timeoutId = setTimeout(() => {
        setBriefingHour(
          new Date().getHours(),
        );
        scheduleNextHour();
      }, Math.max(
        1000,
        nextHour.getTime() - now.getTime(),
      ));
    }

    scheduleNextHour();

    return () => {
      clearTimeout(timeoutId);
    };
  }, []);


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
      setNextStrengthSession(null);
      return;
    }

    let active = true;

    async function loadStrengthTraining() {
      try {
        const plans = await getStrengthPlans(
          accessToken,
        );

        const activePlan = plans.items.find(
          (item) =>
            item.status === "active",
        );

        if (!activePlan) {
          if (active) {
            setNextStrengthSession(null);
          }
          return;
        }

        const detail =
          await getStrengthPlanDetail(
            activePlan.id,
            accessToken,
          );

        const nextWorkout = [
          ...detail.workouts,
        ]
          .filter(
            (item) =>
              item.status === "planned",
          )
          .sort(
            (left, right) =>
              left.scheduled_date.localeCompare(
                right.scheduled_date,
              ) ||
              left.workout_index -
                right.workout_index,
          )[0] ?? null;

        if (active) {
          setNextStrengthSession(
            nextWorkout,
          );
        }
      } catch {
        // Strength is an optional Home enhancement.
        if (active) {
          setNextStrengthSession(null);
        }
      }
    }

    void loadStrengthTraining();

    return () => {
      active = false;
    };
  }, [accessToken]);


  const recentWeights = useMemo(() => {
    const sorted = [...weightHistory].sort(
      (left, right) =>
        new Date(left.date).getTime() -
        new Date(right.date).getTime(),
    );

    if (weightRange === "all") {
      return sorted;
    }

    const days = Number(weightRange);
    const cutoff = new Date();
    cutoff.setHours(0, 0, 0, 0);
    cutoff.setDate(
      cutoff.getDate() - days + 1,
    );

    return sorted.filter(
      (entry) =>
        new Date(entry.date).getTime() >=
        cutoff.getTime(),
    );
  }, [weightHistory, weightRange]);

  const weightChartPoints = useMemo(() => {
    if (!recentWeights.length) {
      return "";
    }

    const values = recentWeights.map(
      (entry) => Number(entry.weight),
    );
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    const range = Math.max(maximum - minimum, 1);

    return recentWeights
      .map((entry, index) => {
        const x =
          recentWeights.length === 1
            ? 150
            : 12 +
              (index /
                (recentWeights.length - 1)) *
                276;
        const y =
          92 -
          ((Number(entry.weight) - minimum) /
            range) *
            72;

        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }, [recentWeights]);

  const weightChange =
    recentWeights.length >= 2
      ? Number(
          (
            Number(
              recentWeights[
                recentWeights.length - 1
              ].weight,
            ) -
            Number(recentWeights[0].weight)
          ).toFixed(1),
        )
      : null;

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

        const homeLoadStartedAt =
          performance.now();

        async function timedHomeRequest<T>(
          label: string,
          request: Promise<T>,
        ): Promise<T> {
          const startedAt = performance.now();

          try {
            const result = await request;

            console.info(
              `[Home perf] ${label}: ${(
                performance.now() - startedAt
              ).toFixed(0)} ms`,
            );

            return result;
          } catch (error) {
            console.info(
              `[Home perf] ${label}: FAILED after ${(
                performance.now() - startedAt
              ).toFixed(0)} ms`,
            );

            throw error;
          }
        }

        const [
          dayPayload,
          budgetPayload,
          nextMealPayload,
          mealsPayload,
          activitiesPayload,
          plannedActivitiesPayload,
          latestWeightPayload,
          profilePayload,
        ] = await Promise.all([
          timedHomeRequest(
            "day",
            getDay(
              date,
              accessToken,
            ),
          ),
          timedHomeRequest(
            "budget",
            getDayBudget(
              date,
              accessToken,
            ),
          ),
          timedHomeRequest(
            "next-meal",
            getNextMeal(
              date,
              accessToken,
            ),
          ),
          timedHomeRequest(
            "meals",
            getMealsForDate(
              date,
              accessToken,
            ),
          ),
          timedHomeRequest(
            "activities",
            getActivitiesForDate(
              date,
              accessToken,
            ),
          ),
          timedHomeRequest(
            "planned-activities",
            getPlannedActivities(
              date,
              futureIso(7),
              accessToken,
            ),
          ),
          timedHomeRequest(
            "latest-weight",
            getLatestWeight(
              accessToken,
            ),
          ),
          timedHomeRequest(
            "profile",
            getProfile(accessToken),
          ),
        ]);

        console.info(
          `[Home perf] CORE READY: ${(
            performance.now() -
            homeLoadStartedAt
          ).toFixed(0)} ms`,
        );

        if (active) {
          setDay(dayPayload);
          setBudgetResult(budgetPayload);
          setNextMeal(nextMealPayload);
          setActualMeals(mealsPayload.items);
          setActualActivities(
            activitiesPayload.items,
          );
          setPlannedActivities(plannedActivitiesPayload.items);

          setNextRunningSession(
            plannedActivitiesPayload.items
              .filter(
                (item) =>
                  item.status === "planned" &&
                  Boolean(
                    item.training_plan_id,
                  ) &&
                  item.activity_type
                    .trim()
                    .toLocaleLowerCase(
                      "it-IT",
                    ) === "corsa",
              )
              .sort(
                (left, right) =>
                  left.scheduled_date.localeCompare(
                    right.scheduled_date,
                  ) ||
                  (
                    left.scheduled_time ?? ""
                  ).localeCompare(
                    right.scheduled_time ?? "",
                  ),
              )[0] ?? null,
          );

          setLatestWeightEntry(
            latestWeightPayload.item ?? null,
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

          setProfile(profilePayload);

          const metadata = profilePayload.metadata;
          setShowWelcomeJourney(
            metadata.onboarding_completed !== true &&
              (!metadata.gender ||
                !metadata.birth_date ||
                !metadata.height ||
                latestWeightPayload.item?.weight == null),
          );

          // The usable home is ready. AI briefing, recommendations and
          // history are enhancements and must never hold up first paint.
          setLoading(false);

          void timedHomeRequest(
            "AI day-briefing",
            getDayBriefing(
              date,
              briefingMoment(),
              experienceMode,
              briefingHour,
              accessToken,
            ),
          ).then((payload) => {
            if (active) setDayBriefing(payload.message);
          }).catch(() => undefined);

          if (nextMealPayload.next_slot) {
            void timedHomeRequest(
              "meal-options",
              getMealOptions(
                date,
                nextMealPayload.next_slot,
                "auto",
                accessToken,
              ),
            ).then((payload) => {
              if (!active) return;
              setNextMealOptions(payload);
              setDinnerOptions(
                nextMealPayload.next_slot === "dinner"
                  ? payload
                  : null,
              );
            }).catch(() => undefined);
          }

          void getDayHistory(accessToken)
            .then((payload) => {
              if (active) setDayHistory(payload);
            })
            .catch(() => undefined);
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
  }, [accessToken, experienceMode, briefingHour]);

  const budget =
    budgetResult?.budget ?? null;

  const bmr = Number(budgetResult?.profile?.bmr ?? 0);
  const onboardingTestEmails = [
    process.env.NEXT_PUBLIC_ONBOARDING_TEST_EMAIL,
    process.env.NEXT_PUBLIC_ONBOARDING_TEST_EMAILS,
  ]
    .filter(Boolean)
    .flatMap((value) => String(value).split(","))
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);
  const onboardingTestIds = String(
    process.env.NEXT_PUBLIC_ONBOARDING_TEST_USER_IDS ??
      process.env.NEXT_PUBLIC_ONBOARDING_TEST_USER_ID ??
      "",
  ).split(",").map((value) => value.trim()).filter(Boolean);
  const isOnboardingTestAccount = Boolean(
    (user?.email && onboardingTestEmails.includes(user.email.trim().toLowerCase())) ||
      (user?.id && onboardingTestIds.includes(user.id)),
  );
  const needsWelcomeJourney =
    (((showWelcomeJourney || budgetResult?.status === "profile_incomplete") &&
      profile?.metadata.onboarding_completed !== true) ||
      (isOnboardingTestAccount && !onboardingTestCompleted));

  const burnedCalories = actualActivities.reduce(
    (total, activity) =>
      total + Number(activity.burned_calories || 0),
    0,
  );

  const currentDayType = day
    ? normalizeDayType(day.context.value)
    : null;

  const dayBriefingBody =
    dayBriefing
      ?.replace(/^[^!]+!\s*/, "")
      .trim() || null;

  const historicalProfile =
    currentDayType && dayHistory
      ? dayHistory.profiles[currentDayType]
      : null;

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

  /*
   * HOME BOTTOM OVERVIEW — derived only from data Home
   * already has. No additional blocking request.
   */
  const macroBudget = budget as
    | (typeof budget & {
        carbs_target_g?: number | null;
        carbs_consumed_g?: number | null;
        carbohydrates_target_g?: number | null;
        carbohydrates_consumed_g?: number | null;
        fat_target_g?: number | null;
        fat_consumed_g?: number | null;
      })
    | null;

  const carbsConsumed = Number(
    macroBudget?.carbs_consumed_g ??
      macroBudget?.carbohydrates_consumed_g ??
      actualMeals.reduce(
        (total, meal) =>
          total + Number(meal.carbs || 0),
        0,
      ),
  );

  const carbsTarget = Number(
    macroBudget?.carbs_target_g ??
      macroBudget?.carbohydrates_target_g ??
      0,
  );

  const fatConsumed = Number(
    macroBudget?.fat_consumed_g ??
      actualMeals.reduce(
        (total, meal) =>
          total + Number(meal.fat || 0),
        0,
      ),
  );

  const fatTarget = Number(
    macroBudget?.fat_target_g ?? 0,
  );

  function focusProgress(
    consumed: number,
    target: number,
  ) {
    if (!target || target <= 0) {
      return 0;
    }

    return Math.min(
      100,
      Math.max(
        0,
        (consumed / target) * 100,
      ),
    );
  }

  const dailyFocusItems = [
    {
      label: "Calorie",
      icon: "🔥",
      consumed: Number(
        budget?.consumed_kcal ?? 0,
      ),
      target: Number(
        budget?.daily_budget_kcal ?? 0,
      ),
      unit: "kcal",
      progress: budgetProgress,
    },
    {
      label: "Proteine",
      icon: "💪",
      consumed: Number(
        budget?.protein_consumed_g ?? 0,
      ),
      target: Number(
        budget?.protein_target_g ?? 0,
      ),
      unit: "g",
      progress: proteinProgress,
    },
    {
      label: "Carboidrati",
      icon: "🌾",
      consumed: carbsConsumed,
      target: carbsTarget,
      unit: "g",
      progress: focusProgress(
        carbsConsumed,
        carbsTarget,
      ),
    },
    {
      label: "Grassi",
      icon: "🥑",
      consumed: fatConsumed,
      target: fatTarget,
      unit: "g",
      progress: focusProgress(
        fatConsumed,
        fatTarget,
      ),
    },
  ];

  const todayForWeek = new Date(
    `${todayIso()}T12:00:00`,
  );

  const mondayForWeek = new Date(
    todayForWeek,
  );

  mondayForWeek.setDate(
    todayForWeek.getDate() -
      ((todayForWeek.getDay() + 6) % 7),
  );

  const weekOverviewDays = Array.from(
    { length: 7 },
    (_, index) => {
      const date = new Date(mondayForWeek);

      date.setDate(
        mondayForWeek.getDate() + index,
      );

      const iso = [
        date.getFullYear(),
        String(date.getMonth() + 1).padStart(
          2,
          "0",
        ),
        String(date.getDate()).padStart(
          2,
          "0",
        ),
      ].join("-");

      return {
        iso,
        shortLabel:
          date
            .toLocaleDateString("it-IT", {
              weekday: "short",
            })
            .replace(".", "")
            .slice(0, 2),
        dayNumber: date.getDate(),
        isToday: iso === todayIso(),
        mealCount: weeklyMealHistory.filter(
          (meal) => meal.date === iso,
        ).length,
      };
    },
  );

  const weeklyMealCount =
    weekOverviewDays.reduce(
      (total, item) => total + item.mealCount,
      0,
    );

  const weeklyMealDays =
    weekOverviewDays.filter(
      (item) => item.mealCount > 0,
    ).length;

  async function openWeightQuickAdd(
    entry: WeightEntry | null = null,
    scrollToOverview = true,
  ) {
    setWeightQuickAddMessage(null);
    setWeightQuickAddOpen(true);

    let history = weightHistory;

    if (accessToken && history.length === 0) {
      setWeightHistoryLoading(true);

      try {
        const payload =
          await getWeightHistory(accessToken);

        history = payload.items;
        setWeightHistory(history);
      } catch {
        // L'editor resta utilizzabile anche se lo storico fallisce.
      } finally {
        setWeightHistoryLoading(false);
      }
    }

    const todayEntry =
      history.find(
        (item) => item.date === todayIso(),
      ) ?? null;

    const selectedEntry =
      entry ?? todayEntry;

    setWeightQuickAddEditingEntry(
      selectedEntry,
    );

    setWeightQuickAddValue(
      selectedEntry
        ? String(
            Number(
              Number(
                selectedEntry.weight,
              ).toFixed(1),
            ),
          )
        : "",
    );

    if (scrollToOverview) {
      window.requestAnimationFrame(() => {
        document
          .getElementById("home-week-overview")
          ?.scrollIntoView({
            behavior: "smooth",
            block: "center",
          });
      });
    }
  }

  async function saveWeightQuickAdd() {
    if (!accessToken) {
      return;
    }

    const weight = Number(
      weightQuickAddValue.replace(",", "."),
    );

    if (!Number.isFinite(weight) || weight <= 0) {
      setWeightQuickAddMessage(
        "Inserisci un peso valido.",
      );
      return;
    }

    setWeightQuickAddSaving(true);
    setWeightQuickAddMessage(null);

    try {
      const editingEntry =
        weightQuickAddEditingEntry;

      const result = editingEntry
        ? await updateWeight(
            editingEntry.id,
            { weight },
            accessToken,
          )
        : await createWeight(
            {
              date: todayIso(),
              weight,
            },
            accessToken,
          );

      const savedEntry: WeightEntry =
        result.item ?? {
          id:
            editingEntry?.id ??
            `weight-${todayIso()}`,
          date:
            editingEntry?.date ??
            todayIso(),
          weight,
        };

      setWeightHistory((current) => {
        const withoutSaved =
          current.filter(
            (item) =>
              String(item.id) !==
              String(savedEntry.id),
          );

        return [
          ...withoutSaved,
          savedEntry,
        ];
      });

      setWeightQuickAddEditingEntry(
        savedEntry,
      );

      if (
        !latestWeightEntry ||
        String(savedEntry.id) ===
          String(latestWeightEntry.id) ||
        savedEntry.date >= latestWeightEntry.date
      ) {
        setLatestWeightEntry(savedEntry);
        setLatestWeight(
          Number(savedEntry.weight),
        );
      }

      setWeightQuickAddValue(
        String(
          Number(
            Number(
              savedEntry.weight,
            ).toFixed(1),
          ),
        ),
      );

      setWeightQuickAddMessage(
        editingEntry
          ? "Peso aggiornato."
          : "Peso di oggi registrato.",
      );
    } catch (err) {
      setWeightQuickAddMessage(
        err instanceof Error
          ? err.message
          : "Non riesco a salvare il peso.",
      );
    } finally {
      setWeightQuickAddSaving(false);
    }
  }

  useEffect(() => {
    return () => {
      speechRecognitionRef.current?.stop();
    };
  }, []);

  function toggleConversationDictation() {
    if (conversationListening) {
      speechRecognitionRef.current?.stop();
      return;
    }

    const speechWindow =
      window as typeof window & {
        SpeechRecognition?:
          HomeSpeechRecognitionConstructor;
        webkitSpeechRecognition?:
          HomeSpeechRecognitionConstructor;
      };

    const Recognition =
      speechWindow.SpeechRecognition ??
      speechWindow.webkitSpeechRecognition;

    if (!Recognition) {
      setConversationError(
        "Il riconoscimento vocale non è disponibile in questo browser.",
      );
      return;
    }

    const recognition = new Recognition();
    const startingText =
      conversationText.trim();

    recognition.lang = "it-IT";
    recognition.continuous = false;
    recognition.interimResults = true;

    recognition.onresult = (event) => {
      let transcript = "";

      for (
        let index = 0;
        index < event.results.length;
        index += 1
      ) {
        transcript +=
          event.results[index][0]
            ?.transcript ?? "";
      }

      const spoken = transcript.trim();

      setConversationText(
        startingText && spoken
          ? `${startingText} ${spoken}`
          : spoken || startingText,
      );
    };

    recognition.onerror = (event) => {
      if (
        event.error !== "aborted" &&
        event.error !== "no-speech"
      ) {
        setConversationError(
          "Non sono riuscito a capire l'audio. Riprova.",
        );
      }
    };

    recognition.onend = () => {
      speechRecognitionRef.current = null;
      setConversationListening(false);
    };

    speechRecognitionRef.current =
      recognition;

    setConversationError(null);
    setConversationListening(true);

    recognition.start();
  }

  async function analyzeConversationDay() {
    if (!accessToken || !conversationText.trim()) {
      return;
    }

    setConversationLoading(true);
    setConversationError(null);
    setConversationPreview(null);
    setConversationDayPreview(null);
    setConversationSuccess(null);

    try {
      const preview =
        await previewConversationalDay(
          conversationText.trim(),
          conversationMealType,
          accessToken,
        );

      setConversationDayPreview(preview);
    } catch (err) {
      setConversationError(
        err instanceof Error
          ? err.message
          : "Non riesco a interpretare questa registrazione.",
      );
    } finally {
      setConversationLoading(false);
    }
  }


  async function confirmConversationDay() {
    if (
      !accessToken ||
      !conversationDayPreview ||
      !conversationDayPreview.actions.length
    ) {
      return;
    }

    setConversationConfirming(true);
    setConversationError(null);
    setConversationSuccess(null);

    const originalPreview =
      conversationDayPreview;

    let remainingActions = [
      ...originalPreview.actions,
    ];

    let completed = 0;

    try {
      for (const action of originalPreview.actions) {
        if (action.kind === "meal") {
          await confirmConversationalMeal(
            {
              date: todayIso(),
              meal_type: action.meal_type,
              items: action.items,
            },
            accessToken,
          );
        } else if (action.kind === "activity") {
          await createActivity(
            {
              date: todayIso(),
              activity_name:
                action.activity_name,
              burned_calories:
                Math.max(
                  0,
                  Math.round(
                    action.burned_calories,
                  ),
                ),
              activity_type:
                action.activity_type,
              duration_seconds:
                action.duration_seconds ??
                undefined,
              distance_meters:
                action.distance_meters ??
                undefined,
            },
            accessToken,
          );
        } else {
          const result = await createWeight(
            {
              date: todayIso(),
              weight: action.weight_kg,
            },
            accessToken,
          );

          const savedEntry =
            result.item ?? null;

          setLatestWeight(
            Number(action.weight_kg),
          );

          if (savedEntry) {
            setLatestWeightEntry(savedEntry);

            setWeightHistory((current) => [
              ...current.filter(
                (item) =>
                  String(item.id) !==
                    String(savedEntry.id) &&
                  item.date !==
                    savedEntry.date,
              ),
              savedEntry,
            ]);
          }
        }

        completed += 1;

        remainingActions =
          remainingActions.filter(
            (item) => item.id !== action.id,
          );

        if (remainingActions.length) {
          setConversationDayPreview({
            ...originalPreview,
            actions: remainingActions,
            needs_review:
              remainingActions.some(
                (item) => item.needs_review,
              ),
          });
        }
      }

      setConversationSuccess(
        completed === 1
          ? "Registrazione completata. Ho aggiornato la tua giornata."
          : `${completed} registrazioni completate. Ho aggiornato la tua giornata.`,
      );

      setConversationText("");
      setConversationPreview(null);
      setConversationDayPreview(null);

      await refreshHome();
    } catch (err) {
      setConversationDayPreview({
        ...originalPreview,
        actions: remainingActions,
        needs_review:
          remainingActions.some(
            (item) => item.needs_review,
          ),
      });

      setConversationError(
        completed > 0
          ? `Ho registrato ${completed} elementi. ${
              err instanceof Error
                ? err.message
                : "Riprova per quelli rimasti."
            }`
          : err instanceof Error
            ? err.message
            : "Non riesco a completare la registrazione.",
      );

      await refreshHome().catch(
        () => undefined,
      );
    } finally {
      setConversationConfirming(false);
    }
  }


  async function analyzePhotoMeal() {
    if (!accessToken || !conversationPhoto) {
      return;
    }

    setConversationLoading(true);
    setConversationError(null);
    setConversationPreview(null);
    setConversationDayPreview(null);
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
      setConversationDayPreview(null);
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
  function normalizeActivityLevel(
    value: string | null | undefined,
  ) {
    const normalized = (value ?? "").toLowerCase();

    if (
      normalized === "low" ||
      normalized.includes("poco")
    ) {
      return "low" as const;
    }

    if (
      normalized === "high" ||
      normalized.includes("molto")
    ) {
      return "high" as const;
    }

    return "moderate" as const;
  }

  async function handleDayPlannerChange(
    changes: {
      day_type?: DayType;
      activity_plan?: "low" | "moderate" | "high";
    },
  ) {
    if (!accessToken || !day) {
      return;
    }

    setDayPlannerSaving(true);
    setDayPlannerMessage(null);

    const previousDay = day;
    setDay((current) => current ? {
      ...current,
      context: changes.day_type
        ? { ...current.context, value: changes.day_type, state: "confirmed", source: "user" }
        : current.context,
      activity_plan: changes.activity_plan
        ? { ...current.activity_plan, value: changes.activity_plan, state: "confirmed", source: "user" }
        : current.activity_plan,
    } : current);

    try {
      await updateDailyLog(
        accessToken,
        todayIso(),
        changes,
      );

      setDayPlannerMessage("Giornata aggiornata.");

      void refreshHome().catch(() => undefined);
    } catch (err) {
      setDay(previousDay);
      setDayPlannerMessage(
        err instanceof Error
          ? err.message
          : "Impossibile aggiornare la giornata.",
      );
    } finally {
      setDayPlannerSaving(false);
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
      plannedActivitiesPayload,
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
      getPlannedActivities(
        date,
        futureIso(7),
        accessToken,
      ),
    ]);

    setDay(dayPayload);
    setBudgetResult(budgetPayload);
    setNextMeal(nextMealPayload);

    if (nextMealPayload.next_slot) {
      void getMealOptions(
        date,
        nextMealPayload.next_slot,
        "auto",
        accessToken,
      )
        .then((payload) => {
          setNextMealOptions(payload);
          setDinnerOptions(
            nextMealPayload.next_slot === "dinner"
              ? payload
              : null,
          );
        })
        .catch(() => undefined);
    } else {
      setNextMealOptions(null);
      setDinnerOptions(null);
    }
    setActualMeals(mealsPayload.items);
    setActualActivities(
      activitiesPayload.items,
    );
    setPlannedActivities(plannedActivitiesPayload.items);

    setNextRunningSession(
      plannedActivitiesPayload.items
        .filter(
          (item) =>
            item.status === "planned" &&
            Boolean(
              item.training_plan_id,
            ) &&
            item.activity_type
              .trim()
              .toLocaleLowerCase(
                "it-IT",
              ) === "corsa",
        )
        .sort(
          (left, right) =>
            left.scheduled_date.localeCompare(
              right.scheduled_date,
            ) ||
            (
              left.scheduled_time ?? ""
            ).localeCompare(
              right.scheduled_time ?? "",
            ),
        )[0] ?? null,
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
      setMealEditType(
        response.item.meal_type ||
          meal.meal_type ||
          "Colazione",
      );

      if (!structured.length) {
        setMealEditIngredients([]);
        setSimpleMealEdit(response.item);
        setSimpleMealQuantity(
          Number(response.item.quantity) || 1,
        );
        return;
      }

      setSimpleMealEdit(null);

      const storedRecipeServings = Math.max(
        1,
        Number(response.item.recipe_servings) || 1,
      );
      const currentCalories = Math.max(
        0,
        Number(response.item.calories) || 0,
      );
      const baseCalories = Math.max(
        0,
        Number(response.item.base_calories) || 0,
      );

      const inferredRecipeServings =
        baseCalories > 0 &&
        currentCalories > baseCalories * 1.05
          ? currentCalories / baseCalories
          : 1;

      const effectiveRecipeServings = Math.max(
        storedRecipeServings,
        inferredRecipeServings,
      );
      const consumedPortions = Math.max(
        0.01,
        Number(response.item.quantity) || 1,
      );
      const portionScale =
        effectiveRecipeServings > 1
          ? consumedPortions /
            effectiveRecipeServings
          : 1;

      setMealEditRecipeServings(
        effectiveRecipeServings,
      );
      setMealEditIngredients(
        structured.map((item) => {
          const portionQuantity =
            (Number(item.quantity_g) || 0) *
            portionScale;

          return {
            ...item,
            quantity: portionQuantity,
            quantity_g: portionQuantity,
            original_quantity_g:
              portionQuantity,
          };
        }),
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
    setMealEditType("Colazione");
    setMealEditRecipeServings(1);
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

    const originalQuantity = Math.max(
      0.01,
      Number(simpleMealEdit.quantity) || 1,
    );

    const originalFactor =
      simpleMealEdit.is_per_100g
        ? originalQuantity / 100
        : originalQuantity;

    const editedFactor =
      simpleMealEdit.is_per_100g
        ? simpleMealQuantity / 100
        : simpleMealQuantity;

    const baseNutritionValue = (
      baseValue: number | null | undefined,
      currentValue: number | null | undefined,
    ): number => {
      if (
        baseValue !== null &&
        baseValue !== undefined &&
        Number.isFinite(Number(baseValue))
      ) {
        return Number(baseValue);
      }

      const current = Number(currentValue);

      if (!Number.isFinite(current)) {
        return 0;
      }

      return originalFactor > 0
        ? current / originalFactor
        : current;
    };

    return {
      calories:
        baseNutritionValue(
          simpleMealEdit.base_calories,
          simpleMealEdit.calories,
        ) * editedFactor,
      protein:
        baseNutritionValue(
          simpleMealEdit.base_protein,
          simpleMealEdit.protein,
        ) * editedFactor,
      carbs:
        baseNutritionValue(
          simpleMealEdit.base_carbs,
          simpleMealEdit.carbs,
        ) * editedFactor,
      fat:
        baseNutritionValue(
          simpleMealEdit.base_fat,
          simpleMealEdit.fat,
        ) * editedFactor,
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
          meal_type: mealEditType,
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
      const ingredientsChanged =
        mealEditIngredients.some(
          (item) =>
            Math.abs(
              Number(item.quantity_g) -
                Number(
                  item.original_quantity_g ??
                    item.quantity_g,
                ),
            ) > 0.001,
        );

      const needsPortionNormalization =
        mealEditRecipeServings > 1;

      if (
        !ingredientsChanged &&
        !needsPortionNormalization
      ) {
        await updateMeal(
          meal.id,
          {
            meal_type: mealEditType,
          },
          accessToken,
        );
      } else {
        await updateMeal(
          meal.id,
          {
            name: meal.name,
            meal_type: mealEditType,
            quantity: 1,
            recipe_servings: 1,
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
      }

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

  function quickMealFitsSlot(
    item: (typeof knownAlternates)[number],
    slot: string,
  ): boolean {
    const requested =
      normalizedMealSlot(slot);

    const compatibleFamily = (
      candidate: string,
    ): boolean => {
      const normalized =
        normalizedMealSlot(candidate);

      if (
        requested === "breakfast" ||
        requested === "snack"
      ) {
        return normalized === requested;
      }

      if (
        requested === "lunch" ||
        requested === "dinner"
      ) {
        return (
          normalized === "lunch" ||
          normalized === "dinner"
        );
      }

      return normalized === requested;
    };

    if (
      item.source === "recipe" ||
      item.source === "history" ||
      item.source === "meal_prep"
    ) {
      return Boolean(
        item.mealType &&
        compatibleFamily(item.mealType),
      );
    }

    return Boolean(
      item.mealSlots?.some(
        compatibleFamily,
      ),
    );
  }

  function quickMealAlternatesForSlot(
    slot: string,
  ): typeof knownAlternates {
    const sourcePriority = {
      history: 0,
      recipe: 1,
      meal_prep: 2,
      pantry: 3,
      ingredient: 4,
    } as const;

    return knownAlternates
      .filter((item) =>
        quickMealFitsSlot(item, slot),
      )
      .sort((left, right) =>
        sourcePriority[left.source] -
        sourcePriority[right.source],
      );
  }


  function selectQuickMealAlternate(
    key: string,
  ) {
    setAlternateSelectedKey(
      key || null,
    );
    setAlternateQuantity(1);

    if (!key) {
      return;
    }

    const selected =
      knownAlternates.find(
        (item) => item.key === key,
      );

    if (!selected) {
      return;
    }

    setAlternateName(selected.name);
    setAlternateCalories(
      String(Math.round(selected.calories)),
    );
    setAlternateProtein(
      String(Math.round(selected.protein)),
    );
    setAlternateCarbs(
      String(Math.round(selected.carbs)),
    );
    setAlternateFat(
      String(Math.round(selected.fat)),
    );
  }

  function updateQuickMealName(
    value: string,
    slot: string,
  ) {
    setAlternateName(value);

    const normalized =
      value.trim().toLocaleLowerCase("it");

    const exact =
      knownAlternates.find(
        (item) =>
          quickMealFitsSlot(item, slot) &&
          item.name
            .trim()
            .toLocaleLowerCase("it") ===
            normalized,
      );

    if (exact) {
      selectQuickMealAlternate(exact.key);
      return;
    }

    if (alternateSelectedKey) {
      setAlternateSelectedKey(null);
      setAlternateQuantity(1);
      setAlternateCalories("");
      setAlternateProtein("");
      setAlternateCarbs("");
      setAlternateFat("");
    }
  }


  function openQuickAddMeal(slot: string) {
    setError(null);

    setQuickAddMode("meal");
    setQuickAddMealSlot(slot);

    setAlternateSelectedKey(null);
    setAlternateQuantity(1);

    setAlternateName("");
    setAlternateCalories("");
    setAlternateProtein("");
    setAlternateCarbs("");
    setAlternateFat("");
  }

  function openQuickAddActivity() {
    setError(null);

    setQuickActivityName("");
    setQuickActivityCalories("");
    setQuickActivityDurationMinutes("");
    setQuickActivityDistanceKm("");

    setQuickAddMode("activity");
  }

  function openSuggestedActivity() {
    const suggestion =
      budgetResult?.energy_baseline?.activity_suggestion;
    if (!suggestion) return;

    setError(null);
    setQuickActivityName(suggestion.activity_name);
    setQuickActivityCalories(String(suggestion.burned_calories));
    setQuickActivityDurationMinutes(
      suggestion.duration_minutes ? String(suggestion.duration_minutes) : "",
    );
    setQuickActivityDistanceKm("");
    setQuickAddMode("activity");
  }

  async function openQuickAddWeight() {
    setError(null);

    await openWeightQuickAdd(
      null,
      false,
    );

    setQuickAddMode("weight");
  }

  function switchQuickAddMode(
    mode: "meal" | "activity" | "weight",
  ) {
    if (mode === "meal") {
      if (!quickAddMealSlot) {
        setQuickAddMealSlot(
          recommendedMealType ||
          "Colazione",
        );
      }

      setQuickAddMode("meal");
      return;
    }

    if (mode === "activity") {
      setQuickAddMode("activity");
      return;
    }

    void openQuickAddWeight();
  }

  function closeUnifiedQuickAdd() {
    setQuickAddMode(null);

    setAlternateSlot(null);
    setQuickAddMealSlot(null);
    setAlternateSelectedKey(null);
    setAlternateQuantity(1);

    setAlternateName("");
    setAlternateCalories("");
    setAlternateProtein("");
    setAlternateCarbs("");
    setAlternateFat("");

    setQuickActivityName("");
    setQuickActivityCalories("");
    setQuickActivityDurationMinutes("");
    setQuickActivityDistanceKm("");

    setWeightQuickAddOpen(false);
  }

  function closeAlternateMeal() {
    closeUnifiedQuickAdd();
  }

  function openAlternateMeal(slot: string) {
    setError(null);
    setAlternateSelectedKey(null);
    setAlternateQuantity(1);
    setAlternateName("");
    setAlternateCalories("");
    setAlternateProtein("");
    setAlternateCarbs("");
    setAlternateFat("");
    setAlternateSlot(slot);

    /*
     * The add form lives inside the meal <details>.
     * Opening only the details made the click appear to do
     * nothing because the form can be much further down.
     *
     * First open the meal, then wait for React to render the
     * alternate form and scroll directly to it.
     */
    window.requestAnimationFrame(() => {
      const mealDetails =
        document.querySelector<HTMLDetailsElement>(
          `[data-meal-slot="${slot}"]`,
        );

      if (mealDetails) {
        mealDetails.open = true;
      }

      window.requestAnimationFrame(() => {
        const form =
          document.getElementById(
            `home-add-meal-${slot}`,
          );

        if (!form) {
          return;
        }

        form.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });

        const nameInput =
          form.querySelector<HTMLInputElement>(
            '[data-home-add-meal-name="true"]',
          );

        window.setTimeout(() => {
          nameInput?.focus({
            preventScroll: true,
          });
        }, 250);
      });
    });
  }

  async function saveQuickActivity() {
    if (!accessToken) {
      return;
    }

    const name = quickActivityName.trim();
    const calories = Number(
      quickActivityCalories,
    );

    const durationMinutes =
      quickActivityDurationMinutes.trim()
        ? Number(
            quickActivityDurationMinutes,
          )
        : 0;

    const distanceKm =
      quickActivityDistanceKm.trim()
        ? Number(
            quickActivityDistanceKm.replace(
              ",",
              ".",
            ),
          )
        : 0;

    if (!name) {
      setError(
        "Inserisci il nome dell’attività.",
      );
      return;
    }

    if (
      !Number.isFinite(calories) ||
      calories < 0
    ) {
      setError(
        "Inserisci delle kcal valide.",
      );
      return;
    }

    if (
      !Number.isFinite(durationMinutes) ||
      durationMinutes < 0
    ) {
      setError(
        "Inserisci una durata valida.",
      );
      return;
    }

    if (
      !Number.isFinite(distanceKm) ||
      distanceKm < 0
    ) {
      setError(
        "Inserisci una distanza valida.",
      );
      return;
    }

    setQuickActivitySaving(true);
    setError(null);

    try {
      await createActivity(
        {
          date: todayIso(),
          activity_name: name,
          burned_calories:
            Math.round(calories),
          ...(durationMinutes > 0
            ? {
                duration_seconds:
                  Math.round(
                    durationMinutes * 60,
                  ),
              }
            : {}),
          ...(distanceKm > 0
            ? {
                distance_meters:
                  Math.round(
                    distanceKm * 1000,
                  ),
              }
            : {}),
        },
        accessToken,
      );

      closeUnifiedQuickAdd();
      await refreshHome();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a registrare l’attività.",
      );
    } finally {
      setQuickActivitySaving(false);
    }
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
      const selected =
        alternateSelectedKey
          ? knownAlternates.find(
              (item) =>
                item.key ===
                alternateSelectedKey,
            )
          : null;

      if (
        selected?.source === "meal_prep" &&
        selected.mealPrepBatchId
      ) {
        await logMealPrepPortion(
          accessToken,
          selected.mealPrepBatchId,
          todayIso(),
          mealLabel(slot),
        );
      } else if (
        selected?.source === "pantry" &&
        selected.pantryItemId &&
        selected.portionGrams
      ) {
        await logPantryMeal(
          {
            date: todayIso(),
            meal_type: mealLabel(slot),
            pantry_item_id:
              selected.pantryItemId,
            quantity_g:
              selected.portionGrams,
          },
          accessToken,
        );
      } else {
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
      }

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
              strategy:
                nextMealOptions.recommended
                  .strategy,
              components:
                nextMealOptions.recommended
                  .candidate.components,
              removed_components:
                nextMealOptions.recommended
                  .adaptation.removed_components,
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

  const todayPlannedActivities = plannedActivities.filter(
    (item) =>
      item.scheduled_date === todayIso() &&
      item.status === "planned",
  );
  const plannedActivityKcal = Number(
    budgetResult?.energy_baseline?.planned_activity_kcal ?? 0,
  );
  const plannedActivityLevel =
    budgetResult?.energy_baseline?.planned_activity_level ?? null;
  const plannedActivitySummary = todayPlannedActivities.length
    ? `${todayPlannedActivities.map((item) => item.title).join(", ")} · circa ${Math.round(plannedActivityKcal)} kcal già incluse nel bilancio.`
    : null;

  return (
    <>
      <AppNav />

      {!loading && needsWelcomeJourney && accessToken ? (
        <WelcomeJourney
          accessToken={accessToken}
          initialName={
            typeof profile?.metadata?.name === "string"
              ? profile.metadata.name
              : firstName
          }
          testMode={isOnboardingTestAccount}
        />
      ) : null}

      <main
        className={
          experienceMode === "zero"
            ? `${styles.page} ${styles.pageZero}`
            : styles.page
        }
      >
      <header className={styles.header}>
        <div>
          <h1>
            {greeting()}
            {firstName
              ? `, ${firstName}`
              : ""}
            <span
              className={styles.greetingWave}
              role="img"
              aria-label="Ciao"
            >
              👋
            </span>
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
          <DayPlanner
            message={
              dayBriefingBody ??
              buildDayMessage(
              buildDayMessageContext(
                user?.user_metadata?.first_name ||
                  user?.user_metadata?.name ||
                  "",
                normalizeDayType(
                  day.context.value,
                ),
                normalizeActivityLevel(
                  plannedActivityLevel ?? day.activity_plan.value,
                ),
                burnedCalories,
                actualActivities.length,
                historicalProfile?.average_burned_calories ?? null,
                historicalProfile?.days ?? 0,
              ),
            )}
            dayType={normalizeDayType(
              day.context.value,
            )}
            activityLevel={normalizeActivityLevel(
              plannedActivityLevel ?? day.activity_plan.value,
            )}
            plannedActivitySummary={plannedActivitySummary}
            onDayTypeChange={(value) => {
              void handleDayPlannerChange({
                day_type: value,
              });
            }}
            onActivityLevelChange={(value) => {
              void handleDayPlannerChange({
                activity_plan: value,
              });
            }}
          />

          {budgetResult?.energy_baseline?.activity_suggestion ? (
            <section className={styles.activitySuggestion}>
              <div>
                <span>Abitudine riconosciuta</span>
                <strong>
                  Hai fatto {budgetResult.energy_baseline.activity_suggestion.activity_name.toLowerCase()} anche oggi?
                </strong>
                <p>{budgetResult.energy_baseline.activity_suggestion.reason}</p>
              </div>
              <button type="button" onClick={openSuggestedActivity}>
                Sì, registrala
              </button>
            </section>
          ) : null}

          {dayPlannerMessage ? (
            <p className={styles.muted}>
              {dayPlannerSaving
                ? "Salvataggio..."
                : dayPlannerMessage}
            </p>
          ) : null}

          {nextRunningSession ? (
            <section
              className={
                styles.nextTrainingCard
              }
            >
              <div
                className={
                  styles.nextTrainingTop
                }
              >
                <div>
                  <span
                    className={
                      styles.nextTrainingEyebrow
                    }
                  >
                    PROSSIMO ALLENAMENTO ·{" "}
                    {plannedTrainingDateLabel(
                      nextRunningSession
                        .scheduled_date,
                    )}
                  </span>

                  <h2>
                    {nextRunningSession.title}
                  </h2>
                </div>

                <span
                  className={
                    styles.nextTrainingKind
                  }
                >
                  {plannedTrainingKindLabel(
                    nextRunningSession
                      .session_kind,
                  )}
                </span>
              </div>

              <div
                className={
                  styles.nextTrainingMetrics
                }
              >
                {nextRunningSession
                  .training_week ? (
                  <span>
                    Settimana{" "}
                    {
                      nextRunningSession
                        .training_week
                    }
                  </span>
                ) : null}

                {nextRunningSession
                  .distance_meters ? (
                  <strong>
                    {(
                      nextRunningSession
                        .distance_meters /
                      1000
                    ).toLocaleString(
                      "it-IT",
                      {
                        maximumFractionDigits:
                          2,
                      },
                    )}{" "}
                    km
                  </strong>
                ) : null}

                {nextRunningSession
                  .duration_minutes ? (
                  <span>
                    {
                      nextRunningSession
                        .duration_minutes
                    }{" "}
                    min
                  </span>
                ) : null}

                {nextRunningSession
                  .scheduled_time ? (
                  <span>
                    ore{" "}
                    {nextRunningSession
                      .scheduled_time
                      .slice(0, 5)}
                  </span>
                ) : null}
              </div>

              <p
                className={
                  styles.nextTrainingMessage
                }
              >
                {experienceMode === "zero"
                  ? `${
                      plannedTrainingDateLabel(
                        nextRunningSession
                          .scheduled_date,
                      )
                    }: ${
                      nextRunningSession.title
                    }. Non si correrà da solo.`
                  : `${
                      plannedTrainingDateLabel(
                        nextRunningSession
                          .scheduled_date,
                      )
                    } hai ${
                      nextRunningSession.title
                    }. Tienilo presente mentre organizzi la giornata.`}
              </p>
            </section>
          ) : null}

          {nextStrengthSession ? (
            <section
              className={
                styles.nextTrainingCard
              }
            >
              <div
                className={
                  styles.nextTrainingTop
                }
              >
                <div>
                  <span
                    className={
                      styles.nextTrainingEyebrow
                    }
                  >
                    PROSSIMA PALESTRA ·{" "}
                    {plannedTrainingDateLabel(
                      nextStrengthSession
                        .scheduled_date,
                    )}
                  </span>

                  <h2>
                    {nextStrengthSession.title}
                  </h2>
                </div>

                <span
                  className={
                    styles.nextTrainingKind
                  }
                >
                  {strengthFocusLabel(
                    nextStrengthSession.focus,
                  )}
                </span>
              </div>

              <div
                className={
                  styles.nextTrainingMetrics
                }
              >
                <span>
                  Settimana{" "}
                  {
                    nextStrengthSession
                      .training_week
                  }
                </span>

                <strong>
                  {
                    nextStrengthSession
                      .exercises.length
                  }{" "}
                  esercizi
                </strong>

                {nextStrengthSession
                  .estimated_duration_minutes !=
                null ? (
                  <span>
                    {
                      nextStrengthSession
                        .estimated_duration_minutes
                    }{" "}
                    min
                  </span>
                ) : null}
              </div>

              <p
                className={
                  styles.nextTrainingMessage
                }
              >
                {experienceMode === "zero"
                  ? `${plannedTrainingDateLabel(
                      nextStrengthSession
                        .scheduled_date,
                    )}: ${
                      nextStrengthSession.title
                    }. I pesi non si alzano da soli.`
                  : `${plannedTrainingDateLabel(
                      nextStrengthSession
                        .scheduled_date,
                    )} hai ${
                      nextStrengthSession.title
                    }. La seduta è già nel tuo programma.`}
              </p>
            </section>
          ) : null}

          {budget ? (
            <section
              className={`${styles.budgetHero} ${
                budgetExpanded
                  ? styles.budgetHeroExpanded
                  : styles.budgetHeroCollapsed
              }`}
            >
              <div className={styles.budgetSummary}>
                <div className={styles.budgetQuestion}>
                  <span className={styles.budgetEyebrow}>
                    Il tuo piano di oggi
                  </span>
                  <h2>Quanto posso ancora mangiare oggi?</h2>
                </div>

                <div className={styles.budgetHeadlineMetric}>
                  <span className={styles.budgetLabel}>Consumate oggi</span>
                  <div className={styles.budgetValueRow}>
                    <strong className={styles.budgetAvailable}>
                      {roundNumber(budget.consumed_kcal)}
                    </strong>
                    <span className={styles.budgetKcal}>kcal</span>
                  </div>
                </div>

                <div className={styles.budgetHeadlineMetric}>
                  <span className={styles.budgetLabel}>
                    Puoi ancora mangiare
                  </span>
                  <div className={styles.budgetValueRow}>
                    <strong className={styles.budgetAvailable}>
                      {roundNumber(Math.max(0, budget.available_kcal))}
                    </strong>
                    <span className={styles.budgetKcal}>kcal</span>
                  </div>
                </div>

                <div className={styles.budgetCalmStatus}>
                  <span className={styles.budgetCalmIcon} aria-hidden="true">
                    {budget.budget_adapted ? "✓" : "○"}
                  </span>
                  <p>
                    {budget.budget_adapted
                      ? "Oggi ti sei mosso meno del previsto. Abbiamo ridotto il deficit per lasciarti pasti completi."
                      : budget.consumed_kcal === 0
                      ? "Il piano è pronto e si adatterà con calma a quello che succede oggi."
                      : budget.consumed_kcal < maintenanceBudgetKcal
                      ? "Sei ancora sotto il mantenimento. Continua la giornata senza inseguire il singolo numero."
                      : "Hai raggiunto il mantenimento: è un'informazione, non un giudizio."
                    }
                  </p>
                  <button
                    type="button"
                    className={styles.budgetToggle}
                    aria-expanded={budgetExpanded}
                    onClick={() => setBudgetExpanded((current) => !current)}
                  >
                    {budgetExpanded ? "Nascondi calcolo" : "Vedi calcolo"}
                    <span
                      className={`${styles.budgetChevron} ${
                        budgetExpanded ? styles.budgetChevronUp : ""
                      }`}
                      aria-hidden="true"
                    />
                  </button>
                </div>
              </div>

              {budgetExpanded ? (
                <div className={styles.budgetExpandedPanel}>
                  <div className={styles.budgetDetailsGrid}>
                    <div className={styles.budgetDetail}>
                      <span>Metabolismo basale</span>
                      <strong>{bmr > 0 ? roundNumber(bmr) : "—"} kcal</strong>
                      <small>energia minima del corpo</small>
                    </div>
                    <div className={styles.budgetDetail}>
                      <span>Mantenimento stimato</span>
                      <strong>{roundNumber(maintenanceBudgetKcal)} kcal</strong>
                      <small>con la giornata di oggi</small>
                    </div>
                    <div className={styles.budgetDetail}>
                      <span>Deficit scelto</span>
                      <strong>{roundNumber(budget.goal_adjustment_kcal)} kcal</strong>
                      <small>dal tuo obiettivo</small>
                    </div>
                    <div className={styles.budgetDetail}>
                      <span>Deficit di oggi</span>
                      <strong>{roundNumber(budget.effective_goal_adjustment_kcal)} kcal</strong>
                      <small>{budget.budget_adapted ? "adattato alla giornata" : "come programmato"}</small>
                    </div>
                  </div>

                  <div className={styles.budgetScale}>
                    <div className={styles.budgetScaleTrack}>
                      <div
                        className={styles.budgetScaleFill}
                        style={{
                          width: `${Math.min(100, Math.max(0,
                            maintenanceBudgetKcal > 0
                              ? (budget.consumed_kcal / maintenanceBudgetKcal) * 100
                              : 0,
                          ))}%`,
                        }}
                      />
                      <span
                        className={styles.budgetScaleTarget}
                        style={{
                          left: maintenanceBudgetKcal > 0
                            ? `${Math.min(100, Math.max(0,
                                (budget.daily_budget_kcal / maintenanceBudgetKcal) * 100,
                              ))}%`
                            : "0%",
                        }}
                        aria-hidden="true"
                      />
                    </div>
                    <div className={styles.budgetScaleLabels}>
                      <span>{roundNumber(budget.consumed_kcal)} consumate</span>
                      <span>{roundNumber(budget.daily_budget_kcal)} obiettivo adattato</span>
                      <span>{roundNumber(maintenanceBudgetKcal)} mantenimento</span>
                    </div>
                  </div>

                  <div className={styles.budgetExplanation}>
                    L'obiettivo si adatta con calma per proteggere pasti completi e sostenibili.
                  </div>
                </div>
              ) : null}
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

          <div className={styles.dashboardToolbar}>
            <button
              type="button"
              className={
                customizingDashboard
                  ? styles.dashboardCustomizeActive
                  : styles.dashboardCustomizeButton
              }
              onClick={() => {
                setCustomizingDashboard(
                  (current) => !current,
                );
                setDraggedWidget(null);
              }}
            >
              {customizingDashboard
                ? "Fine personalizzazione"
                : "Personalizza Home"}
            </button>

            {customizingDashboard ? (
              <button
                type="button"
                className={styles.dashboardResetButton}
                onClick={() => {
                  saveDashboardOrder([
                    ...DEFAULT_DASHBOARD_ORDER,
                  ]);
                  setDashboardSizes({
                    ...DEFAULT_DASHBOARD_SIZES,
                  });
                  window.localStorage.setItem(
                    DASHBOARD_SIZE_KEY,
                    JSON.stringify(
                      DEFAULT_DASHBOARD_SIZES,
                    ),
                  );
                }}
              >
                Ripristina ordine
              </button>
            ) : null}
          </div>

          <div className={styles.desktopHomeGrid}>
            <section

              className={`${styles.homeAssistantSection} ${styles.conversationCard}`}
            >

            <div className={styles.conversationHeader}>
              <div>
                <span className={styles.conversationEyebrow}>
                  <img
                    src={
                      experienceMode === "zero"
                        ? "/assets/SanoSyncAIZero1.png"
                        : "/assets/AILogo.png"
                    }
                    alt={
                      experienceMode === "zero"
                        ? "SanoSync AI Zero"
                        : "SanoSync AI"
                    }
                    className={styles.conversationAiLogo}
                  />
                </span>

                <h2>SanoSync AI</h2>

                <p>
                  {conversationMode === "text"
                    ? "Racconta la tua giornata, penso io al resto."
                    : "Scatta una foto o scegline una dalla galleria."}
                </p>
              </div>

              <span className={styles.aiCapabilityPill}>
                ✦ Tutto in un input
              </span>
            </div>

            <div className={styles.aiHelperPanel}>
              <span aria-hidden="true">✦</span>
              <p>
                Puoi registrare pasti, attività e peso,
                anche insieme nello stesso messaggio.
              </p>
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
                  setConversationDayPreview(null);
                  setConversationError(null);
                  setConversationSuccess(null);
                }}
              >
                <span aria-hidden="true">⌨</span>
                Scrivi
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
                  setConversationDayPreview(null);
                  setConversationError(null);
                  setConversationSuccess(null);
                }}
              >
                <span aria-hidden="true">▣</span>
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
                <option value="Snack">
                  Snack
                </option>
                <option value="Cena">
                  Cena
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
                    placeholder="Es. Ho mangiato una piadina, corso 5 km e peso 77,4 kg..."
                    rows={3}
                  />

                  <button
                    type="button"
                    className={`${styles.aiMicButton} ${
                      conversationListening
                        ? styles.aiMicButtonListening
                        : ""
                    }`}
                    onClick={
                      toggleConversationDictation
                    }
                    aria-pressed={
                      conversationListening
                    }
                    title={
                      conversationListening
                        ? "Ferma dettatura"
                        : "Detta con il microfono"
                    }
                  >
                    <span aria-hidden="true">
                      {conversationListening
                        ? "■"
                        : "🎙"}
                    </span>
                    <span className={styles.srOnly}>
                      {conversationListening
                        ? "Ferma dettatura"
                        : "Detta con il microfono"}
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      void analyzeConversationDay();
                    }}
                    disabled={
                      conversationLoading ||
                      !conversationText.trim()
                    }
                  >
                    <span aria-hidden="true">
                      {conversationLoading ? "…" : "→"}
                    </span>
                    <span className={styles.srOnly}>
                      {conversationLoading
                        ? "Analizzo"
                        : "Analizza"}
                    </span>
                  </button>
                </>
              ) : (
                <>
                  <div
                    className={styles.conversationPhotoActions}
                  >
                    <label
                      className={
                        styles.conversationPhotoAction
                      }
                    >
                      <span aria-hidden="true">📷</span>
                      <strong>Scatta foto</strong>

                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        capture="environment"
                        onChange={(event) => {
                          const file =
                            event.target.files?.[0] ?? null;

                          setConversationPhoto(file);
                          setConversationPreview(null);
                          setConversationDayPreview(null);
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

                    <label
                      className={
                        styles.conversationPhotoAction
                      }
                    >
                      <span aria-hidden="true">🖼️</span>
                      <strong>Carica foto</strong>

                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        onChange={(event) => {
                          const file =
                            event.target.files?.[0] ?? null;

                          setConversationPhoto(file);
                          setConversationPreview(null);
                          setConversationDayPreview(null);
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
                  </div>

                  {conversationPhoto ? (
                    <div
                      className={
                        styles.conversationPhotoSelected
                      }
                    >
                      <span>Foto selezionata</span>
                      <strong>{conversationPhoto.name}</strong>
                    </div>
                  ) : null}

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

            {conversationMode === "text" &&
            !conversationPreview &&
            !conversationDayPreview ? (
              <div
                className={styles.aiSuggestionChips}
                aria-label="Esempi da provare"
              >
                {[
                  "Ho mangiato una piadina con pollo",
                  "Ho corso 5 km in 30 minuti",
                  "Stamattina peso 77,4 kg",
                  "A pranzo pasta, poi palestra 45 minuti",
                ].map((example) => (
                  <button
                    key={example}
                    type="button"
                    onClick={() => {
                      setConversationText(example);
                      setConversationError(null);
                      setConversationSuccess(null);
                    }}
                  >
                    {example}
                  </button>
                ))}
              </div>
            ) : null}

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

            {conversationDayPreview ? (
              <div className={styles.conversationPreview}>
                <div
                  className={styles.conversationPreviewTop}
                >
                  <strong>Ho capito così</strong>

                  {conversationDayPreview.needs_review ? (
                    <span>
                      Controlla le stime prima di registrare
                    </span>
                  ) : (
                    <span>
                      Pronto da registrare
                    </span>
                  )}
                </div>

                <div
                  className={styles.conversationDayActions}
                >
                  {conversationDayPreview.actions.map(
                    (action) => (
                      <div
                        key={action.id}
                        className={
                          styles.conversationDayAction
                        }
                      >
                        <span
                          className={
                            styles.conversationDayActionIcon
                          }
                          aria-hidden="true"
                        >
                          {action.kind === "meal"
                            ? "🍽️"
                            : action.kind === "activity"
                              ? "🏃"
                              : "⚖️"}
                        </span>

                        <div
                          className={
                            styles.conversationDayActionMain
                          }
                        >
                          <strong>
                            {action.kind === "meal"
                              ? action.meal_type
                              : action.kind === "activity"
                                ? action.activity_name
                                : "Peso"}
                          </strong>

                          <span>
                            {action.kind === "meal"
                              ? action.items
                                  .map(
                                    (item) =>
                                      item.name,
                                  )
                                  .join(" · ")
                              : action.kind === "activity"
                                ? [
                                    action.activity_type,
                                    action.duration_seconds
                                      ? `${Math.round(
                                          action.duration_seconds /
                                            60,
                                        )} min`
                                      : null,
                                    action.distance_meters
                                      ? `${(
                                          action.distance_meters /
                                          1000
                                        ).toLocaleString(
                                          "it-IT",
                                          {
                                            maximumFractionDigits:
                                              2,
                                          },
                                        )} km`
                                      : null,
                                  ]
                                    .filter(Boolean)
                                    .join(" · ")
                                : "Peso di oggi"}
                          </span>

                          {action.needs_review ? (
                            <small
                              className={
                                styles.conversationDayActionWarning
                              }
                            >
                              {action.kind === "activity" &&
                              action.calories_estimated
                                ? "Consumo energetico stimato"
                                : "Dato da controllare"}
                            </small>
                          ) : null}
                        </div>

                        <strong
                          className={
                            styles.conversationDayActionMetric
                          }
                        >
                          {action.kind === "meal"
                            ? `${roundNumber(
                                action.totals.calories,
                              )} kcal`
                            : action.kind === "activity"
                              ? action.burned_calories > 0
                                ? `${roundNumber(
                                    action.burned_calories,
                                  )} kcal`
                                : "kcal n/d"
                              : `${Number(
                                  action.weight_kg,
                                ).toLocaleString(
                                  "it-IT",
                                  {
                                    maximumFractionDigits:
                                      1,
                                  },
                                )} kg`}
                        </strong>
                      </div>
                    ),
                  )}
                </div>

                <div
                  className={
                    styles.conversationPreviewActions
                  }
                >
                  <button
                    type="button"
                    onClick={() => {
                      void confirmConversationDay();
                    }}
                    disabled={conversationConfirming}
                  >
                    {conversationConfirming
                      ? "Registro..."
                      : conversationDayPreview.actions.length ===
                          1
                        ? "Conferma e registra"
                        : `Conferma ${conversationDayPreview.actions.length} registrazioni`}
                  </button>

                  <button
                    type="button"
                    onClick={() =>
                      setConversationDayPreview(null)
                    }
                    disabled={conversationConfirming}
                  >
                    Modifica testo
                  </button>
                </div>
              </div>
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

          {typeof document !== "undefined" &&
          quickAddMode
            ? createPortal(
                <div
                  className={styles.quickMealOverlay}
                  role="presentation"
                  onMouseDown={(event) => {
                    if (
                      event.target ===
                      event.currentTarget
                    ) {
                      closeUnifiedQuickAdd();
                    }
                  }}
                >
                  <section
                    className={styles.quickMealModal}
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="quick-add-title"
                  >
                    <div
                      className={
                        styles.quickMealModalHeader
                      }
                    >
                      <div>
                        <span>AGGIUNGI A OGGI</span>

                        <h3 id="quick-add-title">
                          {quickAddMode === "meal"
                            ? quickAddMealSlot
                              ? `Aggiungi a ${mealLabel(
                                  quickAddMealSlot,
                                ).toLowerCase()}`
                              : "Aggiungi un pasto"
                            : quickAddMode ===
                                "activity"
                              ? "Registra attività"
                              : "Registra peso"}
                        </h3>

                        <p>
                          Tutto senza lasciare la Home.
                        </p>
                      </div>

                      <button
                        type="button"
                        aria-label="Chiudi"
                        onClick={
                          closeUnifiedQuickAdd
                        }
                      >
                        ×
                      </button>
                    </div>

                    <div
                      className={
                        styles.quickAddTabs
                      }
                      role="tablist"
                      aria-label="Tipo di registrazione"
                    >
                      {[
                        ["meal", "🍽️", "Pasto"],
                        [
                          "activity",
                          "🏃",
                          "Attività",
                        ],
                        ["weight", "⚖️", "Peso"],
                      ].map(
                        ([
                          mode,
                          icon,
                          label,
                        ]) => (
                          <button
                            key={mode}
                            type="button"
                            role="tab"
                            aria-selected={
                              quickAddMode ===
                              mode
                            }
                            className={
                              quickAddMode ===
                              mode
                                ? styles.quickAddTabActive
                                : undefined
                            }
                            onClick={() =>
                              switchQuickAddMode(
                                mode as
                                  | "meal"
                                  | "activity"
                                  | "weight",
                              )
                            }
                          >
                            <span
                              aria-hidden="true"
                            >
                              {icon}
                            </span>
                            {label}
                          </button>
                        ),
                      )}
                    </div>

                    {quickAddMode === "meal" &&
                    quickAddMealSlot ? (
                      <>
                        <div
                          className={
                            styles.quickMealModalBody
                          }
                        >
                          <label>
                            <span>
                              Scegli un alimento
                            </span>

                            <select
                              value={
                                alternateSelectedKey ??
                                ""
                              }
                              onChange={(event) => {
                                selectQuickMealAlternate(
                                  event.target.value,
                                );
                              }}
                            >
                              <option value="">
                                Seleziona da dispensa o recenti…
                              </option>

                              {knownAlternates.some(
                                (item) =>
                                  item.source ===
                                    "meal_prep" &&
                                  quickMealFitsSlot(
                                    item,
                                    quickAddMealSlot,
                                  ),
                              ) ? (
                                <optgroup label="🏠 Dispensa · porzioni cucinate">
                                  {knownAlternates
                                    .filter(
                                      (item) =>
                                        item.source ===
                                          "meal_prep" &&
                                        quickMealFitsSlot(
                                          item,
                                          quickAddMealSlot,
                                        ),
                                    )
                                    .map((item) => (
                                      <option
                                        key={item.key}
                                        value={item.key}
                                      >
                                        {item.name}
                                        {item.stockLabel
                                          ? ` · ${item.stockLabel}`
                                          : ""}
                                      </option>
                                    ))}
                                </optgroup>
                              ) : null}

                              {knownAlternates.some(
                                (item) =>
                                  item.source === "pantry" &&
                                  quickMealFitsSlot(
                                    item,
                                    quickAddMealSlot,
                                  ),
                              ) ? (
                                <optgroup label="🏠 Dispensa · alimenti">
                                  {knownAlternates
                                    .filter(
                                      (item) =>
                                        item.source ===
                                          "pantry" &&
                                        quickMealFitsSlot(
                                          item,
                                          quickAddMealSlot,
                                        ),
                                    )
                                    .map((item) => (
                                      <option
                                        key={item.key}
                                        value={item.key}
                                      >
                                        {item.name}
                                        {item.stockLabel
                                          ? ` · ${item.stockLabel}`
                                          : ""}
                                      </option>
                                    ))}
                                </optgroup>
                              ) : null}

                              {knownAlternates.some(
                                (item) =>
                                  item.source ===
                                    "history" &&
                                  quickMealFitsSlot(
                                    item,
                                    quickAddMealSlot,
                                  ),
                              ) ? (
                                <optgroup label="🕘 Consumati di recente">
                                  {knownAlternates
                                    .filter(
                                      (item) =>
                                        item.source ===
                                          "history" &&
                                        quickMealFitsSlot(
                                          item,
                                          quickAddMealSlot,
                                        ),
                                    )
                                    .slice(0, 12)
                                    .map((item) => (
                                      <option
                                        key={item.key}
                                        value={item.key}
                                      >
                                        {item.name}
                                      </option>
                                    ))}
                                </optgroup>
                              ) : null}
                            </select>
                          </label>

                          <label>
                            <span>
                              Oppure scrivi
                              manualmente
                            </span>

                            <input
                              type="text"
                              autoFocus
                              list="home-quick-known-foods"
                              value={
                                alternateName
                              }
                              placeholder="Cerca o scrivi cosa hai mangiato…"
                              onChange={(event) => {
                                updateQuickMealName(
                                  event.target.value,
                                  quickAddMealSlot,
                                );
                              }}
                            />

                            <datalist id="home-quick-known-foods">
                              {knownAlternates
                                .filter((item) =>
                                  quickMealFitsSlot(
                                    item,
                                    quickAddMealSlot,
                                  ),
                                )
                                .filter(
                                  (
                                    item,
                                    index,
                                    list,
                                  ) =>
                                    list.findIndex(
                                      (candidate) =>
                                        candidate.name
                                          .trim()
                                          .toLocaleLowerCase(
                                            "it",
                                          ) ===
                                        item.name
                                          .trim()
                                          .toLocaleLowerCase(
                                            "it",
                                          ),
                                    ) === index,
                                )
                                .map((item) => (
                                  <option
                                    key={`known:${item.key}`}
                                    value={item.name}
                                  />
                                ))}
                            </datalist>
                          </label>

                          <div
                            className={
                              styles.quickMealMacroGrid
                            }
                          >
                            <label>
                              <span>Kcal</span>
                              <input
                                type="number"
                                min="0"
                                inputMode="numeric"
                                value={
                                  alternateCalories
                                }
                                onChange={(
                                  event,
                                ) =>
                                  setAlternateCalories(
                                    event.target
                                      .value,
                                  )
                                }
                              />
                            </label>

                            <label>
                              <span>
                                Proteine
                              </span>
                              <input
                                type="number"
                                min="0"
                                inputMode="decimal"
                                value={
                                  alternateProtein
                                }
                                onChange={(
                                  event,
                                ) =>
                                  setAlternateProtein(
                                    event.target
                                      .value,
                                  )
                                }
                              />
                            </label>

                            <label>
                              <span>Carbo</span>
                              <input
                                type="number"
                                min="0"
                                inputMode="decimal"
                                value={
                                  alternateCarbs
                                }
                                onChange={(
                                  event,
                                ) =>
                                  setAlternateCarbs(
                                    event.target
                                      .value,
                                  )
                                }
                              />
                            </label>

                            <label>
                              <span>Grassi</span>
                              <input
                                type="number"
                                min="0"
                                inputMode="decimal"
                                value={
                                  alternateFat
                                }
                                onChange={(
                                  event,
                                ) =>
                                  setAlternateFat(
                                    event.target
                                      .value,
                                  )
                                }
                              />
                            </label>
                          </div>
                        </div>

                        <div
                          className={
                            styles.quickMealModalActions
                          }
                        >
                          <button
                            type="button"
                            className={
                              styles.quickMealCancel
                            }
                            onClick={
                              closeUnifiedQuickAdd
                            }
                          >
                            Annulla
                          </button>

                          <button
                            type="button"
                            className={
                              styles.quickMealSave
                            }
                            disabled={
                              savingAlternate ||
                              !alternateName.trim() ||
                              !alternateCalories.trim()
                            }
                            onClick={() => {
                              void saveAlternateMeal(
                                quickAddMealSlot,
                              );
                            }}
                          >
                            {savingAlternate
                              ? "Registro…"
                              : "Aggiungi al pasto"}
                          </button>
                        </div>
                      </>
                    ) : null}

                    {quickAddMode ===
                    "activity" ? (
                      <>
                        <div
                          className={
                            styles.quickMealModalBody
                          }
                        >
                          <label>
                            <span>
                              Attività
                            </span>
                            <input
                              type="text"
                              autoFocus
                              value={
                                quickActivityName
                              }
                              placeholder="Es. Corsa, palestra, bici"
                              onChange={(
                                event,
                              ) =>
                                setQuickActivityName(
                                  event.target
                                    .value,
                                )
                              }
                            />
                          </label>

                          <div
                            className={
                              styles.quickActivityGrid
                            }
                          >
                            <label>
                              <span>Kcal</span>
                              <input
                                type="number"
                                min="0"
                                value={
                                  quickActivityCalories
                                }
                                placeholder="350"
                                onChange={(
                                  event,
                                ) =>
                                  setQuickActivityCalories(
                                    event.target
                                      .value,
                                  )
                                }
                              />
                            </label>

                            <label>
                              <span>
                                Durata (min)
                              </span>
                              <input
                                type="number"
                                min="0"
                                value={
                                  quickActivityDurationMinutes
                                }
                                placeholder="45"
                                onChange={(
                                  event,
                                ) =>
                                  setQuickActivityDurationMinutes(
                                    event.target
                                      .value,
                                  )
                                }
                              />
                            </label>

                            <label>
                              <span>
                                Distanza (km)
                              </span>
                              <input
                                type="text"
                                inputMode="decimal"
                                value={
                                  quickActivityDistanceKm
                                }
                                placeholder="5"
                                onChange={(
                                  event,
                                ) =>
                                  setQuickActivityDistanceKm(
                                    event.target
                                      .value,
                                  )
                                }
                              />
                            </label>
                          </div>
                        </div>

                        <div
                          className={
                            styles.quickMealModalActions
                          }
                        >
                          <button
                            type="button"
                            className={
                              styles.quickMealCancel
                            }
                            onClick={
                              closeUnifiedQuickAdd
                            }
                          >
                            Annulla
                          </button>

                          <button
                            type="button"
                            className={
                              styles.quickMealSave
                            }
                            disabled={
                              quickActivitySaving ||
                              !quickActivityName.trim() ||
                              !quickActivityCalories.trim()
                            }
                            onClick={() => {
                              void saveQuickActivity();
                            }}
                          >
                            {quickActivitySaving
                              ? "Registro…"
                              : "Aggiungi attività"}
                          </button>
                        </div>
                      </>
                    ) : null}

                    {quickAddMode ===
                    "weight" ? (
                      <>
                        <div
                          className={
                            styles.quickMealModalBody
                          }
                        >
                          <label>
                            <span>
                              Peso di oggi (kg)
                            </span>
                            <input
                              type="text"
                              inputMode="decimal"
                              autoFocus
                              value={
                                weightQuickAddValue
                              }
                              placeholder="77,4"
                              onChange={(
                                event,
                              ) =>
                                setWeightQuickAddValue(
                                  event.target
                                    .value,
                                )
                              }
                            />
                          </label>

                          {weightQuickAddMessage ? (
                            <p
                              className={
                                styles.quickAddMessage
                              }
                            >
                              {
                                weightQuickAddMessage
                              }
                            </p>
                          ) : null}
                        </div>

                        <div
                          className={
                            styles.quickMealModalActions
                          }
                        >
                          <button
                            type="button"
                            className={
                              styles.quickMealCancel
                            }
                            onClick={
                              closeUnifiedQuickAdd
                            }
                          >
                            Chiudi
                          </button>

                          <button
                            type="button"
                            className={
                              styles.quickMealSave
                            }
                            disabled={
                              weightQuickAddSaving ||
                              !weightQuickAddValue.trim()
                            }
                            onClick={() => {
                              void saveWeightQuickAdd();
                            }}
                          >
                            {weightQuickAddSaving
                              ? "Salvo…"
                              : weightQuickAddEditingEntry
                                ? "Aggiorna peso"
                                : "Registra peso"}
                          </button>
                        </div>
                      </>
                    ) : null}
                  </section>
                </div>,
                document.body,
              )
            : null}

          <section

            className={`${styles.section} ${styles.mealsSection}`}
          >

            <div
              className={`${styles.sectionHeader} ${styles.dailySummaryHeader}`}
            >
              <span
                className={styles.dailySummaryHeaderIcon}
                aria-hidden="true"
              >
                ▤
              </span>

              <div className={styles.dailySummaryHeaderCopy}>
                <p className={styles.kicker}>
                  Oggi
                </p>
                <h2>Resoconto giornaliero</h2>
                <p className={styles.dailySummarySubtitle}>
                  Pasti e attività, tutto in un unico elenco.
                </p>
              </div>

              <details className={styles.dailyAddMenu}>
                <summary className={styles.addMealFab}>
                  <span aria-hidden="true">+</span>
                  <span>Aggiungi</span>
                  <span
                    className={styles.dailyAddChevron}
                    aria-hidden="true"
                  >
                    ▾
                  </span>
                </summary>

                <div className={styles.dailyAddMenuPanel}>
                  {Object.keys(day.meals)
                    .sort(
                      (slotA, slotB) =>
                        ["Colazione", "Pranzo", "Snack", "Cena"].indexOf(
                          mealLabel(slotA),
                        ) -
                        ["Colazione", "Pranzo", "Snack", "Cena"].indexOf(
                          mealLabel(slotB),
                        ),
                    )
                    .map((slot) => (
                      <button
                        key={slot}
                        type="button"
                        onClick={(event) => {
                          const menuDetails =
                            event.currentTarget.closest(
                              "details",
                            );

                          if (menuDetails) {
                            menuDetails.open = false;
                          }

                          openQuickAddMeal(slot);
                        }}
                      >
                        <span aria-hidden="true">
                          {mealIcon(slot)}
                        </span>
                        {mealLabel(slot)}
                      </button>
                    ))}

                  <button
                    type="button"
                    onClick={(event) => {
                      const menuDetails =
                        event.currentTarget.closest(
                          "details",
                        );

                      if (menuDetails) {
                        menuDetails.open = false;
                      }

                      openQuickAddActivity();
                    }}
                  >
                    <span aria-hidden="true">🏃</span>
                    Attività
                  </button>

                  <button
                    type="button"
                    onClick={(event) => {
                      const menuDetails =
                        event.currentTarget.closest("details");

                      if (menuDetails) {
                        menuDetails.open = false;
                      }

                      void openQuickAddWeight();
                    }}
                  >
                    <span aria-hidden="true">⚖️</span>
                    Peso
                  </button>
                </div>
              </details>
            </div>

            <a
              href="/inventory"
              className={styles.homePantryCta}
            >
              <span
                className={styles.homePantryCtaIcon}
                aria-hidden="true"
              >
                🧺
              </span>

              <span
                className={styles.homePantryCtaCopy}
              >
                <strong>Dispensa</strong>

                <span>
                  {pantryHomeSummary.breakfastSnack > 0
                    ? `${pantryHomeSummary.breakfastSnack} ${
                        pantryHomeSummary.breakfastSnack === 1
                          ? "alimento"
                          : "alimenti"
                      } per colazione/snack`
                    : "Nessun alimento per colazione/snack"}

                  {" · "}

                  {pantryHomeSummary.lunchDinner > 0
                    ? `${pantryHomeSummary.lunchDinner} ${
                        pantryHomeSummary.lunchDinner === 1
                          ? "alimento"
                          : "alimenti"
                      } per pranzo/cena`
                    : "nessun alimento per pranzo/cena"}

                  {pantryCookableRecipeCount > 0
                    ? ` · ${
                        pantryCookableRecipeCount === 1
                          ? "1 ricetta pronta"
                          : `${pantryCookableRecipeCount} ricette pronte`
                      }`
                    : ""}
                </span>
              </span>

              <span
                className={styles.homePantryCtaAction}
              >
                Apri dispensa
                <span aria-hidden="true">→</span>
              </span>
            </a>

            {actualActivities.length > 0 ? (
              <details className={styles.dailyActivityEntry}>
                <summary>
                  <span
                    className={styles.dailyEntryIcon}
                    aria-hidden="true"
                  >
                    🏃
                  </span>

                  <span className={styles.dailyEntryMain}>
                    <strong>Attività di oggi</strong>
                    <span>
                      {actualActivities.length === 1
                        ? actualActivities[0].activity_name
                        : `${actualActivities.length} attività registrate`}
                    </span>
                  </span>

                  <strong className={styles.dailyActivityCalories}>
                    −{roundNumber(burnedCalories)} kcal
                  </strong>

                  <span
                    className={styles.dailyEntryDone}
                    aria-label="Registrata"
                  >
                    ✓
                  </span>

                  <span
                    className={styles.dailyEntryChevron}
                    aria-hidden="true"
                  >
                    ▾
                  </span>
                </summary>

                <div className={styles.dailyActivityDetails}>
                  {actualActivities.map((activity) => (
                    <div
                      key={String(
                        activity.id ??
                          `${activity.activity_name}-${activity.date}`,
                      )}
                      className={styles.dailyActivityDetailRow}
                    >
                      <span aria-hidden="true">🏃</span>

                      <div>
                        <strong>{activity.activity_name}</strong>

                        <span>
                          {activity.duration_seconds
                            ? `${Math.round(
                                activity.duration_seconds / 60,
                              )} min`
                            : "Attività registrata"}
                          {activity.distance_meters
                            ? ` · ${(
                                activity.distance_meters / 1000
                              ).toLocaleString("it-IT", {
                                maximumFractionDigits: 2,
                              })} km`
                            : ""}
                        </span>
                      </div>

                      <strong>
                        −{roundNumber(
                          Number(activity.burned_calories || 0),
                        )} kcal
                      </strong>
                    </div>
                  ))}

                  <button
                    type="button"
                    className={
                      styles.dailyActivityAddAnother
                    }
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      openQuickAddActivity();
                    }}
                  >
                    <span aria-hidden="true">+</span>
                    Aggiungi attività
                  </button>
                </div>
              </details>
            ) : null}

            <div className={styles.mealList}>
              {Object.entries(day.meals)
                .sort(
                  ([slotA], [slotB]) =>
                    ["Colazione", "Pranzo", "Snack", "Cena"].indexOf(
                      mealLabel(slotA),
                    ) -
                    ["Colazione", "Pranzo", "Snack", "Cena"].indexOf(
                      mealLabel(slotB),
                    ),
                )
                .map(
                ([slot, meal]) => (
                  <details
                    key={slot}
                    data-meal-slot={slot}
                    className={`${styles.mealCard} ${styles.dailyMealEntry} ${
                      actualMealForSlot(slot)
                        ? actualMealsForSlot(slot).length <= 1
                          ? styles.mealCardOneItem
                          : actualMealsForSlot(slot).length === 2
                            ? styles.mealCardTwoItems
                            : styles.mealCardManyItems
                        : ""
                    }`}
                  >
                    <summary
                      className={styles.dailyMealSummary}
                    >
                      <span
                        className={styles.dailyEntryIcon}
                        aria-hidden="true"
                      >
                        {mealIcon(slot)}
                      </span>

                      <span
                        className={styles.dailyEntryMain}
                      >
                        <strong>
                          {mealLabel(slot)}
                        </strong>

                        <span>
                          {actualMealForSlot(slot)
                            ? actualMealsForSlot(slot)
                                .map((registeredMeal) =>
                                  registeredMeal.name.replace(
                                    /\\s*\\([^)]*porz\\.\\)\\s*$/i,
                                    "",
                                  ),
                                )
                                .join(" · ")
                            : meal.value ??
                              "Da decidere"}
                        </span>
                      </span>

                      <strong
                        className={
                          styles.dailyMealCalories
                        }
                      >
                        {actualMealForSlot(slot)
                          ? `${roundNumber(
                              actualMealsForSlot(
                                slot,
                              ).reduce(
                                (
                                  total,
                                  registeredMeal,
                                ) =>
                                  total +
                                  Number(
                                    registeredMeal.calories ||
                                      0,
                                  ),
                                0,
                              ),
                            )} kcal`
                          : meal.estimated_calories != null
                            ? `~${roundNumber(
                                Number(
                                  meal.estimated_calories,
                                ),
                              )} kcal`
                            : "—"}
                      </strong>

                      {actualMealForSlot(slot) ? (
                        <span
                          className={styles.dailyEntryDone}
                          aria-label="Registrato"
                        >
                          ✓
                        </span>
                      ) : null}

                      <span
                        className={
                          styles.dailyEntryChevron
                        }
                        aria-hidden="true"
                      >
                        ▾
                      </span>
                    </summary>

                    <button
                      type="button"
                      className={
                        styles.dailyMealAddAnother
                      }
                      onClick={(event) => {
                        event.preventDefault();
                        event.stopPropagation();

                        openQuickAddMeal(slot);
                      }}
                    >
                      <span aria-hidden="true">+</span>
                      Aggiungi altro
                    </button>

                    <div
                      className={
                        styles.mealCardTop
                      }
                    >
                      <div className={styles.mealIdentity}>
                        <span
                          className={styles.mealIcon}
                          aria-hidden="true"
                        >
                          {mealIcon(slot)}
                        </span>

                        <span
                          className={styles.mealLabel}
                        >
                          {mealLabel(slot)}
                        </span>
                      </div>

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
                                    {registeredMeal.name.replace(
                                      /\s*\([^)]*porz\.\)\s*$/i,
                                      "",
                                    )}
                                  </strong>

                                  <span>
                                    {registeredMeal.recipe_servings
                                      ? `${roundNumber(
                                          registeredMeal.recipe_servings,
                                        )} ${
                                          registeredMeal.recipe_servings === 1
                                            ? "porzione"
                                            : "porzioni"
                                        }`
                                      : "1 porzione"}
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
                          <div className={styles.registeredMealNutrition}>
                            <div className={styles.nutritionItem}>
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
                                )}
                              </strong>
                              <span>kcal</span>
                            </div>

                            <div className={styles.nutritionItem}>
                              <strong>
                                {roundNumber(
                                  actualMealsForSlot(slot).reduce(
                                    (total, registeredMeal) =>
                                      total +
                                      Number(
                                        registeredMeal.protein || 0,
                                      ),
                                    0,
                                  ),
                                )}
                              </strong>
                              <span>Proteine</span>
                            </div>

                            <div className={styles.nutritionItem}>
                              <strong>
                                {roundNumber(
                                  actualMealsForSlot(slot).reduce(
                                    (total, registeredMeal) =>
                                      total +
                                      Number(
                                        registeredMeal.carbs || 0,
                                      ),
                                    0,
                                  ),
                                )}
                              </strong>
                              <span>Carboidrati</span>
                            </div>

                            <div className={styles.nutritionItem}>
                              <strong>
                                {roundNumber(
                                  actualMealsForSlot(slot).reduce(
                                    (total, registeredMeal) =>
                                      total +
                                      Number(
                                        registeredMeal.fat || 0,
                                      ),
                                    0,
                                  ),
                                )}
                              </strong>
                              <span>Grassi</span>
                            </div>
                          </div>
                        ) : null}
                        {actualMealsForSlot(slot).length > 0 ? (
                          <div
                            className={
                              styles.registeredMealInsights
                            }
                          >
                            <span
                              className={
                                styles.registeredMealInsightSuccess
                              }
                            >
                              ✓ Pasto registrato
                            </span>

                            {actualMealsForSlot(slot).reduce(
                              (total, registeredMeal) =>
                                total +
                                Number(
                                  registeredMeal.protein || 0,
                                ),
                              0,
                            ) < 15 ? (
                              <span
                                className={
                                  styles.registeredMealInsightWarning
                                }
                              >
                                ▮▮ Proteine basse
                              </span>
                            ) : actualMealsForSlot(slot).reduce(
                                (total, registeredMeal) =>
                                  total +
                                  Number(
                                    registeredMeal.protein || 0,
                                  ),
                                0,
                              ) <= 30 ? (
                              <span
                                className={
                                  styles.registeredMealInsightSuccess
                                }
                              >
                                ✓ Buon apporto proteico
                              </span>
                            ) : (
                              <span
                                className={
                                  styles.registeredMealInsightSuccess
                                }
                              >
                                ↑ Ricco di proteine
                              </span>
                            )}
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
                            <label
                              className={
                                styles.registeredMealTypeField
                              }
                            >
                              <span>Sposta nel pasto</span>

                              <select
                                value={mealEditType}
                                onChange={(event) =>
                                  setMealEditType(
                                    event.target.value,
                                  )
                                }
                              >
                                <option value="Colazione">
                                  Colazione
                                </option>
                                <option value="Pranzo">
                                  Pranzo
                                </option>
                                <option value="Snack">
                                  Snack
                                </option>
                                <option value="Cena">
                                  Cena
                                </option>
                              </select>
                            </label>

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
                          {slot === nextMeal?.next_slot &&
                          !actualMealForSlot(slot) &&
                          nextMealOptions?.recommended
                            ? nextMealOptions.recommended
                                .candidate.name
                            : meal.value ||
                              "Nessuna routine abbastanza forte"}
                        </strong>

                        {slot === nextMeal?.next_slot &&
                        !actualMealForSlot(slot) &&
                        nextMealOptions?.recommended ? (
                          <p className={styles.mealMeta}>
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
                            {typeof nextMealOptions.recommended
                              .candidate.protein_g === "number"
                              ? ` · ${roundNumber(
                                  nextMealOptions.recommended
                                    .candidate.protein_g,
                                )} g proteine`
                              : ""}
                          </p>
                        ) : typeof meal.estimated_calories ===
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
                              "component_reduction"
                                ? "Pasto alleggerito"
                                : nextMealOptions.recommended
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

                    {slot === nextMeal?.next_slot &&
                    !actualMealForSlot(slot) &&
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
                              if (alternateSlot === slot) {
                                closeAlternateMeal();
                              } else {
                                openAlternateMeal(slot);
                              }
                            }}
                          >
                            Ho mangiato altro
                          </button>
                        </div>

                      </>
                    ) : null}

                    {slot === "dinner" &&
                    slot === nextMeal?.next_slot &&
                    !actualMealForSlot(slot) &&
                    nextMealOptions?.day_context?.kind ===
                      "training_prep" ? (
                      <div
                        className={
                          styles.trainingPrepNotice
                        }
                      >
                        <div
                          className={
                            styles.trainingPrepIcon
                          }
                          aria-hidden="true"
                        >
                          ↗
                        </div>

                        <div>
                          <span
                            className={
                              styles.trainingPrepEyebrow
                            }
                          >
                            ALLENAMENTO DI DOMANI
                          </span>

                          <strong>
                            {experienceMode === "zero"
                              ? "Domani si corre. Sorpresa: serve carburante."
                              : "Preparazione per domani"}
                          </strong>

                          <p>
                            {
                              nextMealOptions
                                .day_context.message
                            }
                          </p>
                        </div>
                      </div>
                    ) : null}

                        {alternateSlot === slot ? (
                          <div
                            id={`home-add-meal-${slot}`}
                            className={`${styles.alternateMealForm} ${styles.alternateMealFormActive}`}
                          >
                            <div>
                              <div className={styles.quickMealChoicesHeader}>
                                <div>
                                  <strong>
                                    Scelte recenti per {mealLabel(slot).toLocaleLowerCase("it")}
                                  </strong>
                                  <span>
                                    Solo proposte adatte a questo pasto.
                                  </span>
                                </div>
                              </div>

                              {quickMealAlternatesForSlot(slot).length ? (
                                <div className={styles.quickMealChoices}>
                                  {quickMealAlternatesForSlot(slot)
                                    .slice(0, 6)
                                    .map((item) => (
                                      <button
                                        key={item.key}
                                        type="button"
                                        className={styles.quickMealChoice}
                                        data-selected={
                                          alternateSelectedKey === item.key
                                            ? "true"
                                            : "false"
                                        }
                                        onClick={() =>
                                          selectQuickMealAlternate(item.key)
                                        }
                                      >
                                        <span>
                                          <strong>{item.name}</strong>
                                          <small>
                                            {Math.round(item.calories)} kcal
                                            {item.protein > 0
                                              ? ` · ${Math.round(item.protein)} g proteine`
                                              : ""}
                                          </small>
                                        </span>
                                        <span aria-hidden="true">→</span>
                                      </button>
                                    ))}
                                </div>
                              ) : (
                                <p className={styles.quickMealChoicesEmpty}>
                                  Nessuna scelta recente per questo pasto.
                                </p>
                              )}

                              {alternateSelectedKey?.startsWith(
                                "recipe:",
                              ) ? (
                                <label
                                  className={
                                    styles.alternatePortionField
                                  }
                                >
                                  Porzioni
                                  <input
                                    type="number"
                                    min="0.5"
                                    step="0.5"
                                    value={
                                      alternateQuantity
                                    }
                                    onChange={(event) => {
                                      const nextQuantity =
                                        Math.max(
                                          0.5,
                                          Number(
                                            event.target
                                              .value,
                                          ) || 0.5,
                                        );

                                      setAlternateQuantity(
                                        nextQuantity,
                                      );

                                      const selected =
                                        knownAlternates.find(
                                          (item) =>
                                            item.key ===
                                            alternateSelectedKey,
                                        );

                                      if (!selected) {
                                        return;
                                      }

                                      setAlternateCalories(
                                        String(
                                          Math.round(
                                            selected.calories *
                                              nextQuantity,
                                          ),
                                        ),
                                      );

                                      setAlternateProtein(
                                        String(
                                          Math.round(
                                            selected.protein *
                                              nextQuantity,
                                          ),
                                        ),
                                      );

                                      setAlternateCarbs(
                                        String(
                                          Math.round(
                                            selected.carbs *
                                              nextQuantity,
                                          ),
                                        ),
                                      );

                                      setAlternateFat(
                                        String(
                                          Math.round(
                                            selected.fat *
                                              nextQuantity,
                                          ),
                                        ),
                                      );
                                    }}
                                  />
                                </label>
                              ) : null}

                              <span className={styles.manualMealLabel}>oppure scrivi manualmente</span>
                              <input
                                type="text"
                                data-home-add-meal-name="true"
                                value={alternateName}
                                placeholder="Es. Piadina con pollo"
                                onChange={(event) => {
                                  setAlternateName(
                                    event.target.value,
                                  );
                                }}
                              />
                            </div>

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
                  </details>
                ),
              )}

            </div>
          </section>

          {!actualDinner &&
          showDinnerAlternatives ? (
            <section
              {...dashboardWidgetProps("dinner")}
              className={`${styles.decisionSection} ${styles.dashboardWidget}`}
            >
            {dashboardWidgetControls(
              "dinner",
              "Alternative cena",
            )}
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

          <section
            className={styles.homeBottomOverview}
            aria-label="Focus della giornata e settimana"
          >
            <div className={styles.dailyFocusCard}>
              <div className={styles.bottomOverviewHeader}>
                <div className={styles.bottomOverviewTitleGroup}>
                  <span
                    className={`${styles.bottomOverviewTitleIcon} ${styles.focusTitleIcon}`}
                    aria-hidden="true"
                  >
                    ◎
                  </span>

                  <div>
                    <p className={styles.bottomOverviewKicker}>
                      Oggi
                    </p>
                    <h2>
                      Focus della giornata
                    </h2>
                  </div>
                </div>

                <span
                  className={styles.bottomOverviewBadge}
                >
                  In tempo reale
                </span>
              </div>

              <p className={styles.bottomOverviewIntro}>
                Dove sei rispetto ai riferimenti di oggi.
              </p>

              <div className={styles.dailyFocusRings}>
                {dailyFocusItems.map((item) => (
                  <div
                    key={item.label}
                    data-focus={item.label}
                    className={
                      item.target > 0
                        ? styles.dailyFocusItem
                        : `${styles.dailyFocusItem} ${styles.dailyFocusItemUntargeted}`
                    }
                  >
                    {item.target > 0 ? (
                      <div
                        className={styles.dailyFocusRing}
                        style={{
                          background: `conic-gradient(${
                            item.label === "Calorie"
                              ? "#ff6868"
                              : item.label === "Proteine"
                                ? "#63cf91"
                                : item.label === "Carboidrati"
                                  ? "#69a9ff"
                                  : "#f4bb42"
                          } ${item.progress}%, #edf0f2 ${item.progress}% 100%)`,
                        }}
                        role="img"
                        aria-label={`${item.label}: ${Math.round(item.progress)}%`}
                      >
                        <div
                          className={styles.dailyFocusRingInner}
                        >
                          <span
                            className={styles.dailyFocusMetricIcon}
                            aria-hidden="true"
                          >
                            {item.icon}
                          </span>

                          <strong>
                            {Math.round(
                              item.consumed,
                            )}
                          </strong>

                          <small>
                            {item.unit}
                          </small>
                        </div>
                      </div>
                    ) : (
                      <div
                        className={styles.dailyFocusStat}
                        role="img"
                        aria-label={`${item.label}: ${Math.round(item.consumed)} ${item.unit} registrati`}
                      >
                        <span
                          className={styles.dailyFocusMetricIcon}
                          aria-hidden="true"
                        >
                          {item.icon}
                        </span>

                        <strong>
                          {Math.round(
                            item.consumed,
                          )}
                        </strong>

                        <span>
                          {item.unit}
                        </span>
                      </div>
                    )}

                    <strong
                      className={styles.dailyFocusLabel}
                    >
                      {item.label}
                    </strong>

                    <span
                      className={styles.dailyFocusNumbers}
                    >
                      {item.target > 0
                        ? `${Math.round(
                            item.progress,
                          )}% · ${Math.round(
                            item.consumed,
                          )} / ${Math.round(
                            item.target,
                          )} ${item.unit}`
                        : `${Math.round(
                            item.consumed,
                          )} ${item.unit} registrati`}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div
              id="home-week-overview"
              className={styles.weekOverviewCard}
            >
              <div className={styles.bottomOverviewHeader}>
                <div className={styles.bottomOverviewTitleGroup}>
                  <span
                    className={`${styles.bottomOverviewTitleIcon} ${styles.weekTitleIcon}`}
                    aria-hidden="true"
                  >
                    ▦
                  </span>

                  <div>
                    <p className={styles.bottomOverviewKicker}>
                      Ritmo
                    </p>
                    <h2>
                      La tua settimana
                    </h2>
                  </div>
                </div>

                <span
                  className={styles.weekCalendarIcon}
                  aria-hidden="true"
                >
                  7g
                </span>
              </div>

              <p className={styles.bottomOverviewIntro}>
                I segnali reali dei giorni che hai registrato,
                senza trasformare la settimana in una pagella.
              </p>

              <div className={styles.weekKpis}>
                <div className={styles.weekKpi}>
                  <span className={styles.weekKpiIcon} aria-hidden="true">
                    ✓
                  </span>
                  <div>
                    <span>Giorni registrati</span>
                    <strong>
                      {weeklyMealDays} / 7
                    </strong>
                  </div>
                </div>

                <div className={styles.weekKpi}>
                  <span className={styles.weekKpiIcon} aria-hidden="true">
                    🍴
                  </span>
                  <div>
                    <span>Pasti settimana</span>
                    <strong>
                      {weeklyMealCount}
                    </strong>
                  </div>
                </div>

                <div className={styles.weekKpi}>
                  <span className={styles.weekKpiIcon} aria-hidden="true">
                    🏃
                  </span>
                  <div>
                    <span>Attività oggi</span>
                    <strong>
                      {actualActivities.length}
                    </strong>
                  </div>
                </div>

                <button
                  type="button"
                  className={`${styles.weekKpi} ${styles.weekWeightKpi}`}
                  onClick={() => {
                    void openWeightQuickAdd(
                      latestWeightEntry,
                    );
                  }}
                  aria-expanded={weightQuickAddOpen}
                >
                  <span
                    className={styles.weekKpiIcon}
                    aria-hidden="true"
                  >
                    ⚖
                  </span>

                  <div>
                    <span>Ultimo peso</span>

                    <strong>
                      {latestWeight != null
                        ? `${latestWeight.toLocaleString(
                            "it-IT",
                            {
                              maximumFractionDigits: 1,
                            },
                          )} kg`
                        : "Aggiungi"}
                    </strong>
                  </div>

                  <span
                    className={styles.weekWeightEditHint}
                    aria-hidden="true"
                  >
                    +
                  </span>
                </button>
              </div>

              {weightQuickAddOpen ? (
                <div className={styles.weekWeightQuickAdd}>
                  <div className={styles.weekWeightQuickAddCopy}>
                    <span>Peso di oggi</span>
                    <strong>
                      {weightQuickAddEditingEntry
                        ? `Modifica il peso del ${new Date(
                            `${weightQuickAddEditingEntry.date}T00:00:00`,
                          ).toLocaleDateString(
                            "it-IT",
                            {
                              day: "numeric",
                              month: "short",
                            },
                          )}.`
                        : "Registra il peso di oggi senza lasciare la Home."}
                    </strong>
                  </div>

                  <div className={styles.weekWeightQuickAddControls}>
                    <label>
                      <span className={styles.srOnly}>
                        Peso in kg
                      </span>

                      <input
                        type="text"
                        inputMode="decimal"
                        value={weightQuickAddValue}
                        placeholder="77,8"
                        onChange={(event) => {
                          setWeightQuickAddValue(
                            event.target.value,
                          );
                          setWeightQuickAddMessage(null);
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            void saveWeightQuickAdd();
                          }
                        }}
                      />

                      <span>kg</span>
                    </label>

                    <button
                      type="button"
                      onClick={() => {
                        void saveWeightQuickAdd();
                      }}
                      disabled={weightQuickAddSaving}
                    >
                      {weightQuickAddSaving
                        ? "Salvo…"
                        : weightQuickAddEditingEntry
                          ? "Aggiorna"
                          : "Registra"}
                    </button>

                    <button
                      type="button"
                      className={styles.weekWeightCancel}
                      onClick={() => {
                        setWeightQuickAddOpen(false);
                        setWeightQuickAddMessage(null);
                      }}
                    >
                      Chiudi
                    </button>
                  </div>

                  <div
                    className={styles.weekWeightRecent}
                    aria-label="Pesi recenti"
                  >
                    <div
                      className={styles.weekWeightRecentHeader}
                    >
                      <strong>Pesi recenti</strong>
                      {weightHistoryLoading ? (
                        <span>Carico…</span>
                      ) : null}
                    </div>

                    {weightHistory.length ? (
                      <div
                        className={styles.weekWeightRecentList}
                      >
                        {[...weightHistory]
                          .sort(
                            (left, right) =>
                              right.date.localeCompare(
                                left.date,
                              ),
                          )
                          .slice(0, 5)
                          .map((entry) => (
                            <button
                              key={entry.id}
                              type="button"
                              className={
                                String(
                                  weightQuickAddEditingEntry?.id,
                                ) ===
                                String(entry.id)
                                  ? styles.weekWeightRecentActive
                                  : undefined
                              }
                              onClick={() => {
                                setWeightQuickAddEditingEntry(
                                  entry,
                                );
                                setWeightQuickAddValue(
                                  String(
                                    Number(
                                      Number(
                                        entry.weight,
                                      ).toFixed(1),
                                    ),
                                  ),
                                );
                                setWeightQuickAddMessage(
                                  null,
                                );
                              }}
                            >
                              <span>
                                {new Date(
                                  `${entry.date}T00:00:00`,
                                ).toLocaleDateString(
                                  "it-IT",
                                  {
                                    day: "numeric",
                                    month: "short",
                                  },
                                )}
                              </span>

                              <strong>
                                {Number(
                                  entry.weight,
                                ).toLocaleString(
                                  "it-IT",
                                  {
                                    maximumFractionDigits: 1,
                                  },
                                )}{" "}
                                kg
                              </strong>

                              <span>Modifica</span>
                            </button>
                          ))}
                      </div>
                    ) : (
                      <span
                        className={styles.weekWeightRecentEmpty}
                      >
                        Nessun peso precedente.
                      </span>
                    )}
                  </div>

                  {weightQuickAddMessage ? (
                    <p
                      className={styles.weekWeightQuickAddMessage}
                    >
                      {weightQuickAddMessage}
                    </p>
                  ) : null}
                </div>
              ) : null}

              <div className={styles.weekDays}>
                {weekOverviewDays.map((item) => (
                  <div
                    key={item.iso}
                    className={
                      item.isToday
                        ? `${styles.weekDay} ${styles.weekDayToday}`
                        : styles.weekDay
                    }
                  >
                    <span
                      className={styles.weekDayName}
                    >
                      {item.shortLabel}
                    </span>

                    <strong>
                      {item.dayNumber}
                    </strong>

                    <span
                      className={`${styles.weekDayDot} ${
                        item.mealCount > 0
                          ? styles.weekDayDotRecorded
                          : ""
                      } ${
                        item.isToday
                          ? styles.weekDayDotActive
                          : ""
                      }`}
                      aria-label={
                        item.mealCount > 0
                          ? `${item.mealCount} pasti registrati`
                          : "Nessun pasto registrato"
                      }
                      title={
                        item.mealCount > 0
                          ? `${item.mealCount} pasti registrati`
                          : "Nessun pasto registrato"
                      }
                    >
                      {item.mealCount > 0 ? "✓" : ""}
                    </span>
                  </div>
                ))}
              </div>

              <div className={styles.weekTodaySummary}>
                <span
                  className={styles.weekTodayProgress}
                  aria-hidden="true"
                >
                  <span
                    style={{
                      width: `${budgetProgress}%`,
                    }}
                  />
                </span>

                <div>
                  <strong>
                    Budget di oggi
                  </strong>
                  <span>
                    {budget
                      ? `${Math.round(
                          budget.consumed_kcal,
                        )} di ${Math.round(
                          budget.daily_budget_kcal,
                        )} kcal`
                      : "Budget non disponibile"}
                  </span>
                </div>
              </div>

              <p className={styles.weekOverviewNote}>
                {weeklyMealDays > 0
                  ? `${weeklyMealDays} giorni su 7 hanno almeno un pasto registrato.`
                  : "La settimana inizierà a prendere forma quando registrerai i pasti."}
              </p>
            </div>
          </section>



          {/* HOME LEGACY SECOND HALF REMOVED V1
              QuickAdd / weight / goal / RegisteredToday
              are intentionally no longer rendered here. */}

          </div>

        </>
      ) : null}
      </main>
    </>
  );
}
