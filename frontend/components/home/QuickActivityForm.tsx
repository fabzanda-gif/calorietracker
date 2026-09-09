"use client";

import { useMemo, useState } from "react";

import { createActivity } from "@/lib/api/activities";
import { updateDailyLog } from "@/lib/api/day";

import styles from "./QuickActivityForm.module.css";

type ActivityKind =
  | "steps"
  | "bike"
  | "ebike"
  | "run"
  | "gym"
  | "padel"
  | "other";

interface QuickActivityFormProps {
  accessToken: string;
  date: string;
  weightKg?: number | null;
  onCancel: () => void;
  onSaved: () => Promise<void>;
  onError: (message: string) => void;
}

const OPTIONS: Array<{
  value: ActivityKind;
  label: string;
}> = [
  { value: "steps", label: "Passi" },
  { value: "bike", label: "Bici" },
  { value: "ebike", label: "Bici elettrica" },
  { value: "run", label: "Corsa" },
  { value: "padel", label: "Padel" },
  { value: "gym", label: "Palestra" },
  { value: "other", label: "Altro" },
];

function numberValue(value: string): number {
  const parsed = Number(value.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : 0;
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
  onCancel,
  onSaved,
  onError,
}: QuickActivityFormProps) {
  const [kind, setKind] =
    useState<ActivityKind>("steps");
  const [steps, setSteps] = useState("");
  const [minutes, setMinutes] = useState("");
  const [distanceKm, setDistanceKm] = useState("");
  const [pace, setPace] = useState("");
  const [calories, setCalories] = useState("");
  const [caloriesEdited, setCaloriesEdited] =
    useState(false);
  const [otherName, setOtherName] = useState("");
  const [saving, setSaving] = useState(false);

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
    const stepCount = numberValue(steps);
    const duration = numberValue(minutes);
    const distance = numberValue(distanceKm);

    if (kind === "steps") {
      if (!Number.isInteger(stepCount) || stepCount <= 0) {
        return "Inserisci un numero di passi intero maggiore di zero.";
      }
      return null;
    }

    if (
      (kind === "bike" || kind === "ebike") &&
      duration <= 0 &&
      distance <= 0
    ) {
      return "Inserisci almeno i minuti oppure i chilometri.";
    }

    if (kind === "run") {
      if (distance <= 0) {
        return "Inserisci i chilometri percorsi.";
      }
      if (paceSeconds(pace) <= 0) {
        return "Inserisci il passo medio nel formato mm:ss.";
      }
    }

    if (kind === "padel" && duration <= 0) {
      return "Inserisci la durata della partita.";
    }

    if (kind === "other" && !otherName.trim()) {
      return "Inserisci il nome dello sport.";
    }

    if (effectiveCalories <= 0) {
      return "Inserisci delle kcal valide.";
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
  ]);

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
        <fieldset className={styles.types}>
          <legend>Tipo di attività</legend>
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
                {option.label}
              </button>
            ))}
          </div>
        </fieldset>

        <div className={styles.hints}>
          <span><strong>Bici:</strong> minuti o km</span>
          <span><strong>Corsa:</strong> km e passo medio</span>
          <span><strong>Altri sport:</strong> kcal</span>
        </div>

        <div className={styles.fields}>
          {kind === "steps" ? (
            <label>
              <span>Numero di passi *</span>
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
              <span>Nome dello sport *</span>
              <input
                autoFocus
                value={otherName}
                placeholder="Es. Tennis"
                onChange={(event) =>
                  setOtherName(event.target.value)
                }
              />
            </label>
          ) : null}

          {showMinutes ? (
            <label>
              <span>
                Durata (min)
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
                Distanza (km)
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
              <span>Passo medio (min/km) *</span>
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
                ? "Kcal stimate"
                : "Kcal *"}
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
            ? "Calcolate automaticamente dal numero di passi."
            : "Calcolate automaticamente quando possibile, puoi modificarle."}
        </p>

        <p
          className={
            validationMessage
              ? styles.validationError
              : styles.validationSuccess
          }
          role="status"
        >
          {validationMessage ?? "✓ Dati validi"}
        </p>
      </div>

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.cancel}
          onClick={onCancel}
        >
          Annulla
        </button>
        <button
          type="button"
          className={styles.save}
          disabled={saving || Boolean(validationMessage)}
          onClick={() => void submit()}
        >
          {saving ? "Registro…" : "Aggiungi attività"}
        </button>
      </div>
    </>
  );
}
