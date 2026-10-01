"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { AppNav } from "@/components/navigation/AppNav";
import { SpecialPeriodsCard } from "@/components/profile/SpecialPeriodsCard";
import { useAuth } from "@/components/auth/AuthProvider";
import {
  createPlannedActivity,
  getPlannedActivities,
  type PlannedActivity,
  type PlannedActivityIntensity,
} from "@/lib/api/activities";

import styles from "./PlanPage.module.css";

function localIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function todayIso(): string {
  return localIsoDate(new Date());
}

function plusDays(days: number): string {
  const date = new Date();
  date.setHours(12, 0, 0, 0);
  date.setDate(date.getDate() + days);
  return localIsoDate(date);
}

function activityIcon(value: string): string {
  const label = value.trim().toLocaleLowerCase("it-IT");
  if (label.includes("corsa") || label.includes("run")) return "🏃";
  if (label.includes("bici") || label.includes("cycl")) return "🚴";
  if (label.includes("nuoto") || label.includes("swim")) return "🏊";
  if (label.includes("palestra") || label.includes("strength") || label.includes("pesi")) return "🏋️";
  if (label.includes("padel") || label.includes("tennis")) return "🎾";
  return "⚡";
}

function dateLabel(value: string): string {
  if (value === todayIso()) return "Oggi";
  if (value === plusDays(1)) return "Domani";
  return new Date(`${value}T12:00:00`).toLocaleDateString("it-IT", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

export default function PlanPage() {
  const { accessToken } = useAuth();
  const [items, setItems] = useState<PlannedActivity[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [activityType, setActivityType] = useState("Corsa");
  const [scheduledDate, setScheduledDate] = useState(todayIso());
  const [scheduledTime, setScheduledTime] = useState("");
  const [duration, setDuration] = useState("");
  const [distance, setDistance] = useState("");
  const [intensity, setIntensity] = useState<PlannedActivityIntensity>("moderate");

  async function loadPlan() {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const response = await getPlannedActivities(todayIso(), plusDays(14), accessToken);
      setItems(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Non riesco a caricare il piano.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadPlan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

  const upcoming = useMemo(
    () => [...items]
      .filter((item) => item.status !== "completed" && item.status !== "skipped")
      .sort((a, b) => `${a.scheduled_date}${a.scheduled_time ?? ""}`.localeCompare(`${b.scheduled_date}${b.scheduled_time ?? ""}`)),
    [items],
  );

  async function addActivity() {
    if (!accessToken || saving) return;
    if (!title.trim()) {
      setError("Dai un nome all'allenamento.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const result = await createPlannedActivity(
        {
          scheduled_date: scheduledDate,
          scheduled_time: scheduledTime || null,
          title: title.trim(),
          activity_type: activityType,
          duration_minutes: duration ? Math.max(1, Number(duration)) : null,
          distance_meters: distance ? Math.max(0, Number(distance) * 1000) : null,
          intensity,
        },
        accessToken,
      );
      setItems((current) => [...current, result.item]);
      setTitle("");
      setDuration("");
      setDistance("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Non riesco a pianificare l'attività.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <AppNav />
      <main className={styles.page}>
        <header className={styles.hero}>
          <div>
            <span className={styles.eyebrow}>PLAN</span>
            <h1>Pianifica la tua vita reale</h1>
            <p>Allenamenti, cambi di routine, vacanze e malattia nello stesso calendario.</p>
          </div>
          <Link href="/activities" className={styles.secondaryAction}>
            Registro attività →
          </Link>
        </header>

        <section className={styles.grid}>
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <div>
                <span className={styles.cardKicker}>PROSSIMI 14 GIORNI</span>
                <h2>Allenamenti pianificati</h2>
              </div>
              <span className={styles.countPill}>{upcoming.length}</span>
            </div>

            {loading ? (
              <p className={styles.muted}>Carico il piano…</p>
            ) : upcoming.length ? (
              <div className={styles.activityList}>
                {upcoming.slice(0, 8).map((item) => (
                  <div key={item.id} className={styles.activityRow}>
                    <span className={styles.activityIcon} aria-hidden="true">
                      {activityIcon(item.activity_type)}
                    </span>
                    <div className={styles.activityCopy}>
                      <strong>{item.title}</strong>
                      <span>
                        {dateLabel(item.scheduled_date)}
                        {item.scheduled_time ? ` · ${item.scheduled_time.slice(0, 5)}` : ""}
                        {item.duration_minutes ? ` · ${item.duration_minutes} min` : ""}
                        {item.distance_meters ? ` · ${(item.distance_meters / 1000).toLocaleString("it-IT", { maximumFractionDigits: 1 })} km` : ""}
                      </span>
                    </div>
                    {item.status === "planned" ? (
                      <span className={styles.statusPlanned}>Pianificato</span>
                    ) : (
                      <span className={styles.statusSuspended}>Sospeso</span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className={styles.emptyState}>
                <strong>Nessun allenamento in programma.</strong>
                <span>Aggiungine uno qui sotto oppure crea un programma completo.</span>
              </div>
            )}

            <div className={styles.formTitle}>+ Pianifica allenamento</div>
            <div className={styles.formGrid}>
              <label>
                <span>Nome</span>
                <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Es. 8 km facile" />
              </label>
              <label>
                <span>Tipo</span>
                <select value={activityType} onChange={(event) => setActivityType(event.target.value)}>
                  <option>Corsa</option>
                  <option>Palestra</option>
                  <option>Bici</option>
                  <option>Nuoto</option>
                  <option>Padel</option>
                  <option>Camminata</option>
                  <option>Altro</option>
                </select>
              </label>
              <label>
                <span>Data</span>
                <input type="date" value={scheduledDate} onChange={(event) => setScheduledDate(event.target.value)} />
              </label>
              <label>
                <span>Ora</span>
                <input type="time" value={scheduledTime} onChange={(event) => setScheduledTime(event.target.value)} />
              </label>
              <label>
                <span>Durata (min)</span>
                <input type="number" min="1" value={duration} onChange={(event) => setDuration(event.target.value)} />
              </label>
              <label>
                <span>Distanza (km)</span>
                <input type="number" min="0" step="0.1" value={distance} onChange={(event) => setDistance(event.target.value)} />
              </label>
              <label>
                <span>Intensità</span>
                <select value={intensity} onChange={(event) => setIntensity(event.target.value as PlannedActivityIntensity)}>
                  <option value="low">Facile</option>
                  <option value="moderate">Moderata</option>
                  <option value="hard">Intensa</option>
                  <option value="race">Gara / test</option>
                  <option value="unknown">Da definire</option>
                </select>
              </label>
            </div>
            <button type="button" className={styles.primaryAction} disabled={saving} onClick={() => void addActivity()}>
              {saving ? "Salvataggio…" : "Aggiungi al piano"}
            </button>
            {error ? <p className={styles.error}>{error}</p> : null}
          </div>

          <aside className={styles.sideColumn}>
            <section className={styles.shortcutCard}>
              <span className={styles.cardKicker}>PROGRAMMI</span>
              <h2>Corsa e palestra</h2>
              <p>I builder completi restano disponibili senza appesantire questa pagina.</p>
              <Link href="/activities" className={styles.textLink}>Apri programmi e attività →</Link>
            </section>

            <section className={styles.shortcutCard}>
              <span className={styles.cardKicker}>REGISTRA</span>
              <h2>Hai già fatto qualcosa?</h2>
              <p>Per GPX, FIT, TCX, passi e dettagli dell'attività usa il registro.</p>
              <Link href="/activities" className={styles.textLink}>Vai al registro attività →</Link>
            </section>
          </aside>
        </section>

        {accessToken ? (
          <section className={styles.specialPeriods}>
            <SpecialPeriodsCard accessToken={accessToken} />
          </section>
        ) : null}
      </main>
    </>
  );
}
