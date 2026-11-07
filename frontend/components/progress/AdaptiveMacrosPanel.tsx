"use client";

import { useEffect, useState } from "react";
import {
  applyAdaptiveMacroProposal,
  getAdaptiveMacroPreview,
  type AdaptiveMacroPreview,
} from "@/lib/api/adaptive-macros";
import styles from "./AdaptiveMacrosPanel.module.css";

type Props = { accessToken: string };

export function AdaptiveMacrosPanel({ accessToken }: Props) {
  const [preview, setPreview] = useState<AdaptiveMacroPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [completeLogging, setCompleteLogging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getAdaptiveMacroPreview(accessToken)
      .then((result) => {
        if (active) setPreview(result);
      })
      .catch(() => {
        if (active) setError("Impossibile analizzare i dati nutrizionali.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [accessToken]);

  async function apply() {
    if (!preview?.proposal || !confirmed || !completeLogging || saving) return;
    setSaving(true);
    setError(null);
    try {
      const result = await applyAdaptiveMacroProposal(accessToken, preview.preview_id);
      setSuccess(
        `Obiettivo aggiornato su tua conferma: ${Math.round(result.updated_goal_adjustment_kcal)} kcal di ${result.updated_goal_mode === "loss" ? "deficit" : "surplus"}.`,
      );
      setPreview(null);
    } catch {
      setError(
        "La proposta non è più valida o non è stato possibile salvarla. " +
        "Aggiorna la pagina per ricalcolare i dati.",
      );
    } finally {
      setSaving(false);
    }
  }

  const observed = preview?.observed;
  const proposed = preview?.proposal;

  return (
    <section className={styles.panel} aria-labelledby="adaptive-macros-title">
      <header>
        <p className={styles.kicker}>Phase 8 · Adaptive Macros</p>
        <h2 id="adaptive-macros-title">Adattamento nutrizionale consapevole</h2>
        <p className={styles.muted}>
          Analisi delle ultime quattro settimane: peso, alimentazione
          registrata e giorni di allenamento. Nessun obiettivo cambia
          senza che tu lo confermi.
        </p>
      </header>
      {loading && <p>Analisi delle osservazioni…</p>}
      {error && <p role="alert" className={styles.error}>{error}</p>}
      {preview && observed && (
        <>
          <div className={styles.metrics}>
            <div>
              <strong>{observed.logged_meal_days}/28</strong>
              <span>Giorni con pasti</span>
            </div>
            <div>
              <strong>{observed.weight_measurements}</strong>
              <span>Pesate</span>
            </div>
            <div>
              <strong>
                {observed.weight_change_pct_per_week === null
                  ? "—"
                  : `${observed.weight_change_pct_per_week > 0 ? "+" : ""}${observed.weight_change_pct_per_week.toFixed(2)}%`}
              </strong>
              <span>Trend peso / settimana</span>
            </div>
            <div>
              <strong>{observed.mean_logged_protein_g === null
                ? "—" : `${Math.round(observed.mean_logged_protein_g)} g`}</strong>
              <span>Proteine medie nei giorni registrati</span>
            </div>
          </div>
          <div className={styles.context}>
            <h3>Contesto alimentazione e allenamento</h3>
            <p>
              Giorni con allenamento e pasti: {observed.training_days_with_meals}.
              Giorni con pasti ma nessun allenamento registrato:{" "}
              {observed.non_training_days_with_meals}.
            </p>
            <p>
              Carboidrati medi nei giorni con allenamento:{" "}
              {observed.mean_training_day_carbs_g === null
                ? "dato insufficiente"
                : `${Math.round(observed.mean_training_day_carbs_g)} g`}.
              Negli altri giorni registrati:{" "}
              {observed.mean_other_day_carbs_g === null
                ? "dato insufficiente"
                : `${Math.round(observed.mean_other_day_carbs_g)} g`}.
            </p>
            <p>
              Obiettivo proteico personale:{" "}
              {observed.protein_target_g === null
                ? "non impostato"
                : `${Math.round(observed.protein_target_g)} g al giorno`}.
            </p>
          </div>
          {preview.reasons.length > 0 && (
            <div className={styles.notice}>
              <strong>Perché non vengono suggeriti cambiamenti ora</strong>
              <ul>{preview.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}</ul>
            </div>
          )}
          {preview.status === "within_range" && (
            <p className={styles.muted}>
              Il trend osservato non giustifica un cambiamento del deficit
              o surplus impostato: mantenere i valori è una scelta valida.
            </p>
          )}
          {proposed && (
            <div className={styles.proposal}>
              <h3>Proposta da valutare</h3>
              <p>{proposed.reason}</p>
              <p>
                {proposed.goal_mode === "loss" ? "Deficit" : "Surplus"}:{" "}
                <strong>{Math.round(proposed.before_goal_adjustment_kcal)} kcal</strong>
                {" → "}
                <strong>{Math.round(proposed.proposed_goal_adjustment_kcal)} kcal</strong>.
                Differenza stimata nel budget base:{" "}
                {proposed.estimated_budget_change_kcal > 0 ? "+" : ""}
                {Math.round(proposed.estimated_budget_change_kcal)} kcal al giorno.
              </p>
              <label className={styles.checkbox}>
                <input
                  type="checkbox"
                  checked={completeLogging}
                  onChange={(event) => setCompleteLogging(event.target.checked)}
                />
                Confermo che i pasti registrati rappresentano in modo
                sufficientemente completo la mia alimentazione recente.
              </label>
              <label className={styles.checkbox}>
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(event) => setConfirmed(event.target.checked)}
                />
                Ho letto la proposta e voglio modificare l'obiettivo del profilo.
              </label>
              <button type="button" onClick={() => void apply()}
                disabled={!completeLogging || !confirmed || saving}>
                {saving ? "Salvataggio…" : "Conferma adattamento"}
              </button>
            </div>
          )}
          <p className={styles.disclaimer}>
            Il trend non misura il dispendio calorico reale. Giorni senza
            pasti non significano digiuno. Il confronto dei carboidrati è
            descrittivo, non un obiettivo nuovo. Per esigenze mediche o
            alimentari specifiche usa un professionista qualificato.
          </p>
        </>
      )}
      {success && <p role="status" className={styles.success}>{success}</p>}
    </section>
  );
}
