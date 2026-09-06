"use client";

import { useState } from "react";

import styles from "./DayPlanner.module.css";

export type DayType =
  | "office"
  | "home"
  | "free";

export type ActivityLevel =
  | "low"
  | "moderate"
  | "high";

type Props = {
  message: string;
  dayType: DayType;
  activityLevel: ActivityLevel;
  onDayTypeChange: (value: DayType) => void;
  onActivityLevelChange: (
    value: ActivityLevel,
  ) => void;
};

const dayOptions: Array<{
  value: DayType;
  label: string;
}> = [
  {
    value: "office",
    label: "Ufficio",
  },
  {
    value: "home",
    label: "Lavoro da casa",
  },
  {
    value: "free",
    label: "Giornata libera",
  },
];

const activityOptions: Array<{
  value: ActivityLevel;
  label: string;
}> = [
  {
    value: "low",
    label: "Poco attiva",
  },
  {
    value: "moderate",
    label: "Moderatamente attiva",
  },
  {
    value: "high",
    label: "Molto attiva",
  },
];

function dayLabel(value: DayType): string {
  return {
    office: "giornata in ufficio",
    home: "giornata di lavoro da casa",
    free: "giornata libera",
  }[value];
}

function activityLabel(
  value: ActivityLevel,
): string {
  return {
    low: "poco attiva",
    moderate: "moderatamente attiva",
    high: "molto attiva",
  }[value];
}

export function DayPlanner({
  message,
  dayType,
  activityLevel,
  onDayTypeChange,
  onActivityLevelChange,
}: Props) {
  const [editing, setEditing] =
    useState(false);

  return (
    <section className={styles.card}>
      <div className={styles.summary}>
        <div className={styles.summaryText}>
          <p className={styles.kicker}>
            Il tuo programma di oggi
          </p>

          <p className={styles.message}>
            {message}
          </p>

          <p className={styles.description}>
            Una proposta basata sul tuo programma
            e sulle tue abitudini.
          </p>
        </div>

        <button
          type="button"
          className={styles.editButton}
          onClick={() =>
            setEditing((value) => !value)
          }
          aria-expanded={editing}
        >
          {editing ? "Chiudi" : "Modifica"}
        </button>
      </div>

      {editing ? (
        <div className={styles.editor}>
          <div className={styles.group}>
            <span className={styles.label}>
              Giornata
            </span>

            <div className={styles.options}>
              {dayOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={
                    dayType === option.value
                      ? styles.optionActive
                      : styles.option
                  }
                  onClick={() =>
                    onDayTypeChange(
                      option.value,
                    )
                  }
                  aria-pressed={
                    dayType === option.value
                  }
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.group}>
            <span className={styles.label}>
              Attività prevista
            </span>

            <div className={styles.options}>
              {activityOptions.map(
                (option) => (
                  <button
                    key={option.value}
                    type="button"
                    className={
                      activityLevel ===
                      option.value
                        ? styles.optionActive
                        : styles.option
                    }
                    onClick={() =>
                      onActivityLevelChange(
                        option.value,
                      )
                    }
                    aria-pressed={
                      activityLevel ===
                      option.value
                    }
                  >
                    {option.label}
                  </button>
                ),
              )}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
