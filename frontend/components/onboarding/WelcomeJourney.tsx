"use client";

import { useState } from "react";
import Link from "next/link";

import { updateProfile } from "@/lib/api/profile";
import { createWeight } from "@/lib/api/weight";

import styles from "./WelcomeJourney.module.css";

type WelcomeJourneyProps = {
  accessToken: string;
  initialName?: string;
  testMode?: boolean;
};

export function WelcomeJourney({
  accessToken,
  initialName = "",
  testMode = false,
}: WelcomeJourneyProps) {
  const [step, setStep] = useState<"welcome" | "profile">(
    "welcome",
  );
  const [name, setName] = useState(initialName);
  const [gender, setGender] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [height, setHeight] = useState("");
  const [weight, setWeight] = useState("");
  const [targetWeight, setTargetWeight] = useState("");
  const [goalMode, setGoalMode] = useState("loss");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function completeJourney(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setError(null);

    const heightValue = Number(height);
    const weightValue = Number(weight);
    const targetWeightValue = targetWeight
      ? Number(targetWeight)
      : null;

    if (
      !gender ||
      !birthDate ||
      !Number.isFinite(heightValue) ||
      heightValue <= 0 ||
      !Number.isFinite(weightValue) ||
      weightValue <= 0
    ) {
      setError("Completa i campi necessari per calcolare il tuo piano.");
      return;
    }

    setSaving(true);

    try {
      await updateProfile(accessToken, {
        onboarding_completed: true,
        name: name.trim() || null,
        gender,
        birth_date: birthDate,
        height: heightValue,
        target_weight: targetWeightValue,
        goal_mode: goalMode,
        goal_adjustment_kcal:
          goalMode === "maintenance" ? 0 : 500,
      });

      await createWeight(
        {
          date: new Date().toISOString().slice(0, 10),
          weight: weightValue,
        },
        accessToken,
      );

      if (testMode) {
        window.sessionStorage.setItem(
          "sanosync-onboarding-test-token",
          accessToken,
        );
      }
      window.location.reload();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non siamo riusciti a salvare il profilo.",
      );
      setSaving(false);
    }
  }

  return (
    <div className={styles.backdrop} role="presentation">
      <section
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="welcome-title"
      >
        <div className={styles.progress} aria-label="Passaggio">
          <span className={styles.progressActive} />
          <span className={step === "profile" ? styles.progressActive : ""} />
        </div>

        {step === "welcome" ? (
          <div className={styles.welcome}>
            <img src="/assets/LogoCoral.png" alt="SanoSync" />
            <p className={styles.eyebrow}>Benvenuto in SanoSync</p>
            <h1 id="welcome-title">Tutto sotto controllo.</h1>
            <p>
              Registra pasti, movimento e peso. SanoSync trasforma i tuoi
              dati in un piano quotidiano semplice da seguire.
            </p>
            <div className={styles.features}>
              <span>◎ Budget calorico personale</span>
              <span>✦ Pasti e attività in un unico posto</span>
              <span>↗ Progressi chiari nel tempo</span>
            </div>
            <button type="button" onClick={() => setStep("profile")}>
              Configura il mio piano
            </button>
          </div>
        ) : (
          <form className={styles.form} onSubmit={completeJourney}>
            <p className={styles.eyebrow}>Il tuo punto di partenza</p>
            <h1 id="welcome-title">Creiamo il tuo piano.</h1>
            <p className={styles.intro}>
              Questi dati servono a stimare metabolismo e obiettivo calorico.
              Potrai modificarli in qualsiasi momento dal profilo.
            </p>

            <div className={styles.grid}>
              <label>
                <span>Nome</span>
                <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="given-name" />
              </label>
              <label>
                <span>Formula per il calcolo BMR</span>
                <select value={gender} onChange={(e) => setGender(e.target.value)} required>
                  <option value="">Seleziona</option>
                  <option value="female">Donna</option>
                  <option value="male">Uomo</option>
                </select>
              </label>
              <label>
                <span>Data di nascita</span>
                <input type="date" value={birthDate} onChange={(e) => setBirthDate(e.target.value)} required />
              </label>
              <label>
                <span>Altezza (cm)</span>
                <input type="number" min="100" max="250" value={height} onChange={(e) => setHeight(e.target.value)} required />
              </label>
              <label>
                <span>Peso attuale (kg)</span>
                <input type="number" min="30" max="350" step="0.1" value={weight} onChange={(e) => setWeight(e.target.value)} required />
              </label>
              <label>
                <span>Peso obiettivo (kg) <small>facoltativo</small></span>
                <input type="number" min="30" max="350" step="0.1" value={targetWeight} onChange={(e) => setTargetWeight(e.target.value)} />
              </label>
              <label className={styles.fullWidth}>
                <span>Obiettivo</span>
                <select value={goalMode} onChange={(e) => setGoalMode(e.target.value)}>
                  <option value="loss">Perdere peso</option>
                  <option value="maintenance">Mantenere il peso</option>
                  <option value="gain">Aumentare il peso</option>
                </select>
              </label>
            </div>

            {error ? <p className={styles.error}>{error}</p> : null}

            <div className={styles.actions}>
              <button type="button" className={styles.back} onClick={() => setStep("welcome")}>
                Indietro
              </button>
              <button type="submit" disabled={saving}>
                {saving ? "Creazione del piano..." : "Inizia con SanoSync"}
              </button>
            </div>
            <p className={styles.consent}>
              Continuando confermi di aver letto la
              {" "}<Link href="/privacy">Privacy Policy</Link> e i
              {" "}<Link href="/terms">Termini e condizioni</Link>.
            </p>
          </form>
        )}
      </section>
    </div>
  );
}
