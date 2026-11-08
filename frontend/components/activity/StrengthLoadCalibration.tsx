"use client";
import { useState } from "react";
import type { StrengthWorkoutExercise } from "@/lib/api/strength";
import { estimatedMax, roundLoadDown, suggestedReps, weightConvention } from "@/lib/strengthRecommendations";
import styles from "./StrengthLoadCalibration.module.css";

export type CalibrationResult = { reps: number; loadKg: number; rir: number; feeling: "easy" | "right" };
export function StrengthLoadCalibration({ exercise, onConfirm, onKnownMax, allowTest = true, initialMode = "choose" }: { exercise: StrengthWorkoutExercise; onConfirm?: (result: CalibrationResult) => Promise<boolean>; onKnownMax: (maxKg: number) => Promise<boolean>; allowTest?: boolean; initialMode?: "choose" | "known" | "test" }) {
  const [mode, setMode] = useState<"choose" | "known" | "test">(initialMode);
  const [knownMax, setKnownMax] = useState("");
  const target = Math.min(12, Math.max(6, suggestedReps(exercise)));
  const [load, setLoad] = useState("");
  const [reps, setReps] = useState(String(target));
  const [reserve, setReserve] = useState<"easy" | "right" | "hard" | "stop" | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const kg = Number(load.replace(",", "."));
  const count = Number(reps);
  const valid = load.trim() !== "" && Number.isFinite(kg) && kg >= 0 && kg <= 1000 && Number.isInteger(count) && count >= 6 && count <= 12;
  const max = valid && (reserve === "right" || reserve === "easy") ? estimatedMax(kg, count, reserve === "easy" ? 4 : 2) : undefined;
  const proposed = max == null ? kg : Math.min(kg, roundLoadDown(max / (1 + (suggestedReps(exercise) + (exercise.target_rir ?? 2)) / 30)));
  async function confirm() {
    if (!onConfirm || !valid || (reserve !== "right" && reserve !== "easy")) return;
    setSaving(true); setError(null);
    try {
      if (!await onConfirm({ reps: count, loadKg: kg, rir: reserve === "easy" ? 4 : 2, feeling: reserve })) setError("La prima serie non è stata salvata. Riprova: i dati inseriti restano qui.");
    } finally { setSaving(false); }
  }
  return <section className={styles.card} aria-label="Troviamo il tuo peso iniziale">
    <span>Il carico per questo esercizio</span><h4>Troviamo il tuo peso iniziale</h4>
    <div className={styles.choices}><button type="button" aria-pressed={mode === "known"} onClick={() => setMode("known")}>Conosco già il mio massimale</button><button type="button" aria-pressed={mode === "test"} onClick={() => setMode("test")}>Non lo conosco: guidami</button></div>
    {mode === "known" ? <div className={styles.result}><details><summary>Quale peso devo inserire?</summary><p>Inserisci un massimale recente per questo preciso esercizio e la stessa attrezzatura. È il peso massimo per una ripetizione completa, non il peso da usare oggi.</p><p>{weightConvention(exercise)}</p></details>
      <label>Massimale conosciuto (kg)<input autoFocus={initialMode === "known"} type="number" min="0.5" max="2000" step="0.5" value={knownMax} onChange={(event) => setKnownMax(event.target.value)} disabled={saving} /></label>
      <p>Calcoleremo un peso di partenza per {suggestedReps(exercise)} ripetizioni con margine, da verificare durante la seduta.</p>
      {Number(knownMax) > 0 && Number(knownMax) <= 2000 ? <p><strong>Peso proposto: {Math.min(1000, roundLoadDown(Number(knownMax) / (1 + (suggestedReps(exercise) + (exercise.target_rir ?? 2)) / 30)))} kg × {suggestedReps(exercise)} ripetizioni</strong></p> : null}
      <button type="button" disabled={saving || !knownMax.trim() || !Number.isFinite(Number(knownMax)) || Number(knownMax) <= 0 || Number(knownMax) > 2000} onClick={() => { setSaving(true); setError(null); void onKnownMax(Number(knownMax)).then((ok) => { if (!ok) setError("Non riesco a salvare il massimale. Riprova."); }).finally(() => setSaving(false)); }}>{saving ? "Salvo…" : "Calcola e salva il peso consigliato"}</button>
    </div> : null}
    {mode === "test" && !allowTest ? <p>Apri l’allenamento per fare una breve prova guidata con un carico leggero. Ti spieghiamo come ricavare una stima senza provare una singola ripetizione massimale.</p> : null}
    {mode === "test" && allowTest ? <>
    <ol><li>Guarda la demo e fai qualche ripetizione di riscaldamento con un carico leggero. Se il movimento è nuovo, fatti aiutare da un istruttore.</li>
      <li>Parti dal minimo carico che riesci a controllare bene. Prova {target} ripetizioni, fermandoti con ancora 2–3 ripetizioni possibili.</li>
      <li>Indica il peso effettivamente usato e come è andata. La prova serve a impostare la scheda e non viene conteggiata tra le serie allenanti.</li></ol>
    <p>{weightConvention(exercise)}</p>
    <div className={styles.fields}><label>Peso provato (kg)<input inputMode="decimal" value={load} onChange={(event) => { setLoad(event.target.value); setReserve(null); }} placeholder="Carico minimo gestibile" disabled={saving} /></label>
      <label>Ripetizioni della prova<input type="number" min="6" max="12" value={reps} onChange={(event) => { setReps(event.target.value); setReserve(null); }} disabled={saving} /></label></div>
    <p>Quante altre ripetizioni avresti potuto fare con una buona tecnica?</p>
    <div className={styles.choices} role="group" aria-label="Margine nella serie di prova">
      {([{ value: "easy", label: "Almeno 4" }, { value: "right", label: "2–3" }, { value: "hard", label: "0–1" }, { value: "stop", label: "Dolore o tecnica instabile" }] as const).map((option) => <button key={option.value} type="button" disabled={!valid || saving} aria-pressed={reserve === option.value} onClick={() => setReserve(option.value)}>{option.label}</button>)}
    </div>
    {reserve === "hard" ? <p role="status">Il carico è troppo impegnativo per partire. Recupera e riprova con un peso inferiore{valid && kg > 0 ? `: circa ${Math.max(0, roundLoadDown(kg * .9))} kg, o lo scatto disponibile inferiore` : ""}. Non cercare il massimo.</p> : null}
    {reserve === "stop" ? <p role="status">Interrompi la prova. Se senti dolore non proseguire; chiedi assistenza prima di riprovare. Puoi scegliere un esercizio alternativo.</p> : null}
    {valid && (reserve === "easy" || reserve === "right") ? <div className={styles.result}><strong>Partiamo da {proposed} kg × {suggestedReps(exercise)} ripetizioni</strong><p>Usiamo questa prova come riferimento, senza aumentare automaticamente il peso. Nelle serie successive troverai già i valori suggeriti.</p>
      {max != null ? <details><summary>Come stimiamo il carico</summary><p>Massimale stimato orientativo: circa {max} kg, ricavato da peso, ripetizioni e margine dichiarato. Usiamo una stima di tipo Epley: peso × [1 + (ripetizioni + margine) / 30]. Non è un peso da provare e non sostituisce una valutazione tecnica.</p></details> : <p>0 kg significa nessun peso esterno aggiunto.</p>}
      <button type="button" onClick={() => { void confirm(); }} disabled={saving}>{saving ? "Salvo…" : "Usa questo peso nella scheda"}</button>
    </div> : null}
    {load && !valid ? <p role="status">Inserisci un peso valido e da 6 a 12 ripetizioni controllate.</p> : null}
    </> : null}
    {error ? <p role="alert">{error}</p> : null}
  </section>;
}
