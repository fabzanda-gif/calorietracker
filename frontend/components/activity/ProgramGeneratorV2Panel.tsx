"use client";

import { useState } from "react";
import {
  createProgramV2,
  previewProgramV2,
  type ProgramV2Goal,
  type ProgramV2Preview,
} from "@/lib/api/program-v2";
import styles from "./ProgramGeneratorV2Panel.module.css";

const EQUIPMENT = [
  ["body-weight", "Corpo libero"],
  ["barbell", "Bilanciere"],
  ["dumbbell", "Manubri"],
  ["cable", "Cavi"],
  ["leverage-machine", "Macchine"],
  ["smith-machine", "Smith"],
  ["sled-machine", "Pressa"],
  ["band", "Elastici"],
  ["ez-barbell", "EZ"],
] as const;

function localDate() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

interface Props {
  accessToken: string;
}

export function ProgramGeneratorV2Panel({ accessToken }: Props) {
  const [startDate, setStartDate] = useState(localDate);
  const [goal, setGoal] = useState<ProgramV2Goal>("hypertrophy");
  const [weeks, setWeeks] = useState(8);
  const [equipment, setEquipment] = useState<string[]>([]);
  const [preview, setPreview] = useState<ProgramV2Preview | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [replaceActive, setReplaceActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const request = () => ({
    start_date: startDate,
    goal,
    total_weeks: weeks,
    allowed_equipment: equipment,
    replace_active: replaceActive,
  });

  function updateEquipment(key: string, checked: boolean) {
    setEquipment((prev) => checked ? [...prev, key] : prev.filter((x) => x !== key));
    setPreview(null);
  }

  async function generatePreview() {
    setLoading(true);
    setPreview(null);
    setError(null);
    setSuccess(null);
    try {
      const response = await previewProgramV2(accessToken, request());
      setPreview(response);
    } catch {
      setError(
        "Anteprima non disponibile: controlla il Training Profile e il rilascio dei dati Exercise Library.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function activate() {
    if (!preview?.ready_for_activation || saving) return;
    setSaving(true);
    setError(null);
    try {
      const result = await createProgramV2(accessToken, request());
      setSuccess(`Programma creato: ${result.workout_count} allenamenti. Puoi consultarlo nella sezione programmi palestra.`);
      setPreview(null);
    } catch {
      setError("Il server ha bloccato l'attivazione: ricontrolla catalogo, attrezzatura e programmi attivi.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className={styles.panel} aria-labelledby="program-v2-title">
      <p className={styles.kicker}>Program Generator · V2</p>
      <h2 id="program-v2-title">Programma costruito sul tuo profilo</h2>
      <p className={styles.muted}>
        Usa esperienza, sedute, giorni e priorità dal Training Profile,
        le tue preferenze esercizi e lo storico atleta. Solo esercizi
        verificati e approvati possono entrare nel programma.
      </p>
      <div className={styles.grid}>
        <label>Inizio
          <input type="date" value={startDate} min={localDate()}
            onChange={(e) => { setStartDate(e.target.value); setPreview(null); }} />
        </label>
        <label>Obiettivo
          <select value={goal} onChange={(e) => {
            setGoal(e.target.value as ProgramV2Goal); setPreview(null);
          }}>
            <option value="hypertrophy">Massa muscolare</option>
            <option value="strength">Forza</option>
            <option value="general_fitness">Fitness generale</option>
          </select>
        </label>
        <label>Durata programma
          <select value={weeks} onChange={(e) => {
            setWeeks(Number(e.target.value)); setPreview(null);
          }}>
            {[4, 6, 8, 10, 12].map((n) => (
              <option key={n} value={n}>{n} settimane</option>
            ))}
          </select>
        </label>
      </div>
      <fieldset className={styles.equipment}>
        <legend>Attrezzatura a disposizione</legend>
        <div className={styles.chips}>
          {EQUIPMENT.map(([key, name]) => (
            <label key={key}>
              <input type="checkbox" checked={equipment.includes(key)}
                onChange={(e) => updateEquipment(key, e.target.checked)} />
              {name}
            </label>
          ))}
        </div>
      </fieldset>
      <button type="button" className={styles.primary} onClick={() => void generatePreview()}
        disabled={loading || !startDate || equipment.length === 0}>
        {loading ? "Genero anteprima…" : "Genera anteprima personalizzata"}
      </button>
      {preview && (
        <div className={styles.preview}>
          <h3>{preview.workout_count} sedute in {preview.total_weeks} settimane</h3>
          <p>Livello: {preview.experience_level} · {preview.sessions_per_week} sedute/settimana · {preview.session_duration_minutes} minuti</p>
          <p>Qualità storico atleta: {preview.athlete_data_status}</p>
          {preview.warnings.length > 0 && (
            <div className={styles.warning} role="status">
              <strong>Verifiche necessarie</strong>
              <ul>{preview.warnings.map((text) => <li key={text}>{text}</li>)}</ul>
            </div>
          )}
          <h4>Prima settimana</h4>
          <ul className={styles.workouts}>
            {preview.workouts.filter((w) => w.training_week === 1).map((workout) => (
              <li key={workout.workout_index}>
                <strong>{workout.title} · {workout.scheduled_date}</strong>
                <span>{workout.exercises.map((x) => x.exercise_name).join(" · ") || "Movimenti non ancora disponibili"}</span>
              </li>
            ))}
          </ul>
          {preview.ready_for_activation ? (
            <>
              <label className={styles.replace}>
                <input type="checkbox" checked={replaceActive}
                  onChange={(e) => setReplaceActive(e.target.checked)} />
                Confermo la sostituzione di un eventuale programma già attivo
              </label>
              <button type="button" className={styles.primary}
                onClick={() => void activate()} disabled={saving}>
                {saving ? "Attivazione…" : "Conferma e crea programma"}
              </button>
            </>
          ) : (
            <p className={styles.muted}>
              Attivazione bloccata: il catalogo approvato non copre ancora
              tutti i movimenti richiesti. Nessuna scheda è stata modificata.
            </p>
          )}
        </div>
      )}
      {error && <p className={styles.error} role="alert">{error}</p>}
      {success && <p className={styles.success} role="status">{success}</p>}
    </section>
  );
}
