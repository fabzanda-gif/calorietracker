"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { ApiError } from "@/lib/api/client";
import { createActivity } from "@/lib/api/activities";
import {
  previewConversationalDay,
  type ConversationalDayPreview,
} from "@/lib/api/conversation";
import { confirmConversationalMeal } from "@/lib/api/meals";
import { createWeight } from "@/lib/api/weight";
import type { HomeSummaryResponse } from "@/lib/api/day";
import { mealTypeForNow } from "@/lib/mealSlots";

import styles from "./HomeAiTile.module.css";

function localIsoDate(date = new Date()): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function metricLabel(action: ConversationalDayPreview["actions"][number]): string {
  if (action.kind === "meal") {
    return `${Math.round(action.totals.calories)} kcal`;
  }
  if (action.kind === "activity") {
    return action.burned_calories > 0
      ? `${Math.round(action.burned_calories)} kcal`
      : "Attività";
  }
  return `${Number(action.weight_kg).toLocaleString("it-IT", {
    maximumFractionDigits: 1,
  })} kg`;
}

export function HomeAiTile({ onSaved, summary }: {
  onSaved: () => Promise<void>;
  summary: HomeSummaryResponse | null;
}) {
  const tileRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (window.location.hash === "#home-ai") tileRef.current?.scrollIntoView({ block: "start" });
  }, []);
  const { accessToken } = useAuth();
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<ConversationalDayPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const examples = useMemo(
    () => [
      "A pranzo ho mangiato pasta al pomodoro e pollo.",
      "Ho corso 7 km in 42 minuti.",
      "Stamattina pesavo 81,2 kg.",
      "A cena sushi e una birra, poi 45 minuti in palestra.",
    ],
    [],
  );

  async function analyze() {
    if (!accessToken || !text.trim() || loading || saving) return;

    setLoading(true);
    setMessage(null);
    setPreview(null);

    try {
      const result = await previewConversationalDay(
        text.trim(),
        mealTypeForNow(summary?.date === localIsoDate()
          ? summary.meals.map((meal) => meal.meal_type) : []),
        localIsoDate(),
        accessToken,
      );
      setPreview(result);
    } catch (error) {
      setMessage(
        error instanceof ApiError && error.status === 429
          ? "Hai raggiunto il limite di richieste AI. Riprova più tardi."
          : "Non riesco a interpretare il messaggio in questo momento. Il testo rimane qui: riprova tra poco.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function confirmAll() {
    if (!accessToken || !preview?.actions.length || saving) return;

    setSaving(true);
    setMessage(null);
    let completed = 0;

    try {
      for (const action of preview.actions) {
        if (action.kind === "meal") {
          await confirmConversationalMeal(
            {
              date: action.date,
              meal_type: action.meal_type,
              items: action.items,
            },
            accessToken,
          );
        } else if (action.kind === "activity") {
          await createActivity(
            {
              date: action.date,
              activity_name: action.activity_name,
              activity_type: action.activity_type,
              burned_calories: Math.max(0, Math.round(action.burned_calories)),
              duration_seconds: action.duration_seconds ?? undefined,
              distance_meters: action.distance_meters ?? undefined,
            },
            accessToken,
          );
        } else {
          await createWeight(
            {
              date: action.date,
              weight: action.weight_kg,
            },
            accessToken,
          );
        }
        completed += 1;
      }

      setPreview(null);
      setText("");
      setMessage(
        completed === 1
          ? "Registrazione completata."
          : `${completed} registrazioni completate.`,
      );
    } catch {
      setPreview({ ...preview, actions: preview.actions.slice(completed) });
      setMessage(
        completed > 0
          ? `Ho registrato ${completed} ${completed === 1 ? "elemento" : "elementi"}. Riprova per quelli rimasti.`
          : "Non riesco a completare la registrazione. Riprova tra poco.",
      );
    } finally {
      if (completed > 0) await onSaved();
      setSaving(false);
    }
  }

  return (
    <section id="home-ai" ref={tileRef} className={styles.tile} aria-label="SanoSync AI">
        <section className={styles.hero}>
          <span className={styles.spark}>✦</span>
          <div>
            <p className={styles.kicker}>SanoSync AI</p>
            <h2>Raccontami la tua giornata</h2>
            <p>
              Pasti, attività e peso possono stare nello stesso messaggio.
              Analizzo prima, poi confermi tu cosa registrare.
            </p>
          </div>
        </section>

        <section className={styles.composer}>
          <label className={styles.inputLabel} htmlFor="home-ai-message">Pasti, attività o peso</label>
          <textarea
            id="home-ai-message"
            disabled={loading || saving}
            value={text}
            onChange={(event) => { setText(event.target.value); setPreview(null); }}
            placeholder="Es. A pranzo pollo e riso, ho corso 5 km e stamattina pesavo 81,2 kg..."
            rows={3}
          />

          <div className={styles.examples}>
            {examples.map((example) => (
              <button key={example} disabled={loading || saving} type="button" onClick={() => { setText(example); setPreview(null); }}>
                {example}
              </button>
            ))}
          </div>

          <button
            type="button"
            className={styles.primary}
            disabled={!accessToken || !text.trim() || loading || saving}
            onClick={() => void analyze()}
          >
            {loading ? "Analizzo…" : "Analizza con SanoSync AI"}
          </button>
        </section>

        {preview ? (
          <section className={styles.preview}>
            <div className={styles.previewHeader}>
              <div>
                <p className={styles.kicker}>Ho capito questo</p>
                <h2>Controlla prima di registrare</h2>
              </div>
              {preview.needs_review ? (
                <span className={styles.reviewBadge}>Da verificare</span>
              ) : null}
            </div>

            <div className={styles.actionList}>
              {preview.actions.map((action) => (
                <article key={action.id} className={styles.actionCard}>
                  <span className={styles.actionIcon} aria-hidden="true">
                    {action.kind === "meal" ? "🍽️" : action.kind === "activity" ? "🏃" : "⚖️"}
                  </span>
                  <div className={styles.actionMain}>
                    <strong>
                      {action.kind === "meal"
                        ? action.meal_type
                        : action.kind === "activity"
                          ? action.activity_name
                          : "Peso"}
                    </strong>
                    <span>
                      {action.kind === "meal"
                        ? action.items.map((item) => item.name).join(" · ")
                        : action.kind === "activity"
                          ? [
                              action.activity_type,
                              action.duration_seconds
                                ? `${Math.round(action.duration_seconds / 60)} min`
                                : null,
                              action.distance_meters
                                ? `${(action.distance_meters / 1000).toLocaleString("it-IT", {
                                    maximumFractionDigits: 2,
                                  })} km`
                                : null,
                            ]
                              .filter(Boolean)
                              .join(" · ")
                          : action.date}
                    </span>
                  </div>
                  <strong className={styles.metric}>{metricLabel(action)}</strong>
                </article>
              ))}
            </div>

            <div className={styles.previewActions}>
              <button
                type="button"
                className={styles.primary}
                disabled={saving || !preview.actions.length}
                onClick={() => void confirmAll()}
              >
                {saving ? "Registro…" : "Conferma e registra"}
              </button>
              <button
                type="button"
                className={styles.secondary}
                disabled={saving}
                onClick={() => setPreview(null)}
              >
                Modifica testo
              </button>
            </div>
          </section>
        ) : null}

        {message ? <p className={styles.message} role="status">{message}</p> : null}
    </section>
  );
}
