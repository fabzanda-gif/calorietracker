"use client";

import { useEffect, useState } from "react";
import {
  getCrossTrainingTimeline,
  type CrossTrainingTimeline,
  type CrossTrainingEvent,
} from "@/lib/api/cross-training";
import styles from "./CrossTrainingPanel.module.css";

type Props = { accessToken: string };

function todayLocal(): string {
  const now = new Date();
  const day = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
}

function shortDay(iso: string): string {
  return new Date(iso + "T12:00:00").toLocaleDateString("it-IT", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

function eventLabel(event: CrossTrainingEvent): string {
  const type = event.modality === "strength" ? "Palestra" : "Corsa";
  const done = event.status === "completed" ? "completata" : "prevista";
  return `${type} ${done}: ${event.title}`;
}

export function CrossTrainingPanel({ accessToken }: Props) {
  const [startDate, setStartDate] = useState(todayLocal);
  const [timeline, setTimeline] = useState<CrossTrainingTimeline | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    getCrossTrainingTimeline(accessToken, startDate, 14)
      .then((data) => {
        if (active) setTimeline(data);
      })
      .catch(() => {
        if (active) {
          setTimeline(null);
          setError("Impossibile caricare il calendario Gym ↔ Running.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [accessToken, startDate]);

  return (
    <section className={styles.panel} aria-labelledby="cross-title">
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Phase 7 · Cross-training</p>
          <h2 id="cross-title">Palestra ↔ Corsa</h2>
        </div>
        <label className={styles.picker}>
          Dal giorno
          <input type="date" value={startDate}
            onChange={(event) => {
              if (event.target.value) setStartDate(event.target.value);
            }} />
        </label>
      </header>
      <p className={styles.muted}>
        Calendario combinato di 14 giorni. Segnala le sedute impegnative vicine
        senza modificarle o spostare le gare automaticamente.
      </p>
      {loading && <p aria-live="polite">Caricamento calendario…</p>}
      {error && <p role="alert" className={styles.error}>{error}</p>}
      {timeline && !loading && (
        <>
          <div className={styles.metrics}>
            <span><strong>{timeline.summary.strength_sessions}</strong> palestra</span>
            <span><strong>{timeline.summary.running_sessions}</strong> corsa</span>
            <span><strong>{timeline.summary.potential_conflicts}</strong> sovrapposizioni da valutare</span>
          </div>
          {timeline.conflicts.length > 0 && (
            <div className={styles.conflicts}>
              <h3>Attenzione al calendario</h3>
              {timeline.conflicts.map((item) => (
                <p key={item.id}>
                  <strong>{shortDay(item.date)}</strong> —{" "}
                  {item.race_protected
                    ? "Gara protetta: valuta la seduta di palestra vicina, senza spostare la gara."
                    : "Seduta gambe e corsa di qualità ravvicinate: valuta il recupero e la distanza tra le sedute."}
                  {" "}Nessuna modifica viene applicata.
                </p>
              ))}
            </div>
          )}
          <ul className={styles.days}>
            {timeline.timeline.map((day) => (
              <li key={day.date} className={styles.day}>
                <strong>{shortDay(day.date)}</strong>
                {day.events.length > 0 ? (
                  <ul>
                    {day.events.map((event) => (
                      <li key={event.id} className={styles.event}>
                        {eventLabel(event)}
                        {event.is_race ? " · Gara" : ""}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className={styles.muted}>Nessun allenamento registrato</span>
                )}
              </li>
            ))}
          </ul>
          <p className={styles.disclaimer}>{timeline.note}</p>
        </>
      )}
    </section>
  );
}
