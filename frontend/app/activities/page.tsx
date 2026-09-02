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
  importGpxActivity,
  previewGpxActivity,
  type Activity,
  type ActivityRoutePoint,
  type ActivitySeriesPoint,
  type GpxActivityPreview,
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
    "bici",
    "bicicletta",
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
  const [importMessage, setImportMessage] =
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
      const response = await getActivitiesForRange(
        bounds.start,
        bounds.end,
        accessToken,
      );

      setActivities(response.items);

      setSelectedActivity((current) => {
        const visibleItems = response.items.filter(
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
        },
        accessToken,
      );

      setGpxBase64(contentBase64);
      setGpxPreview(response.preview);
      setGpxName(response.preview.activity_name);
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

  return (
    <>
      <AppNav experienceMode={experienceMode} />

      <main
        className={`${styles.page} ${
          zero ? styles.pageZero : ""
        }`}
      >
        <header className={styles.header}>
          <div>
            <p className={styles.eyebrow}>
              Movimento
            </p>
            <h1>Attività</h1>
            <p>
              Gli allenamenti che aggiungono qualcosa
              al movimento naturale della tua giornata.
            </p>
          </div>

          <div className={styles.monthTotal}>
            <strong>{trainingActivities.length}</strong>
            <span>
              {trainingActivities.length === 1
                ? "allenamento nel mese"
                : "allenamenti nel mese"}
            </span>
          </div>
        </header>

        {error ? (
          <div className={styles.error}>{error}</div>
        ) : null}

        {importMessage ? (
          <div className={styles.success}>
            {importMessage}
          </div>
        ) : null}

        <section className={styles.loggerCard}>
          <div className={styles.loggerHeading}>
            <div>
              <p className={styles.eyebrow}>
                Registra
              </p>
              <h2>Attività e movimento</h2>
              <p>
                Aggiungi un allenamento oppure aggiorna
                i passi totali rilevati nella giornata.
              </p>
            </div>
          </div>

          <ActivityLogger
            date={
              selectedDate ||
              isoDate(new Date())
            }
            accessToken={accessToken}
            showMovement
            onSaved={loadMonth}
          />
        </section>

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
              points={gpxPreview.route_points ?? []}
              activityName={gpxPreview.activity_name}
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
                <h2>Allenamenti registrati</h2>
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
                        {activity.activity_type ??
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
                    : "Nessun allenamento registrato in questo mese."}
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

                  <span className={styles.gpxBadge}>
                    {detail.source === "gpx"
                      ? "GPX"
                      : "Manuale"}
                  </span>
                </div>

                <div className={styles.detailStats}>
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

                <ActivityMap
                  points={detail.route_points ?? []}
                  activityName={detail.activity_name}
                />

                <div className={styles.charts}>
                  <MetricChart
                    points={detail.series_points ?? []}
                    metric="cadence"
                    title="Cadenza"
                    unit="spm"
                  />
                  <MetricChart
                    points={detail.series_points ?? []}
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
