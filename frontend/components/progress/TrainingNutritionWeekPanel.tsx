"use client";

import { useEffect, useState } from "react";
import {
  getTrainingNutritionWeek,
  type TrainingNutritionWeek,
} from "@/lib/api/training-nutrition";
import styles from "./TrainingNutritionWeekPanel.module.css";

type Props = { accessToken: string };

function localWeekStart(): string {
  const now = new Date();
  const weekday = (now.getDay() + 6) % 7;
  now.setDate(now.getDate() - weekday);
  return [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");
}

function trainingLabel(row: TrainingNutritionWeek["days"][number]): string {
  const t = row.training;
  const tags: string[] = [];
  if (t.strength_completed) tags.push(`Palestra completata ×${t.strength_completed}`);
  if (t.running_completed) tags.push(`Corsa completata ×${t.running_completed}`);
  if (t.strength_planned) tags.push(`Palestra prevista ×${t.strength_planned}`);
  if (t.running_planned) tags.push(`Corsa prevista ×${t.running_planned}`);
  return tags.join(" · ") || "Nessun allenamento registrato";
}

function localizedDate(day: string): string {
  return new Date(day + "T12:00:00").toLocaleDateString("it-IT", {
    weekday: "short", day: "numeric", month: "short",
  });
}

export function TrainingNutritionWeekPanel({ accessToken }: Props) {
  const [weekStart, setWeekStart] = useState(localWeekStart);
  const [week, setWeek] = useState<TrainingNutritionWeek | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    getTrainingNutritionWeek(accessToken, weekStart)
      .then((result) => {
        if (mounted) setWeek(result);
      })
      .catch(() => {
        if (mounted) {
          setWeek(null);
          setError("Impossibile caricare il contesto Training e Nutrition.");
        }
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => { mounted = false; };
  }, [accessToken, weekStart]);

  return (
    <section className={styles.panel} aria-labelledby="training-nutrition-title">
      <div className={styles.header}>
        <div>
          <p className={styles.kicker}>Training ↔ Nutrition · Phase 6</p>
          <h2 id="training-nutrition-title">Allenamento e alimentazione</h2>
        </div>
        <label className={styles.picker}>
          Settimana dal
          <input type="date" value={weekStart}
            onChange={(event) => { if (event.target.value) setWeekStart(event.target.value); }} />
        </label>
      </div>
      <p className={styles.description}>
        Confronta le sedute previste e completate con i nutrienti che hai
        registrato. Non vengono cambiati i tuoi obiettivi calorici o macro.
      </p>
      {loading && <p aria-live="polite">Caricamento settimana…</p>}
      {error && <p className={styles.error} role="alert">{error}</p>}
      {week && !loading && (
        <>
          <div className={styles.summary}>
            <span><strong>{week.summary.training_days}</strong> giorni con allenamento</span>
            <span><strong>{week.summary.days_with_meals_and_training}</strong> giorni con alimentazione e allenamento registrati</span>
          </div>
          {!week.summary.protein_goal_configured && (
            <p className={styles.notice}>
              Obiettivo proteico non configurato: visualizzo soltanto le
              quantità registrate, senza inventare un obiettivo.
            </p>
          )}
          <ul className={styles.days}>
            {week.days.map((item) => (
              <li key={item.date} className={styles.day}>
                <div className={styles.dayHeader}>
                  <strong>{localizedDate(item.date)}</strong>
                  <span>{trainingLabel(item)}</span>
                </div>
                {item.meal_count ? (
                  <div className={styles.macros}>
                    <span>{Math.round(item.logged_macros.calories_kcal)} kcal registrate</span>
                    <span><strong>{Math.round(item.logged_macros.protein_g)} g</strong> proteine</span>
                    <span>{Math.round(item.logged_macros.carbs_g)} g carboidrati</span>
                    <span>{Math.round(item.logged_macros.fat_g)} g grassi</span>
                    {item.protein_target_g !== null && (
                      <span>
                        {item.protein_target_status === "met"
                          ? "Obiettivo proteico raggiunto"
                          : `Mancano ${Math.round(item.protein_remaining_g ?? 0)} g rispetto al tuo obiettivo proteico`}
                      </span>
                    )}
                  </div>
                ) : (
                  <p className={styles.empty}>Nessun pasto registrato per questa data.</p>
                )}
              </li>
            ))}
          </ul>
          <p className={styles.disclaimer}>{week.disclaimer}</p>
        </>
      )}
    </section>
  );
}
