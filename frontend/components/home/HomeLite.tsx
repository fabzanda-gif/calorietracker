"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { AppNav } from "@/components/navigation/AppNav";
import {
  getHomeSummary,
  type HomeSummaryResponse,
} from "@/lib/api/day";

import styles from "./HomeLite.module.css";

const MEAL_ORDER = ["Colazione", "Pranzo", "Snack", "Cena"];

function localIsoDate(date = new Date()): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Buongiorno";
  if (hour < 18) return "Buon pomeriggio";
  return "Buonasera";
}

function mealIcon(label: string): string {
  return {
    Colazione: "☕",
    Pranzo: "🍽️",
    Snack: "🍎",
    Cena: "🌙",
  }[label] ?? "🍴";
}

function activityTitle(item: Record<string, unknown>): string {
  return String(
    item.title ?? item.activity_name ?? item.session_name ?? "Allenamento",
  );
}

function activityMeta(item: Record<string, unknown>): string {
  const pieces: string[] = [];
  const time = item.scheduled_time;
  const distance = Number(item.distance_meters ?? 0);
  const duration = Number(item.duration_minutes ?? 0);

  if (typeof time === "string" && time) pieces.push(time.slice(0, 5));
  if (distance > 0) pieces.push(`${(distance / 1000).toLocaleString("it-IT", { maximumFractionDigits: 1 })} km`);
  if (duration > 0) pieces.push(`${Math.round(duration)} min`);
  return pieces.join(" · ");
}

export function HomeLite() {
  const { accessToken, user } = useAuth();
  const [summary, setSummary] = useState<HomeSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const today = useMemo(() => localIsoDate(), []);

  useEffect(() => {
    if (!accessToken) return;

    let active = true;
    setLoading(true);
    setError(null);

    void getHomeSummary(today, accessToken)
      .then((payload) => {
        if (active) setSummary(payload);
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof Error ? err.message : "Non riesco a caricare la Home.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [accessToken, today]);

  const firstName = useMemo(() => {
    const metadata = user?.user_metadata ?? {};
    const value = metadata.first_name ?? metadata.full_name ?? metadata.name;
    if (typeof value === "string" && value.trim()) {
      return value.trim().split(/\s+/)[0];
    }
    return user?.email?.split("@")[0] ?? "";
  }, [user]);

  const mealsByType = useMemo(() => {
    const result = new Map<string, HomeSummaryResponse["meals"]>();
    for (const label of MEAL_ORDER) result.set(label, []);
    for (const meal of summary?.meals ?? []) {
      const current = result.get(meal.meal_type) ?? [];
      current.push(meal);
      result.set(meal.meal_type, current);
    }
    return result;
  }, [summary]);

  const totalActivityKcal = (summary?.activities ?? []).reduce(
    (total, item) => total + Number(item.burned_calories || 0),
    0,
  );

  const consumed = summary?.budget?.consumed_kcal ?? 0;
  const dailyBudget = summary?.budget?.daily_budget_kcal ?? 0;
  const remaining = summary?.budget?.available_kcal ?? 0;
  const protein = summary?.budget?.protein_consumed_g ?? 0;
  const proteinTarget = summary?.budget?.protein_target_g ?? summary?.profile_goal.protein_target_g ?? null;
  const budgetPercent = dailyBudget > 0 ? Math.min(100, Math.max(0, (consumed / dailyBudget) * 100)) : 0;

  return (
    <>
      <AppNav />
      <main className={styles.page}>
        <header className={styles.header}>
          <div>
            <p className={styles.eyebrow}>ADESSO</p>
            <h1>{greeting()}{firstName ? `, ${firstName}` : ""}</h1>
            <p className={styles.dateLabel}>
              {new Date(`${today}T12:00:00`).toLocaleDateString("it-IT", {
                weekday: "long",
                day: "numeric",
                month: "long",
              })}
            </p>
          </div>
          <Link href="/ai" className={styles.aiTopAction}>✦ SanoSync AI</Link>
        </header>

        {loading ? (
          <section className={styles.loadingCard}>
            <span className={styles.loadingDot} />
            <div>
              <strong>Sto preparando la giornata…</strong>
              <p>Solo le informazioni essenziali.</p>
            </div>
          </section>
        ) : null}

        {error ? (
          <section className={styles.errorCard}>
            <strong>Home non disponibile</strong>
            <p>{error}</p>
          </section>
        ) : null}

        {summary ? (
          <>
            <section className={`${styles.heroCard} ${styles[`hero_${summary.hero.kind}`] ?? ""}`}>
              <div className={styles.heroIcon} aria-hidden="true">{summary.hero.icon}</div>
              <div className={styles.heroCopy}>
                <span>IL TUO CONTESTO</span>
                <h2>{summary.hero.title}</h2>
                <p>{summary.hero.message}</p>
              </div>
              {summary.special_period ? (
                <Link href="/activities" className={styles.heroLink}>
                  {summary.special_period.period_type === "vacation" ? "Vacanza" : "Malattia"} · gestisci
                </Link>
              ) : null}
            </section>

            <section className={styles.budgetCard}>
              <div className={styles.budgetMain}>
                <span className={styles.sectionKicker}>BUDGET DI OGGI</span>
                {summary.budget ? (
                  <>
                    <div className={styles.budgetNumber}>
                      <strong>{Math.round(remaining).toLocaleString("it-IT")}</strong>
                      <span>kcal rimaste</span>
                    </div>
                    <div className={styles.progressTrack} aria-label={`${Math.round(budgetPercent)}% del budget utilizzato`}>
                      <span style={{ width: `${budgetPercent}%` }} />
                    </div>
                    <p>{Math.round(consumed).toLocaleString("it-IT")} / {Math.round(dailyBudget).toLocaleString("it-IT")} kcal consumate</p>
                  </>
                ) : (
                  <p>Completa il profilo per vedere il budget calorico.</p>
                )}
              </div>
              <div className={styles.budgetStats}>
                <div>
                  <span>Proteine</span>
                  <strong>{Math.round(protein)}{proteinTarget ? ` / ${Math.round(proteinTarget)}` : ""} g</strong>
                </div>
                <div>
                  <span>Peso</span>
                  <strong>{summary.latest_weight ? `${Number(summary.latest_weight.weight).toLocaleString("it-IT", { maximumFractionDigits: 1 })} kg` : "—"}</strong>
                </div>
                <div>
                  <span>Attività</span>
                  <strong>{totalActivityKcal > 0 ? `${Math.round(totalActivityKcal)} kcal` : "—"}</strong>
                </div>
              </div>
            </section>

            <div className={styles.mainGrid}>
              <section className={styles.card}>
                <div className={styles.cardHeader}>
                  <div>
                    <span className={styles.sectionKicker}>PASTI</span>
                    <h2>Oggi</h2>
                  </div>
                  <Link href="/ai" className={styles.smallAction}>+ Registra</Link>
                </div>

                <div className={styles.mealList}>
                  {MEAL_ORDER.map((label) => {
                    const items = mealsByType.get(label) ?? [];
                    const kcal = items.reduce((total, item) => total + Number(item.calories || 0), 0);
                    return (
                      <div key={label} className={styles.mealRow}>
                        <span className={styles.mealIcon}>{mealIcon(label)}</span>
                        <div>
                          <strong>{label}</strong>
                          <span>{items.length ? items.map((item) => item.name).join(" · ") : "Nessun pasto registrato"}</span>
                        </div>
                        {items.length ? <strong>{Math.round(kcal)} kcal</strong> : <Link href="/ai">Registra</Link>}
                      </div>
                    );
                  })}
                </div>
              </section>

              <section className={styles.card}>
                <div className={styles.cardHeader}>
                  <div>
                    <span className={styles.sectionKicker}>MOVIMENTO</span>
                    <h2>Allenamento e attività</h2>
                  </div>
                  <Link href="/activities" className={styles.smallAction}>Plan →</Link>
                </div>

                {summary.planned_today.length ? (
                  <div className={styles.trainingCard}>
                    <span className={styles.trainingIcon}>🏃</span>
                    <div>
                      <span>PROSSIMO ALLENAMENTO</span>
                      <strong>{activityTitle(summary.planned_today[0])}</strong>
                      {activityMeta(summary.planned_today[0]) ? <p>{activityMeta(summary.planned_today[0])}</p> : null}
                    </div>
                  </div>
                ) : (
                  <div className={styles.emptyState}>
                    <strong>Nessun allenamento pianificato oggi</strong>
                    <span>Puoi pianificarlo dalla sezione Plan.</span>
                  </div>
                )}

                {summary.activities.length ? (
                  <div className={styles.activityList}>
                    {summary.activities.map((activity, index) => (
                      <div key={String(activity.id ?? index)}>
                        <span>✓</span>
                        <div>
                          <strong>{activity.activity_name}</strong>
                          <small>{Math.round(Number(activity.burned_calories || 0))} kcal</small>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}
              </section>
            </div>

            <section className={styles.aiCard}>
              <div>
                <span className={styles.aiSpark}>✦</span>
                <div>
                  <span className={styles.sectionKicker}>SANOSYNC AI</span>
                  <h2>Logga tutto in una frase</h2>
                  <p>“Ho mangiato una piadina, corso 7 km e stamattina pesavo 81,2 kg.”</p>
                </div>
              </div>
              <Link href="/ai">Scrivi a SanoSync →</Link>
            </section>

            <p className={styles.performanceNote}>
              Home leggera · {summary.meta.history_days_used} giorni usati solo per la baseline attività · {summary.meta.ai_calls} chiamate AI automatiche
            </p>
          </>
        ) : null}
      </main>
    </>
  );
}
