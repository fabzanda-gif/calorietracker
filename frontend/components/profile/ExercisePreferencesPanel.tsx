"use client";

import { useCallback, useEffect, useState } from "react";

import {
  deleteExercisePreference,
  getExercise,
  getExercisePreferences,
  listExercises,
  setExercisePreference,
  type ExerciseLibraryItem,
  type ExercisePreference,
  type ExercisePreferenceRecord,
} from "@/lib/api/exercises";
import styles from "./ExercisePreferencesPanel.module.css";

type Props = { accessToken: string };

export function ExercisePreferencesPanel({ accessToken }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ExerciseLibraryItem[]>([]);
  const [preferences, setPreferences] = useState<ExercisePreferenceRecord[]>([]);
  const [names, setNames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadPreferences = useCallback(async () => {
    const response = await getExercisePreferences(accessToken);
    setPreferences(response.items);
    const lookup = await Promise.allSettled(
      response.items.map((item) => getExercise(accessToken, item.exercise_id)),
    );
    const labels: Record<string, string> = {};
    lookup.forEach((result, index) => {
      const id = response.items[index].exercise_id;
      if (result.status === "fulfilled") {
        labels[id] = result.value.name;
      }
    });
    setNames((current) => ({ ...current, ...labels }));
  }, [accessToken]);

  useEffect(() => {
    let active = true;
    getExercisePreferences(accessToken)
      .then(async (response) => {
        if (!active) return;
        setPreferences(response.items);
        const resolved = await Promise.allSettled(
          response.items.map((item) => getExercise(accessToken, item.exercise_id)),
        );
        if (!active) return;
        const labels: Record<string, string> = {};
        resolved.forEach((result, index) => {
          if (result.status === "fulfilled") {
            labels[response.items[index].exercise_id] = result.value.name;
          }
        });
        setNames(labels);
      })
      .catch(() => {
        if (active) setError("Non riesco a caricare le preferenze esercizi.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [accessToken]);

  async function searchExercises() {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    setSearching(true);
    setError(null);
    setMessage(null);
    try {
      const response = await listExercises(accessToken, {
        search: query.trim(),
        language: "it",
        limit: 20,
      });
      setResults(response.items);
      setNames((current) => {
        const next = { ...current };
        for (const exercise of response.items) next[exercise.id] = exercise.name;
        return next;
      });
    } catch {
      setError("Ricerca esercizi non disponibile. Riprova.");
    } finally {
      setSearching(false);
    }
  }

  async function changePreference(
    exerciseId: string,
    preference: ExercisePreference | null,
  ) {
    if (busyId) return;
    setBusyId(exerciseId);
    setError(null);
    setMessage(null);
    try {
      if (preference === null) {
        await deleteExercisePreference(accessToken, exerciseId);
      } else {
        await setExercisePreference(accessToken, exerciseId, preference);
      }
      await loadPreferences();
      setMessage("Preferenze aggiornate.");
    } catch {
      setError("Non è stato possibile salvare la preferenza.");
    } finally {
      setBusyId(null);
    }
  }

  const selected = new Map(
    preferences.map((item) => [item.exercise_id, item.preference]),
  );

  return (
    <section className={styles.panel} aria-labelledby="exercise-preferences-heading">
      <h2 id="exercise-preferences-heading">Preferenze esercizi · Training</h2>
      <p className={styles.help}>
        Scegli gli esercizi che preferisci o vuoi evitare. Le preferenze
        guideranno i suggerimenti futuri, ma non cambieranno le tue schede.
      </p>
      <div className={styles.search}>
        <label htmlFor="exercise-search">Cerca un esercizio</label>
        <div className={styles.searchRow}>
          <input
            id="exercise-search"
            value={query}
            maxLength={120}
            placeholder="Es. panca, squat, lat pulldown"
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void searchExercises();
              }
            }}
          />
          <button type="button" onClick={() => void searchExercises()} disabled={searching}>
            {searching ? "Cerco…" : "Cerca"}
          </button>
        </div>
      </div>
      {loading ? <p>Caricamento preferenze…</p> : (
        <div className={styles.selected}>
          <h3>Le tue scelte ({preferences.length})</h3>
          {preferences.length === 0 ? (
            <p className={styles.help}>Non hai ancora indicato preferenze.</p>
          ) : (
            <ul className={styles.list}>
              {preferences.map((item) => (
                <li className={styles.item} key={item.exercise_id}>
                  <span>
                    <strong>{names[item.exercise_id] ?? "Esercizio salvato"}</strong>
                    <small>{item.preference === "preferred" ? "Preferito" : "Da evitare"}</small>
                  </span>
                  <button
                    type="button"
                    disabled={busyId !== null}
                    onClick={() => void changePreference(item.exercise_id, null)}
                  >
                    Rimuovi
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {results.length > 0 && (
        <div className={styles.results}>
          <h3>Risultati di ricerca</h3>
          <ul className={styles.list}>
            {results.map((exercise) => (
              <li className={styles.item} key={exercise.id}>
                <span>
                  <strong>{exercise.name}</strong>
                  <small>{exercise.body_part ?? "Corpo"} · {exercise.difficulty ?? "Livello variabile"}</small>
                </span>
                <div className={styles.actions}>
                  <button
                    type="button"
                    disabled={busyId !== null}
                    aria-pressed={selected.get(exercise.id) === "preferred"}
                    onClick={() => void changePreference(exercise.id, "preferred")}
                  >Preferito</button>
                  <button
                    type="button"
                    disabled={busyId !== null}
                    aria-pressed={selected.get(exercise.id) === "excluded"}
                    onClick={() => void changePreference(exercise.id, "excluded")}
                  >Evita</button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
      {error && <p className={styles.error} role="alert">{error}</p>}
      {message && <p className={styles.success} role="status">{message}</p>}
    </section>
  );
}
