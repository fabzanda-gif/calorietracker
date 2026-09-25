"use client";

import Link from "next/link";
import { useI18n } from "@/components/i18n/I18nProvider";
import styles from "./TrainingProgramLinks.module.css";

const labels = {
  it: {
    eyebrow: "PROGRAMMI", title: "Il tuo allenamento",
    intro: "Apri un programma per vedere progressi e tutte le settimane.",
    runKind: "CORSA", strengthKind: "FORZA",
    running: "Piano di corsa", runningIntro: "Progressi, obiettivo e sessioni del percorso.",
    strength: "Programma forza", strengthIntro: "Sedute, esercizi e progressione dei carichi.",
    open: "Apri il programma",
  },
  en: {
    eyebrow: "PROGRAMS", title: "Your training",
    intro: "Open a program to see progress and every week.",
    runKind: "RUNNING", strengthKind: "STRENGTH",
    running: "Running plan", runningIntro: "Progress, goal and sessions along the way.",
    strength: "Strength program", strengthIntro: "Workouts, exercises and load progression.",
    open: "Open program",
  },
  nl: {
    eyebrow: "PROGRAMMA'S", title: "Jouw training",
    intro: "Open een programma voor je voortgang en alle weken.",
    runKind: "HARDLOPEN", strengthKind: "KRACHT",
    running: "Hardloopschema", runningIntro: "Voortgang, doel en sessies.",
    strength: "Krachtprogramma", strengthIntro: "Trainingen, oefeningen en belasting.",
    open: "Open programma",
  },
  fr: {
    eyebrow: "PROGRAMMES", title: "Votre entraînement",
    intro: "Ouvrez un programme pour voir vos progrès et toutes les semaines.",
    runKind: "COURSE", strengthKind: "FORCE",
    running: "Programme de course", runningIntro: "Progrès, objectif et séances.",
    strength: "Programme de musculation", strengthIntro: "Séances, exercices et progression des charges.",
    open: "Ouvrir le programme",
  },
} as const;

export function TrainingProgramLinks() {
  const { locale } = useI18n();
  const copy = labels[locale];
  return (
    <section className={styles.section} aria-labelledby="training-title">
      <div className={styles.heading}>
        <p>{copy.eyebrow}</p>
        <h2 id="training-title">{copy.title}</h2>
        <span>{copy.intro}</span>
      </div>
      <div className={styles.links}>
        <Link href="/training/running" className={styles.card}>
          <span className={styles.kind}>{copy.runKind}</span>
          <strong>{copy.running}</strong>
          <span>{copy.runningIntro}</span>
          <b>{copy.open} →</b>
        </Link>
        <Link href="/training/strength" className={styles.card}>
          <span className={styles.kind}>{copy.strengthKind}</span>
          <strong>{copy.strength}</strong>
          <span>{copy.strengthIntro}</span>
          <b>{copy.open} →</b>
        </Link>
      </div>
    </section>
  );
}
