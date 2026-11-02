"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { AppNav } from "@/components/navigation/AppNav";
import { useI18n, type AppLocale } from "@/components/i18n/I18nProvider";
import {
  getHomeSummary,
  type HomeSummaryResponse,
} from "@/lib/api/day";

import styles from "./HomeLite.module.css";

const MEAL_ORDER = ["Colazione", "Pranzo", "Snack", "Cena"];

const HOME_COPY: Record<AppLocale, {
  now: string;
  welcomeBack: string;
  firstMealTitle: string;
  firstMealBody: string;
  firstMealAction: string;
  firstMealHint: string;
  returningDoneHint: string;
  preparing: string;
  essentials: string;
  unavailable: string;
  todayBudget: string;
  kcalRemaining: string;
  consumed: string;
  protein: string;
  weight: string;
  activity: string;
  meals: string;
  today: string;
  add: string;
  noMeal: string;
  log: string;
  movement: string;
  trainingActivity: string;
  plan: string;
  nextTraining: string;
  noTraining: string;
  planHint: string;
  aiTitle: string;
  aiBody: string;
  aiAction: string;
  context: string;
  vacation: string;
  illness: string;
  manage: string;
  breakfast: string;
  lunch: string;
  snack: string;
  dinner: string;
  localeTag: string;
}> = {
  it: {
    now: "ADESSO", welcomeBack: "Bentornato", firstMealTitle: "Cominciamo dal primo pasto",
    firstMealBody: "{copy.firstMealBody}",
    firstMealAction: "{copy.firstMealAction}", firstMealHint: "{copy.firstMealHint}",
    returningDoneHint: "{copy.returningDoneHint}",
    preparing: "Sto preparando la giornata…", essentials: "Solo le informazioni essenziali.",
    unavailable: "Home non disponibile", todayBudget: "BUDGET DI OGGI", kcalRemaining: "kcal rimaste",
    consumed: "kcal consumate", protein: "Proteine", weight: "Peso", activity: "Attività",
    meals: "PASTI", today: "Oggi", add: "+ Registra", noMeal: copy.noMeal, log: "Registra",
    movement: "MOVIMENTO", trainingActivity: "Allenamento e attività", plan: "Plan →",
    nextTraining: "PROSSIMO ALLENAMENTO", noTraining: "Nessun allenamento pianificato oggi",
    planHint: "Puoi pianificarlo dalla sezione Plan.", aiTitle: "Logga tutto in una frase",
    aiBody: "“Ho mangiato una piadina, corso 7 km e stamattina pesavo 81,2 kg.”",
    aiAction: "Scrivi a SanoSync →", context: "IL TUO CONTESTO", vacation: "Vacanza",
    illness: "Malattia", manage: "gestisci", breakfast: "Colazione", lunch: "Pranzo",
    snack: "Snack", dinner: "Cena", localeTag: "it-IT",
  },
  en: {
    now: "NOW", welcomeBack: "Welcome back", firstMealTitle: "Let’s start with your first meal",
    firstMealBody: "Log what you eat and SanoSync will get your day moving again right away.",
    firstMealAction: "+ Log your first meal", firstMealHint: "Write it just as you would say it to someone.",
    returningDoneHint: "After your first log, your full Home returns automatically.",
    preparing: "Preparing your day…", essentials: "Only the essentials.",
    unavailable: "Home unavailable", todayBudget: "TODAY’S BUDGET", kcalRemaining: "kcal remaining",
    consumed: "kcal consumed", protein: "Protein", weight: "Weight", activity: "Activity",
    meals: "MEALS", today: "Today", add: "+ Log", noMeal: "No meal logged", log: "Log",
    movement: "MOVEMENT", trainingActivity: "Training and activity", plan: "Plan →",
    nextTraining: "NEXT WORKOUT", noTraining: "No workout planned for today",
    planHint: "You can plan one from Plan.", aiTitle: "Log everything in one sentence",
    aiBody: "“I had a wrap, ran 7 km and weighed 81.2 kg this morning.”",
    aiAction: "Write to SanoSync →", context: "YOUR CONTEXT", vacation: "Vacation",
    illness: "Illness", manage: "manage", breakfast: "Breakfast", lunch: "Lunch",
    snack: "Snack", dinner: "Dinner", localeTag: "en-GB",
  },
  nl: {
    now: "NU", welcomeBack: "Welkom terug", firstMealTitle: "Laten we beginnen met je eerste maaltijd",
    firstMealBody: "Registreer wat je eet en SanoSync brengt je dag meteen weer op gang.",
    firstMealAction: "+ Registreer je eerste maaltijd", firstMealHint: "Schrijf het zoals je het tegen iemand zou zeggen.",
    returningDoneHint: "Na je eerste registratie verschijnt je volledige Home automatisch weer.",
    preparing: "Je dag wordt voorbereid…", essentials: "Alleen de belangrijkste informatie.",
    unavailable: "Home niet beschikbaar", todayBudget: "BUDGET VAN VANDAAG", kcalRemaining: "kcal over",
    consumed: "kcal gegeten", protein: "Eiwit", weight: "Gewicht", activity: "Activiteit",
    meals: "MAALTIJDEN", today: "Vandaag", add: "+ Registreren", noMeal: "Geen maaltijd geregistreerd", log: "Registreren",
    movement: "BEWEGING", trainingActivity: "Training en activiteit", plan: "Plan →",
    nextTraining: "VOLGENDE TRAINING", noTraining: "Geen training gepland vandaag",
    planHint: "Je kunt er een plannen via Plan.", aiTitle: "Registreer alles in één zin",
    aiBody: "“Ik at een wrap, liep 7 km en woog vanochtend 81,2 kg.”",
    aiAction: "Schrijf naar SanoSync →", context: "JOUW CONTEXT", vacation: "Vakantie",
    illness: "Ziekte", manage: "beheren", breakfast: "Ontbijt", lunch: "Lunch",
    snack: "Snack", dinner: "Avondeten", localeTag: "nl-NL",
  },
  fr: {
    now: "MAINTENANT", welcomeBack: "Bon retour", firstMealTitle: "Commençons par votre premier repas",
    firstMealBody: "Enregistrez ce que vous mangez et SanoSync relancera immédiatement votre journée.",
    firstMealAction: "+ Enregistrer le premier repas", firstMealHint: "Écrivez-le comme vous le diriez à quelqu’un.",
    returningDoneHint: "Après votre première saisie, l’accueil complet revient automatiquement.",
    preparing: "Préparation de votre journée…", essentials: "Seulement l’essentiel.",
    unavailable: "Accueil indisponible", todayBudget: "BUDGET DU JOUR", kcalRemaining: "kcal restantes",
    consumed: "kcal consommées", protein: "Protéines", weight: "Poids", activity: "Activité",
    meals: "REPAS", today: "Aujourd’hui", add: "+ Enregistrer", noMeal: "Aucun repas enregistré", log: "Enregistrer",
    movement: "MOUVEMENT", trainingActivity: "Entraînement et activité", plan: "Plan →",
    nextTraining: "PROCHAIN ENTRAÎNEMENT", noTraining: "Aucun entraînement prévu aujourd’hui",
    planHint: "Vous pouvez en planifier un depuis Plan.", aiTitle: "Tout enregistrer en une phrase",
    aiBody: "« J’ai mangé un wrap, couru 7 km et je pesais 81,2 kg ce matin. »",
    aiAction: "Écrire à SanoSync →", context: "VOTRE CONTEXTE", vacation: "Vacances",
    illness: "Maladie", manage: "gérer", breakfast: "Petit-déjeuner", lunch: "Déjeuner",
    snack: "Collation", dinner: "Dîner", localeTag: "fr-FR",
  },
};


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
  const { locale } = useI18n();
  const copy = HOME_COPY[locale];
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

  const returning = summary?.engagement.state === "returning";

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
            <p className={styles.eyebrow}>{copy.now}</p>
            <h1>{returning ? copy.welcomeBack : greeting()}{firstName ? `, ${firstName}` : ""}</h1>
            <p className={styles.dateLabel}>
              {new Date(`${today}T12:00:00`).toLocaleDateString(copy.localeTag, {
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
              <strong>{copy.preparing}</strong>
              <p>{copy.essentials}</p>
            </div>
          </section>
        ) : null}

        {error ? (
          <section className={styles.errorCard}>
            <strong>{copy.unavailable}</strong>
            <p>{error}</p>
          </section>
        ) : null}

        {summary ? (
          returning ? (
            <section className={styles.returningShell}>
              <div className={styles.returningCard}>
                <span className={styles.returningIcon} aria-hidden="true">✦</span>
                <div className={styles.returningCopy}>
                  <span className={styles.returningEyebrow}>{copy.welcomeBack.toUpperCase()}</span>
                  <h2>{copy.firstMealTitle}</h2>
                  <p>
                    Registra quello che mangi e SanoSync rimetterà subito in moto la tua giornata.
                  </p>
                  <Link href="/ai" className={styles.returningAction}>
                    + Registra il primo pasto
                  </Link>
                  <small>Puoi scriverlo come lo diresti a una persona.</small>
                </div>
              </div>
              <div className={styles.returningHint}>
                <span>✓</span>
                <p>Dopo la prima registrazione ritrovi automaticamente la Home completa.</p>
              </div>
            </section>
          ) : (
          <>
            <section className={`${styles.heroCard} ${styles[`hero_${summary.hero.kind}`] ?? ""}`}>
              <div className={styles.heroIcon} aria-hidden="true">{summary.hero.icon}</div>
              <div className={styles.heroCopy}>
                <span>{copy.context}</span>
                <h2>{summary.hero.title}</h2>
                <p>{summary.hero.message}</p>
              </div>
              {summary.special_period ? (
                <Link href="/activities" className={styles.heroLink}>
                  {summary.special_period.period_type === "vacation" ? copy.vacation : copy.illness} · {copy.manage}
                </Link>
              ) : null}
            </section>

            <section className={styles.budgetCard}>
              <div className={styles.budgetMain}>
                <span className={styles.sectionKicker}>{copy.todayBudget}</span>
                {summary.budget ? (
                  <>
                    <div className={styles.budgetNumber}>
                      <strong>{Math.round(remaining).toLocaleString("it-IT")}</strong>
                      <span>{copy.kcalRemaining}</span>
                    </div>
                    <div className={styles.progressTrack} aria-label={`${Math.round(budgetPercent)}% del budget utilizzato`}>
                      <span style={{ width: `${budgetPercent}%` }} />
                    </div>
                    <p>{Math.round(consumed).toLocaleString("it-IT")} / {Math.round(dailyBudget).toLocaleString("it-IT")} {copy.consumed}</p>
                  </>
                ) : (
                  <p>Completa il profilo per vedere il budget calorico.</p>
                )}
              </div>
              <div className={styles.budgetStats}>
                <div>
                  <span>{copy.protein}</span>
                  <strong>{Math.round(protein)}{proteinTarget ? ` / ${Math.round(proteinTarget)}` : ""} g</strong>
                </div>
                <div>
                  <span>{copy.weight}</span>
                  <strong>{summary.latest_weight ? `${Number(summary.latest_weight.weight).toLocaleString("it-IT", { maximumFractionDigits: 1 })} kg` : "—"}</strong>
                </div>
                <div>
                  <span>{copy.activity}</span>
                  <strong>{totalActivityKcal > 0 ? `${Math.round(totalActivityKcal)} kcal` : "—"}</strong>
                </div>
              </div>
            </section>

            <div className={styles.mainGrid}>
              <section className={styles.card}>
                <div className={styles.cardHeader}>
                  <div>
                    <span className={styles.sectionKicker}>{copy.meals}</span>
                    <h2>{copy.today}</h2>
                  </div>
                  <Link href="/ai" className={styles.smallAction}>{copy.add}</Link>
                </div>

                <div className={styles.mealList}>
                  {MEAL_ORDER.map((label) => {
                    const items = mealsByType.get(label) ?? [];
                    const kcal = items.reduce((total, item) => total + Number(item.calories || 0), 0);
                    return (
                      <div key={label} className={styles.mealRow}>
                        <span className={styles.mealIcon}>{mealIcon(label)}</span>
                        <div>
                          <strong>{
                            label === "Colazione" ? copy.breakfast :
                            label === "Pranzo" ? copy.lunch :
                            label === "Snack" ? copy.snack :
                            copy.dinner
                          }</strong>
                          <span>{items.length ? items.map((item) => item.name).join(" · ") : "Nessun pasto registrato"}</span>
                        </div>
                        {items.length ? <strong>{Math.round(kcal)} kcal</strong> : <Link href="/ai">{copy.log}</Link>}
                      </div>
                    );
                  })}
                </div>
              </section>

              <section className={styles.card}>
                <div className={styles.cardHeader}>
                  <div>
                    <span className={styles.sectionKicker}>{copy.movement}</span>
                    <h2>{copy.trainingActivity}</h2>
                  </div>
                  <Link href="/activities" className={styles.smallAction}>{copy.plan}</Link>
                </div>

                {summary.planned_today.length ? (
                  <div className={styles.trainingCard}>
                    <span className={styles.trainingIcon}>🏃</span>
                    <div>
                      <span>{copy.nextTraining}</span>
                      <strong>{activityTitle(summary.planned_today[0])}</strong>
                      {activityMeta(summary.planned_today[0]) ? <p>{activityMeta(summary.planned_today[0])}</p> : null}
                    </div>
                  </div>
                ) : (
                  <div className={styles.emptyState}>
                    <strong>{copy.noTraining}</strong>
                    <span>{copy.planHint}</span>
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
                  <h2>{copy.aiTitle}</h2>
                  <p>{copy.aiBody}</p>
                </div>
              </div>
              <Link href="/ai">{copy.aiAction}</Link>
            </section>

            <p className={styles.performanceNote}>
              Home leggera · {summary.meta.history_days_used} giorni usati solo per la baseline attività · {summary.meta.ai_calls} chiamate AI automatiche
            </p>
          </>
          )
        ) : null}
      </main>
    </>
  );
}
