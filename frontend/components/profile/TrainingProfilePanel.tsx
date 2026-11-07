"use client";

import { useEffect, useState } from "react";
import {
  getOnboardingStatus,
  saveTrainingSetup,
  type OnboardingStatus,
  type TrainingProfile,
} from "@/lib/api/onboarding";
import styles from "./TrainingProfilePanel.module.css";

type Props = { accessToken: string };

const MUSCLES = [
  ["chest", "Petto"], ["back", "Schiena"], ["shoulders", "Spalle"],
  ["biceps", "Bicipiti"], ["triceps", "Tricipiti"],
  ["glutes", "Glutei"], ["quadriceps", "Quadricipiti"],
  ["hamstrings", "Femorali"], ["calves", "Polpacci"], ["core", "Core"],
] as const;
const DAYS = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"];

export function TrainingProfilePanel({ accessToken }: Props) {
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [form, setForm] = useState<TrainingProfile | null>(null);
  const [days, setDays] = useState<number[]>([]);
  const [muscles, setMuscles] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getOnboardingStatus(accessToken)
      .then((result) => {
        if (!active) return;
        setStatus(result);
        if (result.training_profile) {
          setForm(result.training_profile);
          setDays(result.preferred_days);
          setMuscles(result.priority_muscles);
        }
      })
      .catch(() => {
        if (active) setError("Impossibile caricare il profilo Training.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [accessToken]);

  function toggleDay(day: number) {
    setDays((current) => current.includes(day)
      ? current.filter((item) => item !== day)
      : [...current, day].sort((a, b) => a - b));
  }

  function toggleMuscle(muscle: string) {
    setMuscles((current) => current.includes(muscle)
      ? current.filter((item) => item !== muscle)
      : current.length < 3 ? [...current, muscle] : current);
  }

  async function save() {
    if (!form) return;
    if (form.schedule_flexibility === "fixed" && days.length === 0) {
      setError("Seleziona almeno un giorno per una pianificazione fissa.");
      return;
    }
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const response = await saveTrainingSetup(accessToken, {
        experience_level: form.experience_level,
        sessions_per_week: form.sessions_per_week,
        session_duration_minutes: form.session_duration_minutes,
        planning_horizon: form.planning_horizon,
        environment: "commercial_gym",
        coach_style: form.coach_style,
        feedback_mode: form.feedback_mode,
        schedule_flexibility: form.schedule_flexibility,
        preferred_days: days,
        priority_muscles: muscles,
      });
      setStatus(response);
      if (response.training_profile) setForm(response.training_profile);
      setDays(response.preferred_days);
      setMuscles(response.priority_muscles);
      setMessage("Profilo Training aggiornato.");
    } catch {
      setError("Impossibile salvare il profilo Training.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <section className={styles.panel}><p>Caricamento Training…</p></section>;
  if (!form) {
    return (
      <section className={styles.panel}>
        <h2>Profilo Training</h2>
        <p>
          {status?.preferences?.training_enabled
            ? "Completa il setup Training per modificare le tue preferenze."
            : "Attiva il modulo Training nell'onboarding per personalizzare gli allenamenti."}
        </p>
        {error && <p role="alert">{error}</p>}
      </section>
    );
  }

  return (
    <section className={styles.panel} aria-labelledby="training-profile-heading">
      <h2 id="training-profile-heading">Profilo Training</h2>
      <p className={styles.muted}>
        Aggiorna il punto di partenza del Coach senza cancellare
        allenamenti o progressi già registrati.
      </p>
      <div className={styles.fields}>
        <label>
          Esperienza
          <select value={form.experience_level}
            onChange={(event) => setForm({ ...form, experience_level: event.target.value as TrainingProfile["experience_level"] })}>
            <option value="beginner">Principiante</option>
            <option value="intermediate">Intermedio</option>
            <option value="advanced">Avanzato</option>
          </select>
        </label>
        <label>
          Sedute a settimana
          <select value={form.sessions_per_week}
            onChange={(event) => setForm({ ...form, sessions_per_week: Number(event.target.value) })}>
            {[2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <label>
          Durata seduta (minuti)
          <select value={form.session_duration_minutes}
            onChange={(event) => setForm({ ...form, session_duration_minutes: Number(event.target.value) })}>
            {[20, 30, 45, 60, 75, 90, 120, 150, 180].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <label>
          Orizzonte
          <select value={form.planning_horizon}
            onChange={(event) => setForm({ ...form, planning_horizon: event.target.value as TrainingProfile["planning_horizon"] })}>
            <option value="weekly">Settimanale</option>
            <option value="monthly">Mensile</option>
          </select>
        </label>
        <label>
          Stile Coach
          <select value={form.coach_style}
            onChange={(event) => setForm({ ...form, coach_style: event.target.value as TrainingProfile["coach_style"] })}>
            <option value="conservative">Prudente</option>
            <option value="balanced">Bilanciato</option>
            <option value="ambitious">Ambizioso</option>
          </select>
        </label>
        <label>
          Feedback
          <select value={form.feedback_mode}
            onChange={(event) => setForm({ ...form, feedback_mode: event.target.value as TrainingProfile["feedback_mode"] })}>
            <option value="simple">Essenziale</option>
            <option value="advanced">Dettagliato</option>
          </select>
        </label>
        <label>
          Calendario
          <select value={form.schedule_flexibility}
            onChange={(event) => setForm({ ...form, schedule_flexibility: event.target.value as TrainingProfile["schedule_flexibility"] })}>
            <option value="flexible">Flessibile</option>
            <option value="fixed">Giorni fissi</option>
          </select>
        </label>
      </div>
      <fieldset className={styles.group}>
        <legend>Giorni preferiti</legend>
        <div className={styles.chips}>
          {DAYS.map((label, index) => (
            <button type="button" key={index}
              aria-pressed={days.includes(index + 1)}
              onClick={() => toggleDay(index + 1)}>{label}</button>
          ))}
        </div>
      </fieldset>
      <fieldset className={styles.group}>
        <legend>Gruppi muscolari prioritari (max 3)</legend>
        <div className={styles.chips}>
          {MUSCLES.map(([key, label]) => (
            <button type="button" key={key}
              aria-pressed={muscles.includes(key)}
              disabled={!muscles.includes(key) && muscles.length >= 3}
              onClick={() => toggleMuscle(key)}>{label}</button>
          ))}
        </div>
      </fieldset>
      {error && <p className={styles.error} role="alert">{error}</p>}
      {message && <p className={styles.success} role="status">{message}</p>}
      <button type="button" className={styles.save}
        disabled={saving} onClick={() => void save()}>
        {saving ? "Salvataggio…" : "Salva profilo Training"}
      </button>
    </section>
  );
}
