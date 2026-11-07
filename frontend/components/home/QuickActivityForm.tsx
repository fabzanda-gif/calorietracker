"use client";

import { useMemo, useState } from "react";

import {
  createActivity,
  importGpxActivity,
  previewGpxActivity,
  updatePlannedActivity,
  type GpxActivityPreview,
} from "@/lib/api/activities";
import { updateDailyLog } from "@/lib/api/day";
import { useI18n } from "@/components/i18n/I18nProvider";

import styles from "./QuickActivityForm.module.css";

type ActivityKind =
  | "steps"
  | "bike"
  | "ebike"
  | "run"
  | "gym"
  | "padel"
  | "other";

interface QuickActivityInitialValue {
  name: string;
  activityType?: string | null;
  calories?: number | null;
  durationMinutes?: number | null;
  distanceKm?: number | null;
  plannedActivityId?: string | null;
}

interface QuickActivityFormProps {
  accessToken: string;
  date: string;
  weightKg?: number | null;
  initialValue?: QuickActivityInitialValue | null;
  onCancel: () => void;
  onSaved: () => Promise<void>;
  onError: (message: string) => void;
}

const OPTIONS: Array<{
  value: ActivityKind;
  label: ActivityKind;
}> = [
  { value: "steps", label: "steps" },
  { value: "bike", label: "bike" },
  { value: "ebike", label: "ebike" },
  { value: "run", label: "run" },
  { value: "padel", label: "padel" },
  { value: "gym", label: "gym" },
  { value: "other", label: "other" },
];


const copy = {
  it: {
    steps: "Passi",
    bike: "Bici",
    ebike: "Bici elettrica",
    run: "Corsa",
    padel: "Padel",
    gym: "Palestra",
    other: "Altro",
    wholeSteps: "Inserisci un numero di passi intero maggiore di zero.",
    bikeMetric: "Inserisci almeno i minuti oppure i chilometri.",
    runDistance: "Inserisci i chilometri percorsi.",
    runPace: "Inserisci il passo medio nel formato mm:ss.",
    padelDuration: "Inserisci la durata della partita.",
    sportNameRequired: "Inserisci il nome dello sport.",
    caloriesRequired: "Inserisci delle kcal valide.",
    saveFailed: "Impossibile registrare l’attività.",
    activityType: "Tipo di attività",
    bikeHint: "minuti o km",
    runHint: "km e passo medio",
    otherHint: "kcal",
    otherSports: "Altri sport",
    stepCount: "Numero di passi *",
    sportName: "Nome dello sport *",
    sportExample: "Es. Tennis",
    duration: "Durata (min)",
    distance: "Distanza (km)",
    averagePace: "Passo medio (min/km) *",
    estimatedCalories: "Kcal stimate",
    calories: "Kcal *",
    stepsHelper: "Calcolate automaticamente dal numero di passi.",
    caloriesHelper: "Calcolate automaticamente quando possibile, puoi modificarle.",
    validData: "✓ Dati validi",
    cancel: "Annulla",
    saving: "Registro…",
    addActivity: "Aggiungi attività",
    uploadFile: "Carica GPX / FIT / TCX",
    uploadHint: "Importa il file registrato dal tuo orologio o app.",
    analyzingFile: "Analizzo il file…",
    fileReady: "File pronto",
    unsupportedFile: "Formato non supportato. Usa GPX, FIT o TCX.",
    fileTooLarge: "Il file attività supera il limite di 10 MB.",
  },
  en: {
    steps: "Steps",
    bike: "Bike",
    ebike: "E-bike",
    run: "Run",
    padel: "Padel",
    gym: "Gym",
    other: "Other",
    wholeSteps: "Enter a whole number of steps greater than zero.",
    bikeMetric: "Enter at least minutes or kilometres.",
    runDistance: "Enter the distance covered in kilometres.",
    runPace: "Enter the average pace in mm:ss format.",
    padelDuration: "Enter the match duration.",
    sportNameRequired: "Enter the sport name.",
    caloriesRequired: "Enter valid kcal.",
    saveFailed: "Unable to log the activity.",
    activityType: "Activity type",
    bikeHint: "minutes or km",
    runHint: "km and average pace",
    otherHint: "kcal",
    otherSports: "Other sports",
    stepCount: "Number of steps *",
    sportName: "Sport name *",
    sportExample: "E.g. Tennis",
    duration: "Duration (min)",
    distance: "Distance (km)",
    averagePace: "Average pace (min/km) *",
    estimatedCalories: "Estimated kcal",
    calories: "Kcal *",
    stepsHelper: "Calculated automatically from the number of steps.",
    caloriesHelper: "Calculated automatically when possible; you can edit them.",
    validData: "✓ Valid data",
    cancel: "Cancel",
    saving: "Saving…",
    addActivity: "Add activity",
    uploadFile: "Upload GPX / FIT / TCX",
    uploadHint: "Import the file recorded by your watch or app.",
    analyzingFile: "Analyzing file…",
    fileReady: "File ready",
    unsupportedFile: "Unsupported format. Use GPX, FIT or TCX.",
    fileTooLarge: "The activity file exceeds the 10 MB limit.",
  },
  nl: {
    steps: "Stappen",
    bike: "Fiets",
    ebike: "Elektrische fiets",
    run: "Hardlopen",
    padel: "Padel",
    gym: "Sportschool",
    other: "Overig",
    wholeSteps: "Voer een geheel aantal stappen groter dan nul in.",
    bikeMetric: "Voer minimaal het aantal minuten of kilometers in.",
    runDistance: "Voer het aantal afgelegde kilometers in.",
    runPace: "Voer het gemiddelde tempo in als mm:ss.",
    padelDuration: "Voer de duur van de wedstrijd in.",
    sportNameRequired: "Voer de naam van de sport in.",
    caloriesRequired: "Voer geldige kcal in.",
    saveFailed: "De activiteit kan niet worden geregistreerd.",
    activityType: "Type activiteit",
    bikeHint: "minuten of km",
    runHint: "km en gemiddeld tempo",
    otherHint: "kcal",
    otherSports: "Andere sporten",
    stepCount: "Aantal stappen *",
    sportName: "Naam van de sport *",
    sportExample: "Bijv. tennis",
    duration: "Duur (min)",
    distance: "Afstand (km)",
    averagePace: "Gemiddeld tempo (min/km) *",
    estimatedCalories: "Geschatte kcal",
    calories: "Kcal *",
    stepsHelper: "Automatisch berekend op basis van het aantal stappen.",
    caloriesHelper: "Waar mogelijk automatisch berekend; je kunt dit aanpassen.",
    validData: "✓ Geldige gegevens",
    cancel: "Annuleren",
    saving: "Opslaan…",
    addActivity: "Activiteit toevoegen",
    uploadFile: "GPX / FIT / TCX uploaden",
    uploadHint: "Importeer het bestand van je horloge of app.",
    analyzingFile: "Bestand analyseren…",
    fileReady: "Bestand gereed",
    unsupportedFile: "Niet ondersteund formaat. Gebruik GPX, FIT of TCX.",
    fileTooLarge: "Het activiteitenbestand is groter dan 10 MB.",
  },
  fr: {
    steps: "Pas", bike: "Vélo", ebike: "Vélo électrique", run: "Course",
    padel: "Padel", gym: "Salle de sport", other: "Autre",
    wholeSteps: "Saisissez un nombre entier de pas supérieur à zéro.",
    bikeMetric: "Saisissez au moins une durée ou une distance.",
    runDistance: "Saisissez la distance parcourue en kilomètres.",
    runPace: "Saisissez l’allure moyenne au format mm:ss.",
    padelDuration: "Saisissez la durée du match.",
    sportNameRequired: "Saisissez le nom du sport.",
    caloriesRequired: "Saisissez un nombre de kcal valide.",
    saveFailed: "Impossible d’enregistrer l’activité.",
    activityType: "Type d’activité", bikeHint: "minutes ou km",
    runHint: "km et allure moyenne", otherHint: "kcal", otherSports: "Autres sports",
    stepCount: "Nombre de pas *", sportName: "Nom du sport *", sportExample: "Ex. Tennis",
    duration: "Durée (min)", distance: "Distance (km)",
    averagePace: "Allure moyenne (min/km) *", estimatedCalories: "Kcal estimées",
    calories: "Kcal *", stepsHelper: "Calculées automatiquement à partir du nombre de pas.",
    caloriesHelper: "Calculées automatiquement lorsque possible ; vous pouvez les modifier.",
    validData: "✓ Données valides", cancel: "Annuler", saving: "Enregistrement…",
    addActivity: "Ajouter l’activité",
    uploadFile: "Importer GPX / FIT / TCX",
    uploadHint: "Importez le fichier enregistré par votre montre ou application.",
    analyzingFile: "Analyse du fichier…",
    fileReady: "Fichier prêt",
    unsupportedFile: "Format non pris en charge. Utilisez GPX, FIT ou TCX.",
    fileTooLarge: "Le fichier d’activité dépasse la limite de 10 Mo.",
  },
} as const;

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const value = String(reader.result ?? "");
      const comma = value.indexOf(",");
      resolve(comma >= 0 ? value.slice(comma + 1) : value);
    };
    reader.onerror = () =>
      reject(new Error("Non riesco a leggere il file attività."));
    reader.readAsDataURL(file);
  });
}

function numberValue(value: string): number {
  const parsed = Number(value.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : 0;
}

function initialKind(
  value?: QuickActivityInitialValue | null,
): ActivityKind {
  const name = (
    value?.activityType ||
    value?.name ||
    ""
  ).trim().toLocaleLowerCase("it-IT");

  if (name.includes("elettric")) return "ebike";
  if (name.includes("bici") || name.includes("cicl")) return "bike";
  if (name.includes("cors") || name.includes("running")) return "run";
  if (name.includes("padel")) return "padel";
  if (name.includes("palestr") || name.includes("forza")) return "gym";
  return value ? "other" : "steps";
}

function paceSeconds(value: string): number {
  const match = value.trim().match(/^(\d{1,2}):([0-5]\d)$/);
  if (!match) {
    return 0;
  }
  return Number(match[1]) * 60 + Number(match[2]);
}

export default function QuickActivityForm({
  accessToken,
  date,
  weightKg,
  initialValue,
  onCancel,
  onSaved,
  onError,
}: QuickActivityFormProps) {
  const { locale } = useI18n();
  const text = copy[locale];
  const startingKind = initialKind(initialValue);
  const [kind, setKind] =
    useState<ActivityKind>(startingKind);
  const [steps, setSteps] = useState("");
  const [minutes, setMinutes] = useState(
    initialValue?.durationMinutes
      ? String(initialValue.durationMinutes)
      : startingKind === "padel"
        ? "90"
        : "",
  );
  const [distanceKm, setDistanceKm] = useState(
    initialValue?.distanceKm
      ? String(initialValue.distanceKm)
      : "",
  );
  const [pace, setPace] = useState("");
  const [calories, setCalories] = useState(
    initialValue?.calories
      ? String(initialValue.calories)
      : "",
  );
  const [caloriesEdited, setCaloriesEdited] =
    useState(Boolean(initialValue?.calories));
  const [otherName, setOtherName] = useState(
    startingKind === "other"
      ? initialValue?.name ?? ""
      : "",
  );
  const [saving, setSaving] = useState(false);
  const [activityFile, setActivityFile] =
    useState<File | null>(null);
  const [activityFileBase64, setActivityFileBase64] =
    useState("");
  const [activityFilePreview, setActivityFilePreview] =
    useState<GpxActivityPreview | null>(null);
  const [previewingFile, setPreviewingFile] =
    useState(false);

  const weight = Math.max(1, Number(weightKg) || 75);

  const estimatedCalories = useMemo(() => {
    const distance = numberValue(distanceKm);
    const duration = numberValue(minutes);

    if (kind === "steps") {
      return Math.max(0, Math.round(numberValue(steps) * 0.04));
    }
    if (kind === "run" && distance > 0) {
      return Math.max(1, Math.round(weight * distance));
    }
    if (kind === "bike" || kind === "ebike") {
      if (duration > 0) {
        const met = kind === "ebike" ? 4 : 6.8;
        return Math.max(
          1,
          Math.round(met * weight * (duration / 60)),
        );
      }
      if (distance > 0) {
        const factor = kind === "ebike" ? 0.18 : 0.32;
        return Math.max(
          1,
          Math.round(weight * distance * factor),
        );
      }
    }
    if (kind === "padel" && duration > 0) {
      return Math.max(
        1,
        Math.round(7 * weight * (duration / 60)),
      );
    }
    return 0;
  }, [distanceKm, kind, minutes, steps, weight]);

  const effectiveCalories = caloriesEdited
    ? numberValue(calories)
    : estimatedCalories;

  const validationMessage = useMemo(() => {
    if (activityFilePreview) {
      return null;
    }

    const stepCount = numberValue(steps);
    const duration = numberValue(minutes);
    const distance = numberValue(distanceKm);

    if (kind === "steps") {
      if (!Number.isInteger(stepCount) || stepCount <= 0) {
        return text.wholeSteps;
      }
      return null;
    }

    if (
      (kind === "bike" || kind === "ebike") &&
      duration <= 0 &&
      distance <= 0
    ) {
      return text.bikeMetric;
    }

    if (kind === "run") {
      if (distance <= 0) {
        return text.runDistance;
      }
      if (paceSeconds(pace) <= 0) {
        return text.runPace;
      }
    }

    if (kind === "padel" && duration <= 0) {
      return text.padelDuration;
    }

    if (kind === "other" && !otherName.trim()) {
      return text.sportNameRequired;
    }

    if (effectiveCalories <= 0) {
      return text.caloriesRequired;
    }

    return null;
  }, [
    distanceKm,
    effectiveCalories,
    kind,
    minutes,
    otherName,
    pace,
    steps,
    text,
    activityFilePreview,
  ]);

  async function chooseActivityFile(file: File | null) {
    setActivityFile(file);
    setActivityFileBase64("");
    setActivityFilePreview(null);
    onError("");

    if (!file) return;

    const extension =
      file.name.toLowerCase().split(".").pop();

    if (!extension || !["gpx", "fit", "tcx"].includes(extension)) {
      onError(text.unsupportedFile);
      setActivityFile(null);
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      onError(text.fileTooLarge);
      setActivityFile(null);
      return;
    }

    setPreviewingFile(true);

    try {
      const contentBase64 = await fileToBase64(file);
      const response = await previewGpxActivity(
        {
          file_name: file.name,
          content_base64: contentBase64,
          activity_type:
            initialValue?.activityType ||
            initialValue?.name ||
            undefined,
        },
        accessToken,
      );

      setActivityFileBase64(contentBase64);
      setActivityFilePreview(response.preview);

      if (response.preview.distance_meters) {
        setDistanceKm(
          String(
            Number(
              (response.preview.distance_meters / 1000).toFixed(2),
            ),
          ),
        );
      }

      if (response.preview.estimated_calories) {
        setCalories(String(Math.round(response.preview.estimated_calories)));
        setCaloriesEdited(true);
      }

      if (
        response.preview.distance_meters &&
        response.preview.duration_seconds
      ) {
        const distance = response.preview.distance_meters / 1000;
        if (distance > 0) {
          const paceSecondsValue =
            response.preview.duration_seconds / distance;
          const paceMinutes = Math.floor(paceSecondsValue / 60);
          const paceSecondsPart = Math.round(paceSecondsValue % 60);
          setPace(
            `${paceMinutes}:${String(paceSecondsPart).padStart(2, "0")}`,
          );
        }
      }
    } catch (error) {
      onError(
        error instanceof Error
          ? error.message
          : "Non riesco ad analizzare il file attività.",
      );
      setActivityFile(null);
      setActivityFileBase64("");
      setActivityFilePreview(null);
    } finally {
      setPreviewingFile(false);
    }
  }

  function selectKind(value: ActivityKind) {
    setKind(value);
    setSteps("");
    setMinutes(value === "padel" ? "90" : "");
    setDistanceKm("");
    setPace("");
    setCalories("");
    setCaloriesEdited(false);
    setOtherName("");
    onError("");
  }

  async function submit() {
    if (validationMessage || saving) {
      return;
    }

    setSaving(true);
    onError("");

    try {
      if (activityFile && activityFileBase64 && activityFilePreview) {
        await importGpxActivity(
          {
            file_name: activityFile.name,
            content_base64: activityFileBase64,
            activity_name:
              initialValue?.name ||
              activityFilePreview.activity_name,
            activity_type:
              initialValue?.activityType ||
              activityFilePreview.activity_type ||
              undefined,
            activity_date:
              activityFilePreview.date || date,
            burned_calories:
              Math.max(
                0,
                Number(
                  activityFilePreview.estimated_calories ??
                  effectiveCalories ??
                  0,
                ),
              ),
            planned_activity_id:
              initialValue?.plannedActivityId || undefined,
          },
          accessToken,
        );

        if (initialValue?.plannedActivityId) {
          await updatePlannedActivity(
            initialValue.plannedActivityId,
            { status: "completed" },
            accessToken,
          );
        }

        await onSaved();
        return;
      }

      if (kind === "steps") {
        await updateDailyLog(
          accessToken,
          date,
          { steps: Math.round(numberValue(steps)) },
        );
      } else {
        const distance = numberValue(distanceKm);
        let duration = numberValue(minutes);

        if (kind === "run") {
          duration =
            distance * paceSeconds(pace) / 60;
        }

        const names: Record<
          Exclude<ActivityKind, "steps" | "other">,
          string
        > = {
          bike: "Bici",
          ebike: "Bici elettrica",
          run: "Corsa",
          gym: "Palestra",
          padel: "Padel",
        };

        const activityName =
          kind === "other"
            ? otherName.trim()
            : names[kind];

        await createActivity(
          {
            date,
            activity_name: activityName,
            activity_type: activityName,
            burned_calories:
              Math.round(effectiveCalories),
            ...(duration > 0
              ? {
                  duration_seconds:
                    Math.round(duration * 60),
                }
              : {}),
            ...(distance > 0
              ? {
                  distance_meters:
                    Math.round(distance * 1000),
                }
              : {}),
            ...(initialValue?.plannedActivityId
              ? {
                  planned_activity_id:
                    initialValue.plannedActivityId,
                }
              : {}),
          },
          accessToken,
        );
      }

      await onSaved();
    } catch (error) {
      onError(
        error instanceof Error
          ? error.message
          : "Non riesco a registrare l’attività.",
      );
    } finally {
      setSaving(false);
    }
  }

  const showMinutes = [
    "bike",
    "ebike",
    "gym",
    "padel",
    "other",
  ].includes(kind);
  const showDistance = [
    "bike",
    "ebike",
    "run",
  ].includes(kind);
  const showCalories = kind !== "steps";

  return (
    <>
      <div className={styles.body}>
        <label className={styles.activityFileUpload}>
          <input
            type="file"
            accept=".gpx,.fit,.tcx,application/gpx+xml,application/xml,application/octet-stream"
            onChange={(event) => {
              const file =
                event.currentTarget.files?.[0] ?? null;
              void chooseActivityFile(file);
              event.currentTarget.value = "";
            }}
          />

          <span className={styles.activityFileUploadIcon}>↑</span>

          <span className={styles.activityFileUploadCopy}>
            <strong>
              {previewingFile
                ? text.analyzingFile
                : activityFilePreview
                  ? text.fileReady
                  : text.uploadFile}
            </strong>
            <small>
              {activityFile
                ? activityFile.name
                : text.uploadHint}
            </small>
          </span>

          <span className={styles.activityFileUploadAction}>
            {activityFilePreview ? "✓" : "Scegli"}
          </span>
        </label>

        <div className={styles.activityFileDivider}>
          <span>oppure inserisci manualmente</span>
        </div>

        <fieldset className={styles.types}>
          <legend>{text.activityType}</legend>
          <div className={styles.typeGrid}>
            {OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                aria-pressed={kind === option.value}
                className={
                  kind === option.value
                    ? styles.typeActive
                    : undefined
                }
                onClick={() => selectKind(option.value)}
              >
                {text[option.label]}
              </button>
            ))}
          </div>
        </fieldset>

        <div className={styles.hints}>
          <span><strong>{text.bike}:</strong> {text.bikeHint}</span>
          <span><strong>{text.run}:</strong> {text.runHint}</span>
          <span><strong>{text.otherSports}:</strong> {text.otherHint}</span>
        </div>

        <div className={styles.fields}>
          {kind === "steps" ? (
            <label>
              <span>{text.stepCount}</span>
              <input
                autoFocus
                type="number"
                min="1"
                step="1"
                inputMode="numeric"
                value={steps}
                placeholder="8.500"
                onChange={(event) =>
                  setSteps(event.target.value)
                }
              />
            </label>
          ) : null}

          {kind === "other" ? (
            <label>
              <span>{text.sportName}</span>
              <input
                autoFocus
                value={otherName}
                placeholder={text.sportExample}
                onChange={(event) =>
                  setOtherName(event.target.value)
                }
              />
            </label>
          ) : null}

          {showMinutes ? (
            <label>
              <span>
                {text.duration}
                {kind === "padel" ? " *" : ""}
              </span>
              <input
                type="number"
                min="0"
                inputMode="numeric"
                value={minutes}
                placeholder={
                  kind === "padel" ? "90" : "45"
                }
                onChange={(event) =>
                  setMinutes(event.target.value)
                }
              />
            </label>
          ) : null}

          {showDistance ? (
            <label>
              <span>
                {text.distance}
                {kind === "run" ? " *" : ""}
              </span>
              <input
                type="text"
                inputMode="decimal"
                value={distanceKm}
                placeholder="5"
                onChange={(event) =>
                  setDistanceKm(event.target.value)
                }
              />
            </label>
          ) : null}

          {kind === "run" ? (
            <label>
              <span>{text.averagePace}</span>
              <input
                type="text"
                inputMode="numeric"
                value={pace}
                placeholder="5:30"
                onChange={(event) =>
                  setPace(event.target.value)
                }
              />
            </label>
          ) : null}

          <label>
            <span>
              {kind === "steps"
                ? text.estimatedCalories
                : text.calories}
            </span>
            <input
              type="number"
              min="0"
              readOnly={kind === "steps"}
              value={
                kind === "steps"
                  ? estimatedCalories || ""
                  : caloriesEdited
                    ? calories
                    : estimatedCalories || ""
              }
              placeholder="350"
              onChange={(event) => {
                setCalories(event.target.value);
                setCaloriesEdited(true);
              }}
            />
          </label>
        </div>

        <p className={styles.helper}>
          {kind === "steps"
            ? text.stepsHelper
            : text.caloriesHelper}
        </p>

        <p
          className={
            validationMessage
              ? styles.validationError
              : styles.validationSuccess
          }
          role="status"
        >
          {validationMessage ?? text.validData}
        </p>
      </div>

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.cancel}
          onClick={onCancel}
        >
          {text.cancel}
        </button>
        <button
          type="button"
          className={styles.save}
          disabled={
            saving ||
            previewingFile ||
            Boolean(validationMessage)
          }
          onClick={() => void submit()}
        >
          {saving
            ? text.saving
            : activityFilePreview
              ? text.uploadFile
              : text.addActivity}
        </button>
      </div>
    </>
  );
}
