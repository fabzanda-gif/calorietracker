"use client";

import Link from "next/link";
import Image from "next/image";
import { FormEvent, useState } from "react";

import { useAuth } from "./AuthProvider";
import styles from "./LoginCard.module.css";

function GoogleIcon() {
  return (
    <svg aria-hidden="true" className={styles.googleIcon} viewBox="0 0 24 24">
      <path fill="#4285F4" d="M21.6 12.23c0-.71-.06-1.4-.18-2.06H12v3.9h5.38a4.6 4.6 0 0 1-2 3.02v2.53h3.24c1.9-1.75 2.98-4.32 2.98-7.39Z" />
      <path fill="#34A853" d="M12 22c2.7 0 4.98-.9 6.63-2.43l-3.24-2.52c-.9.6-2.05.96-3.39.96-2.61 0-4.82-1.76-5.61-4.13H3.04v2.6A10 10 0 0 0 12 22Z" />
      <path fill="#FBBC05" d="M6.39 13.88A6.02 6.02 0 0 1 6.08 12c0-.65.11-1.29.31-1.88v-2.6H3.04A10 10 0 0 0 2 12c0 1.61.39 3.14 1.04 4.48l3.35-2.6Z" />
      <path fill="#EA4335" d="M12 5.99c1.47 0 2.79.5 3.83 1.5l2.87-2.87A9.62 9.62 0 0 0 12 2a10 10 0 0 0-8.96 5.52l3.35 2.6C7.18 7.75 9.39 5.99 12 5.99Z" />
    </svg>
  );
}

function ProductPreview() {
  return (
    <div className={styles.preview} aria-label="Anteprima della dashboard SanoSync">
      <div className={styles.previewNav}>
        <strong>SanoSync</strong>
        <span className={styles.previewNavActive}>Oggi</span>
        <span>Ricette</span>
        <span>Attività</span>
        <span>Progressi</span>
      </div>
      <div className={styles.previewContent}>
        <div className={styles.previewTop}>
          <div className={styles.calorieTile}>
            <span>Calorie giornaliere</span>
            <strong>1.680 <small>kcal</small></strong>
            <span>420 kcal rimanenti</span>
            <i aria-hidden="true">80%</i>
          </div>
          <div className={styles.stepsTile}>
            <span>Attività</span>
            <strong>8.432 <small>/ 10.000</small></strong>
            <svg aria-hidden="true" viewBox="0 0 150 36">
              <path d="M2 29 C 22 31, 32 20, 47 24 S 75 34, 89 20 S 112 19, 124 9 S 139 8, 148 3" />
            </svg>
          </div>
        </div>
        <div className={styles.mealPreview}>
          <div className={styles.previewSectionTitle}>
            <strong>I pasti di oggi</strong><span>Vedi piano</span>
          </div>
          <div className={styles.previewMeals}>
            <div><i>☕</i><span>Colazione</span><strong>Latte e cheesecake</strong><small>440 kcal</small></div>
            <div><i>🥗</i><span>Pranzo</span><strong>Pollo, riso e verdure</strong><small>620 kcal</small></div>
            <div><i>🍲</i><span>Cena</span><strong>Zuppa di legumi</strong><small>410 kcal</small></div>
          </div>
        </div>
        <div className={styles.previewBottom}>
          <div>
            <span>Peso</span><strong>72,4 <small>kg</small></strong>
            <svg aria-hidden="true" viewBox="0 0 180 30">
              <path d="M2 5 C 35 8, 50 4, 72 12 S 112 18, 129 16 S 156 25, 178 24" />
            </svg>
          </div>
          <div className={styles.routineTile}>
            <span>Routine</span><strong>4/5</strong><small>completate oggi</small>
          </div>
        </div>
      </div>
    </div>
  );
}

export function LoginCard() {
  const {
    signInWithPassword,
    signInWithGoogle,
    signUpWithPassword,
  } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      if (mode === "signup") {
        const needsConfirmation = await signUpWithPassword(
          email.trim(),
          password,
        );
        if (needsConfirmation) {
          setMessage(
            "Controlla la tua email e conferma l’account per iniziare.",
          );
        }
      } else {
        await signInWithPassword(email.trim(), password);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : mode === "signup"
          ? "Registrazione non riuscita"
          : "Accesso non riuscito",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGoogleSignIn() {
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await signInWithGoogle();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Accesso con Google non riuscito");
      setSubmitting(false);
    }
  }

  return (
    <main className={styles.page}>
      <header className={styles.topbar}>
        <a className={styles.logo} href="#" aria-label="SanoSync">
          <Image
            src="/assets/LogoCoral.png"
            alt="SanoSync"
            width={72}
            height={71}
            priority
          />
        </a>
        <nav aria-label="Link legali">
          <Link href="/privacy">Privacy</Link><Link href="/terms">Termini</Link>
        </nav>
      </header>

      <div className={styles.shell}>
        <section className={styles.hero}>
          <div className={styles.heroCopy}>
            <p className={styles.eyebrow}>IL TUO BENESSERE, IN SINCRONIA</p>
            <h1>Tutto sotto controllo.</h1>
            <p className={styles.intro}>
              SanoSync unisce alimentazione, attività, peso e routine
              quotidiane in un piano che si adatta davvero a te.
            </p>
          </div>
          <ProductPreview />
          <div className={styles.benefits}>
            <span><i aria-hidden="true">◎</i>Piano quotidiano</span>
            <span><i aria-hidden="true">✦</i>Decisioni personalizzate</span>
            <span><i aria-hidden="true">↗</i>Dati sotto controllo</span>
          </div>
        </section>

        <section className={styles.loginPanel} aria-labelledby="login-title">
          <p className={styles.brand}>SANOSYNC</p>
          <div className={styles.heading}>
            <h2 id="login-title">
              {mode === "signup" ? "Inizia da qui." : "Bentornato."}
            </h2>
            <p>
              {mode === "signup"
                ? "Crea il tuo account e configura il tuo primo piano."
                : "Accedi con lo stesso account che usi su SanoSync."}
            </p>
          </div>
          <button className={styles.googleButton} type="button" disabled={submitting} onClick={handleGoogleSignIn}>
            <GoogleIcon />
            <span>
              {mode === "signup"
                ? "Registrati con Google"
                : "Continua con Google"}
            </span>
          </button>
          <div className={styles.divider}><span>oppure</span></div>
          <form className={styles.form} onSubmit={handleSubmit}>
            <label className={styles.field}>
              <span>Email</span>
              <input type="email" autoComplete="email" placeholder="nome@esempio.com" required value={email} onChange={(event) => setEmail(event.target.value)} />
            </label>
            <label className={styles.field}>
              <span>Password</span>
              <input type="password" minLength={8} autoComplete={mode === "signup" ? "new-password" : "current-password"} placeholder={mode === "signup" ? "Almeno 8 caratteri" : "La tua password"} required value={password} onChange={(event) => setPassword(event.target.value)} />
            </label>
            {mode === "signup" ? (
              <label className={styles.legalConsent}>
                <input type="checkbox" required />
                <span>
                  Accetto i <Link href="/terms">Termini e condizioni</Link>
                  {" "}e dichiaro di aver letto la
                  {" "}<Link href="/privacy">Privacy Policy</Link>.
                </span>
              </label>
            ) : null}
            {error ? <p className={styles.error} role="alert">{error}</p> : null}
            {message ? <p className={styles.success} role="status">{message}</p> : null}
            <button className={styles.button} type="submit" disabled={submitting}>
              {submitting
                ? mode === "signup" ? "Creazione account…" : "Accesso…"
                : mode === "signup" ? "Crea account" : "Accedi"}
            </button>
          </form>
          <p className={styles.authSwitch}>
            {mode === "signup" ? "Hai già un account?" : "Non hai ancora un account?"}
            <button
              type="button"
              onClick={() => {
                setMode(mode === "signup" ? "login" : "signup");
                setError(null);
                setMessage(null);
              }}
            >
              {mode === "signup" ? "Accedi" : "Registrati"}
            </button>
          </p>
          <p className={styles.securityNote}>
            <span aria-hidden="true">✓</span>
            I tuoi dati restano privati e sotto il tuo controllo.
          </p>
          <footer className={styles.legalFooter}>
            <Link href="/privacy">Privacy Policy</Link>
            <span aria-hidden="true">·</span>
            <Link href="/terms">Termini e condizioni</Link>
          </footer>
        </section>
      </div>
    </main>
  );
}
