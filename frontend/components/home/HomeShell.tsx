"use client";

import { AppNav } from "@/components/navigation/AppNav";
import { WelcomeJourney } from "@/components/onboarding/WelcomeJourney";
import { QuickAdd } from "@/components/home/QuickAdd";
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
import { RegisteredToday } from "@/components/home/RegisteredToday";
import { getActivitiesForDate, type Activity } from "@/lib/api/activities";

import {
  type DragEvent,
  useEffect,
  useMemo,
  useState,
} from "react";

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
  getLatestWeight,
  getWeightHistory,
  type WeightEntry,
} from "@/lib/api/weight";
import {
  getProfile,
  type ProfileResponse,
} from "@/lib/api/profile";

import styles from "./HomeShell.module.css";

type ExperienceMode =
  | "standard"
  | "zero";

const EXPERIENCE_MODE_KEY =
  "sanosync-experience-mode";

function readExperienceMode(): ExperienceMode {
  if (typeof window === "undefined") {
    return "standard";
  }

  return window.localStorage.getItem(
    EXPERIENCE_MODE_KEY,
  ) === "zero"
    ? "zero"
    : "standard";
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
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
    lunch: "▦",
    snack: "●",
    dinner: "♨",
  }[slot] ?? "•";
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

export function HomeShell() {
  const [experienceMode, setExperienceMode] =
    useState<ExperienceMode>(readExperienceMode);

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
      ? budgetResult.budget.daily_budget_kcal +
        budgetResult.budget.goal_adjustment_kcal
      : 0;
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
    if (
      conversationPreview ||
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

        const [
          dayPayload,
          budgetPayload,
          briefingPayload,
          nextMealPayload,
          mealsPayload,
          activitiesPayload,
          latestWeightPayload,
          weightHistoryPayload,
          dayHistoryPayload,
          profilePayload,
        ] = await Promise.all([
          getDay(
            date,
            accessToken,
          ),
          getDayBudget(
            date,
            accessToken,
          ),
          getDayBriefing(
            date,
            briefingMoment(),
            experienceMode,
            briefingHour,
            accessToken,
          ).catch(() => null),
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
          getWeightHistory(
            accessToken,
          ).catch(() => ({
            count: 0,
            items: [],
          })),
          getDayHistory(
            accessToken,
          ),
          getProfile(accessToken),
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
          setDayBriefing(
            briefingPayload?.message ?? null,
          );
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
          setWeightHistory(
            weightHistoryPayload.items,
          );
          setActualDinner(
            mealsPayload.items.find(
              (meal) => meal.meal_type === "Cena",
            ) ?? null,
          );

          setDayHistory(
            dayHistoryPayload,
          );
          setProfile(profilePayload);

          const metadata = profilePayload.metadata;
          setShowWelcomeJourney(
            !metadata.gender ||
              !metadata.birth_date ||
              !metadata.height ||
              !metadata.goal_mode ||
              latestWeightPayload.item?.weight == null,
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
  }, [accessToken, experienceMode, briefingHour]);

  const budget =
    budgetResult?.budget ?? null;

  const bmr = Number(budgetResult?.profile?.bmr ?? 0);
  const needsWelcomeJourney =
    showWelcomeJourney ||
    budgetResult?.status === "profile_incomplete";

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

    try {
      await updateDailyLog(
        accessToken,
        todayIso(),
        changes,
      );

      setDayPlannerMessage("Giornata aggiornata.");

      await refreshHome();
    } catch (err) {
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

  return (
    <>
      <AppNav experienceMode={experienceMode} />

      {!loading && needsWelcomeJourney && accessToken ? (
        <WelcomeJourney
          accessToken={accessToken}
          initialName={
            typeof profile?.metadata?.name === "string"
              ? profile.metadata.name
              : firstName
          }
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

        <div
          className={styles.experienceSwitch}
          aria-label="Modalità SanoSync"
        >
          <button
            type="button"
            className={
              experienceMode === "standard"
                ? styles.experienceSwitchActive
                : undefined
            }
            onClick={() => {
              setExperienceMode("standard");
              window.localStorage.setItem(
                EXPERIENCE_MODE_KEY,
                "standard",
              );
            }}
          >
            Standard
          </button>

          <button
            type="button"
            className={
              experienceMode === "zero"
                ? styles.experienceSwitchZeroActive
                : undefined
            }
            onClick={() => {
              setExperienceMode("zero");
              window.localStorage.setItem(
                EXPERIENCE_MODE_KEY,
                "zero",
              );
            }}
          >
            Zero
          </button>
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
                  day.activity_plan.value,
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
              day.activity_plan.value,
            )}
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

          {dayPlannerMessage ? (
            <p className={styles.muted}>
              {dayPlannerSaving
                ? "Salvataggio..."
                : dayPlannerMessage}
            </p>
          ) : null}

          {budget ? (
            <section
              className={`${styles.budgetHero} ${
                budgetExpanded
                  ? styles.budgetHeroExpanded
                  : styles.budgetHeroCollapsed
              }`}
            >
              <div className={styles.budgetEyebrow}>
                <span aria-hidden="true">◎</span>
                <strong>Il tuo piano di oggi</strong>
              </div>

              <div className={styles.budgetHeader}>
                <div className={styles.budgetColumn}>
                  <span className={styles.budgetLabel}>
                    Kcal disponibili
                  </span>

                  <div className={styles.budgetValueRow}>
                    <strong className={styles.budgetAvailable}>
                      {roundNumber(budget.available_kcal)}
                    </strong>
                    <span className={styles.budgetKcal}>kcal</span>
                  </div>

                  <span className={styles.budgetPositive}>
                    {budget.consumed_kcal === 0
                      ? "Budget disponibile"
                      : budget.consumed_kcal <=
                        budget.daily_budget_kcal
                      ? "Stai rispettando il tuo deficit"
                      : budget.consumed_kcal <
                        maintenanceBudgetKcal
                      ? "Sei ancora in deficit"
                      : "Hai raggiunto il mantenimento"}
                  </span>
                </div>

                <div className={styles.budgetDivider} />

                <div className={styles.budgetColumn}>
                  <span className={styles.budgetLabel}>
                    Metabolismo basale
                  </span>

                  <div className={styles.budgetValueRow}>
                    <strong className={styles.budgetMainValue}>
                      {bmr > 0 ? roundNumber(bmr) : "—"}
                    </strong>
                    <span className={styles.budgetKcal}>kcal</span>
                  </div>

                  <span className={styles.budgetSecondary}>
                    BMR giornaliero
                  </span>
                </div>

                <div className={styles.budgetDivider} />

                <div className={styles.budgetColumn}>
                  <span className={styles.budgetLabel}>
                    Obiettivo con deficit
                  </span>

                  <div className={styles.budgetValueRow}>
                    <strong className={styles.budgetMainValue}>
                      {roundNumber(
                        budget.consumed_kcal +
                          budget.available_kcal,
                      )}
                    </strong>
                    <span className={styles.budgetKcal}>kcal</span>
                  </div>

                  <span className={styles.budgetSecondary}>
                    {budget.goal_mode === "loss" &&
                    budget.goal_adjustment_kcal > 0
                      ? `${roundNumber(
                          budget.goal_adjustment_kcal,
                        )} kcal di deficit`
                      : "Target giornaliero"}
                  </span>
                </div>

                <div className={styles.budgetDivider} />

                <div className={styles.budgetColumn}>
                  <span className={styles.budgetLabel}>
                    Consumato oggi
                  </span>

                  <div className={styles.budgetValueRow}>
                    <strong className={styles.budgetMainValue}>
                      {roundNumber(budget.consumed_kcal)}
                    </strong>
                    <span className={styles.budgetKcal}>kcal</span>
                  </div>

                  <span className={styles.budgetSecondary}>
                    {budget.available_kcal >= 0
                      ? `${roundNumber(
                          budget.available_kcal,
                        )} kcal disponibili`
                      : "Target superato"}
                  </span>
                </div>

                <div className={styles.budgetDivider} />

                <button
                  type="button"
                  className={styles.budgetStatus}
                  aria-expanded={budgetExpanded}
                  onClick={() =>
                    setBudgetExpanded((current) => !current)
                  }
                >
                  <span className={styles.budgetLabel}>
                    Stato di oggi
                  </span>

                  <span
                    className={`${styles.budgetStatusRow} ${
                      budget.consumed_kcal === 0
                        ? styles.budgetStatusPending
                        : ""
                    }`}
                  >
                    <span
                      className={styles.budgetStatusIcon}
                      aria-hidden="true"
                    >
                      {budget.consumed_kcal === 0
                        ? "○"
                        : "✓"}
                    </span>

                    <strong>
                      {budget.consumed_kcal === 0
                        ? "Giornata da iniziare"
                        : budget.consumed_kcal <
                          maintenanceBudgetKcal
                        ? "Deficit in corso"
                        : "Mantenimento raggiunto"}
                    </strong>
                  </span>

                  <span
                    className={`${styles.budgetChevron} ${
                      budgetExpanded
                        ? styles.budgetChevronUp
                        : ""
                    }`}
                    aria-hidden="true"
                  />
                </button>
              </div>

              <div className={styles.budgetScale}>
                <span className={styles.budgetScaleStart}>
                  0
                </span>

                <div className={styles.budgetScaleTrack}>
                  <div
                    className={styles.budgetScaleFill}
                    style={{
                      width: `${Math.min(
                        100,
                        Math.max(
                          0,
                          maintenanceBudgetKcal > 0
                            ? (budget.consumed_kcal /
                                maintenanceBudgetKcal) *
                                100
                            : 0,
                        ),
                      )}%`,
                    }}
                  />

                  <span
                    className={styles.budgetScaleTarget}
                    style={{
                      left:
                        maintenanceBudgetKcal > 0
                          ? `${Math.min(
                              100,
                              Math.max(
                                0,
                                (budget.daily_budget_kcal /
                                  maintenanceBudgetKcal) *
                                  100,
                              ),
                            )}%`
                          : "0%",
                    }}
                    aria-hidden="true"
                  />
                </div>

                <div className={styles.budgetScaleLabels}>
                  <span>
                    {roundNumber(budget.consumed_kcal)} consumate
                  </span>

                  <span>
                    {roundNumber(
                      budget.consumed_kcal +
                        budget.available_kcal,
                    )}{" "}
                    target
                  </span>

                  <span>
                    {roundNumber(
                      maintenanceBudgetKcal,
                    )}{" "}
                    mantenimento
                  </span>
                </div>
              </div>

              {budgetExpanded ? (
                <div className={styles.budgetExpandedPanel}>
                  <div className={styles.budgetDetail}>
                    <span className={styles.budgetDetailIcon}>
                      🍴
                    </span>
                    <div>
                      <span>Consumate</span>
                      <strong>
                        {roundNumber(
                          budget.consumed_kcal,
                        )}{" "}
                        kcal
                      </strong>
                      <small>di cibo</small>
                    </div>
                  </div>

                  <div className={styles.budgetDetail}>
                    <span className={styles.budgetDetailIcon}>
                      🏃
                    </span>
                    <div>
                      <span>Attività</span>
                      <strong>
                        {roundNumber(burnedCalories)} kcal
                      </strong>
                      <small>bruciate</small>
                    </div>
                  </div>

                  <div className={styles.budgetDetail}>
                    <span className={styles.budgetDetailIcon}>
                      ⚖
                    </span>
                    <div>
                      <span>Rispetto al target</span>
                      <strong>
                        {roundNumber(
                          budget.available_kcal,
                        )}{" "}
                        kcal
                      </strong>
                      <small>
                        {budget.available_kcal >= 0
                          ? "ancora disponibili"
                          : "oltre il target"}
                      </small>
                    </div>
                  </div>

                  <div className={styles.budgetDetail}>
                    <span className={styles.budgetDetailIcon}>
                      ◉
                    </span>
                    <div>
                      <span>Non allocate</span>
                      <strong>
                        {roundNumber(
                          budget.unallocated_kcal,
                        )}{" "}
                        kcal
                      </strong>
                      <small>margine residuo</small>
                    </div>
                  </div>

                  <div className={styles.budgetExplanation}>
                    <span aria-hidden="true">ⓘ</span>
                    <span>
                      Il target con deficit è il budget
                      di mantenimento meno{" "}
                      {roundNumber(
                        budget.goal_adjustment_kcal,
                      )}{" "}
                      kcal di deficit.
                    </span>
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
              {...dashboardWidgetProps("ai")}
              className={`${styles.conversationCard} ${styles.dashboardWidget}`}
            >
            {dashboardWidgetControls(
              "ai",
              "SanoSync AI",
            )}
            <div className={styles.conversationHeader}>
              <div>
                <span className={styles.conversationEyebrow}>
                  <img
                    src={
                      experienceMode === "zero"
                        ? "/assets/SanoSyncAIZero.png"
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

          <section
            {...dashboardWidgetProps("meals")}
            className={`${styles.section} ${styles.mealsSection} ${styles.dashboardWidget}`}
          >
            {dashboardWidgetControls(
              "meals",
              "I tuoi pasti",
            )}
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

              <article
                className={`${styles.mealCard} ${styles.snackCard}`}
              >
                <div className={styles.mealCardTop}>
                  <span className={styles.mealLabel}>
                    Snack
                  </span>

                  <span className={styles.unknownBadge}>
                    Da pianificare
                  </span>
                </div>

                <div className={styles.snackIcon} aria-hidden="true">
                  +
                </div>

                <strong className={styles.mealName}>
                  Uno spuntino per la giornata
                </strong>

                <p className={styles.mealMeta}>
                  Puoi aggiungerlo quando vuoi.
                </p>

                <div className={styles.mealActions}>
                  <button
                    type="button"
                    onClick={() => {
                      document
                        .querySelector<HTMLTextAreaElement>(
                          "textarea",
                        )
                        ?.focus();
                    }}
                  >
                    Aggiungi
                  </button>
                </div>
              </article>
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

          <div
            {...dashboardWidgetProps("quick-add")}
            className={`${styles.quickAddWidget} ${styles.dashboardWidget}`}
          >
            {dashboardWidgetControls(
              "quick-add",
              "Aggiunta rapida",
            )}

            <QuickAdd
              date={todayIso()}
              accessToken={accessToken}
              latestWeight={latestWeight}
              defaultMealType={recommendedMealType}
              onSaved={refreshHome}
            />
          </div>

          <section
            {...dashboardWidgetProps("weight")}
            className={`${styles.insightWidget} ${styles.weightWidget} ${styles.dashboardWidget}`}
          >
            {dashboardWidgetControls(
              "weight",
              "Trend peso",
            )}

            <div className={styles.insightWidgetHeader}>
              <div>
                <p className={styles.kicker}>
                  Andamento
                </p>
                <h2>Trend peso</h2>
              </div>

              <select
                className={styles.periodBadge}
                value={weightRange}
                aria-label="Intervallo del grafico peso"
                onChange={(event) => {
                  setWeightRange(
                    event.target.value as
                      | "14"
                      | "30"
                      | "90"
                      | "180"
                      | "365"
                      | "all",
                  );
                }}
              >
                <option value="14">
                  14 giorni
                </option>
                <option value="30">
                  30 giorni
                </option>
                <option value="90">
                  3 mesi
                </option>
                <option value="180">
                  6 mesi
                </option>
                <option value="365">
                  1 anno
                </option>
                <option value="all">
                  Tutto
                </option>
              </select>
            </div>

            {recentWeights.length ? (
              <>
                <div className={styles.weightSummary}>
                  <strong>
                    {Number(
                      recentWeights[
                        recentWeights.length - 1
                      ].weight,
                    ).toFixed(1)}{" "}
                    kg
                  </strong>

                  {weightChange !== null ? (
                    <span
                      className={
                        weightChange <= 0
                          ? styles.weightChangePositive
                          : styles.weightChangeNeutral
                      }
                    >
                      {weightChange > 0 ? "+" : ""}
                      {weightChange.toFixed(1)} kg
                    </span>
                  ) : null}
                </div>

                <svg
                  className={styles.weightChart}
                  viewBox="0 0 300 110"
                  role="img"
                  aria-label={`Andamento del peso: ${
                    weightRange === "all"
                      ? "tutto il periodo"
                      : `ultimi ${weightRange} giorni`
                  }`}
                >
                  <line x1="12" y1="92" x2="288" y2="92" />
                  <line x1="12" y1="56" x2="288" y2="56" />
                  <line x1="12" y1="20" x2="288" y2="20" />

                  <polyline
                    points={weightChartPoints}
                    fill="none"
                    vectorEffect="non-scaling-stroke"
                  />

                  {recentWeights.map((entry, index) => {
                    const [x, y] =
                      weightChartPoints
                        .split(" ")[index]
                        .split(",");

                    return (
                      <circle
                        key={`${entry.date}-${entry.id}`}
                        cx={x}
                        cy={y}
                        r="3.5"
                      />
                    );
                  })}
                </svg>

                <div className={styles.weightDates}>
                  <span>
                    {new Date(
                      recentWeights[0].date,
                    ).toLocaleDateString("it-IT", {
                      day: "2-digit",
                      month: "2-digit",
                    })}
                  </span>
                  <span>
                    {new Date(
                      recentWeights[
                        recentWeights.length - 1
                      ].date,
                    ).toLocaleDateString("it-IT", {
                      day: "2-digit",
                      month: "2-digit",
                    })}
                  </span>
                </div>
              </>
            ) : (
              <div className={styles.insightEmpty}>
                <strong>Nessun peso registrato</strong>
                <p>
                  Aggiungi il primo peso dal tuo profilo.
                </p>
              </div>
            )}
          </section>

          <section
            {...dashboardWidgetProps("goal")}
            className={`${styles.insightWidget} ${styles.goalWidget} ${styles.dashboardWidget}`}
          >
            {dashboardWidgetControls(
              "goal",
              "Obiettivo calorico",
            )}

            <div className={styles.insightWidgetHeader}>
              <div>
                <p className={styles.kicker}>
                  Obiettivo
                </p>
                <h2>Obiettivo calorico</h2>
              </div>

              <span
                className={styles.goalIcon}
                aria-hidden="true"
              >
                ◎
              </span>
            </div>

            <div className={styles.goalValue}>
              <span>Deficit giornaliero</span>
              <strong>
                {budget
                  ? roundNumber(
                      budget.goal_adjustment_kcal,
                    )
                  : "—"}{" "}
                kcal
              </strong>
            </div>

            <p className={styles.goalDescription}>
              Il target viene calcolato dal tuo
              mantenimento e dal piano scelto.
            </p>

            <a
              href="/profile"
              className={styles.goalEditLink}
            >
              Modifica nel profilo →
            </a>
          </section>

          <div
            {...dashboardWidgetProps("summary")}
            className={`${styles.summaryWidget} ${styles.dashboardWidget}`}
          >
            {dashboardWidgetControls(
              "summary",
              "Resoconto della giornata",
            )}

            <RegisteredToday
              meals={actualMeals}
              activities={actualActivities}
              accessToken={accessToken}
              onChanged={refreshHome}
            />
          </div>

          </div>

        </>
      ) : null}
      </main>
    </>
  );
}
