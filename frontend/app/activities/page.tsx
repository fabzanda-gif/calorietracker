"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { ActivityLogger } from "@/components/activity/ActivityLogger";
import { ActivityMap } from "@/components/activity/ActivityMap";
import { RunningPlanBuilder } from "@/components/activity/RunningPlanBuilder";
import { StrengthPlanPanel } from "@/components/activity/StrengthPlanPanel";
import { useAuth } from "@/components/auth/AuthProvider";
import {
  useExperienceMode,
} from "@/components/experience/ExperienceModeProvider";
import { AppNav } from "@/components/navigation/AppNav";
import { useI18n } from "@/components/i18n/I18nProvider";
import {
  getActivitiesForRange,
  getActivityOverview,
  getPlannedActivities,
  createPlannedActivity,
  updatePlannedActivity,
  deletePlannedActivity,
  getPlannedActivityAdaptation,
  applyPlannedActivityAdaptation,
  keepPlannedActivityAdaptation,
  getActivityComment,
  deleteActivity,
  importGpxActivity,
  previewGpxActivity,
  type Activity,
  type ActivityRoutePoint,
  type ActivitySeriesPoint,
  type GpxActivityPreview,
  type ActivityEnergyDay,
  type PlannedActivity,
  type PlannedActivityIntensity,
  type PlannedActivityAdaptationResponse,
} from "@/lib/api/activities";

import {
  getGoogleCalendarStatus,
  syncGoogleCalendar,
} from "@/lib/api/google-calendar";

import styles from "./ActivitiesPage.module.css";
import { activitiesCopy, activityLocale } from "./activitiesI18n";

const plannerCopy = {
  it: { plan: "Pianifica", planActivity: "Pianifica attività", openToAdd: "Apri per aggiungere la prossima.", activity: "Attività", example: "Es. Lungo 12 km", type: "Tipo", date: "Data", time: "Ora", expectedDuration: "Durata prevista", distance: "Distanza", noDistance: "Distanza non prevista per", intensity: "Intensità", easy: "Facile", moderate: "Moderata", hard: "Intensa", race: "Gara / test", unknown: "Da definire", notes: "Note", optional: "Opzionale", planning: "Pianifico…", add: "Aggiungi al piano", edit: "Modifica", closeEdit: "Chiudi modifica", completed: "Completata", skipped: "Saltata", remove: "Elimina", noMore: "Nessun'altra attività programmata.", firstSix: "Mostra i primi 6", all: "Mostra tutti", uploadGpx: "Carica GPX", saveChanges: "Salva modifiche" },
  en: { plan: "Plan", planActivity: "Plan activity", openToAdd: "Open to add the next one.", activity: "Activity", example: "E.g. Long run 12 km", type: "Type", date: "Date", time: "Time", expectedDuration: "Expected duration", distance: "Distance", noDistance: "Distance not available for", intensity: "Intensity", easy: "Easy", moderate: "Moderate", hard: "Hard", race: "Race / test", unknown: "To be decided", notes: "Notes", optional: "Optional", planning: "Planning…", add: "Add to plan", edit: "Edit", closeEdit: "Close editor", completed: "Completed", skipped: "Skipped", remove: "Delete", noMore: "No other activities planned.", firstSix: "Show first 6", all: "Show all", uploadGpx: "Upload GPX", saveChanges: "Save changes" },
  nl: { plan: "Plannen", planActivity: "Activiteit plannen", openToAdd: "Open om de volgende toe te voegen.", activity: "Activiteit", example: "Bijv. lange duurloop 12 km", type: "Type", date: "Datum", time: "Tijd", expectedDuration: "Verwachte duur", distance: "Afstand", noDistance: "Afstand niet van toepassing op", intensity: "Intensiteit", easy: "Rustig", moderate: "Gemiddeld", hard: "Intensief", race: "Wedstrijd / test", unknown: "Nog te bepalen", notes: "Notities", optional: "Optioneel", planning: "Plannen…", add: "Aan plan toevoegen", edit: "Bewerken", closeEdit: "Bewerking sluiten", completed: "Voltooid", skipped: "Overgeslagen", remove: "Verwijderen", noMore: "Geen andere activiteiten gepland.", firstSix: "Eerste 6 tonen", all: "Alles tonen", uploadGpx: "GPX uploaden", saveChanges: "Wijzigingen opslaan" },
  fr: { plan: "Planifier", planActivity: "Planifier une activité", openToAdd: "Ouvrez pour ajouter la prochaine.", activity: "Activité", example: "Ex. Sortie longue 12 km", type: "Type", date: "Date", time: "Heure", expectedDuration: "Durée prévue", distance: "Distance", noDistance: "Distance non prévue pour", intensity: "Intensité", easy: "Facile", moderate: "Modérée", hard: "Intense", race: "Course / test", unknown: "À définir", notes: "Notes", optional: "Facultatif", planning: "Planification…", add: "Ajouter au programme", edit: "Modifier", closeEdit: "Fermer la modification", completed: "Terminée", skipped: "Ignorée", remove: "Supprimer", noMore: "Aucune autre activité planifiée.", firstSix: "Afficher les 6 premières", all: "Tout afficher", uploadGpx: "Importer un GPX", saveChanges: "Enregistrer les modifications" },
} as const;

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

function monthBounds(month: Date) {
  const start = new Date(
    month.getFullYear(),
    month.getMonth(),
    1,
  );
  const end = new Date(
    month.getFullYear(),
    month.getMonth() + 1,
    0,
  );

  return {
    start: isoDate(start),
    end: isoDate(end),
  };
}

function calendarDays(month: Date): Array<Date | null> {
  const first = new Date(
    month.getFullYear(),
    month.getMonth(),
    1,
  );
  const last = new Date(
    month.getFullYear(),
    month.getMonth() + 1,
    0,
  );
  const mondayOffset = (first.getDay() + 6) % 7;
  const result: Array<Date | null> = Array(
    mondayOffset,
  ).fill(null);

  for (let day = 1; day <= last.getDate(); day += 1) {
    result.push(
      new Date(
        month.getFullYear(),
        month.getMonth(),
        day,
      ),
    );
  }

  while (result.length % 7 !== 0) {
    result.push(null);
  }

  return result;
}

function weekDays(anchor: Date): Date[] {
  const monday = new Date(anchor);
  const offset = (monday.getDay() + 6) % 7;
  monday.setDate(monday.getDate() - offset);

  return Array.from({ length: 7 }, (_, index) => {
    const day = new Date(monday);
    day.setDate(monday.getDate() + index);
    return day;
  });
}

function weekBounds(anchor: Date) {
  const days = weekDays(anchor);
  return {
    start: isoDate(days[0]),
    end: isoDate(days[6]),
  };
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = () => {
      const value = String(reader.result ?? "");
      const comma = value.indexOf(",");

      resolve(
        comma >= 0
          ? value.slice(comma + 1)
          : value,
      );
    };

    reader.onerror = () => {
      reject(
        new Error("Non riesco a leggere il file GPX."),
      );
    };

    reader.readAsDataURL(file);
  });
}

function normalizedActivityLabel(
  activity: Activity,
): string {
  return [
    activity.activity_name,
    activity.activity_type ?? "",
  ]
    .join(" ")
    .trim()
    .toLocaleLowerCase("it-IT");
}

function isDailyMovement(
  activity: Activity,
): boolean {
  if (activity.source === "gpx") {
    return false;
  }

  const name = activity.activity_name
    .trim()
    .toLocaleLowerCase("it-IT");

  return [
    "passi",
    "steps",
  ].some(
    (prefix) =>
      name === prefix ||
      name.startsWith(`${prefix} `) ||
      name.startsWith(`${prefix} (`),
  );
}

function activityIcon(
  activity: Activity,
): string {
  const label = normalizedActivityLabel(activity);

  if (
    label.includes("padel") ||
    label.includes("tennis")
  ) {
    return "🎾";
  }

  if (
    label.includes("corsa") ||
    label.includes("running") ||
    label.includes("jogging")
  ) {
    return "🏃";
  }

  if (
    label.includes("palestra") ||
    label.includes("pesi") ||
    label.includes("strength")
  ) {
    return "🏋️";
  }

  if (
    label.includes("calcio") ||
    label.includes("football")
  ) {
    return "⚽";
  }

  if (
    label.includes("nuoto") ||
    label.includes("swim")
  ) {
    return "🏊";
  }

  if (
    label.includes("escursion") ||
    label.includes("hiking") ||
    label.includes("trekking")
  ) {
    return "🥾";
  }

  if (
    (
      label.includes("bici") ||
      label.includes("bicicletta") ||
      label.includes("cycling") ||
      label.includes("ciclismo")
    )
  ) {
    return "🚴";
  }

  return "🔥";
}


function formatDistance(value?: number | null): string {
  if (value == null) {
    return "—";
  }

  if (value >= 1000) {
    return `${(value / 1000).toLocaleString("it-IT", {
      maximumFractionDigits: 2,
    })} km`;
  }

  return `${Math.round(value)} m`;
}

function formatDuration(value?: number | null): string {
  if (value == null) {
    return "—";
  }

  const hours = Math.floor(value / 3600);
  const minutes = Math.floor(
    (value % 3600) / 60,
  );
  const seconds = value % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }

  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }

  return `${seconds}s`;
}

function plannedActivitySupportsDistance(
  activityType: string,
): boolean {
  return [
    "corsa",
    "bici",
    "nuoto",
    "camminata",
  ].includes(
    activityType
      .trim()
      .toLocaleLowerCase("it-IT"),
  );
}

const PLANNED_INTENSITY_LABELS: Record<
  PlannedActivityIntensity,
  string
> = {
  low: "Facile",
  moderate: "Moderata",
  hard: "Intensa",
  race: "Gara / test",
  unknown: "Da definire",
};

const RUNNING_SESSION_LABELS: Record<
  string,
  string
> = {
  easy: "Facile",
  recovery: "Recupero",
  tempo: "Tempo",
  interval: "Intervalli",
  long: "Lungo",
  race: "Gara",
};

function runningSessionLabel(
  value?: string | null,
): string | null {
  if (!value) {
    return null;
  }

  return (
    RUNNING_SESSION_LABELS[value] ??
    value
  );
}

// STEP A: planned activity editor
type PlannedActivityEditDraft = {
  scheduledDate: string;
  scheduledTime: string;
  title: string;
  durationMinutes: string;
  distanceKm: string;
  notes: string;
};

function plannedDateLabel(
  value: string,
  locale: string,
  todayLabel: string,
  tomorrowLabel: string,
): string {
  const target = new Date(
    `${value}T00:00:00`,
  );

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const tomorrow = new Date(today);
  tomorrow.setDate(
    tomorrow.getDate() + 1,
  );

  if (
    target.getTime() ===
    today.getTime()
  ) {
    return todayLabel;
  }

  if (
    target.getTime() ===
    tomorrow.getTime()
  ) {
    return tomorrowLabel;
  }

  return target.toLocaleDateString(
    locale,
    {
      weekday: "short",
      day: "numeric",
      month: "short",
    },
  );
}


function formatActivityDate(value: string, locale: string): string {
  return new Date(`${value}T00:00:00`).toLocaleDateString(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function normalizedArray<T>(value: T[] | string | null | undefined): T[] {
  if (Array.isArray(value)) return value;
  if (typeof value !== "string") return [];
  try {
    const parsed: unknown = JSON.parse(value);
    return Array.isArray(parsed) ? (parsed as T[]) : [];
  } catch {
    return [];
  }
}

function activityTimestamp(activity: Activity): number {
  return new Date(activity.started_at ?? `${activity.date}T00:00:00`).getTime();
}

function MetricChart({
  points,
  metric,
  title,
  unit,
  copy,
}: {
  points: ActivitySeriesPoint[];
  metric: "cadence" | "heart_rate";
  title: string;
  unit: string;
  copy: typeof activitiesCopy.it | typeof activitiesCopy.en | typeof activitiesCopy.nl | typeof activitiesCopy.fr;
}) {
  const values = points
    .map((point, index) => ({
      index,
      value: point[metric],
    }))
    .filter(
      (
        point,
      ): point is {
        index: number;
        value: number;
      } => typeof point.value === "number",
    );

  if (!values.length) {
    return (
      <section className={styles.chartCard}>
        <h3>{title}</h3>
        <div className={styles.emptyChart}>
          <strong>{copy.dataUnavailable}</strong>
          <span>
            GPX: {copy.unavailable.toLowerCase()} ({title.toLowerCase()}).
          </span>
        </div>
      </section>
    );
  }

  const width = 600;
  const height = 230;
  const paddingX = 36;
  const paddingY = 28;
  let minimum = Math.min(
    ...values.map((item) => item.value),
  );
  let maximum = Math.max(
    ...values.map((item) => item.value),
  );

  if (minimum === maximum) {
    minimum -= 1;
    maximum += 1;
  }

  const coordinates = values.map((item, position) => {
    const x =
      paddingX +
      (position / Math.max(1, values.length - 1)) *
        (width - paddingX * 2);
    const y =
      height -
      paddingY -
      ((item.value - minimum) /
        (maximum - minimum)) *
        (height - paddingY * 2);

    return { x, y, value: item.value };
  });

  const path = coordinates
    .map(
      (point, index) =>
        `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`,
    )
    .join(" ");

  const average =
    values.reduce(
      (sum, item) => sum + item.value,
      0,
    ) / values.length;

  return (
    <section className={styles.chartCard}>
      <div className={styles.chartHeading}>
        <h3>{title}</h3>
        <strong>
          {Math.round(average)} {unit}
        </strong>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${copy.chart}: ${title}`}
      >
        {[0, 1, 2, 3].map((line) => {
          const y =
            paddingY +
            (line / 3) *
              (height - paddingY * 2);

          return (
            <line
              key={line}
              x1={paddingX}
              x2={width - paddingX}
              y1={y}
              y2={y}
              className={styles.chartGrid}
            />
          );
        })}

        <path
          d={path}
          className={styles.chartLine}
        />

        {coordinates.map((point, index) => (
          <circle
            key={index}
            cx={point.x}
            cy={point.y}
            r="4"
            className={styles.chartPoint}
          />
        ))}
      </svg>

      <div className={styles.chartRange}>
        <span>
          {copy.min} {Math.round(minimum)} {unit}
        </span>
        <span>
          {copy.max} {Math.round(maximum)} {unit}
        </span>
      </div>
    </section>
  );
}

export default function ActivitiesPage() {
  const { locale } = useI18n();
  const copy = activitiesCopy[locale];
  const planText = plannerCopy[locale];
  const displayLocale = activityLocale[locale];
  const { accessToken } = useAuth();
  const {
    experienceMode,
    setExperienceMode,
  } = useExperienceMode();
  const [month, setMonth] = useState(
    () => new Date(),
  );
  const [calendarView, setCalendarView] =
    useState<"weekly" | "monthly">("weekly");
  const [calendarExpanded, setCalendarExpanded] =
    useState(true);
  const [activities, setActivities] = useState<
    Activity[]
  >([]);
  const [recentActivities, setRecentActivities] = useState<Activity[]>([]);
  const [energyDays, setEnergyDays] = useState<ActivityEnergyDay[]>([]);
  const [selectedActivity, setSelectedActivity] =
    useState<Activity | null>(null);
  const [selectedDate, setSelectedDate] =
    useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] =
    useState<string | null>(null);

  const [calendarSyncing, setCalendarSyncing] =
    useState(false);
  const [calendarSyncMessage, setCalendarSyncMessage] =
    useState<string | null>(null);

  const [gpxFile, setGpxFile] =
    useState<File | null>(null);
  const plannedGpxInputRef =
    useRef<HTMLInputElement | null>(null);
  const plannedGpxTargetRef =
    useRef<PlannedActivity | null>(null);

  const [
    plannedGpxActivity,
    setPlannedGpxActivity,
  ] = useState<PlannedActivity | null>(null);
  const [gpxBase64, setGpxBase64] = useState("");
  const [gpxPreview, setGpxPreview] =
    useState<GpxActivityPreview | null>(null);
  const [gpxName, setGpxName] = useState("");
  const [gpxType, setGpxType] = useState("Altro");
  const [gpxCalories, setGpxCalories] =
    useState("0");
  const [previewing, setPreviewing] =
    useState(false);
  const [importing, setImporting] =
    useState(false);
  const [deletingId, setDeletingId] = useState<string | number | null>(null);
  const [importMessage, setImportMessage] =
    useState<string | null>(null);

  const [
    activityComments,
    setActivityComments,
  ] = useState<Record<string, string>>({});

  const [
    activityCommentLoading,
    setActivityCommentLoading,
  ] = useState(false);

  const [
    plannedActivities,
    setPlannedActivities,
  ] = useState<PlannedActivity[]>([]);

  const [
    trainingPlanActivities,
    setTrainingPlanActivities,
  ] = useState<PlannedActivity[]>([]);

  const [
    showAllPlannedActivities,
    setShowAllPlannedActivities,
  ] = useState(false);

  const [planTitle, setPlanTitle] =
    useState("");
  const [planType, setPlanType] =
    useState("Corsa");

  const [planDate, setPlanDate] =
    useState(() => {
      const tomorrow = new Date();
      tomorrow.setDate(
        tomorrow.getDate() + 1,
      );
      return isoDate(tomorrow);
    });

  const [planTime, setPlanTime] =
    useState("");
  const [planDuration, setPlanDuration] =
    useState("");
  const [planDistanceKm, setPlanDistanceKm] =
    useState("");

  const [
    planIntensity,
    setPlanIntensity,
  ] = useState<PlannedActivityIntensity>(
    "moderate",
  );

  const [planNotes, setPlanNotes] =
    useState("");
  const [savingPlan, setSavingPlan] =
    useState(false);
  const [busyPlanId, setBusyPlanId] =
    useState<string | null>(null);

  const [
    editingPlan,
    setEditingPlan,
  ] = useState<PlannedActivity | null>(
    null,
  );

  const [
    editPlan,
    setEditPlan,
  ] = useState<PlannedActivityEditDraft | null>(
    null,
  );

  const [
    savingPlanEdit,
    setSavingPlanEdit,
  ] = useState(false);

  const [
    planAdaptations,
    setPlanAdaptations,
  ] = useState<
    Record<
      string,
      PlannedActivityAdaptationResponse | null
    >
  >({});

  const [
    adaptationLoadingIds,
    setAdaptationLoadingIds,
  ] = useState<Record<string, boolean>>({});

  const [
    adaptationApplyingId,
    setAdaptationApplyingId,
  ] = useState<string | null>(null);

  const [
    dismissedAdaptations,
    setDismissedAdaptations,
  ] = useState<Record<string, boolean>>({});

  const [
    adaptationFeedback,
    setAdaptationFeedback,
  ] = useState<Record<string, string>>({});

  const loadMonth = useCallback(async () => {
    if (!accessToken) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const bounds = calendarView === "weekly"
        ? weekBounds(month)
        : monthBounds(month);
      const today = new Date();
      const rollingStart = new Date(today);
      rollingStart.setDate(today.getDate() - 29);

      const plannedStart = bounds.start;
      const plannedEnd = bounds.end;

      const loadStartedAt = performance.now();

      const overviewPromise = getActivityOverview(
        bounds.start,
        bounds.end,
        accessToken,
      ).then((response) => {
        const sortedItems = [...response.items].sort(
          (left, right) =>
            activityTimestamp(right) -
            activityTimestamp(left),
        );

        setActivities(sortedItems);
        setEnergyDays(response.energy_days);

        setSelectedActivity((current) => {
          const visibleItems = sortedItems.filter(
            (item) => !isDailyMovement(item),
          );

          if (
            current &&
            visibleItems.some(
              (item) => item.id === current.id,
            )
          ) {
            return current;
          }

          return visibleItems[0] ?? null;
        });

        console.info(
          `[Activities perf] overview ready: ${Math.round(
            performance.now() - loadStartedAt,
          )} ms`,
        );
      });

      const recentPromise = getActivitiesForRange(
        isoDate(rollingStart),
        isoDate(today),
        accessToken,
      ).then((recentResponse) => {
        setRecentActivities(
          [...recentResponse.items].sort(
            (left, right) =>
              activityTimestamp(right) -
              activityTimestamp(left),
          ),
        );

        console.info(
          `[Activities perf] recent ready: ${Math.round(
            performance.now() - loadStartedAt,
          )} ms`,
        );
      });

      const plannedPromise = getPlannedActivities(
        plannedStart,
        plannedEnd,
        accessToken,
      ).then((plannedResponse) => {
        setPlannedActivities(
          plannedResponse.items,
        );

        console.info(
          `[Activities perf] planned ready: ${Math.round(
            performance.now() - loadStartedAt,
          )} ms`,
        );
      });

      const results = await Promise.allSettled([
        overviewPromise,
        recentPromise,
        plannedPromise,
      ]);

      const failed = results.find(
        (result) => result.status === "rejected",
      );

      if (failed?.status === "rejected") {
        throw failed.reason;
      }

      console.info(
        `[Activities perf] ALL READY: ${Math.round(
          performance.now() - loadStartedAt,
        )} ms`,
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a caricare le attività.",
      );
    } finally {
      setLoading(false);
    }
  }, [accessToken, calendarView, month]);

  const loadTrainingPlanActivities = useCallback(async () => {
    if (!accessToken) {
      setTrainingPlanActivities([]);
      return;
    }

    try {
      const today = new Date();
      const planningEnd = new Date(today);

      planningEnd.setDate(
        planningEnd.getDate() + 366,
      );

      const response =
        await getPlannedActivities(
          isoDate(today),
          isoDate(planningEnd),
          accessToken,
        );

      setTrainingPlanActivities(
        response.items.filter(
          (item) =>
            item.status === "planned" &&
            item.scheduled_date >= isoDate(today),
        ),
      );
    } catch (error) {
      console.error(
        "Unable to load upcoming activities",
        error,
      );

      setTrainingPlanActivities([]);
    }
  }, [accessToken]);

  useEffect(() => {
    void loadMonth();
  }, [loadMonth]);

  useEffect(() => {
    void loadTrainingPlanActivities();
  }, [loadTrainingPlanActivities]);

  const days = useMemo(
    () => calendarView === "weekly"
      ? weekDays(month)
      : calendarDays(month),
    [calendarView, month],
  );

  const periodLabel = useMemo(() => {
    if (calendarView === "monthly") {
      return month.toLocaleDateString(displayLocale, {
        month: "long",
        year: "numeric",
      });
    }

    const range = weekDays(month);
    const start = range[0];
    const end = range[6];
    const sameMonth =
      start.getMonth() === end.getMonth();

    return sameMonth
      ? `${start.getDate()}–${end.getDate()} ${end.toLocaleDateString(displayLocale, { month: "long", year: "numeric" })}`
      : `${start.toLocaleDateString(displayLocale, { day: "numeric", month: "short" })} – ${end.toLocaleDateString(displayLocale, { day: "numeric", month: "short", year: "numeric" })}`;
  }, [calendarView, displayLocale, month]);

  const navigatePeriod = useCallback((direction: -1 | 1) => {
    setMonth((current) => {
      const next = new Date(current);
      if (calendarView === "weekly") {
        next.setDate(next.getDate() + direction * 7);
      } else {
        next.setMonth(next.getMonth() + direction, 1);
      }
      return next;
    });
  }, [calendarView]);

  const trainingActivities = useMemo(
    () =>
      activities.filter(
        (activity) => !isDailyMovement(activity),
      ),
    [activities],
  );

  const rollingTrainingActivities = useMemo(
    () => recentActivities.filter((activity) => !isDailyMovement(activity)),
    [recentActivities],
  );

  const rollingSummary = useMemo(
    () => ({
      workouts: rollingTrainingActivities.length,
      duration: rollingTrainingActivities.reduce((sum, item) => sum + Number(item.duration_seconds ?? 0), 0),
      distance: rollingTrainingActivities.reduce((sum, item) => sum + Number(item.distance_meters ?? 0), 0),
      calories: rollingTrainingActivities.reduce((sum, item) => sum + Number(item.burned_calories ?? 0), 0),
    }),
    [rollingTrainingActivities],
  );

  const energyByDate = useMemo(
    () => new Map(energyDays.map((item) => [item.date, item])),
    [energyDays],
  );

  const plannerActivities = useMemo(() => {
    const byId =
      new Map<string, PlannedActivity>();

    for (const item of [
      ...trainingPlanActivities,
      ...plannedActivities,
    ]) {
      byId.set(item.id, item);
    }

    return [...byId.values()];
  }, [
    plannedActivities,
    trainingPlanActivities,
  ]);

  const sortedPlannedActivities =
    useMemo(
      () =>
        [...plannerActivities].sort(
          (left, right) => {
            const leftTime =
              `${left.scheduled_date}T${
                left.scheduled_time ??
                "23:59:59"
              }`;

            const rightTime =
              `${right.scheduled_date}T${
                right.scheduled_time ??
                "23:59:59"
              }`;

            return (
              new Date(
                leftTime,
              ).getTime() -
              new Date(
                rightTime,
              ).getTime()
            );
          },
        ),
      [plannerActivities],
    );

  const nextPlannedActivity =
    sortedPlannedActivities.find(
      (item) =>
        item.status === "planned" &&
        item.scheduled_date >= isoDate(new Date()),
    ) ?? null;

  const nextPlannedActivityId =
    nextPlannedActivity?.id ?? null;

  const remainingPlannedActivities =
    useMemo(
      () =>
        sortedPlannedActivities.filter(
          (item) =>
            item.id !== nextPlannedActivityId &&
            item.status === "planned" &&
            item.scheduled_date >=
              isoDate(new Date()),
        ),
      [
        sortedPlannedActivities,
        nextPlannedActivityId,
      ],
    );

  const visiblePlannedActivities =
    useMemo(
      () =>
        showAllPlannedActivities
          ? remainingPlannedActivities
          : remainingPlannedActivities.slice(0, 6),
      [
        remainingPlannedActivities,
        showAllPlannedActivities,
      ],
    );

  const activitiesByDate = useMemo(() => {
    const grouped = new Map<string, Activity[]>();

    for (const activity of trainingActivities) {
      const current =
        grouped.get(activity.date) ?? [];

      current.push(activity);
      grouped.set(activity.date, current);
    }

    return grouped;
  }, [trainingActivities]);

  const linkedPlannedActivityIds = useMemo(
    () =>
      new Set(
        trainingActivities
          .map(
            (activity) =>
              activity.planned_activity_id,
          )
          .filter(
            (id): id is string =>
              Boolean(id),
          ),
      ),
    [trainingActivities],
  );

  const plannedActivitiesByDate = useMemo(() => {
    const grouped =
      new Map<string, PlannedActivity[]>();

    for (const item of plannedActivities) {
      if (
        linkedPlannedActivityIds.has(item.id)
      ) {
        continue;
      }

      const current =
        grouped.get(item.scheduled_date) ?? [];

      current.push(item);
      grouped.set(
        item.scheduled_date,
        current,
      );
    }

    return grouped;
  }, [
    plannedActivities,
    linkedPlannedActivityIds,
  ]);

  async function syncActivitiesToGoogleCalendar() {
    if (!accessToken || calendarSyncing) {
      return;
    }

    setCalendarSyncing(true);
    setCalendarSyncMessage(null);
    setError(null);

    try {
      const status = await getGoogleCalendarStatus(
        accessToken,
      );

      if (!status.connected) {
        window.location.assign("/profile");
        return;
      }

      const today = new Date();

      const start = new Date(today);
      start.setDate(start.getDate() - 30);

      const end = new Date(today);
      end.setDate(end.getDate() + 335);

      const result = await syncGoogleCalendar(
        accessToken,
        isoDate(start),
        isoDate(end),
      );

      const changes =
        result.created +
        result.updated +
        result.deleted;

      setCalendarSyncMessage(
        changes > 0
          ? `Google Calendar aggiornato: ${result.created} creati, ${result.updated} aggiornati, ${result.deleted} rimossi.`
          : "Google Calendar è già aggiornato.",
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a sincronizzare Google Calendar.",
      );
    } finally {
      setCalendarSyncing(false);
    }
  }

  async function savePlannedActivity() {
    if (
      !accessToken ||
      !planTitle.trim() ||
      !planDate
    ) {
      return;
    }

    setSavingPlan(true);
    setError(null);

    try {
      await createPlannedActivity(
        {
          scheduled_date: planDate,
          scheduled_time:
            planTime || null,
          title: planTitle.trim(),
          activity_type:
            planType.trim() || "Attività",
          duration_minutes:
            planDuration
              ? Number(planDuration)
              : null,
          distance_meters:
            plannedActivitySupportsDistance(
              planType,
            ) &&
            planDistanceKm
              ? Number(planDistanceKm) *
                1000
              : null,
          intensity: planIntensity,
          notes:
            planNotes.trim() || null,
        },
        accessToken,
      );

      setPlanTitle("");
      setPlanTime("");
      setPlanDuration("");
      setPlanDistanceKm("");
      setPlanNotes("");
      setPlanIntensity("moderate");

      await loadMonth();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a pianificare l’attività.",
      );
    } finally {
      setSavingPlan(false);
    }
  }

  function startPlannedActivityEdit(
    item: PlannedActivity,
  ) {
    if (item.status !== "planned") {
      return;
    }

    setEditingPlan(item);

    setEditPlan({
      scheduledDate: item.scheduled_date,
      scheduledTime:
        item.scheduled_time?.slice(0, 5) ??
        "",
      title: item.title,
      durationMinutes:
        item.duration_minutes != null
          ? String(item.duration_minutes)
          : "",
      distanceKm:
        item.distance_meters != null
          ? String(
              item.distance_meters / 1000,
            )
          : "",
      notes: item.notes ?? "",
    });

    setError(null);
  }

  function cancelPlannedActivityEdit() {
    if (savingPlanEdit) {
      return;
    }

    setEditingPlan(null);
    setEditPlan(null);
  }

  async function savePlannedActivityEdit() {
    if (
      !accessToken ||
      !editingPlan ||
      !editPlan
    ) {
      return;
    }

    const title = editPlan.title.trim();

    if (!title) {
      setError(
        "Inserisci un titolo per l’attività.",
      );
      return;
    }

    const runningRace = Boolean(
      editingPlan.training_plan_id &&
        editingPlan.session_kind === "race",
    );

    if (
      !runningRace &&
      !editPlan.scheduledDate
    ) {
      setError(
        "Inserisci una data per l’attività.",
      );
      return;
    }

    const durationText =
      editPlan.durationMinutes.trim();

    const durationMinutes =
      durationText.length > 0
        ? Number(durationText)
        : null;

    if (
      durationMinutes !== null &&
      (
        !Number.isFinite(durationMinutes) ||
        durationMinutes <= 0
      )
    ) {
      setError(
        "La durata deve essere maggiore di zero.",
      );
      return;
    }

    const supportsDistance =
      plannedActivitySupportsDistance(
        editingPlan.activity_type,
      );

    let distanceMeters: number | null =
      null;

    if (
      supportsDistance &&
      editPlan.distanceKm.trim()
    ) {
      const distanceKm = Number(
        editPlan.distanceKm,
      );

      if (
        !Number.isFinite(distanceKm) ||
        distanceKm < 0
      ) {
        setError(
          "La distanza non può essere negativa.",
        );
        return;
      }

      distanceMeters =
        distanceKm * 1000;
    }

    const input: Parameters<
      typeof updatePlannedActivity
    >[1] = {
      scheduled_time:
        editPlan.scheduledTime || null,
      title,
      duration_minutes:
        durationMinutes,
      notes:
        editPlan.notes.trim() || null,
    };

    // Race date/distance are intentionally
    // kept under control of the Running plan.
    if (!runningRace) {
      input.scheduled_date =
        editPlan.scheduledDate;

      if (supportsDistance) {
        input.distance_meters =
          distanceMeters;
      }
    }

    setSavingPlanEdit(true);
    setError(null);

    try {
      const response =
        await updatePlannedActivity(
          editingPlan.id,
          input,
          accessToken,
        );

      setPlannedActivities(
        (current) =>
          current.map((item) =>
            item.id ===
            response.item.id
              ? response.item
              : item,
          ),
      );

      setEditingPlan(null);
      setEditPlan(null);

      await loadMonth();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a modificare l’attività pianificata.",
      );
    } finally {
      setSavingPlanEdit(false);
    }
  }

  async function loadPlanAdaptation(
    item: PlannedActivity,
  ) {
    if (
      !accessToken ||
      !item.training_plan_id ||
      !["completed", "skipped"].includes(
        item.status,
      ) ||
      dismissedAdaptations[item.id]
    ) {
      return;
    }

    setAdaptationLoadingIds(
      (current) => ({
        ...current,
        [item.id]: true,
      }),
    );

    try {
      const response =
        await getPlannedActivityAdaptation(
          item.id,
          accessToken,
        );

      setPlanAdaptations(
        (current) => ({
          ...current,
          [item.id]: response,
        }),
      );
    } catch {
      // Adaptation is an enhancement.
      // The planner must remain usable if it fails.
    } finally {
      setAdaptationLoadingIds(
        (current) => ({
          ...current,
          [item.id]: false,
        }),
      );
    }
  }

  async function setPlannedStatus(
    item: PlannedActivity,
    status:
      | "completed"
      | "skipped",
  ) {
    if (!accessToken) return;

    setBusyPlanId(item.id);
    setError(null);

    try {
      await updatePlannedActivity(
        item.id,
        { status },
        accessToken,
      );

      const updatedItem: PlannedActivity = {
        ...item,
        status,
      };

      if (item.training_plan_id) {
        await loadPlanAdaptation(
          updatedItem,
        );
      }

      await loadMonth();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco ad aggiornare il piano.",
      );
    } finally {
      setBusyPlanId(null);
    }
  }

  async function removePlannedActivity(
    item: PlannedActivity,
  ) {
    if (
      !accessToken ||
      !window.confirm(
        `Eliminare “${item.title}” dal piano?`,
      )
    ) {
      return;
    }

    setBusyPlanId(item.id);
    setError(null);

    try {
      await deletePlannedActivity(
        item.id,
        accessToken,
      );
      await loadMonth();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a eliminare l’attività pianificata.",
      );
    } finally {
      setBusyPlanId(null);
    }
  }

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    for (const item of plannedActivities) {
      if (
        !item.training_plan_id ||
        !["completed", "skipped"].includes(
          item.status,
        ) ||
        dismissedAdaptations[item.id] ||
        planAdaptations[item.id] !== undefined ||
        adaptationLoadingIds[item.id]
      ) {
        continue;
      }

      void loadPlanAdaptation(item);
    }
  }, [
    accessToken,
    plannedActivities,
    dismissedAdaptations,
    planAdaptations,
    adaptationLoadingIds,
  ]);

  async function applyAdaptation(
    source: PlannedActivity,
  ) {
    if (!accessToken) {
      return;
    }

    const response =
      planAdaptations[source.id];

    const targetId =
      response?.proposal.target?.id;

    if (
      !response?.proposal.adaptation_required ||
      !targetId
    ) {
      return;
    }

    setAdaptationApplyingId(
      source.id,
    );
    setError(null);

    try {
      await applyPlannedActivityAdaptation(
        source.id,
        targetId,
        accessToken,
      );

      setDismissedAdaptations(
        (current) => ({
          ...current,
          [source.id]: true,
        }),
      );

      setAdaptationFeedback(
        (current) => ({
          ...current,
          [source.id]:
            "Adattamento applicato al piano.",
        }),
      );

      setPlanAdaptations(
        (current) => ({
          ...current,
          [source.id]: null,
        }),
      );

      await loadMonth();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco ad applicare l’adattamento.",
      );
    } finally {
      setAdaptationApplyingId(null);
    }
  }

  async function keepCurrentPlan(
    source: PlannedActivity,
  ) {
    if (!accessToken) {
      return;
    }

    setAdaptationApplyingId(
      source.id,
    );
    setError(null);

    try {
      await keepPlannedActivityAdaptation(
        source.id,
        accessToken,
      );

      setDismissedAdaptations(
        (current) => ({
          ...current,
          [source.id]: true,
        }),
      );

      setAdaptationFeedback(
        (current) => ({
          ...current,
          [source.id]:
            "Piano mantenuto senza modifiche.",
        }),
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a salvare la decisione.",
      );
    } finally {
      setAdaptationApplyingId(null);
    }
  }

  async function chooseGpx(
    file: File | null,
    plannedActivity?: PlannedActivity | null,
  ) {
    setGpxFile(file);

    if (plannedActivity) {
      setPlannedGpxActivity(plannedActivity);
      setGpxType(plannedActivity.activity_type);
      setGpxName(plannedActivity.title);
      setSelectedDate(
        plannedActivity.scheduled_date,
      );
    } else {
      setPlannedGpxActivity(null);
    }
    setGpxPreview(null);
    setImportMessage(null);
    setError(null);

    if (!file) {
      setGpxBase64("");
      return;
    }

    const extension =
      file.name.toLowerCase().split(".").pop();

    if (
      !extension ||
      !["gpx", "fit", "tcx"].includes(extension)
    ) {
      setError(
        "Formato non supportato. Usa GPX, FIT o TCX.",
      );
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setError(
        "Il file attività supera il limite di 10 MB.",
      );
      return;
    }

    if (!accessToken) {
      return;
    }

    setPreviewing(true);

    try {
      const contentBase64 = await fileToBase64(
        file,
      );
      const response = await previewGpxActivity(
        {
          file_name: file.name,
          content_base64: contentBase64,
          activity_type:
            plannedActivity?.activity_type ||
            undefined,
        },
        accessToken,
      );

      setGpxBase64(contentBase64);
      setGpxPreview(response.preview);

      setGpxType(
        plannedActivity?.activity_type ||
        response.preview.activity_type ||
        "Altro",
      );

      setGpxName(
        plannedActivity
          ? plannedActivity.title
          : response.preview.activity_name,
      );
      setGpxCalories(
        String(
          response.preview.estimated_calories ?? 0,
        ),
      );

      const previewDate =
        plannedActivity?.scheduled_date ||
        response.preview.date ||
        isoDate(new Date());

      setSelectedDate(previewDate);

      const parsedPreviewDate = new Date(
        `${previewDate}T00:00:00`,
      );

      if (
        parsedPreviewDate.getMonth() !==
          month.getMonth() ||
        parsedPreviewDate.getFullYear() !==
          month.getFullYear()
      ) {
        setMonth(
          new Date(
            parsedPreviewDate.getFullYear(),
            parsedPreviewDate.getMonth(),
            1,
          ),
        );
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco ad analizzare il file attività.",
      );
    } finally {
      setPreviewing(false);
    }
  }

  function openPlannedGpxPicker(
    activity: PlannedActivity,
  ) {
    plannedGpxTargetRef.current = activity;
    plannedGpxInputRef.current?.click();
  }

  async function removeActivity(activity: Activity) {
    if (!accessToken || activity.id == null) return;
    if (!window.confirm(`Eliminare “${activity.activity_name}”?`)) return;

    setDeletingId(activity.id);
    setError(null);
    try {
      await deleteActivity(activity.id, accessToken);
      setSelectedActivity(null);
      await loadMonth();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Non riesco a eliminare l’attività.");
    } finally {
      setDeletingId(null);
    }
  }

  async function saveGpx() {
    if (
      !accessToken ||
      !gpxFile ||
      !gpxBase64 ||
      !gpxPreview
    ) {
      return;
    }

    setImporting(true);
    setError(null);
    setImportMessage(null);

    try {
      const response = await importGpxActivity(
        {
          file_name: gpxFile.name,
          content_base64: gpxBase64,
          activity_name:
            gpxName.trim() ||
            gpxPreview.activity_name,
          activity_type: gpxType,
          activity_date: selectedDate,
          burned_calories:
            Math.max(
              0,
              Number(gpxCalories) || 0,
            ),
          planned_activity_id:
            plannedGpxActivity?.id,
        },
        accessToken,
      );

      if (plannedGpxActivity) {
        await updatePlannedActivity(
          plannedGpxActivity.id,
          { status: "completed" },
          accessToken,
        );
      }

      setImportMessage(
        plannedGpxActivity
          ? "Attività completata e file importato."
          : "Attività importata.",
      );
      setGpxFile(null);
      setGpxBase64("");
      setGpxPreview(null);
      setPlannedGpxActivity(null);
      setSelectedActivity(response.item);

      const importedDate = new Date(
        `${response.item.date}T00:00:00`,
      );

      if (
        importedDate.getMonth() !==
          month.getMonth() ||
        importedDate.getFullYear() !==
          month.getFullYear()
      ) {
        setMonth(
          new Date(
            importedDate.getFullYear(),
            importedDate.getMonth(),
            1,
          ),
        );
      } else {
        await loadMonth();
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a importare l'attività.",
      );
    } finally {
      setImporting(false);
    }
  }

  const visibleActivities = selectedDate
    ? activitiesByDate.get(selectedDate) ?? []
    : trainingActivities;

  const detail =
    selectedActivity ??
    visibleActivities[0] ??
    null;

  const zero = experienceMode === "zero";

  const detailCommentKey = detail
    ? `${String(
        detail.id ??
          `${detail.date}-${detail.activity_name}`,
      )}:${experienceMode}`
    : "";

  const activityComment =
    detailCommentKey
      ? activityComments[
          detailCommentKey
        ] ?? null
      : null;

  useEffect(() => {
    if (
      !detail ||
      !accessToken ||
      !detailCommentKey ||
      activityComments[
        detailCommentKey
      ]
    ) {
      return;
    }

    let active = true;

    async function loadActivityComment() {
      setActivityCommentLoading(true);

      try {
        const response =
          await getActivityComment(
            detail!,
            experienceMode,
            accessToken,
          );

        if (!active) {
          return;
        }

        setActivityComments(
          (current) => ({
            ...current,
            [detailCommentKey]:
              response.comment,
          }),
        );
      } catch {
        // The backend already has a deterministic
        // fallback. If the request itself fails,
        // keep the activity detail usable.
      } finally {
        if (active) {
          setActivityCommentLoading(false);
        }
      }
    }

    void loadActivityComment();

    return () => {
      active = false;
    };
  }, [
    accessToken,
    activityComments,
    detail,
    detailCommentKey,
    experienceMode,
  ]);

  return (
    <>
      <AppNav />

      <main
        className={`${styles.page} ${
          zero ? styles.pageZero : ""
        }`}
      >
        <input
          ref={plannedGpxInputRef}
          hidden
          type="file"
          accept=".gpx,.fit,.tcx,application/gpx+xml,application/xml,application/octet-stream"
          onChange={(event) => {
            const file = event.currentTarget.files?.[0] ?? null;
            const activity = plannedGpxTargetRef.current;

            if (activity) {
              void chooseGpx(file, activity);
            }

            plannedGpxTargetRef.current = null;
            event.currentTarget.value = "";
          }}
        />
        <header className={styles.header}>
          <div>
            <p className={styles.eyebrow}>
              {copy.activity}
            </p>
            <h1>
              {zero
                ? copy.zeroTitle
                : copy.activeRoutine}
            </h1>
            <p>
              {zero
                ? copy.zeroIntro
                : copy.activeIntro}
            </p>
          </div>

          <div className={styles.monthTotal}>
            <strong>{rollingTrainingActivities.length}</strong>
            <span>
              {copy.last30Activities}
            </span>
          </div>
        </header>

        <section className={styles.summarySection}>
          <div className={styles.summaryHeading}>
            <div>
              <p className={styles.eyebrow}>{copy.yourMovement}</p>
              <h2>{copy.last30Days}</h2>
            </div>
          </div>
          <div className={styles.summaryGrid}>
            <div><span>{copy.activity}</span><strong>{rollingSummary.workouts}</strong></div>
            <div><span>{copy.totalTime}</span><strong>{formatDuration(rollingSummary.duration)}</strong></div>
            <div><span>{copy.distance}</span><strong>{formatDistance(rollingSummary.distance)}</strong></div>
            <div><span>{copy.energy}</span><strong>{rollingSummary.calories.toLocaleString(displayLocale)} kcal</strong></div>
          </div>
        </section>

        <div className={styles.topGrid}>
          <section className={`${styles.card} ${styles.calendarCard}`}>
            <div className={styles.cardHeading}>
              <div>
                <p className={styles.eyebrow}>
                  {copy.consistency}
                </p>
                <h2>{copy.activityCalendar}</h2>
              </div>

              <div className={styles.calendarActions}>
                <div
                  className={styles.calendarViewToggle}
                  aria-label={copy.calendarView}
                >
                  <button
                    type="button"
                    className={calendarView === "weekly" ? styles.calendarViewActive : ""}
                    onClick={() => setCalendarView("weekly")}
                  >
                    {copy.weekly}
                  </button>
                  <button
                    type="button"
                    className={calendarView === "monthly" ? styles.calendarViewActive : ""}
                    onClick={() => setCalendarView("monthly")}
                  >
                    {copy.monthly}
                  </button>
                </div>

                <button
                  type="button"
                  className={styles.googleCalendarButton}
                  disabled={calendarSyncing}
                  onClick={() =>
                    void syncActivitiesToGoogleCalendar()
                  }
                >
                  {calendarSyncing
                    ? copy.syncing
                    : copy.syncCalendar}
                </button>

                <div className={styles.monthControls}>
                <button
                  type="button"
                  aria-label={copy.previousPeriod}
                  onClick={() => navigatePeriod(-1)}
                >
                  ←
                </button>

                <strong>
                  {periodLabel}
                </strong>

                <button
                  type="button"
                  aria-label={copy.nextPeriod}
                  onClick={() => navigatePeriod(1)}
                >
                  →
                </button>
                </div>

                <button
                  type="button"
                  className={styles.circularToggle}
                  aria-label={calendarExpanded ? copy.collapseCalendar : copy.expandCalendar}
                  aria-expanded={calendarExpanded}
                  onClick={() => setCalendarExpanded((current) => !current)}
                >
                  {calendarExpanded ? "−" : "+"}
                </button>
              </div>
            </div>

            {calendarSyncMessage && (
              <p className={styles.calendarSyncMessage}>
                {calendarSyncMessage}
              </p>
            )}

            {calendarExpanded ? (
              <div className={styles.calendarBody}>
            <div className={`${styles.calendar} ${calendarView === "weekly" ? styles.weekCalendar : ""}`}>
              {copy.weekdays.map((weekday) => (
                <span
                  key={weekday}
                  className={styles.weekday}
                >
                  {weekday}
                </span>
              ))}

              {days.map((day, index) => {
                if (!day) {
                  return (
                    <span
                      key={`empty-${index}`}
                      className={styles.emptyDay}
                    />
                  );
                }

                const date = isoDate(day);
                const dayActivities =
                  activitiesByDate.get(date) ?? [];

                const dayPlannedActivities =
                  plannedActivitiesByDate.get(
                    date,
                  ) ?? [];

                const visiblePlannedActivities =
                  dayPlannedActivities.filter(
                    (item) =>
                      item.status === "planned",
                  );

                const skippedPlannedActivities =
                  dayPlannedActivities.filter(
                    (item) =>
                      item.status === "skipped",
                  );

                const active =
                  dayActivities.length > 0;

                const hasPlanned =
                  visiblePlannedActivities.length > 0;

                const hasSkipped =
                  skippedPlannedActivities.length > 0;
                const selected =
                  selectedDate === date;
                const today =
                  date === isoDate(new Date());
                const energy = energyByDate.get(date);

                return (
                  <button
                    key={date}
                    type="button"
                    className={`${styles.day} ${
                      active ? styles.activeDay : ""
                    } ${
                      hasPlanned
                        ? styles.plannedDay
                        : ""
                    } ${
                      hasSkipped
                        ? styles.skippedDay
                        : ""
                    } ${
                      selected
                        ? styles.selectedDay
                        : ""
                    } ${
                      today ? styles.today : ""
                    }`}
                    onClick={() => {
                      if (selectedDate === date) {
                        setSelectedDate("");
                        setSelectedActivity(
                          trainingActivities[0] ?? null,
                        );
                        return;
                      }

                      setSelectedDate(date);
                      setSelectedActivity(
                        dayActivities[0] ?? null,
                      );
                    }}
                  >
                    <span>{day.getDate()}</span>

                    {energy ? (
                      <span
                        className={`${styles.energyState} ${
                          energy.state === "deficit"
                            ? styles.energyDeficit
                            : energy.state === "surplus"
                            ? styles.energySurplus
                            : styles.energyMaintenance
                        }`}
                        title={`${energy.state === "deficit" ? copy.deficit : energy.state === "surplus" ? copy.surplus : copy.maintenance}: ${Math.abs(energy.balance_kcal)} kcal`}
                        aria-label={energy.state}
                      >
                        {energy.state === "deficit" ? "↓" : energy.state === "surplus" ? "↑" : "="}
                      </span>
                    ) : null}

                    {active ? (
                      <span
                        className={styles.dayActivityIcon}
                        aria-label={
                          dayActivities[0].activity_name
                        }
                        title={
                          dayActivities
                            .map(
                              (activity) =>
                                activity.activity_name,
                            )
                            .join(", ")
                        }
                      >
                        {activityIcon(
                          dayActivities[0],
                        )}
                      </span>
                    ) : null}

                    {hasPlanned ? (
                      <span
                        className={
                          styles.dayPlannedMarker
                        }
                        aria-label={copy.plannedActivity}
                        title={
                          visiblePlannedActivities
                            .map(
                              (item) =>
                                item.title,
                            )
                            .join(", ")
                        }
                      >
                        P
                      </span>
                    ) : null}

                    {!hasPlanned &&
                    hasSkipped ? (
                      <span
                        className={
                          styles.daySkippedMarker
                        }
                        aria-label={copy.skippedActivity}
                        title={
                          skippedPlannedActivities
                            .map(
                              (item) =>
                                item.title,
                            )
                            .join(", ")
                        }
                      >
                        S
                      </span>
                    ) : null}

                    {dayActivities.length > 1 ? (
                      <i>
                        +{dayActivities.length - 1}
                      </i>
                    ) : null}
                  </button>
                );
              })}
            </div>

            <div className={styles.energyLegend}>
              <span className={styles.energyDeficit}>↓ <i>Deficit</i></span>
              <span className={styles.energyMaintenance}>= <i>Mantenimento</i></span>
              <span className={styles.energySurplus}>↑ <i>Surplus</i></span>
            </div>

            {loading ? (
              <p className={styles.loading}>
                Carico il mese…
              </p>
            ) : null}
              </div>
            ) : null}
          </section>

          <details className={`${styles.uploadCard} ${styles.utilityCard}`}>
            <summary className={styles.utilitySummary}>
              <div>
              <p className={styles.eyebrow}>
                {copy.import}
              </p>
              <h2>{copy.uploadGpx}</h2>
              <p>
                {copy.uploadGpxIntro}
              </p>
              </div>
              <span className={styles.expandToggle} aria-hidden="true" />
            </summary>

            <div className={styles.utilityBody}>
            <label className={styles.dropZone}>
              <input
                type="file"
                accept=".gpx,.fit,.tcx,application/gpx+xml,application/xml,application/octet-stream"
                onChange={(event) => {
                  void chooseGpx(
                    event.target.files?.[0] ?? null,
                  );
                  event.currentTarget.value = "";
                }}
              />
              <span className={styles.uploadIcon}>
                ↑
              </span>
              <strong>
                {previewing
                  ? "Analizzo il percorso…"
                  : "Scegli file attività"}
              </strong>
              <small>GPX, FIT o TCX · massimo 10 MB</small>
            </label>

            {gpxFile ? (
              <p className={styles.fileName}>
                {gpxFile.name}
              </p>
            ) : null}
            </div>
          </details>
        </div>


        <details
          className={styles.trainingPrograms}
        >
          <summary
            className={
              styles.trainingProgramsSummary
            }
          >
            <div>
              <p className={styles.eyebrow}>
                {copy.programs}
              </p>

              <strong>
                {copy.trainingPrograms}
              </strong>

              <span>
                {copy.programsIntro}
              </span>
            </div>

            <span
              className={
                styles.expandToggle
              }
              aria-hidden="true"
            />
          </summary>

          <div
            className={
              styles.trainingProgramsBody
            }
          >
            <RunningPlanBuilder
              onCreated={() => {
                void loadMonth();
                void loadTrainingPlanActivities();
              }}
            />

            <StrengthPlanPanel />
          </div>
        </details>

        <details
          className={`${styles.plannerSection} ${styles.plannerCollapsible}`}
        >
          <summary className={styles.plannerHeading}>
            {nextPlannedActivity ? (
              <>
                <div className={styles.nextActivitySpotlightCopy}>
                  <p className={styles.eyebrow}>
                    {copy.nextActivity}
                  </p>

                  <h2>{nextPlannedActivity.title}</h2>

                  <p className={styles.nextActivitySpotlightMeta}>
                    {plannedDateLabel(
                      nextPlannedActivity.scheduled_date,
                      displayLocale,
                      copy.today,
                      copy.tomorrow,
                    )}

                    {nextPlannedActivity.scheduled_time
                      ? ` · ${nextPlannedActivity.scheduled_time.slice(
                          0,
                          5,
                        )}`
                      : ""}

                    {nextPlannedActivity.duration_minutes
                      ? ` · ${nextPlannedActivity.duration_minutes} min`
                      : ""}

                    {nextPlannedActivity.distance_meters &&
                    plannedActivitySupportsDistance(
                      nextPlannedActivity.activity_type,
                    )
                      ? ` · ${(
                          nextPlannedActivity.distance_meters /
                          1000
                        ).toLocaleString("it-IT", {
                          maximumFractionDigits: 1,
                        })} km`
                      : ""}

                    {` · ${
                      PLANNED_INTENSITY_LABELS[
                        nextPlannedActivity.intensity
                      ]
                    }`}
                  </p>
                </div>

                <div className={styles.nextActivitySpotlightActions}>
                  <button
                    type="button"
                    className={styles.nextActivityConfirm}
                    disabled={
                      busyPlanId === nextPlannedActivity.id
                    }
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();

                      void setPlannedStatus(
                        nextPlannedActivity,
                        "completed",
                      );
                    }}
                  >
                    {nextPlannedActivity.activity_type
                      .trim()
                      .toLocaleLowerCase("it-IT") === "corsa"
                      ? `✓ ${copy.confirmRun}`
                      : `✓ ${copy.confirmActivity}`}
                  </button>

                  <button
                    type="button"
                    className={styles.nextActivityGpx}
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      openPlannedGpxPicker(
                        nextPlannedActivity,
                      );
                    }}
                    disabled={
                      busyPlanId === nextPlannedActivity.id
                    }
                  >
                    {copy.uploadGpx}
                  </button>

                  <span className={styles.plannerMorePrompt}>
                    {copy.seeMorePlanned}
                    <span
                      className={styles.expandToggle}
                      aria-hidden="true"
                    />
                  </span>
                </div>
              </>
            ) : (
              <>
                <div>
                  <p className={styles.eyebrow}>
                    {planText.plan}
                  </p>
                  <h2>{copy.noPlanned}</h2>
                  <p>
                    {planText.openToAdd}
                  </p>
                </div>

                <span className={styles.plannerMorePrompt}>
                  {planText.planActivity}
                  <span
                    className={styles.expandToggle}
                    aria-hidden="true"
                  />
                </span>
              </>
            )}
          </summary>


          <div className={styles.plannerGrid}>
            <div className={styles.plannerForm}>
              <label>
                {planText.activity}
                <input
                  value={planTitle}
                  placeholder={planText.example}
                  onChange={(event) =>
                    setPlanTitle(
                      event.target.value,
                    )
                  }
                />
              </label>

              <label>
                {planText.type}
                <select
                  value={planType}
                  onChange={(event) => {
                    const nextType =
                      event.target.value;

                    setPlanType(
                      nextType,
                    );

                    if (
                      !plannedActivitySupportsDistance(
                        nextType,
                      )
                    ) {
                      setPlanDistanceKm("");
                    }
                  }}
                >
                  <option value="Corsa">{copy.run}</option>
                  <option value="Palestra">{locale === "it" ? "Palestra" : locale === "en" ? "Gym" : locale === "nl" ? "Sportschool" : "Musculation"}</option>
                  <option value="Padel">Padel</option>
                  <option value="Bici">{copy.bicycle}</option>
                  <option value="Nuoto">{locale === "it" ? "Nuoto" : locale === "en" ? "Swimming" : locale === "nl" ? "Zwemmen" : "Natation"}</option>
                  <option value="Camminata">{copy.walk}</option>
                  <option value="Altro">{copy.other}</option>
                </select>
              </label>

              <label>
                {planText.date}
                <input
                  type="date"
                  value={planDate}
                  onChange={(event) =>
                    setPlanDate(
                      event.target.value,
                    )
                  }
                />
              </label>

              <label>
                {planText.time}
                <input
                  type="time"
                  value={planTime}
                  onChange={(event) =>
                    setPlanTime(
                      event.target.value,
                    )
                  }
                />
              </label>

              <label>
                {planText.expectedDuration}
                <div className={styles.planUnitInput}>
                  <input
                    type="number"
                    min="1"
                    value={planDuration}
                    placeholder="60"
                    onChange={(event) =>
                      setPlanDuration(
                        event.target.value,
                      )
                    }
                  />
                  <span>min</span>
                </div>
              </label>

              {plannedActivitySupportsDistance(
                planType,
              ) ? (
                <label>
                  {planText.distance}
                  <div
                    className={
                      styles.planUnitInput
                    }
                  >
                    <input
                      type="number"
                      min="0"
                      step="0.1"
                      value={planDistanceKm}
                      placeholder="10"
                      onChange={(event) =>
                        setPlanDistanceKm(
                          event.target.value,
                        )
                      }
                    />
                    <span>km</span>
                  </div>
                </label>
              ) : (
                <div
                  className={
                    styles.planNoDistance
                  }
                >
                  <span>
                    {planText.distance}
                  </span>
                  <strong>
                    {planText.noDistance}{" "}
                    {planType.toLocaleLowerCase(
                      "it-IT",
                    )}
                  </strong>
                </div>
              )}

              <label>
                {planText.intensity}
                <select
                  value={planIntensity}
                  onChange={(event) =>
                    setPlanIntensity(
                      event.target
                        .value as PlannedActivityIntensity,
                    )
                  }
                >
                  <option value="low">
                    {planText.easy}
                  </option>
                  <option value="moderate">
                    {planText.moderate}
                  </option>
                  <option value="hard">
                    {planText.hard}
                  </option>
                  <option value="race">
                    {planText.race}
                  </option>
                  <option value="unknown">
                    {planText.unknown}
                  </option>
                </select>
              </label>

              <label className={styles.planNotes}>
                {planText.notes}
                <input
                  value={planNotes}
                  placeholder={planText.optional}
                  onChange={(event) =>
                    setPlanNotes(
                      event.target.value,
                    )
                  }
                />
              </label>

              <button
                type="button"
                className={styles.savePlanButton}
                disabled={
                  savingPlan ||
                  !planTitle.trim() ||
                  !planDate
                }
                onClick={() => {
                  void savePlannedActivity();
                }}
              >
                {savingPlan
                  ? planText.planning
                  : planText.add}
              </button>
            </div>

            <div className={styles.upcomingList}>
              {visiblePlannedActivities.length ? (
                visiblePlannedActivities.map(
                  (item) => (
                    <article
                      key={item.id}
                      className={`${styles.upcomingCard} ${
                        item.training_plan_id
                          ? styles.upcomingTrainingCard
                          : ""
                      } ${
                        item.id === nextPlannedActivityId
                          ? styles.nextUpcomingCard
                          : ""
                      }`}
                    >
                      <div
                        className={
                          styles.upcomingDate
                        }
                      >
                        <strong>
                          {plannedDateLabel(
                            item.scheduled_date,
                            displayLocale,
                            copy.today,
                            copy.tomorrow,
                          )}
                        </strong>

                        <small>
                          {new Date(
                            `${item.scheduled_date}T00:00:00`,
                          ).toLocaleDateString(
                            "it-IT",
                            {
                              day: "numeric",
                              month: "short",
                            },
                          )}
                        </small>

                        {item.scheduled_time ? (
                          <span>
                            {item.scheduled_time.slice(
                              0,
                              5,
                            )}
                          </span>
                        ) : null}
                      </div>

                      <div
                        className={
                          styles.upcomingBody
                        }
                      >
                        {item.training_plan_id ? (
                          <div
                            className={
                              styles.trainingSessionMeta
                            }
                          >
                            {item.training_week ? (
                              <span
                                className={
                                  styles.trainingWeekBadge
                                }
                              >
                                Settimana{" "}
                                {item.training_week}
                              </span>
                            ) : null}

                            {runningSessionLabel(
                              item.session_kind,
                            ) ? (
                              <span
                                className={`${styles.trainingKindBadge} ${
                                  styles[
                                    `trainingKind_${item.session_kind}`
                                  ] ?? ""
                                }`}
                              >
                                {runningSessionLabel(
                                  item.session_kind,
                                )}
                              </span>
                            ) : null}

                            <span
                              className={
                                styles.trainingPlanBadge
                              }
                            >
                              Running plan
                            </span>
                          </div>
                        ) : null}

                        <div
                          className={
                            styles.upcomingBadges
                          }
                        >
                          {item.id ===
                          nextPlannedActivityId ? (
                            <span
                              className={
                                styles.nextActivityBadge
                              }
                            >
                              PROSSIMA
                            </span>
                          ) : null}
                          <span
                            className={`${styles.upcomingType} ${
                              item.training_plan_id
                                ? styles.upcomingTypeTraining
                                : ""
                            }`}
                          >
                            {item.activity_type}
                          </span>

                          <span
                            className={`${styles.upcomingIntensity} ${
                              styles[
                                `upcomingIntensity_${item.intensity}`
                              ] ?? ""
                            }`}
                          >
                            {
                              PLANNED_INTENSITY_LABELS[
                                item.intensity
                              ]
                            }
                          </span>
                        </div>

                        <h3>{item.title}</h3>

                        <p>
                          {item.duration_minutes
                            ? `${item.duration_minutes} min`
                            : "Durata da definire"}

                          {item.distance_meters &&
                          plannedActivitySupportsDistance(
                            item.activity_type,
                          )
                            ? ` · ${(
                                item.distance_meters /
                                1000
                              ).toLocaleString(
                                "it-IT",
                                {
                                  maximumFractionDigits:
                                    1,
                                },
                              )} km`
                            : ""}
                        </p>

                        {item.notes ? (
                          <small>
                            {item.notes}
                          </small>
                        ) : null}

                        {editingPlan?.id ===
                          item.id &&
                        editPlan ? (
                          <div
                            className={
                              styles.planEditPanel
                            }
                          >
                            <div
                              className={
                                styles.planEditHeading
                              }
                            >
                              <strong>
                                Modifica attività
                              </strong>

                              <span>
                                {item.training_plan_id
                                  ? "Sessione Running"
                                  : "Attività pianificata"}
                              </span>
                            </div>

                            <div
                              className={
                                styles.planEditGrid
                              }
                            >
                              <label
                                className={
                                  styles.planEditWide
                                }
                              >
                                Titolo
                                <input
                                  maxLength={160}
                                  value={
                                    editPlan.title
                                  }
                                  onChange={(
                                    event,
                                  ) =>
                                    setEditPlan(
                                      (
                                        current,
                                      ) =>
                                        current
                                          ? {
                                              ...current,
                                              title:
                                                event
                                                  .target
                                                  .value,
                                            }
                                          : current,
                                    )
                                  }
                                />
                              </label>

                              <label>
                                Data
                                <input
                                  type="date"
                                  value={
                                    editPlan.scheduledDate
                                  }
                                  disabled={Boolean(
                                    item.training_plan_id &&
                                      item.session_kind ===
                                        "race",
                                  )}
                                  onChange={(
                                    event,
                                  ) =>
                                    setEditPlan(
                                      (
                                        current,
                                      ) =>
                                        current
                                          ? {
                                              ...current,
                                              scheduledDate:
                                                event
                                                  .target
                                                  .value,
                                            }
                                          : current,
                                    )
                                  }
                                />
                              </label>

                              <label>
                                Ora
                                <input
                                  type="time"
                                  value={
                                    editPlan.scheduledTime
                                  }
                                  onChange={(
                                    event,
                                  ) =>
                                    setEditPlan(
                                      (
                                        current,
                                      ) =>
                                        current
                                          ? {
                                              ...current,
                                              scheduledTime:
                                                event
                                                  .target
                                                  .value,
                                            }
                                          : current,
                                    )
                                  }
                                />
                              </label>

                              <label>
                                Durata
                                <div
                                  className={
                                    styles.planUnitInput
                                  }
                                >
                                  <input
                                    type="number"
                                    min="1"
                                    value={
                                      editPlan.durationMinutes
                                    }
                                    placeholder="60"
                                    onChange={(
                                      event,
                                    ) =>
                                      setEditPlan(
                                        (
                                          current,
                                        ) =>
                                          current
                                            ? {
                                                ...current,
                                                durationMinutes:
                                                  event
                                                    .target
                                                    .value,
                                              }
                                            : current,
                                      )
                                    }
                                  />
                                  <span>
                                    min
                                  </span>
                                </div>
                              </label>

                              {plannedActivitySupportsDistance(
                                item.activity_type,
                              ) ? (
                                <label>
                                  Distanza
                                  <div
                                    className={
                                      styles.planUnitInput
                                    }
                                  >
                                    <input
                                      type="number"
                                      min="0"
                                      step="0.1"
                                      disabled={Boolean(
                                        item.training_plan_id &&
                                          item.session_kind ===
                                            "race",
                                      )}
                                      value={
                                        editPlan.distanceKm
                                      }
                                      onChange={(
                                        event,
                                      ) =>
                                        setEditPlan(
                                          (
                                            current,
                                          ) =>
                                            current
                                              ? {
                                                  ...current,
                                                  distanceKm:
                                                    event
                                                      .target
                                                      .value,
                                                }
                                              : current,
                                        )
                                      }
                                    />
                                    <span>
                                      km
                                    </span>
                                  </div>
                                </label>
                              ) : null}

                              <label
                                className={
                                  styles.planEditWide
                                }
                              >
                                Note
                                <textarea
                                  rows={3}
                                  maxLength={2000}
                                  value={
                                    editPlan.notes
                                  }
                                  onChange={(
                                    event,
                                  ) =>
                                    setEditPlan(
                                      (
                                        current,
                                      ) =>
                                        current
                                          ? {
                                              ...current,
                                              notes:
                                                event
                                                  .target
                                                  .value,
                                            }
                                          : current,
                                    )
                                  }
                                />
                              </label>
                            </div>

                            {item.training_plan_id ? (
                              <p
                                className={
                                  styles.planEditHint
                                }
                              >
                                Tipo e intensità
                                restano gestiti dal
                                Running plan.
                                {item.session_kind ===
                                "race"
                                  ? " Data e distanza della gara restano protette."
                                  : ""}
                              </p>
                            ) : null}

                            <div
                              className={
                                styles.planEditActions
                              }
                            >
                              <button
                                type="button"
                                disabled={
                                  savingPlanEdit
                                }
                                onClick={
                                  cancelPlannedActivityEdit
                                }
                              >
                                Annulla
                              </button>

                              <button
                                type="button"
                                className={
                                  styles.savePlanEditButton
                                }
                                disabled={
                                  savingPlanEdit ||
                                  !editPlan.title.trim()
                                }
                                onClick={() => {
                                  void savePlannedActivityEdit();
                                }}
                              >
                                {savingPlanEdit
                                  ? "Salvo…"
                                  : "Salva modifiche"}
                              </button>
                            </div>
                          </div>
                        ) : null}

                        {adaptationFeedback[
                          item.id
                        ] ? (
                          <div
                            className={
                              styles.adaptationFeedback
                            }
                          >
                            {
                              adaptationFeedback[
                                item.id
                              ]
                            }
                          </div>
                        ) : null}

                        {item.training_plan_id &&
                        !dismissedAdaptations[
                          item.id
                        ] &&
                        planAdaptations[
                          item.id
                        ]?.proposal
                          .adaptation_required ? (
                          <div
                            className={
                              styles.adaptationCard
                            }
                          >
                            <div
                              className={
                                styles.adaptationHeading
                              }
                            >
                              <span
                                className={
                                  styles.adaptationEyebrow
                                }
                              >
                                ADATTAMENTO DEL PIANO
                              </span>

                              <strong>
                                {zero
                                  ? "Il piano ha notato quello che hai combinato."
                                  : planAdaptations[
                                      item.id
                                    ]!.proposal.title}
                              </strong>
                            </div>

                            <p>
                              {
                                planAdaptations[
                                  item.id
                                ]!.proposal.message
                              }
                            </p>

                            {planAdaptations[
                              item.id
                            ]!.proposal.target &&
                            planAdaptations[
                              item.id
                            ]!.proposal.preview ? (
                              <div
                                className={
                                  styles.adaptationComparison
                                }
                              >
                                <div>
                                  <span>
                                    Prima
                                  </span>
                                  <strong>
                                    {
                                      planAdaptations[
                                        item.id
                                      ]!.proposal
                                        .target!.title
                                    }
                                  </strong>
                                  <small>
                                    {planAdaptations[
                                      item.id
                                    ]!.proposal
                                      .target!
                                      .distance_meters
                                      ? `${(
                                          Number(
                                            planAdaptations[
                                              item.id
                                            ]!.proposal
                                              .target!
                                              .distance_meters,
                                          ) / 1000
                                        ).toLocaleString(
                                          "it-IT",
                                          {
                                            maximumFractionDigits:
                                              1,
                                          },
                                        )} km`
                                      : ""}
                                    {planAdaptations[
                                      item.id
                                    ]!.proposal
                                      .target!
                                      .duration_minutes
                                      ? `${
                                          planAdaptations[
                                            item.id
                                          ]!.proposal
                                            .target!
                                            .distance_meters
                                            ? " · "
                                            : ""
                                        }${
                                          planAdaptations[
                                            item.id
                                          ]!.proposal
                                            .target!
                                            .duration_minutes
                                        } min`
                                      : ""}
                                  </small>
                                </div>

                                <span
                                  className={
                                    styles.adaptationArrow
                                  }
                                  aria-hidden="true"
                                >
                                  →
                                </span>

                                <div>
                                  <span>
                                    Proposta
                                  </span>
                                  <strong>
                                    {
                                      planAdaptations[
                                        item.id
                                      ]!.proposal
                                        .preview!.title
                                    }
                                  </strong>
                                  <small>
                                    {planAdaptations[
                                      item.id
                                    ]!.proposal
                                      .preview!
                                      .distance_meters
                                      ? `${(
                                          Number(
                                            planAdaptations[
                                              item.id
                                            ]!.proposal
                                              .preview!
                                              .distance_meters,
                                          ) / 1000
                                        ).toLocaleString(
                                          "it-IT",
                                          {
                                            maximumFractionDigits:
                                              1,
                                          },
                                        )} km`
                                      : ""}
                                    {planAdaptations[
                                      item.id
                                    ]!.proposal
                                      .preview!
                                      .duration_minutes
                                      ? `${
                                          planAdaptations[
                                            item.id
                                          ]!.proposal
                                            .preview!
                                            .distance_meters
                                            ? " · "
                                            : ""
                                        }${
                                          planAdaptations[
                                            item.id
                                          ]!.proposal
                                            .preview!
                                            .duration_minutes
                                        } min`
                                      : ""}
                                  </small>
                                </div>
                              </div>
                            ) : null}

                            <div
                              className={
                                styles.adaptationActions
                              }
                            >
                              <button
                                type="button"
                                className={
                                  styles.keepPlanButton
                                }
                                disabled={
                                  adaptationApplyingId ===
                                  item.id
                                }
                                onClick={() => {
                                  void keepCurrentPlan(
                                    item,
                                  );
                                }}
                              >
                                Mantieni piano
                              </button>

                              <button
                                type="button"
                                className={
                                  styles.applyAdaptationButton
                                }
                                disabled={
                                  adaptationApplyingId ===
                                  item.id
                                }
                                onClick={() => {
                                  void applyAdaptation(
                                    item,
                                  );
                                }}
                              >
                                {adaptationApplyingId ===
                                item.id
                                  ? "Applico…"
                                  : "Applica adattamento"}
                              </button>
                            </div>
                          </div>
                        ) : adaptationLoadingIds[
                            item.id
                          ] ? (
                          <div
                            className={
                              styles.adaptationLoading
                            }
                          >
                            Valuto se il piano va adattato…
                          </div>
                        ) : null}

                        <div
                          className={
                            styles.upcomingActions
                          }
                        >
                          {item.status ===
                          "planned" ? (
                            <>
                              <button
                                type="button"
                                className={
                                  styles.editPlanButton
                                }
                                disabled={
                                  busyPlanId ===
                                    item.id ||
                                  savingPlanEdit
                                }
                                onClick={() => {
                                  if (
                                    editingPlan?.id ===
                                    item.id
                                  ) {
                                    cancelPlannedActivityEdit();
                                    return;
                                  }

                                  startPlannedActivityEdit(
                                    item,
                                  );
                                }}
                              >
                                {editingPlan?.id ===
                                item.id
                                  ? "Chiudi modifica"
                                  : planText.edit}
                              </button>

                              <button
                                type="button"
                                className={
                                  styles.completePlanButton
                                }
                                disabled={
                                  busyPlanId ===
                                  item.id
                                }
                                onClick={() => {
                                  void setPlannedStatus(
                                    item,
                                    "completed",
                                  );
                                }}
                              >
                                {item.id === nextPlannedActivityId &&
                                item.activity_type
                                  .trim()
                                  .toLocaleLowerCase("it-IT") === "corsa"
                                  ? "✓ Conferma corsa"
                                  : planText.completed}
                              </button>

                              <button
                                type="button"
                                className={
                                  styles.completePlanButton
                                }
                                disabled={
                                  busyPlanId === item.id
                                }
                                onClick={() => {
                                  openPlannedGpxPicker(item);
                                }}
                              >
                                {copy.uploadGpx}
                              </button>

                              <button
                                type="button"
                                disabled={
                                  busyPlanId ===
                                  item.id
                                }
                                onClick={() => {
                                  void setPlannedStatus(
                                    item,
                                    "skipped",
                                  );
                                }}
                              >
                                {planText.skipped}
                              </button>
                            </>
                          ) : (
                            <span>
                              {item.status ===
                              "completed"
                                ? planText.completed
                                : planText.skipped}
                            </span>
                          )}

                          <button
                            type="button"
                            className={
                              styles.deletePlanButton
                            }
                            disabled={
                              busyPlanId ===
                              item.id
                            }
                            onClick={() => {
                              void removePlannedActivity(
                                item,
                              );
                            }}
                          >
                            {planText.remove}
                          </button>
                        </div>
                      </div>
                    </article>
                  ),
                )
              ) : (
                <div className={styles.emptyPlan}>
                  <strong>
                    {planText.noMore}
                  </strong>
                  <p>
                    Per ora il futuro è sorprendentemente
                    libero.
                  </p>
                </div>
              )}

              {remainingPlannedActivities.length > 6 ? (
                <button
                  type="button"
                  className={
                    styles.showAllPlannedButton
                  }
                  onClick={() => {
                    setShowAllPlannedActivities(
                      (current) => !current,
                    );
                  }}
                >
                  {showAllPlannedActivities
                    ? planText.firstSix
                    : `${planText.all} (${remainingPlannedActivities.length})`}
                </button>
              ) : null}

            </div>
          </div>
        </details>

        {error ? (
          <div className={styles.error}>{error}</div>
        ) : null}

        {importMessage ? (
          <div className={styles.success}>
            {importMessage}
          </div>
        ) : null}

        <details className={styles.loggerCard}>
          <summary className={styles.loggerHeading}>
            <span>
              <span className={styles.eyebrow}>{copy.register}</span>
              <strong>{copy.newActivityOrSteps}</strong>
            </span>
            <span
              className={
                styles.expandToggle
              }
              aria-hidden="true"
            />
          </summary>
          <ActivityLogger
            date={selectedDate || isoDate(new Date())}
            accessToken={accessToken}
            showMovement
            onSaved={(savedDate) => {
              if (!savedDate) {
                return loadMonth();
              }

              setSelectedDate(savedDate);
              setMonth(
                new Date(`${savedDate}T12:00:00`),
              );
            }}
          />
        </details>

        {gpxPreview ? (
          <section className={styles.previewCard}>
            <div className={styles.cardHeading}>
              <div>
                <p className={styles.eyebrow}>
                  {copy.preview}
                </p>
                <h2>{copy.confirmActivity}</h2>
              </div>

              <span className={styles.gpxBadge}>
                {gpxPreview.file_format ?? "ACTIVITY"}
              </span>
            </div>

            <div className={styles.previewGrid}>
              <div className={styles.previewForm}>
                <label>
                  {copy.name}
                  <input
                    value={gpxName}
                    onChange={(event) =>
                      setGpxName(event.target.value)
                    }
                  />
                </label>

                <label>
                  {copy.type}
                  <select
                    value={gpxType}
                    onChange={(event) =>
                      setGpxType(event.target.value)
                    }
                  >
                    <option value="Corsa">{copy.run}</option>
                    <option value="Camminata">{copy.walk}</option>
                    <option value="Escursione">{copy.hike}</option>
                    <option value="Bicicletta">{copy.bicycle}</option>
                    <option value="Nuoto">
                      {locale === "it" ? "Nuoto" : locale === "en" ? "Swimming" : locale === "nl" ? "Zwemmen" : "Natation"}
                    </option>
                    <option value="Palestra">
                      {locale === "it" ? "Palestra" : locale === "en" ? "Gym / strength" : locale === "nl" ? "Sportschool / kracht" : "Musculation"}
                    </option>
                    <option value="Padel">Padel</option>
                    <option value="Tennis">Tennis</option>
                    <option value="Calcio">
                      {locale === "it" ? "Calcio" : locale === "en" ? "Football" : locale === "nl" ? "Voetbal" : "Football"}
                    </option>
                    <option value="Altro">{copy.other}</option>
                  </select>
                </label>

                <label>
                  {copy.date}
                  <input
                    type="date"
                    value={selectedDate}
                    onChange={(event) =>
                      setSelectedDate(
                        event.target.value,
                      )
                    }
                  />
                </label>

                <label>
                  {copy.caloriesBurned}
                  <input
                    type="number"
                    min="0"
                    value={gpxCalories}
                    onChange={(event) =>
                      setGpxCalories(
                        event.target.value,
                      )
                    }
                  />
                </label>
              </div>

              <div className={styles.previewStats}>
                <div>
                  <span>{copy.distance}</span>
                  <strong>
                    {formatDistance(
                      gpxPreview.distance_meters,
                    )}
                  </strong>
                </div>
                <div>
                  <span>{copy.duration}</span>
                  <strong>
                    {formatDuration(
                      gpxPreview.duration_seconds,
                    )}
                  </strong>
                </div>
                <div>
                  <span>{copy.averageCadence}</span>
                  <strong>
                    {gpxPreview.average_cadence != null
                      ? `${Math.round(
                          gpxPreview.average_cadence,
                        )} spm`
                      : copy.unavailable}
                  </strong>
                </div>
                <div>
                  <span>{copy.averageHeartRate}</span>
                  <strong>
                    {gpxPreview.average_heart_rate != null
                      ? `${Math.round(
                          gpxPreview.average_heart_rate,
                        )} bpm`
                      : copy.unavailable}
                  </strong>
                </div>
              </div>
            </div>

            <ActivityMap
              points={normalizedArray<ActivityRoutePoint>(gpxPreview.route_points)}
              activityName={gpxPreview.activity_name}
              compact
            />

            <button
              type="button"
              className={styles.importButton}
              disabled={importing}
              onClick={() => {
                void saveGpx();
              }}
            >
              {importing
                ? copy.importing
                : copy.saveActivity}
            </button>
          </section>
        ) : null}

        <div className={styles.contentGrid}>
          <section className={styles.card}>
            <div className={styles.cardHeading}>
              <div>
                <p className={styles.eyebrow}>
                  {selectedDate
                    ? new Date(
                        `${selectedDate}T00:00:00`,
                      ).toLocaleDateString(
                        displayLocale,
                        {
                          day: "numeric",
                          month: "long",
                        },
                      )
                    : copy.monthly}
                </p>
                <h2>{copy.registeredActivities}</h2>
              </div>

              {selectedDate ? (
                <button
                  type="button"
                  className={styles.showMonthButton}
                  onClick={() => {
                    setSelectedDate("");
                    setSelectedActivity(
                      trainingActivities[0] ?? null,
                    );
                  }}
                >
                  {copy.showWholeMonth}
                </button>
              ) : null}
            </div>

            <div className={styles.activityList}>
              {visibleActivities.length ? (
                visibleActivities.map((activity) => (
                  <button
                    type="button"
                    key={String(activity.id)}
                    className={`${styles.activityRow} ${
                      detail?.id === activity.id
                        ? styles.activityRowActive
                        : ""
                    }`}
                    onClick={() =>
                      setSelectedActivity(activity)
                    }
                  >
                    <span
                      className={styles.activityMark}
                      aria-hidden="true"
                    >
                      {activityIcon(activity)}
                    </span>

                    <span className={styles.activityInfo}>
                      <strong>
                        {activity.activity_name}
                      </strong>
                      <small>
                        {formatActivityDate(activity.date, displayLocale)} · {activity.activity_type ??
                          (activity.source === "gpx"
                            ? copy.gpxActivity
                            : copy.manualActivity)}
                      </small>
                    </span>

                    <span className={styles.activityValue}>
                      {activity.distance_meters
                        ? formatDistance(
                            activity.distance_meters,
                          )
                        : `${activity.burned_calories} kcal`}
                    </span>
                  </button>
                ))
              ) : (
                <div className={styles.emptyList}>
                  {selectedDate
                    ? copy.noDayActivities
                    : copy.noMonthActivities}
                </div>
              )}
            </div>
          </section>

          <section className={styles.detailCard}>
            {detail ? (
              <>
                <div className={styles.cardHeading}>
                  <div>
                    <p className={styles.eyebrow}>
                      {copy.detail}
                    </p>
                    <h2>{detail.activity_name}</h2>
                  </div>

                  <div className={styles.detailActions}>
                    <span className={styles.gpxBadge}>{detail.source === "gpx" ? "GPX" : copy.manual}</span>
                    <button
                      type="button"
                      className={styles.deleteButton}
                      disabled={deletingId === detail.id}
                      onClick={() => void removeActivity(detail)}
                    >
                      {deletingId === detail.id ? copy.deleting : copy.delete}
                    </button>
                  </div>
                </div>

                <div className={styles.detailStats}>
                  <div>
                    <span>{copy.date}</span>
                    <strong>{formatActivityDate(detail.date, displayLocale)}</strong>
                  </div>
                  <div>
                    <span>{copy.distance}</span>
                    <strong>
                      {formatDistance(
                        detail.distance_meters,
                      )}
                    </strong>
                  </div>
                  <div>
                    <span>{copy.duration}</span>
                    <strong>
                      {formatDuration(
                        detail.duration_seconds,
                      )}
                    </strong>
                  </div>
                  <div>
                    <span>{copy.calories}</span>
                    <strong>
                      {detail.burned_calories} kcal
                    </strong>
                  </div>
                </div>

                <div
                  className={
                    styles.activityAiComment
                  }
                >
                  <div
                    className={
                      styles.activityAiCommentHeader
                    }
                  >
                    <span
                      className={
                        styles.activityAiMark
                      }
                      aria-hidden="true"
                    >
                      AI
                    </span>
                    <div>
                      <span>
                        SanoSync AI
                      </span>
                      <strong>
                        {zero
                          ? copy.verdict
                          : copy.activityComment}
                      </strong>
                    </div>
                  </div>

                  <p>
                    {activityCommentLoading &&
                    !activityComment
                      ? zero
                        ? copy.zeroAnalysing
                        : copy.analysing
                      : activityComment ??
                        (zero
                          ? copy.zeroRegisteredFallback
                          : copy.registeredFallback)}
                  </p>
                </div>

                <ActivityMap
                  points={normalizedArray<ActivityRoutePoint>(detail.route_points)}
                  activityName={detail.activity_name}
                  compact
                />

                <div className={styles.charts}>
                  <MetricChart
                    points={normalizedArray<ActivitySeriesPoint>(detail.series_points)}
                    metric="cadence"
                    title={copy.cadence}
                    unit="spm"
                    copy={copy}
                  />
                  <MetricChart
                    points={normalizedArray<ActivitySeriesPoint>(detail.series_points)}
                    metric="heart_rate"
                    title={copy.heartRate}
                    unit="bpm"
                    copy={copy}
                  />
                </div>
              </>
            ) : (
              <div className={styles.emptyDetail}>
                <strong>
                  {copy.selectActivity}
                </strong>
                <span>
                  {copy.selectActivityIntro}
                </span>
              </div>
            )}
          </section>
        </div>
      </main>
    </>
  );
}
