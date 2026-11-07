"use client";

import Link from "next/link";
import Image from "next/image";
import { FormEvent, useState } from "react";

import { useAuth } from "./AuthProvider";
import { useI18n } from "@/components/i18n/I18nProvider";
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
  const { t } = useI18n();

  return (
    <div className={styles.preview} aria-label={t("previewHomeLabel")}>
      <aside className={styles.previewNav}>
        <Image
          src="/assets/LogoCoral.png"
          alt=""
          width={82}
          height={81}
          aria-hidden="true"
        />
        <span className={styles.previewNavActive}>⌂ <b>{t("today")}</b></span>
        <span>⌁ <b>{t("activities")}</b></span>
        <span>↗ <b>{t("progress")}</b></span>
        <span>◇ <b>{t("recipes")}</b></span>
      </aside>

      <div className={styles.previewContent}>
        <div className={styles.previewGreeting}>
          <div>
            <strong>{t("previewGreeting")} <span aria-hidden="true">👋</span></strong>
            <small>{t("previewDayReady")}</small>
          </div>
          <span className={styles.previewMode}>Standard</span>
        </div>

        <div className={styles.previewHabit}>
          <div>
            <small>{t("recognizedHabit")}</small>
            <strong>{t("bikeOfficeQuestion")}</strong>
          </div>
          <span>{t("yesLogIt")}</span>
        </div>

        <div className={styles.previewPlan}>
          <div className={styles.previewPlanTitle}>
            <small>{t("todayPlan")}</small>
            <strong>{t("remainingQuestion")}</strong>
          </div>
          <div>
            <span>{t("consumedToday")}</span>
            <strong>0 <small>kcal</small></strong>
          </div>
          <div>
            <span>{t("canStillEat")}</span>
            <strong>2.305 <small>kcal</small></strong>
          </div>
          <p><i aria-hidden="true">◎</i> {t("planReady")}</p>
        </div>

        <div className={styles.previewColumns}>
          <div className={styles.previewSummary}>
            <div className={styles.previewCardTitle}>
              <strong>▤ {t("dailySummary")}</strong>
              <span>＋ {t("add")}</span>
            </div>
            <p><b>🧺 {t("pantry")}</b><small>{t("availableItems")}</small></p>
            <p><b>☕ {t("breakfast")}</b><small>{t("homeBreakfast")}</small></p>
          </div>
          <div className={styles.previewAi}>
            <div className={styles.previewCardTitle}>
              <strong>✦ SanoSync AI</strong>
              <span>{t("allInOneInput")}</span>
            </div>
            <p>{t("aiIntro")}</p>
            <div>{t("aiPlaceholder")}</div>
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
  const { t } = useI18n();
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
            t("confirmationEmail"),
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
          ? t("signupFailed")
          : t("loginFailed"),
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
      setError(err instanceof Error ? err.message : t("googleFailed"));
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
        <nav aria-label={t("legalNavigation")}>
          <Link href="/privacy">{t("privacyPolicy")}</Link><Link href="/terms">{t("terms")}</Link>
        </nav>
      </header>

      <div className={styles.shell}>
        <section className={styles.hero}>
          <div className={styles.heroCopy}>
            <p className={styles.eyebrow}>{t("landingEyebrow")}</p>
            <h1>{t("landingTitle")}</h1>
            <p className={styles.intro}>
              {t("landingIntro")}
            </p>
          </div>
          <ProductPreview />
          <div className={styles.benefits}>
            <span><i aria-hidden="true">◎</i>{t("predictivePlan")}</span>
            <span><i aria-hidden="true">✦</i>{t("everythingConnected")}</span>
            <span><i aria-hidden="true">↗</i>{t("instantLogging")}</span>
          </div>
        </section>

        <section className={styles.loginPanel} aria-labelledby="login-title">
          <p className={styles.brand}>SANOSYNC</p>
          <div className={styles.heading}>
            <h2 id="login-title">
              {mode === "signup" ? t("startHere") : t("welcomeBack")}
            </h2>
            <p>
              {mode === "signup"
                ? t("signupIntro")
                : t("loginIntro")}
            </p>
          </div>
          <button className={styles.googleButton} type="button" disabled={submitting} onClick={handleGoogleSignIn}>
            <GoogleIcon />
            <span>
              {mode === "signup"
                ? t("signupGoogle")
                : t("continueGoogle")}
            </span>
          </button>
          <div className={styles.divider}><span>{t("or")}</span></div>
          <form className={styles.form} onSubmit={handleSubmit}>
            <label className={styles.field}>
              <span>{t("email")}</span>
              <input type="email" autoComplete="email" placeholder={t("emailPlaceholder")} required value={email} onChange={(event) => setEmail(event.target.value)} />
            </label>
            <label className={styles.field}>
              <span>{t("password")}</span>
              <input type="password" minLength={8} autoComplete={mode === "signup" ? "new-password" : "current-password"} placeholder={mode === "signup" ? t("newPasswordPlaceholder") : t("passwordPlaceholder")} required value={password} onChange={(event) => setPassword(event.target.value)} />
            </label>
            {mode === "signup" ? (
              <label className={styles.legalConsent}>
                <input type="checkbox" required />
                <span>
                  {t("consentPrefix")} <Link href="/terms">{t("terms")}</Link>
                  {" "}{t("consentMiddle")}
                  {" "}<Link href="/privacy">{t("privacyPolicy")}</Link>.
                </span>
              </label>
            ) : null}
            {error ? <p className={styles.error} role="alert">{error}</p> : null}
            {message ? <p className={styles.success} role="status">{message}</p> : null}
            <button className={styles.button} type="submit" disabled={submitting}>
              {submitting
                ? mode === "signup" ? t("creatingAccount") : t("signingIn")
                : mode === "signup" ? t("createAccount") : t("login")}
            </button>
          </form>
          <p className={styles.authSwitch}>
            {mode === "signup" ? t("haveAccount") : t("noAccount")}
            <button
              type="button"
              onClick={() => {
                setMode(mode === "signup" ? "login" : "signup");
                setError(null);
                setMessage(null);
              }}
            >
              {mode === "signup" ? t("login") : t("register")}
            </button>
          </p>
          <p className={styles.securityNote}>
            <span aria-hidden="true">✓</span>
            {t("privacyNote")}
          </p>
          <footer className={styles.legalFooter}>
            <Link href="/privacy">{t("privacyPolicy")}</Link>
            <span aria-hidden="true">·</span>
            <Link href="/terms">{t("terms")}</Link>
          </footer>
        </section>
      </div>
    </main>
  );
}
