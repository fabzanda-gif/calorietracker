"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { ActivityLogger } from "@/components/activity/ActivityLogger";
import { ActivityMap } from "@/components/activity/ActivityMap";
import { useAuth } from "@/components/auth/AuthProvider";
import { AppNav } from "@/components/navigation/AppNav";
import {
  getActivitiesForRange,
  getActivityOverview,
  getPlannedActivities,
  createPlannedActivity,
  updatePlannedActivity,
  deletePlannedActivity,
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
} from "@/lib/api/activities";

import styles from "./ActivitiesPage.module.css";

type ExperienceMode = "standard" | "zero";

const WEEKDAYS = [
  "Lun",
  "Mar",
  "Mer",
  "Gio",
  "Ven",
  "Sab",
  "Dom",
];

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
    activity.source === "gpx" &&
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

function formatActivityDate(value: string): string {
  return new Date(`${value}T00:00:00`).toLocaleDateString("it-IT", {
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
}: {
  points: ActivitySeriesPoint[];
  metric: "cadence" | "heart_rate";
  title: string;
  unit: string;
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
          <strong>Dato non disponibile</strong>
          <span>
            Questo GPX non contiene {title.toLowerCase()}.
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
        aria-label={`Grafico ${title}`}
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
          Min {Math.round(minimum)} {unit}
        </span>
        <span>
          Max {Math.round(maximum)} {unit}
        </span>
      </div>
    </section>
  );
}

export default function ActivitiesPage() {
  const { accessToken } = useAuth();
  const [experienceMode, setExperienceMode] =
    useState<ExperienceMode>("standard");
  const [month, setMonth] = useState(
    () => new Date(),
  );
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

  const [gpxFile, setGpxFile] =
    useState<File | null>(null);
  const [gpxBase64, setGpxBase64] = useState("");
  const [gpxPreview, setGpxPreview] =
    useState<GpxActivityPreview | null>(null);
  const [gpxName, setGpxName] = useState("");
  const [gpxType, setGpxType] = useState("Corsa");
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

  useEffect(() => {
    const stored = window.localStorage.getItem(
      "sanosync-experience-mode",
    );

    if (stored === "zero") {
      setExperienceMode("zero");
    }
  }, []);

  const loadMonth = useCallback(async () => {
    if (!accessToken) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const bounds = monthBounds(month);
      const today = new Date();
      const rollingStart = new Date(today);
      rollingStart.setDate(today.getDate() - 29);
      const plannedEnd = new Date(today);
      plannedEnd.setDate(
        today.getDate() + 30,
      );

      const [
        response,
        recentResponse,
        plannedResponse,
      ] = await Promise.all([
        getActivityOverview(
          bounds.start,
          bounds.end,
          accessToken,
        ),
        getActivitiesForRange(
          isoDate(rollingStart),
          isoDate(today),
          accessToken,
        ),
        getPlannedActivities(
          isoDate(today),
          isoDate(plannedEnd),
          accessToken,
        ),
      ]);

      const sortedItems = [...response.items].sort(
        (left, right) => activityTimestamp(right) - activityTimestamp(left),
      );
      setActivities(sortedItems);
      setRecentActivities(
        [...recentResponse.items].sort(
          (left, right) => activityTimestamp(right) - activityTimestamp(left),
        ),
      );
      setEnergyDays(response.energy_days);
      setPlannedActivities(
        plannedResponse.items,
      );

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
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a caricare le attività.",
      );
    } finally {
      setLoading(false);
    }
  }, [accessToken, month]);

  useEffect(() => {
    void loadMonth();
  }, [loadMonth]);

  const days = useMemo(
    () => calendarDays(month),
    [month],
  );

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

  async function chooseGpx(file: File | null) {
    setGpxFile(file);
    setGpxPreview(null);
    setImportMessage(null);
    setError(null);

    if (!file) {
      setGpxBase64("");
      return;
    }

    if (!file.name.toLowerCase().endsWith(".gpx")) {
      setError("Seleziona un file con estensione .gpx.");
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      setError("Il file GPX supera il limite di 5 MB.");
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
          activity_type: gpxType,
        },
        accessToken,
      );

      setGpxBase64(contentBase64);
      setGpxPreview(response.preview);
      setGpxName(response.preview.activity_name);
      setGpxCalories(String(response.preview.estimated_calories ?? 0));
      const previewDate =
        response.preview.date || isoDate(new Date());

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
          : "Non riesco ad analizzare il GPX.",
      );
    } finally {
      setPreviewing(false);
    }
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
        },
        accessToken,
      );

      setImportMessage("Attività GPX importata.");
      setGpxFile(null);
      setGpxBase64("");
      setGpxPreview(null);
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
        <header className={styles.header}>
          <div>
            <p className={styles.eyebrow}>
              Attività
            </p>
            <h1>
              {zero
                ? "Muoviti. Poi ne parliamo."
                : "La tua routine attiva"}
            </h1>
            <p>
              {zero
                ? "La cronaca dei tuoi tentativi di non diventare arredamento."
                : "Gli allenamenti che aggiungono qualcosa al movimento naturale della tua giornata."}
            </p>
          </div>

          <div className={styles.monthTotal}>
            <strong>{rollingTrainingActivities.length}</strong>
            <span>
              {rollingTrainingActivities.length === 1
                ? "attività negli ultimi 30 giorni"
                : "attività negli ultimi 30 giorni"}
            </span>
          </div>
        </header>

        <section className={styles.summarySection}>
          <div className={styles.summaryHeading}>
            <div>
              <p className={styles.eyebrow}>Il tuo movimento</p>
              <h2>Ultimi 30 giorni</h2>
            </div>
          </div>
          <div className={styles.summaryGrid}>
            <div><span>Attività</span><strong>{rollingSummary.workouts}</strong></div>
            <div><span>Tempo totale</span><strong>{formatDuration(rollingSummary.duration)}</strong></div>
            <div><span>Distanza</span><strong>{formatDistance(rollingSummary.distance)}</strong></div>
            <div><span>Energia</span><strong>{rollingSummary.calories.toLocaleString("it-IT")} kcal</strong></div>
          </div>
        </section>

        <section className={styles.plannerSection}>
          <div className={styles.plannerHeading}>
            <div>
              <p className={styles.eyebrow}>
                Pianifica
              </p>
              <h2>Prossime attività</h2>
              <p>
                Quello che hai intenzione di fare,
                non quello che è già successo.
              </p>
            </div>

            <span className={styles.plannerCount}>
              {
                plannedActivities.filter(
                  (item) =>
                    item.status === "planned",
                ).length
              }{" "}
              in programma
            </span>
          </div>

          <div className={styles.plannerGrid}>
            <div className={styles.plannerForm}>
              <label>
                Attività
                <input
                  value={planTitle}
                  placeholder="Es. Lungo 12 km"
                  onChange={(event) =>
                    setPlanTitle(
                      event.target.value,
                    )
                  }
                />
              </label>

              <label>
                Tipo
                <select
                  value={planType}
                  onChange={(event) =>
                    setPlanType(
                      event.target.value,
                    )
                  }
                >
                  <option>Corsa</option>
                  <option>Palestra</option>
                  <option>Padel</option>
                  <option>Bici</option>
                  <option>Nuoto</option>
                  <option>Camminata</option>
                  <option>Altro</option>
                </select>
              </label>

              <label>
                Data
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
                Ora
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
                Durata prevista
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

              <label>
                Distanza
                <div className={styles.planUnitInput}>
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

              <label>
                Intensità
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
                    Facile
                  </option>
                  <option value="moderate">
                    Moderata
                  </option>
                  <option value="hard">
                    Intensa
                  </option>
                  <option value="race">
                    Gara / test
                  </option>
                  <option value="unknown">
                    Da definire
                  </option>
                </select>
              </label>

              <label className={styles.planNotes}>
                Note
                <input
                  value={planNotes}
                  placeholder="Opzionale"
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
                  ? "Pianifico…"
                  : "Aggiungi al piano"}
              </button>
            </div>

            <div className={styles.upcomingList}>
              {plannedActivities.length ? (
                plannedActivities.map(
                  (item) => (
                    <article
                      key={item.id}
                      className={
                        styles.upcomingCard
                      }
                    >
                      <div
                        className={
                          styles.upcomingDate
                        }
                      >
                        <strong>
                          {new Date(
                            `${item.scheduled_date}T00:00:00`,
                          ).toLocaleDateString(
                            "it-IT",
                            {
                              weekday: "short",
                              day: "numeric",
                              month: "short",
                            },
                          )}
                        </strong>

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
                        <span
                          className={
                            styles.upcomingType
                          }
                        >
                          {item.activity_type}
                        </span>

                        <h3>{item.title}</h3>

                        <p>
                          {item.duration_minutes
                            ? `${item.duration_minutes} min`
                            : "Durata da definire"}

                          {item.distance_meters
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
                                Completata
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
                                Saltata
                              </button>
                            </>
                          ) : (
                            <span>
                              {item.status ===
                              "completed"
                                ? "Completata"
                                : "Saltata"}
                            </span>
                          )}

                          <button
                            type="button"
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
                            Elimina
                          </button>
                        </div>
                      </div>
                    </article>
                  ),
                )
              ) : (
                <div className={styles.emptyPlan}>
                  <strong>
                    Nessuna attività pianificata.
                  </strong>
                  <p>
                    Per ora il futuro è sorprendentemente
                    libero.
                  </p>
                </div>
              )}
            </div>
          </div>
        </section>

        {error ? (
          <div className={styles.error}>{error}</div>
        ) : null}

        {importMessage ? (
          <div className={styles.success}>
            {importMessage}
          </div>
        ) : null}

        <div className={styles.topGrid}>
          <section className={styles.card}>
            <div className={styles.cardHeading}>
              <div>
                <p className={styles.eyebrow}>
                  Costanza
                </p>
                <h2>Calendario attività</h2>
              </div>

              <div className={styles.monthControls}>
                <button
                  type="button"
                  aria-label="Mese precedente"
                  onClick={() =>
                    setMonth(
                      new Date(
                        month.getFullYear(),
                        month.getMonth() - 1,
                        1,
                      ),
                    )
                  }
                >
                  ←
                </button>

                <strong>
                  {month.toLocaleDateString("it-IT", {
                    month: "long",
                    year: "numeric",
                  })}
                </strong>

                <button
                  type="button"
                  aria-label="Mese successivo"
                  onClick={() =>
                    setMonth(
                      new Date(
                        month.getFullYear(),
                        month.getMonth() + 1,
                        1,
                      ),
                    )
                  }
                >
                  →
                </button>
              </div>
            </div>

            <div className={styles.calendar}>
              {WEEKDAYS.map((weekday) => (
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
                const active =
                  dayActivities.length > 0;
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
                        title={`${energy.state === "deficit" ? "Deficit" : energy.state === "surplus" ? "Surplus" : "Mantenimento"}: ${Math.abs(energy.balance_kcal)} kcal`}
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
          </section>

          <section className={styles.uploadCard}>
            <div>
              <p className={styles.eyebrow}>
                Importa
              </p>
              <h2>Carica un GPX</h2>
              <p>
                Percorso, durata, cadenza e frequenza
                cardiaca vengono letti dal file.
              </p>
            </div>

            <label className={styles.dropZone}>
              <input
                type="file"
                accept=".gpx,application/gpx+xml"
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
                  : "Scegli file GPX"}
              </strong>
              <small>Massimo 5 MB</small>
            </label>

            {gpxFile ? (
              <p className={styles.fileName}>
                {gpxFile.name}
              </p>
            ) : null}
          </section>
        </div>

        <details className={styles.loggerCard}>
          <summary className={styles.loggerHeading}>
            <span>
              <span className={styles.eyebrow}>Registra</span>
              <strong>Nuova attività o passi</strong>
            </span>
            <span className={styles.openHint}>Apri modulo ＋</span>
          </summary>
          <ActivityLogger
            date={selectedDate || isoDate(new Date())}
            accessToken={accessToken}
            showMovement
            onSaved={loadMonth}
          />
        </details>

        {gpxPreview ? (
          <section className={styles.previewCard}>
            <div className={styles.cardHeading}>
              <div>
                <p className={styles.eyebrow}>
                  Anteprima
                </p>
                <h2>Conferma l’attività</h2>
              </div>

              <span className={styles.gpxBadge}>
                GPX
              </span>
            </div>

            <div className={styles.previewGrid}>
              <div className={styles.previewForm}>
                <label>
                  Nome
                  <input
                    value={gpxName}
                    onChange={(event) =>
                      setGpxName(event.target.value)
                    }
                  />
                </label>

                <label>
                  Tipo
                  <select
                    value={gpxType}
                    onChange={(event) =>
                      setGpxType(event.target.value)
                    }
                  >
                    <option>Corsa</option>
                    <option>Camminata</option>
                    <option>Escursione</option>
                    <option>Bicicletta</option>
                    <option>Altro</option>
                  </select>
                </label>

                <label>
                  Data
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
                  Calorie bruciate
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
                  <span>Distanza</span>
                  <strong>
                    {formatDistance(
                      gpxPreview.distance_meters,
                    )}
                  </strong>
                </div>
                <div>
                  <span>Durata</span>
                  <strong>
                    {formatDuration(
                      gpxPreview.duration_seconds,
                    )}
                  </strong>
                </div>
                <div>
                  <span>Cadenza media</span>
                  <strong>
                    {gpxPreview.average_cadence != null
                      ? `${Math.round(
                          gpxPreview.average_cadence,
                        )} spm`
                      : "Non disponibile"}
                  </strong>
                </div>
                <div>
                  <span>FC media</span>
                  <strong>
                    {gpxPreview.average_heart_rate != null
                      ? `${Math.round(
                          gpxPreview.average_heart_rate,
                        )} bpm`
                      : "Non disponibile"}
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
                ? "Importazione…"
                : "Salva attività"}
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
                        "it-IT",
                        {
                          day: "numeric",
                          month: "long",
                        },
                      )
                    : "Mese"}
                </p>
                <h2>Attività registrate</h2>
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
                  Mostra tutto il mese
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
                        {formatActivityDate(activity.date)} · {activity.activity_type ??
                          (activity.source === "gpx"
                            ? "Attività GPX"
                            : "Attività manuale")}
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
                    ? "Nessuna attività registrata in questo giorno."
                    : "Nessuna attività registrata in questo mese."}
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
                      Dettaglio
                    </p>
                    <h2>{detail.activity_name}</h2>
                  </div>

                  <div className={styles.detailActions}>
                    <span className={styles.gpxBadge}>{detail.source === "gpx" ? "GPX" : "Manuale"}</span>
                    <button
                      type="button"
                      className={styles.deleteButton}
                      disabled={deletingId === detail.id}
                      onClick={() => void removeActivity(detail)}
                    >
                      {deletingId === detail.id ? "Elimino…" : "Elimina"}
                    </button>
                  </div>
                </div>

                <div className={styles.detailStats}>
                  <div>
                    <span>Data</span>
                    <strong>{formatActivityDate(detail.date)}</strong>
                  </div>
                  <div>
                    <span>Distanza</span>
                    <strong>
                      {formatDistance(
                        detail.distance_meters,
                      )}
                    </strong>
                  </div>
                  <div>
                    <span>Durata</span>
                    <strong>
                      {formatDuration(
                        detail.duration_seconds,
                      )}
                    </strong>
                  </div>
                  <div>
                    <span>Calorie</span>
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
                          ? "Il verdetto"
                          : "Commento attività"}
                      </strong>
                    </div>
                  </div>

                  <p>
                    {activityCommentLoading &&
                    !activityComment
                      ? zero
                        ? "Sto cercando qualcosa da dire. Non abituarti."
                        : "Analizzo questa attività…"
                      : activityComment ??
                        (zero
                          ? "Attività registrata. Le prove esistono."
                          : "Attività registrata. La continuità parte anche da qui.")}
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
                    title="Cadenza"
                    unit="spm"
                  />
                  <MetricChart
                    points={normalizedArray<ActivitySeriesPoint>(detail.series_points)}
                    metric="heart_rate"
                    title="Frequenza cardiaca"
                    unit="bpm"
                  />
                </div>
              </>
            ) : (
              <div className={styles.emptyDetail}>
                <strong>
                  Seleziona un’attività
                </strong>
                <span>
                  Qui vedrai percorso e metriche del GPX.
                </span>
              </div>
            )}
          </section>
        </div>
      </main>
    </>
  );
}
