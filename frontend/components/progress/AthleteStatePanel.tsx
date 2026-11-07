"use client";

import { useEffect, useState } from "react";

import { getAthleteState, type AthleteState } from "@/lib/api/athlete-state";
import styles from "./AthleteStatePanel.module.css";

interface Props {
  accessToken: string;
}

export function AthleteStatePanel({ accessToken }: Props) {
  const [state, setState] = useState<AthleteState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    getAthleteState(accessToken)
      .then((response) => {
        if (mounted) { setState(response); setError(null); }
      })
      .catch(() => {
        if (mounted) setError("Lo stato atletico non è disponibile al momento.");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => { mounted = false; };
  }, [accessToken]);

  return (
    <section className={styles.panel} aria-labelledby="athlete-state-title">
      <div className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Training · Phase 3</p>
          <h2 id="athlete-state-title">Stato dell’atleta</h2>
        </div>
        {state && <small>Aggiornato al {state.as_of}</small>}
      </div>
      {loading && <p>Caricamento dello storico palestra…</p>}
      {error && <p role="alert" className={styles.error}>{error}</p>}
      {state && (
        <>
          {state.data_status === "limited" && (
            <p className={styles.notice}>
              Dati ancora limitati: le statistiche diventano più rappresentative con nuove sedute completate.
            </p>
          )}
          <div className={styles.metrics}>
            <div><strong>{state.last_28_days.completed_sessions}</strong><span>Sedute · 28 giorni</span></div>
            <div><strong>{state.last_28_days.total_sets}</strong><span>Serie · 28 giorni</span></div>
            <div><strong>{state.last_28_days.volume_load_kg.toLocaleString("it-IT")}</strong><span>Volume kg × rip. · 28 giorni</span></div>
            <div><strong>{state.consistency_ratio_last_4_weeks === null ? "—" : `${Math.round(state.consistency_ratio_last_4_weeks * 100)}%`}</strong><span>Frequenza rispetto al piano</span></div>
          </div>
          <h3>Continuità nelle ultime 8 settimane</h3>
          <div className={styles.weeks} aria-label="Sedute completate per settimana">
            {state.weekly.map((week) => (
              <div key={week.start} className={styles.week}>
                <div className={styles.barOuter}>
                  <div className={styles.barInner} style={{ height: `${Math.min(100, week.sessions * 20)}%` }} />
                </div>
                <span>{week.sessions}</span>
                <small>{week.start.slice(5)}</small>
              </div>
            ))}
          </div>
          {state.most_logged_exercises.length > 0 && (
            <>
              <h3>Esercizi più registrati</h3>
              <ul className={styles.exercises}>
                {state.most_logged_exercises.slice(0, 5).map((item) => (
                  <li key={item.exercise_id}>
                    <strong>{item.name}</strong>
                    <span>{item.sessions} sedute · {item.sets} serie</span>
                  </li>
                ))}
              </ul>
            </>
          )}
          <p className={styles.disclaimer}>{state.note}</p>
        </>
      )}
    </section>
  );
}
