"use client";

import { useMemo, useState } from "react";

import { AppNav } from "@/components/navigation/AppNav";
import { useAuth } from "@/components/auth/AuthProvider";
import { createActivity } from "@/lib/api/activities";
import {
  previewConversationalDay,
  type ConversationalDayPreview,
} from "@/lib/api/conversation";
import { confirmConversationalMeal } from "@/lib/api/meals";
import { createWeight } from "@/lib/api/weight";

import styles from "./SanoSyncAIPage.module.css";

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

export default function SanoSyncAIPage() {
  const { accessToken } = useAuth();
  const [text, setText] = useState("");
  const [defaultMealType, setDefaultMealType] = useState("Pranzo");
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
    if (!accessToken || !text.trim() || loading) return;

    setLoading(true);
    setMessage(null);
    setPreview(null);

    try {
      const result = await previewConversationalDay(
        text.trim(),
        defaultMealType,
        localIsoDate(),
        accessToken,
      );
      setPreview(result);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Non riesco a interpretare questa registrazione.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function confirmAll() {
    if (!accessToken || !preview || saving) return;

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
    } catch (error) {
      setMessage(
        completed > 0
          ? `Ho registrato ${completed} elementi. Riprova per quelli rimasti.`
          : error instanceof Error
            ? error.message
            : "Non riesco a completare la registrazione.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <AppNav />
      <main className={styles.page}>
        <section className={styles.hero}>
          <span className={styles.spark}>✦</span>
          <div>
            <p className={styles.kicker}>SanoSync AI</p>
            <h1>Scrivi cosa hai fatto. Al resto penso io.</h1>
            <p>
              Pasti, attività e peso possono stare nello stesso messaggio.
              Analizzo prima, poi confermi tu cosa registrare.
            </p>
          </div>
        </section>

        <section className={styles.composer}>
          <label className={styles.mealType}>
            <span>Pasto predefinito</span>
            <select
              value={defaultMealType}
              onChange={(event) => setDefaultMealType(event.target.value)}
            >
              <option>Colazione</option>
              <option>Pranzo</option>
              <option>Snack</option>
              <option>Cena</option>
            </select>
          </label>

          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Es. A pranzo pollo e riso, ho corso 5 km e stamattina pesavo 81,2 kg..."
            rows={5}
          />

          <div className={styles.examples}>
            {examples.map((example) => (
              <button key={example} type="button" onClick={() => setText(example)}>
                {example}
              </button>
            ))}
          </div>

          <button
            type="button"
            className={styles.primary}
            disabled={!accessToken || !text.trim() || loading}
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
                disabled={saving}
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

        {message ? <p className={styles.message}>{message}</p> : null}
      </main>
    </>
  );
}
