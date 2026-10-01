"use client";

import { useState } from "react";
import Link from "next/link";

import { updateProfile } from "@/lib/api/profile";
import { createWeight } from "@/lib/api/weight";
import { useI18n } from "@/components/i18n/I18nProvider";

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
  const { t } = useI18n();
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
  const [adjustment, setAdjustment] = useState("300");
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
      setError(t("onboardingRequired"));
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
          goalMode === "maintenance" ? 0 : Number(adjustment),
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
          : t("profileSaveFailed"),
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
        <div className={styles.progress} aria-label={t("onboardingStep")}>
          <span className={styles.progressActive} />
          <span className={step === "profile" ? styles.progressActive : ""} />
        </div>

        {step === "welcome" ? (
          <div className={styles.welcome}>
            <img src="/assets/LogoCoral.png" alt="SanoSync" />
            <p className={styles.eyebrow}>{t("onboardingWelcome")}</p>
            <h1 id="welcome-title">{t("onboardingTitle")}</h1>
            <p>
              {t("onboardingIntro")}
            </p>
            <div className={styles.features}>
              <span>◎ {t("personalCalorieBudget")}</span>
              <span>✦ {t("mealsActivitiesTogether")}</span>
              <span>↗ {t("clearProgress")}</span>
            </div>
            <button type="button" onClick={() => setStep("profile")}>
              {t("configurePlan")}
            </button>
          </div>
        ) : (
          <form className={styles.form} onSubmit={completeJourney}>
            <p className={styles.eyebrow}>{t("startingPoint")}</p>
            <h1 id="welcome-title">{t("createPlanTitle")}</h1>
            <p className={styles.intro}>
              {t("createPlanIntro")}
            </p>

            <div className={styles.grid}>
              <label>
                <span>{t("name")}</span>
                <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="given-name" />
              </label>
              <label>
                <span>{t("bmrFormula")}</span>
                <select value={gender} onChange={(e) => setGender(e.target.value)} required>
                  <option value="">{t("select")}</option>
                  <option value="female">{t("female")}</option>
                  <option value="male">{t("male")}</option>
                </select>
              </label>
              <label>
                <span>{t("birthDate")}</span>
                <input type="date" value={birthDate} onChange={(e) => setBirthDate(e.target.value)} required />
              </label>
              <label>
                <span>{t("heightCm")}</span>
                <input type="number" min="100" max="250" value={height} onChange={(e) => setHeight(e.target.value)} required />
              </label>
              <label>
                <span>{t("currentWeightKg")}</span>
                <input type="number" min="30" max="350" step="0.1" value={weight} onChange={(e) => setWeight(e.target.value)} required />
              </label>
              <label>
                <span>{t("targetWeightKg")} <small>{t("optional")}</small></span>
                <input type="number" min="30" max="350" step="0.1" value={targetWeight} onChange={(e) => setTargetWeight(e.target.value)} />
              </label>
              <label className={styles.fullWidth}>
                <span>{t("goal")}</span>
                <select value={goalMode} onChange={(e) => setGoalMode(e.target.value)}>
                  <option value="loss">{t("loseWeight")}</option>
                  <option value="maintenance">{t("maintainWeight")}</option>
                  <option value="gain">{t("gainWeight")}</option>
                </select>
              </label>
              {goalMode !== "maintenance" ? (
                <label className={styles.fullWidth}>
                  <span>{goalMode === "loss" ? t("lossSpeed") : t("gainSpeed")}</span>
                  <select value={adjustment} onChange={(e) => setAdjustment(e.target.value)}>
                    <option value="100">{t("slow")} · {goalMode === "loss" ? t("deficit") : t("surplus")} 100 kcal</option>
                    <option value="300">{t("balanced")} · {goalMode === "loss" ? t("deficit") : t("surplus")} 300 kcal</option>
                    <option value="500">{t("fast")} · {goalMode === "loss" ? t("deficit") : t("surplus")} 500 kcal</option>
                  </select>
                </label>
              ) : null}
            </div>

            {error ? <p className={styles.error}>{error}</p> : null}

            <div className={styles.actions}>
              <button type="button" className={styles.back} onClick={() => setStep("welcome")}>
                {t("back")}
              </button>
              <button type="submit" disabled={saving}>
                {saving ? t("creatingPlan") : t("startSanoSync")}
              </button>
            </div>
            <p className={styles.consent}>
              {t("consentContinue")}
              {" "}<Link href="/privacy">{t("privacyPolicy")}</Link> {t("consentAnd")}
              {" "}<Link href="/terms">{t("terms")}</Link>.
            </p>
          </form>
        )}
      </section>
    </div>
  );
}
