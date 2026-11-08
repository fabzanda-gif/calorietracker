"use client";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { getStrengthPlans } from "@/lib/api/strength";
import { getTrainingPlans } from "@/lib/api/activities";
import { RunningPlanBuilder } from "./RunningPlanBuilder";
import { StrengthPlanPanel } from "./StrengthPlanPanel";
import styles from "./TrainingProgramWorkspace.module.css";

type Sport = "running" | "strength";
export function TrainingProgramWorkspace({ onChanged, onSportFocus }: { onChanged?: () => void; onSportFocus?: (sport: Sport | null) => void }) {
  const { accessToken } = useAuth();
  const [active, setActive] = useState<Sport[]>([]);
  const [selected, setSelected] = useState<Sport>("running");
  const [other, setOther] = useState<Sport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    if (!accessToken) return;
    setError(null);
    try {
      const [running, strength] = await Promise.all([getTrainingPlans(accessToken), getStrengthPlans(accessToken)]);
      setActive([...(running.items.some((plan) => plan.status === "active") ? ["running" as const] : []), ...(strength.items.some((plan) => plan.status === "active") ? ["strength" as const] : [])]);
      setOther(null);
    } catch { setError("Non riesco a verificare il programma attivo. Riprova."); }
    finally { setLoading(false); }
  }, [accessToken]);
  useEffect(() => { if (window.location.hash === "#palestra") setSelected("strength"); void refresh(); }, [refresh]);
  useEffect(() => { if (!loading && !error) onSportFocus?.(active.length === 1 ? active[0] : null); }, [active, loading, error, onSportFocus]);
  const changed = () => { void refresh(); onChanged?.(); };
  if (loading) return <p role="status">Carico il tuo programma…</p>;
  if (error) return <p role="alert">{error} <button type="button" onClick={() => { void refresh(); }}>Riprova</button></p>;
  const both = active.length === 2;
  const sport = active.length === 1 ? active[0] : selected;
  const panel = (kind: Sport) => kind === "strength" ? <StrengthPlanPanel showCombinedCoach={both} onProgramChanged={changed} /> : <RunningPlanBuilder onCreated={changed} />;
  return <>
    {active.length !== 1 ? <div className={styles.tabs} role="tablist" aria-label="Programmi" onKeyDown={(event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault(); const next = event.key === "Home" ? "running" : event.key === "End" ? "strength" : selected === "running" ? "strength" : "running";
      setSelected(next); document.getElementById(`${next}-tab`)?.focus();
    }}>{(["running", "strength"] as const).map((kind) => <button id={`${kind}-tab`} key={kind} type="button" role="tab" aria-selected={sport === kind} tabIndex={sport === kind ? 0 : -1} aria-controls="program-panel" onClick={() => setSelected(kind)}>{kind === "running" ? "Corsa" : "Palestra"}</button>)}</div> : <h2 className={styles.title}>{sport === "strength" ? "Il tuo programma palestra" : "Il tuo programma corsa"}</h2>}
    <div id="program-panel" role={active.length === 1 ? undefined : "tabpanel"} aria-labelledby={active.length === 1 ? undefined : `${sport}-tab`}>{panel(sport)}</div>
    {active.length === 1 ? <details className={styles.other}><summary>Altri programmi</summary><p>Se vuoi affiancare un secondo sport, puoi creare un altro programma qui.</p>
      <button type="button" onClick={() => setOther(sport === "strength" ? "running" : "strength")}>Crea un programma {sport === "strength" ? "corsa" : "palestra"}</button>
      {other ? <div>{panel(other)}</div> : null}
    </details> : null}
  </>;
}
