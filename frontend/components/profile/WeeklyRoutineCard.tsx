"use client";

import { useEffect, useState } from "react";
import { getWeeklySchedule, updateWeeklySchedule, type WeeklyScheduleContext } from "@/lib/api/profile";
import styles from "./WeeklyRoutineCard.module.css";

const DAYS = [
  ["monday", "Lunedì"], ["tuesday", "Martedì"], ["wednesday", "Mercoledì"],
  ["thursday", "Giovedì"], ["friday", "Venerdì"], ["saturday", "Sabato"], ["sunday", "Domenica"],
] as const;

function mondayIso() {
  const date = new Date();
  date.setHours(12, 0, 0, 0);
  date.setDate(date.getDate() - (date.getDay() + 6) % 7);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function WeeklyRoutineCard({ accessToken }: { accessToken: string }) {
  const [weekStart] = useState(mondayIso);
  const [days, setDays] = useState<Record<string, WeeklyScheduleContext> | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setDays(null);
    setError("");
    void getWeeklySchedule(accessToken, weekStart).then((response) => {
      if (active) setDays(response.days);
    }).catch(() => {
      if (active) setError("Non riesco a caricare la routine di questa settimana. Ricarica la pagina per riprovare.");
    });
    return () => { active = false; };
  }, [accessToken, weekStart]);

  async function save() {
    if (!days || saving) return;
    setSaving(true);
    setMessage("");
    setError("");
    try {
      const response = await updateWeeklySchedule(accessToken, {
        week_start: weekStart,
        days: DAYS.map(([key], index) => ({ day_of_week: index + 1, context: days[key] ?? "home" })),
      });
      setDays(response.days);
      setMessage("Routine della settimana aggiornata.");
    } catch {
      setError("Non riesco a salvare la routine. Riprova.");
    } finally {
      setSaving(false);
    }
  }

  return <details id="planning-settings" className={styles.card}>
    <summary><strong>Questa settimana</strong><span>Casa, ufficio o giorni liberi diversi dalla routine abituale.</span></summary>
    {days ? <div className={styles.days}>{DAYS.map(([key, label]) => <label key={key}>
      <span>{label}</span>
      <select aria-label={label} disabled={saving} value={days[key] ?? "home"} onChange={(event) => {
        setDays({ ...days, [key]: event.target.value as WeeklyScheduleContext });
        setMessage("");
      }}>
        <option value="home">Casa</option><option value="office">Ufficio</option><option value="free">Libero</option>
      </select>
    </label>)}</div> : !error ? <p role="status">Carico la routine…</p> : null}
    <button type="button" disabled={!days || saving} onClick={() => void save()}>{saving ? "Salvataggio…" : "Salva questa settimana"}</button>
    {message ? <p role="status">{message}</p> : null}
    {error ? <p role="alert">{error}</p> : null}
  </details>;
}
