"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { AppNav } from "@/components/navigation/AppNav";
import { useAuth } from "@/components/auth/AuthProvider";
import { getNutritionProgress, type NutritionProgressResponse } from "@/lib/api/progress";
import { getWeightHistoryRange, type WeightEntry } from "@/lib/api/weight";

import styles from "./InsightsPage.module.css";

type RangeKey = "7" | "30";

function isoDate(value: Date): string {
  return value.toISOString().slice(0, 10);
}

function rangeBounds(days: number) {
  const end = new Date();
  const start = new Date(end);
  start.setDate(end.getDate() - days + 1);
  return {
    startDate: isoDate(start),
    endDate: isoDate(end),
  };
}

function fmt(value: number, digits = 0): string {
  return value.toLocaleString("it-IT", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

export default function InsightsPage() {
  const { accessToken } = useAuth();
  const [range, setRange] = useState<RangeKey>("30");
  const [nutrition, setNutrition] = useState<NutritionProgressResponse | null>(null);
  const [weights, setWeights] = useState<WeightEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) return;

    const { startDate, endDate } = rangeBounds(Number(range));
    let active = true;

    setLoading(true);
    setError(null);

    Promise.all([
      getNutritionProgress(startDate, endDate, accessToken),
      getWeightHistoryRange(startDate, endDate, accessToken),
    ])
      .then(([nutritionResponse, weightResponse]) => {
        if (!active) return;
        setNutrition(nutritionResponse);
        setWeights(weightResponse.items);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Impossibile caricare gli insight.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [accessToken, range]);

  const stats = useMemo(() => {
    const items = nutrition?.items ?? [];
    const loggedDays = nutrition?.summary.logged_days ?? 0;
    const avgCalories = nutrition?.summary.average_consumed_kcal ?? 0;
    const avgBudget = nutrition?.summary.average_budget_kcal ?? null;
    const daysWithin = nutrition?.summary.days_within_budget ?? 0;
    const daysWithBudget = nutrition?.summary.days_with_budget ?? 0;
    const adherence = daysWithBudget > 0 ? Math.round((daysWithin / daysWithBudget) * 100) : null;

    const proteinTotal = items.reduce((sum, item) => sum + Number(item.protein_g || 0), 0);
    const avgProtein = loggedDays > 0 ? proteinTotal / loggedDays : 0;
    const activityTotal = items.reduce((sum, item) => sum + Number(item.activity_kcal || 0), 0);
    const activeDays = items.filter((item) => Number(item.activity_kcal || 0) > 0).length;
    const avgActivity = activeDays > 0 ? activityTotal / activeDays : 0;
    const totalBalance = items.reduce(
      (sum, item) => sum + (item.difference_kcal == null ? 0 : Number(item.difference_kcal)),
      0,
    );

    const firstWeight = weights[0]?.weight ?? null;
    const latestWeight = weights.at(-1)?.weight ?? null;
    const weightChange = firstWeight != null && latestWeight != null
      ? Number(latestWeight) - Number(firstWeight)
      : null;

    const maxActivity = Math.max(1, ...items.map((item) => Number(item.activity_kcal || 0)));

    return {
      items,
      loggedDays,
      avgCalories,
      avgBudget,
      adherence,
      avgProtein,
      activityTotal,
      activeDays,
      avgActivity,
      totalBalance,
      firstWeight,
      latestWeight,
      weightChange,
      maxActivity,
    };
  }, [nutrition, weights]);

  return (
    <>
      <AppNav />
      <main className={styles.page}>
        <header className={styles.header}>
          <div>
            <span className={styles.eyebrow}>INSIGHTS</span>
            <h1>Come sta andando</h1>
            <p>
              Trend essenziali di peso, alimentazione e attività. Nessun calcolo storico viene eseguito dalla Home.
            </p>
          </div>

          <div className={styles.rangeSwitch} aria-label="Periodo insight">
            <button
              type="button"
              className={range === "7" ? styles.activeRange : undefined}
              onClick={() => setRange("7")}
            >
              7 giorni
            </button>
            <button
              type="button"
              className={range === "30" ? styles.activeRange : undefined}
              onClick={() => setRange("30")}
            >
              30 giorni
            </button>
          </div>
        </header>

        {loading ? <div className={styles.loading}>Caricamento insight…</div> : null}
        {error ? <div className={styles.error}>{error}</div> : null}

        {!loading && !error ? (
          <>
            <section className={styles.summaryGrid}>
              <article className={styles.metricCard}>
                <span className={styles.metricLabel}>Peso</span>
                <strong className={styles.metricValue}>
                  {stats.latestWeight == null ? "—" : `${fmt(Number(stats.latestWeight), 1)} kg`}
                </strong>
                <span className={styles.metricHint}>
                  {stats.weightChange == null
                    ? "Servono almeno 2 misurazioni"
                    : `${stats.weightChange > 0 ? "+" : ""}${fmt(stats.weightChange, 1)} kg nel periodo`}
                </span>
              </article>

              <article className={styles.metricCard}>
                <span className={styles.metricLabel}>Calorie medie</span>
                <strong className={styles.metricValue}>{fmt(stats.avgCalories)} kcal</strong>
                <span className={styles.metricHint}>
                  {stats.avgBudget == null ? "Budget non disponibile" : `Budget medio ${fmt(stats.avgBudget)} kcal`}
                </span>
              </article>

              <article className={styles.metricCard}>
                <span className={styles.metricLabel}>Proteine</span>
                <strong className={styles.metricValue}>{fmt(stats.avgProtein)} g</strong>
                <span className={styles.metricHint}>Media nei giorni registrati</span>
              </article>

              <article className={styles.metricCard}>
                <span className={styles.metricLabel}>Entro budget</span>
                <strong className={styles.metricValue}>
                  {stats.adherence == null ? "—" : `${stats.adherence}%`}
                </strong>
                <span className={styles.metricHint}>{stats.loggedDays} giorni registrati</span>
              </article>
            </section>

            <section className={styles.contentGrid}>
              <article className={styles.panel}>
                <div className={styles.panelHeader}>
                  <h2>Peso e direzione</h2>
                  <span>{range} giorni</span>
                </div>

                {weights.length === 0 ? (
                  <div className={styles.empty}>Nessuna misurazione nel periodo.</div>
                ) : (
                  <div className={styles.weightTrend}>
                    <div className={styles.trendStat}>
                      <strong>{stats.firstWeight == null ? "—" : `${fmt(Number(stats.firstWeight), 1)} kg`}</strong>
                      <span>inizio periodo</span>
                    </div>
                    <div className={styles.trendStat}>
                      <strong>{stats.latestWeight == null ? "—" : `${fmt(Number(stats.latestWeight), 1)} kg`}</strong>
                      <span>ultima misura</span>
                    </div>
                    <div className={styles.trendStat}>
                      <strong>
                        {stats.weightChange == null ? "—" : `${stats.weightChange > 0 ? "+" : ""}${fmt(stats.weightChange, 1)} kg`}
                      </strong>
                      <span>variazione</span>
                    </div>
                  </div>
                )}
              </article>

              <article className={styles.panel}>
                <div className={styles.panelHeader}>
                  <h2>Attività</h2>
                  <span>{stats.activeDays} giorni attivi</span>
                </div>
                <div className={styles.trendStat}>
                  <strong>{fmt(stats.activityTotal)} kcal</strong>
                  <span>attività registrata nel periodo</span>
                </div>
                <div className={styles.trendStat} style={{ marginTop: 12 }}>
                  <strong>{fmt(stats.avgActivity)} kcal</strong>
                  <span>media per giorno attivo</span>
                </div>
              </article>

              <article className={styles.panel}>
                <div className={styles.panelHeader}>
                  <h2>Attività giorno per giorno</h2>
                  <span>solo dati registrati</span>
                </div>
                <div className={styles.activityBars}>
                  {stats.items.slice(-10).map((item) => (
                    <div className={styles.barRow} key={item.date}>
                      <span>{item.date.slice(5)}</span>
                      <div className={styles.barTrack}>
                        <div
                          className={styles.barFill}
                          style={{ width: `${Math.max(2, (Number(item.activity_kcal || 0) / stats.maxActivity) * 100)}%` }}
                        />
                      </div>
                      <strong>{fmt(Number(item.activity_kcal || 0))}</strong>
                    </div>
                  ))}
                </div>
              </article>

              <article className={styles.panel}>
                <div className={styles.panelHeader}>
                  <h2>Lettura rapida</h2>
                  <span>deterministica</span>
                </div>
                <div className={styles.insightList}>
                  <div className={styles.insightItem}>
                    <strong>Bilancio calorico</strong>
                    <span>
                      {stats.totalBalance === 0
                        ? "Non ci sono abbastanza confronti tra budget e calorie per il periodo."
                        : `Somma degli scostamenti registrati: ${stats.totalBalance > 0 ? "+" : ""}${fmt(stats.totalBalance)} kcal.`}
                    </span>
                  </div>
                  <div className={styles.insightItem}>
                    <strong>Consistenza</strong>
                    <span>
                      {stats.adherence == null
                        ? "Serve più storico con budget disponibile."
                        : `Sei rimasto entro il budget nel ${stats.adherence}% dei giorni confrontabili.`}
                    </span>
                  </div>
                  <div className={styles.insightItem}>
                    <strong>Movimento</strong>
                    <span>
                      {stats.activeDays === 0
                        ? "Nessuna attività registrata nel periodo."
                        : `${stats.activeDays} giorni con attività e ${fmt(stats.activityTotal)} kcal registrate complessivamente.`}
                    </span>
                  </div>
                </div>
              </article>
            </section>

            <section className={styles.ctaCard}>
              <div>
                <h3>Vuoi il dettaglio completo?</h3>
                <p>Grafici avanzati, macro, distribuzione pasti e storico completo restano disponibili nella vista analitica.</p>
              </div>
              <Link href="/progress">Apri analisi completa</Link>
            </section>
          </>
        ) : null}
      </main>
    </>
  );
}
