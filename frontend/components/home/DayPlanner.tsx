"use client";

import { useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";

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
  plannedActivitySummary?: string | null;
};

const dayOptions: Array<{
  value: DayType;
  label: "office" | "home" | "free";
}> = [
  {
    value: "office",
    label: "office",
  },
  {
    value: "home",
    label: "home",
  },
  {
    value: "free",
    label: "free",
  },
];

const activityOptions: Array<{
  value: ActivityLevel;
  label: "low" | "moderate" | "high";
}> = [
  {
    value: "low",
    label: "low",
  },
  {
    value: "moderate",
    label: "moderate",
  },
  {
    value: "high",
    label: "high",
  },
];


const copy = {
  it: {
    office: "Ufficio",
    home: "Lavoro da casa",
    free: "Giornata libera",
    low: "Poco attiva",
    moderate: "Moderatamente attiva",
    high: "Molto attiva",
    program: "Il tuo programma di oggi",
    description:
      "Una proposta basata sul tuo programma e sulle tue abitudini.",
    close: "Chiudi",
    edit: "Modifica",
    day: "Giornata",
    planned: "Attività calcolata dal programma",
    expectedActivity: "Attività prevista",
  },
  en: {
    office: "Office",
    home: "Working from home",
    free: "Day off",
    low: "Lightly active",
    moderate: "Moderately active",
    high: "Very active",
    program: "Your plan for today",
    description:
      "A suggestion based on your schedule and habits.",
    close: "Close",
    edit: "Edit",
    day: "Day",
    planned: "Activity calculated from your training plan",
    expectedActivity: "Expected activity",
  },
  nl: {
    office: "Kantoor",
    home: "Thuiswerken",
    free: "Vrije dag",
    low: "Licht actief",
    moderate: "Redelijk actief",
    high: "Zeer actief",
    program: "Jouw programma voor vandaag",
    description:
      "Een voorstel op basis van je planning en gewoonten.",
    close: "Sluiten",
    edit: "Wijzigen",
    day: "Dag",
    planned: "Activiteit berekend op basis van je trainingsplan",
    expectedActivity: "Verwachte activiteit",
  },
  fr: {
    office: "Bureau", home: "Télétravail", free: "Jour de repos",
    low: "Peu actif", moderate: "Modérément actif", high: "Très actif",
    program: "Votre programme du jour",
    description: "Une proposition basée sur votre programme et vos habitudes.",
    close: "Fermer", edit: "Modifier", day: "Journée",
    planned: "Activité calculée à partir de votre programme",
    expectedActivity: "Activité prévue",
  },
} as const;

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
  plannedActivitySummary = null,
}: Props) {
  const { locale } = useI18n();
  const text = copy[locale];
  const [editing, setEditing] =
    useState(false);

  return (
    <section className={styles.card}>
      <div className={styles.summary}>
        <div className={styles.summaryText}>
          <p className={styles.kicker}>
            {text.program}
          </p>

          <p className={styles.message}>
            {message}
          </p>

          <p className={styles.description}>
            {text.description}
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
          {editing ? text.close : text.edit}
        </button>
      </div>

      {editing ? (
        <div className={styles.editor}>
          <div className={styles.group}>
            <span className={styles.label}>
              {text.day}
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
                  {text[option.label]}
                </button>
              ))}
            </div>
          </div>

          {plannedActivitySummary ? (
            <div className={styles.plannedActivityNotice}>
              <strong>{text.planned}</strong>
              <span>{plannedActivitySummary}</span>
            </div>
          ) : (
          <div className={styles.group}>
            <span className={styles.label}>
              {text.expectedActivity}
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
                    {text[option.label]}
                  </button>
                ),
              )}
            </div>
          </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
