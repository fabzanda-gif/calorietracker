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
    <div className={styles.preview} aria-label="Anteprima della Home SanoSync">
      <aside className={styles.previewNav}>
        <Image
          src="/assets/LogoCoral.png"
          alt=""
          width={82}
          height={81}
          aria-hidden="true"
        />
        <span className={styles.previewNavActive}>⌂ <b>Oggi</b></span>
        <span>⌁ <b>Attività</b></span>
        <span>↗ <b>Progressi</b></span>
        <span>◇ <b>Ricette</b></span>
      </aside>

      <div className={styles.previewContent}>
        <div className={styles.previewGreeting}>
          <div>
            <strong>Buongiorno, Fabio <span aria-hidden="true">👋</span></strong>
            <small>La tua giornata è pronta. Il piano si adatta a ciò che succede.</small>
          </div>
          <span className={styles.previewMode}>Standard</span>
        </div>

        <div className={styles.previewHabit}>
          <div>
            <small>ABITUDINE RICONOSCIUTA</small>
            <strong>Sei andato in ufficio in bicicletta anche oggi?</strong>
          </div>
          <span>Sì, registrala</span>
        </div>

        <div className={styles.previewPlan}>
          <div className={styles.previewPlanTitle}>
            <small>IL TUO PIANO DI OGGI</small>
            <strong>Quanto posso ancora mangiare oggi?</strong>
          </div>
          <div>
            <span>Consumate oggi</span>
            <strong>0 <small>kcal</small></strong>
          </div>
          <div>
            <span>Puoi ancora mangiare</span>
            <strong>2.305 <small>kcal</small></strong>
          </div>
          <p><i aria-hidden="true">◎</i> Il piano è pronto e si adatterà alla giornata.</p>
        </div>

        <div className={styles.previewColumns}>
          <div className={styles.previewSummary}>
            <div className={styles.previewCardTitle}>
              <strong>▤ Resoconto giornaliero</strong>
              <span>＋ Aggiungi</span>
            </div>
            <p><b>🧺 Dispensa</b><small>2 alimenti disponibili</small></p>
            <p><b>☕ Colazione</b><small>Colazione Casa · 235 kcal</small></p>
          </div>
          <div className={styles.previewAi}>
            <div className={styles.previewCardTitle}>
              <strong>✦ SanoSync AI</strong>
              <span>Tutto in un input</span>
            </div>
            <p>Racconta la tua giornata, penso io al resto.</p>
            <div>Scrivi cosa hai mangiato o fatto…</div>
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
            <p className={styles.eyebrow}>LA TUA GIORNATA, SOTTO CONTROLLO</p>
            <h1>Tutto ciò che ti serve. Senza doverlo cercare.</h1>
            <p className={styles.intro}>
              SanoSync collega pasti, dispensa, allenamenti e progressi per anticipare ciò che ti serve e rendere ogni registrazione più semplice.
            </p>
          </div>
          <ProductPreview />
          <div className={styles.benefits}>
            <span><i aria-hidden="true">◎</i>Piano predittivo</span>
            <span><i aria-hidden="true">✦</i>Tutto connesso</span>
            <span><i aria-hidden="true">↗</i>Logging immediato</span>
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
