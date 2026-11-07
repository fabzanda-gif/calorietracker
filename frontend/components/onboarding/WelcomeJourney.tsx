"use client";

import {
  useMemo,
  useState,
} from "react";
import Link from "next/link";

import {
  saveNutritionSetup,
  saveOnboardingCore,
  saveTrainingSetup,
  type OnboardingStatus,
  type PrimaryGoal,
} from "@/lib/api/onboarding";
import { updateProfile } from "@/lib/api/profile";
import { createWeight } from "@/lib/api/weight";
import { useI18n } from "@/components/i18n/I18nProvider";

import styles from "./WelcomeJourney.module.css";


type Step =
  | "welcome"
  | "goal"
  | "modules"
  | "food"
  | "training"
  | "summary";

type WelcomeJourneyProps = {
  accessToken: string;
  initialName?: string;
  initialStatus?: OnboardingStatus | null;
  testMode?: boolean;
};

const MUSCLES = [
  "chest",
  "back",
  "shoulders",
  "biceps",
  "triceps",
  "glutes",
  "quadriceps",
  "hamstrings",
  "calves",
  "core",
] as const;

const WEEKDAYS = [
  { value: 1, it: "Lun", en: "Mon" },
  { value: 2, it: "Mar", en: "Tue" },
  { value: 3, it: "Mer", en: "Wed" },
  { value: 4, it: "Gio", en: "Thu" },
  { value: 5, it: "Ven", en: "Fri" },
  { value: 6, it: "Sab", en: "Sat" },
  { value: 7, it: "Dom", en: "Sun" },
];

const MUSCLE_LABELS: Record<
  (typeof MUSCLES)[number],
  { it: string; en: string }
> = {
  chest: { it: "Petto", en: "Chest" },
  back: { it: "Schiena", en: "Back" },
  shoulders: { it: "Spalle", en: "Shoulders" },
  biceps: { it: "Bicipiti", en: "Biceps" },
  triceps: { it: "Tricipiti", en: "Triceps" },
  glutes: { it: "Glutei", en: "Glutes" },
  quadriceps: { it: "Quadricipiti", en: "Quadriceps" },
  hamstrings: { it: "Femorali", en: "Hamstrings" },
  calves: { it: "Polpacci", en: "Calves" },
  core: { it: "Core", en: "Core" },
};


function initialStep(
  status?: OnboardingStatus | null,
): Step {
  if (status?.next_step === "food_setup") {
    return "food";
  }

  if (status?.next_step === "training_setup") {
    return "training";
  }

  return "welcome";
}


export function WelcomeJourney({
  accessToken,
  initialName = "",
  initialStatus = null,
  testMode = false,
}: WelcomeJourneyProps) {
  const { locale, t } = useI18n();
  const lang = locale === "it" ? "it" : "en";

  const copy = lang === "it"
    ? {
        welcomeEyebrow: "Benvenuto in SanoSync",
        welcomeTitle: "Costruiamolo intorno a te.",
        welcomeIntro:
          "Scegli il tuo obiettivo e usa solo le parti di SanoSync che ti servono. Potrai attivare Food o Training anche più avanti.",
        start: "Inizia",
        goalEyebrow: "Il tuo obiettivo",
        goalTitle: "Da dove vuoi partire?",
        goalIntro:
          "Scegli l'obiettivo principale. SanoSync userà questo contesto per personalizzare allenamento e nutrizione.",
        muscle: "Aumentare massa muscolare",
        muscleHelp: "Costruisci muscolo e monitora i progressi.",
        strength: "Aumentare la forza",
        strengthHelp: "Migliora progressivamente le prestazioni.",
        fitness: "Fitness generale",
        fitnessHelp: "Allenati con continuità e migliora la forma fisica.",
        modulesEyebrow: "La tua esperienza",
        modulesTitle: "Come vuoi usare SanoSync?",
        modulesIntro:
          "Food e Training funzionano anche separatamente. Insieme possono condividere più contesto.",
        training: "Training",
        trainingHelp: "Programmi personalizzati, workout e progressione.",
        food: "Food",
        foodHelp: "Calorie, proteine, macro e alimentazione.",
        both: "Training + Food",
        bothHelp: "Allenamento e nutrizione lavorano insieme.",
        recommended: "Consigliato",
        continue: "Continua",
        foodEyebrow: "Setup Food",
        foodTitle: "Il tuo punto di partenza.",
        foodIntro:
          "Questi dati servono al Budget Engine. Il Training resta indipendente da questo setup.",
        strategy: "Strategia nutrizionale",
        automaticProtein: "Proteine automatiche",
        macroTracking: "Monitoraggio macro attivo",
        trainingEyebrow: "Setup Training",
        trainingTitle: "Costruiamo il tuo profilo Training.",
        trainingIntro:
          "Poche informazioni iniziali; carichi, aderenza e progressione verranno appresi dai tuoi workout.",
        experience: "Esperienza",
        beginner: "Sto iniziando",
        intermediate: "Mi alleno da un po'",
        advanced: "Sono esperto",
        sessions: "Sedute a settimana",
        duration: "Durata tipica",
        horizon: "Pianificazione",
        weekly: "Settimana per settimana",
        monthly: "4 settimane",
        coach: "Stile coach",
        conservative: "Prudente",
        balanced: "Bilanciato",
        ambitious: "Ambizioso",
        schedule: "I tuoi giorni",
        flexible: "I miei giorni cambiano spesso",
        fixed: "Preferisco giorni fissi",
        preferredDays: "Giorni preferiti",
        priorities: "Priorità muscolari",
        prioritiesHelp: "Facoltativo · massimo 3",
        summaryEyebrow: "Configurazione pronta",
        summaryTitle: "Il tuo SanoSync è pronto.",
        summaryIntro:
          "Queste scelte diventano il punto di partenza. SanoSync imparerà poi dai tuoi dati reali.",
        primaryGoal: "Obiettivo",
        modules: "Moduli",
        nutrition: "Nutrizione",
        startApp: "Inizia con SanoSync",
        required: "Completa i campi necessari.",
        selectModule: "Scegli almeno un modulo.",
        saveFailed: "Non siamo riusciti a salvare il setup.",
        noPriority: "Nessuna priorità",
      }
    : {
        welcomeEyebrow: "Welcome to SanoSync",
        welcomeTitle: "Build it around you.",
        welcomeIntro:
          "Choose your goal and use only the parts of SanoSync you need. You can enable Food or Training later too.",
        start: "Start",
        goalEyebrow: "Your goal",
        goalTitle: "Where do you want to start?",
        goalIntro:
          "Choose your main goal. SanoSync will use it to personalize training and nutrition.",
        muscle: "Build muscle",
        muscleHelp: "Build muscle and track progress.",
        strength: "Get stronger",
        strengthHelp: "Progressively improve performance.",
        fitness: "General fitness",
        fitnessHelp: "Train consistently and improve overall fitness.",
        modulesEyebrow: "Your experience",
        modulesTitle: "How do you want to use SanoSync?",
        modulesIntro:
          "Food and Training work independently. Together they can share more context.",
        training: "Training",
        trainingHelp: "Personalized programs, workouts and progression.",
        food: "Food",
        foodHelp: "Calories, protein, macros and nutrition.",
        both: "Training + Food",
        bothHelp: "Training and nutrition work together.",
        recommended: "Recommended",
        continue: "Continue",
        foodEyebrow: "Food setup",
        foodTitle: "Your starting point.",
        foodIntro:
          "These details power the Budget Engine. Training remains independent from this setup.",
        strategy: "Nutrition strategy",
        automaticProtein: "Automatic protein target",
        macroTracking: "Macro tracking enabled",
        trainingEyebrow: "Training setup",
        trainingTitle: "Build your Training profile.",
        trainingIntro:
          "Just a few starting details; loads, adherence and progression will be learned from your workouts.",
        experience: "Experience",
        beginner: "I'm starting",
        intermediate: "I have some experience",
        advanced: "I'm experienced",
        sessions: "Sessions per week",
        duration: "Typical duration",
        horizon: "Planning",
        weekly: "Week by week",
        monthly: "4 weeks",
        coach: "Coach style",
        conservative: "Conservative",
        balanced: "Balanced",
        ambitious: "Ambitious",
        schedule: "Your schedule",
        flexible: "My days often change",
        fixed: "I prefer fixed days",
        preferredDays: "Preferred days",
        priorities: "Muscle priorities",
        prioritiesHelp: "Optional · up to 3",
        summaryEyebrow: "Setup ready",
        summaryTitle: "Your SanoSync is ready.",
        summaryIntro:
          "These choices are the starting point. SanoSync will keep learning from your real data.",
        primaryGoal: "Goal",
        modules: "Modules",
        nutrition: "Nutrition",
        startApp: "Start SanoSync",
        required: "Complete the required fields.",
        selectModule: "Choose at least one module.",
        saveFailed: "We couldn't save your setup.",
        noPriority: "No priority",
      };

  const statusGoal =
    initialStatus?.preferences?.primary_goal;

  const [step, setStep] = useState<Step>(
    initialStep(initialStatus),
  );
  const [goal, setGoal] = useState<PrimaryGoal>(
    statusGoal ?? "hypertrophy",
  );

  const [foodEnabled, setFoodEnabled] =
    useState(
      initialStatus?.preferences?.food_enabled ??
        true,
    );
  const [trainingEnabled, setTrainingEnabled] =
    useState(
      initialStatus?.preferences
        ?.training_enabled ??
        true,
    );

  const [name, setName] = useState(initialName);
  const [gender, setGender] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [height, setHeight] = useState("");
  const [weight, setWeight] = useState("");
  const [targetWeight, setTargetWeight] =
    useState("");
  const [weightStrategy, setWeightStrategy] =
    useState<"loss" | "maintenance" | "gain">(
      goal === "hypertrophy"
        ? "gain"
        : "maintenance",
    );
  const [adjustment, setAdjustment] =
    useState("300");

  const [experience, setExperience] =
    useState<
      "beginner" | "intermediate" | "advanced"
    >("intermediate");
  const [sessions, setSessions] = useState(3);
  const [duration, setDuration] = useState(60);
  const [planningHorizon, setPlanningHorizon] =
    useState<"weekly" | "monthly">("weekly");
  const [coachStyle, setCoachStyle] =
    useState<
      "conservative" | "balanced" | "ambitious"
    >("balanced");
  const [
    scheduleFlexibility,
    setScheduleFlexibility,
  ] = useState<"fixed" | "flexible">(
    "flexible",
  );
  const [preferredDays, setPreferredDays] =
    useState<number[]>([1, 3, 5]);
  const [
    priorityMuscles,
    setPriorityMuscles,
  ] = useState<string[]>([]);

  const [saving, setSaving] = useState(false);
  const [error, setError] =
    useState<string | null>(null);

  const progressIndex = useMemo(() => {
    const map: Record<Step, number> = {
      welcome: 0,
      goal: 1,
      modules: 2,
      food: 3,
      training: 4,
      summary: 5,
    };
    return map[step];
  }, [step]);

  function chooseGoal(next: PrimaryGoal) {
    setGoal(next);
    setWeightStrategy(
      next === "hypertrophy"
        ? "gain"
        : "maintenance",
    );
  }

  function toggleDay(day: number) {
    setPreferredDays((current) =>
      current.includes(day)
        ? current.filter((item) => item !== day)
        : [...current, day].sort(
            (left, right) => left - right,
          ),
    );
  }

  function togglePriority(key: string) {
    setPriorityMuscles((current) => {
      if (current.includes(key)) {
        return current.filter(
          (item) => item !== key,
        );
      }

      if (current.length >= 3) {
        return current;
      }

      return [...current, key];
    });
  }

  async function saveCore() {
    if (!foodEnabled && !trainingEnabled) {
      setError(copy.selectModule);
      return;
    }

    setSaving(true);
    setError(null);

    try {
      await saveOnboardingCore(
        accessToken,
        {
          primary_goal: goal,
          food_enabled: foodEnabled,
          training_enabled: trainingEnabled,
        },
      );

      if (foodEnabled) {
        setStep("food");
      } else if (trainingEnabled) {
        setStep("training");
      } else {
        setStep("summary");
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : copy.saveFailed,
      );
    } finally {
      setSaving(false);
    }
  }

  async function saveFood() {
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
      setError(copy.required);
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const adjustmentValue =
        weightStrategy === "maintenance"
          ? 0
          : Number(adjustment);

      await updateProfile(accessToken, {
        onboarding_completed: true,
        name: name.trim() || null,
        gender,
        birth_date: birthDate,
        height: heightValue,
        target_weight: targetWeightValue,
        goal_mode: weightStrategy,
        goal_adjustment_kcal:
          adjustmentValue,
      });

      await createWeight(
        {
          date: new Date()
            .toISOString()
            .slice(0, 10),
          weight: weightValue,
        },
        accessToken,
      );

      await saveNutritionSetup(
        accessToken,
        {
          weight_strategy: weightStrategy,
          target_weight_kg:
            targetWeightValue,
          calorie_adjustment_kcal:
            adjustmentValue,
          protein_target_mode: "automatic",
          protein_target_g: null,
          macro_tracking_enabled: true,
        },
      );

      setStep(
        trainingEnabled
          ? "training"
          : "summary",
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : copy.saveFailed,
      );
    } finally {
      setSaving(false);
    }
  }

  async function saveTraining() {
    if (
      scheduleFlexibility === "fixed" &&
      preferredDays.length === 0
    ) {
      setError(copy.required);
      return;
    }

    setSaving(true);
    setError(null);

    try {
      await saveTrainingSetup(
        accessToken,
        {
          experience_level: experience,
          sessions_per_week: sessions,
          session_duration_minutes: duration,
          planning_horizon:
            planningHorizon,
          environment: "commercial_gym",
          coach_style: coachStyle,
          feedback_mode: "simple",
          schedule_flexibility:
            scheduleFlexibility,
          preferred_days:
            scheduleFlexibility === "fixed"
              ? preferredDays
              : [],
          priority_muscles:
            priorityMuscles,
        },
      );

      setStep("summary");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : copy.saveFailed,
      );
    } finally {
      setSaving(false);
    }
  }

  function finish() {
    if (testMode) {
      window.sessionStorage.setItem(
        "sanosync-onboarding-test-token",
        accessToken,
      );
    }

    window.location.reload();
  }

  const goalLabel = {
    hypertrophy: copy.muscle,
    strength: copy.strength,
    general_fitness: copy.fitness,
  }[goal];

  const moduleLabel =
    foodEnabled && trainingEnabled
      ? copy.both
      : trainingEnabled
        ? copy.training
        : copy.food;

  return (
    <div
      className={styles.backdrop}
      role="presentation"
    >
      <section
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="welcome-title"
      >
        <div
          className={styles.progress}
          aria-label={t("onboardingStep")}
        >
          {Array.from({ length: 6 }).map(
            (_, index) => (
              <span
                key={index}
                className={
                  index <= progressIndex
                    ? styles.progressActive
                    : ""
                }
              />
            ),
          )}
        </div>

        {step === "welcome" ? (
          <div className={styles.welcome}>
            <img
              src="/assets/LogoCoral.png"
              alt="SanoSync"
            />
            <p className={styles.eyebrow}>
              {copy.welcomeEyebrow}
            </p>
            <h1 id="welcome-title">
              {copy.welcomeTitle}
            </h1>
            <p>{copy.welcomeIntro}</p>

            <div className={styles.features}>
              <span>◎ {copy.food}</span>
              <span>↗ {copy.training}</span>
              <span>✦ {copy.both}</span>
            </div>

            <button
              type="button"
              onClick={() => setStep("goal")}
            >
              {copy.start}
            </button>
          </div>
        ) : null}

        {step === "goal" ? (
          <div>
            <p className={styles.eyebrow}>
              {copy.goalEyebrow}
            </p>
            <h1 id="welcome-title">
              {copy.goalTitle}
            </h1>
            <p className={styles.intro}>
              {copy.goalIntro}
            </p>

            <div className={styles.choiceGrid}>
              {([
                [
                  "hypertrophy",
                  copy.muscle,
                  copy.muscleHelp,
                ],
                [
                  "strength",
                  copy.strength,
                  copy.strengthHelp,
                ],
                [
                  "general_fitness",
                  copy.fitness,
                  copy.fitnessHelp,
                ],
              ] as const).map(
                ([value, title, description]) => (
                  <button
                    key={value}
                    type="button"
                    className={
                      goal === value
                        ? styles.choiceActive
                        : styles.choice
                    }
                    onClick={() =>
                      chooseGoal(value)
                    }
                  >
                    <strong>{title}</strong>
                    <span>{description}</span>
                  </button>
                ),
              )}
            </div>

            <div className={styles.actions}>
              <button
                type="button"
                className={styles.back}
                onClick={() =>
                  setStep("welcome")
                }
              >
                {t("back")}
              </button>
              <button
                type="button"
                onClick={() =>
                  setStep("modules")
                }
              >
                {copy.continue}
              </button>
            </div>
          </div>
        ) : null}

        {step === "modules" ? (
          <div>
            <p className={styles.eyebrow}>
              {copy.modulesEyebrow}
            </p>
            <h1 id="welcome-title">
              {copy.modulesTitle}
            </h1>
            <p className={styles.intro}>
              {copy.modulesIntro}
            </p>

            <div className={styles.choiceGrid}>
              <button
                type="button"
                className={
                  trainingEnabled &&
                  !foodEnabled
                    ? styles.choiceActive
                    : styles.choice
                }
                onClick={() => {
                  setTrainingEnabled(true);
                  setFoodEnabled(false);
                }}
              >
                <strong>{copy.training}</strong>
                <span>{copy.trainingHelp}</span>
              </button>

              <button
                type="button"
                className={
                  foodEnabled &&
                  !trainingEnabled
                    ? styles.choiceActive
                    : styles.choice
                }
                onClick={() => {
                  setTrainingEnabled(false);
                  setFoodEnabled(true);
                }}
              >
                <strong>{copy.food}</strong>
                <span>{copy.foodHelp}</span>
              </button>

              <button
                type="button"
                className={
                  foodEnabled &&
                  trainingEnabled
                    ? styles.choiceActive
                    : styles.choice
                }
                onClick={() => {
                  setTrainingEnabled(true);
                  setFoodEnabled(true);
                }}
              >
                <small className={styles.badge}>
                  {copy.recommended}
                </small>
                <strong>{copy.both}</strong>
                <span>{copy.bothHelp}</span>
              </button>
            </div>

            {error ? (
              <p className={styles.error}>
                {error}
              </p>
            ) : null}

            <div className={styles.actions}>
              <button
                type="button"
                className={styles.back}
                onClick={() => setStep("goal")}
              >
                {t("back")}
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={() => void saveCore()}
              >
                {saving
                  ? t("creatingPlan")
                  : copy.continue}
              </button>
            </div>
          </div>
        ) : null}

        {step === "food" ? (
          <div>
            <p className={styles.eyebrow}>
              {copy.foodEyebrow}
            </p>
            <h1 id="welcome-title">
              {copy.foodTitle}
            </h1>
            <p className={styles.intro}>
              {copy.foodIntro}
            </p>

            <div className={styles.grid}>
              <label>
                <span>{t("name")}</span>
                <input
                  value={name}
                  onChange={(event) =>
                    setName(event.target.value)
                  }
                  autoComplete="given-name"
                />
              </label>

              <label>
                <span>{t("bmrFormula")}</span>
                <select
                  value={gender}
                  onChange={(event) =>
                    setGender(event.target.value)
                  }
                  required
                >
                  <option value="">
                    {t("select")}
                  </option>
                  <option value="female">
                    {t("female")}
                  </option>
                  <option value="male">
                    {t("male")}
                  </option>
                </select>
              </label>

              <label>
                <span>{t("birthDate")}</span>
                <input
                  type="date"
                  value={birthDate}
                  onChange={(event) =>
                    setBirthDate(
                      event.target.value,
                    )
                  }
                />
              </label>

              <label>
                <span>{t("heightCm")}</span>
                <input
                  type="number"
                  min="100"
                  max="250"
                  value={height}
                  onChange={(event) =>
                    setHeight(event.target.value)
                  }
                />
              </label>

              <label>
                <span>
                  {t("currentWeightKg")}
                </span>
                <input
                  type="number"
                  min="30"
                  max="350"
                  step="0.1"
                  value={weight}
                  onChange={(event) =>
                    setWeight(event.target.value)
                  }
                />
              </label>

              <label>
                <span>
                  {t("targetWeightKg")}{" "}
                  <small>{t("optional")}</small>
                </span>
                <input
                  type="number"
                  min="30"
                  max="350"
                  step="0.1"
                  value={targetWeight}
                  onChange={(event) =>
                    setTargetWeight(
                      event.target.value,
                    )
                  }
                />
              </label>

              <label className={styles.fullWidth}>
                <span>{copy.strategy}</span>
                <select
                  value={weightStrategy}
                  onChange={(event) =>
                    setWeightStrategy(
                      event.target.value as
                        | "loss"
                        | "maintenance"
                        | "gain",
                    )
                  }
                >
                  <option value="loss">
                    {t("loseWeight")}
                  </option>
                  <option value="maintenance">
                    {t("maintainWeight")}
                  </option>
                  <option value="gain">
                    {t("gainWeight")}
                  </option>
                </select>
              </label>

              {weightStrategy !==
              "maintenance" ? (
                <label
                  className={styles.fullWidth}
                >
                  <span>
                    {weightStrategy === "loss"
                      ? t("lossSpeed")
                      : t("gainSpeed")}
                  </span>
                  <select
                    value={adjustment}
                    onChange={(event) =>
                      setAdjustment(
                        event.target.value,
                      )
                    }
                  >
                    <option value="100">
                      {t("slow")} · 100 kcal
                    </option>
                    <option value="300">
                      {t("balanced")} · 300 kcal
                    </option>
                    <option value="500">
                      {t("fast")} · 500 kcal
                    </option>
                  </select>
                </label>
              ) : null}
            </div>

            <div className={styles.inlineInfo}>
              <span>✓ {copy.automaticProtein}</span>
              <span>✓ {copy.macroTracking}</span>
            </div>

            {error ? (
              <p className={styles.error}>
                {error}
              </p>
            ) : null}

            <div className={styles.actions}>
              <button
                type="button"
                className={styles.back}
                onClick={() =>
                  setStep("modules")
                }
              >
                {t("back")}
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={() => void saveFood()}
              >
                {saving
                  ? t("creatingPlan")
                  : copy.continue}
              </button>
            </div>
          </div>
        ) : null}

        {step === "training" ? (
          <div>
            <p className={styles.eyebrow}>
              {copy.trainingEyebrow}
            </p>
            <h1 id="welcome-title">
              {copy.trainingTitle}
            </h1>
            <p className={styles.intro}>
              {copy.trainingIntro}
            </p>

            <div className={styles.grid}>
              <label>
                <span>{copy.experience}</span>
                <select
                  value={experience}
                  onChange={(event) =>
                    setExperience(
                      event.target.value as
                        | "beginner"
                        | "intermediate"
                        | "advanced",
                    )
                  }
                >
                  <option value="beginner">
                    {copy.beginner}
                  </option>
                  <option value="intermediate">
                    {copy.intermediate}
                  </option>
                  <option value="advanced">
                    {copy.advanced}
                  </option>
                </select>
              </label>

              <label>
                <span>{copy.sessions}</span>
                <select
                  value={sessions}
                  onChange={(event) =>
                    setSessions(
                      Number(event.target.value),
                    )
                  }
                >
                  {[2, 3, 4, 5, 6].map(
                    (value) => (
                      <option
                        key={value}
                        value={value}
                      >
                        {value}
                      </option>
                    ),
                  )}
                </select>
              </label>

              <label>
                <span>{copy.duration}</span>
                <select
                  value={duration}
                  onChange={(event) =>
                    setDuration(
                      Number(event.target.value),
                    )
                  }
                >
                  {[30, 45, 60, 75, 90].map(
                    (value) => (
                      <option
                        key={value}
                        value={value}
                      >
                        {value} min
                      </option>
                    ),
                  )}
                </select>
              </label>

              <label>
                <span>{copy.horizon}</span>
                <select
                  value={planningHorizon}
                  onChange={(event) =>
                    setPlanningHorizon(
                      event.target.value as
                        | "weekly"
                        | "monthly",
                    )
                  }
                >
                  <option value="weekly">
                    {copy.weekly}
                  </option>
                  <option value="monthly">
                    {copy.monthly}
                  </option>
                </select>
              </label>

              <label>
                <span>{copy.coach}</span>
                <select
                  value={coachStyle}
                  onChange={(event) =>
                    setCoachStyle(
                      event.target.value as
                        | "conservative"
                        | "balanced"
                        | "ambitious",
                    )
                  }
                >
                  <option value="conservative">
                    {copy.conservative}
                  </option>
                  <option value="balanced">
                    {copy.balanced}
                  </option>
                  <option value="ambitious">
                    {copy.ambitious}
                  </option>
                </select>
              </label>

              <label>
                <span>{copy.schedule}</span>
                <select
                  value={scheduleFlexibility}
                  onChange={(event) =>
                    setScheduleFlexibility(
                      event.target.value as
                        | "fixed"
                        | "flexible",
                    )
                  }
                >
                  <option value="flexible">
                    {copy.flexible}
                  </option>
                  <option value="fixed">
                    {copy.fixed}
                  </option>
                </select>
              </label>
            </div>

            {scheduleFlexibility ===
            "fixed" ? (
              <div className={styles.fieldGroup}>
                <strong>
                  {copy.preferredDays}
                </strong>
                <div className={styles.chips}>
                  {WEEKDAYS.map((day) => (
                    <button
                      key={day.value}
                      type="button"
                      className={
                        preferredDays.includes(
                          day.value,
                        )
                          ? styles.chipActive
                          : styles.chip
                      }
                      onClick={() =>
                        toggleDay(day.value)
                      }
                    >
                      {day[lang]}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            <div className={styles.fieldGroup}>
              <div>
                <strong>{copy.priorities}</strong>
                <span className={styles.help}>
                  {copy.prioritiesHelp}
                </span>
              </div>
              <div className={styles.chips}>
                {MUSCLES.map((muscle) => (
                  <button
                    key={muscle}
                    type="button"
                    className={
                      priorityMuscles.includes(
                        muscle,
                      )
                        ? styles.chipActive
                        : styles.chip
                    }
                    onClick={() =>
                      togglePriority(muscle)
                    }
                  >
                    {
                      MUSCLE_LABELS[muscle][
                        lang
                      ]
                    }
                  </button>
                ))}
              </div>
            </div>

            {error ? (
              <p className={styles.error}>
                {error}
              </p>
            ) : null}

            <div className={styles.actions}>
              <button
                type="button"
                className={styles.back}
                onClick={() =>
                  setStep(
                    foodEnabled
                      ? "food"
                      : "modules",
                  )
                }
              >
                {t("back")}
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={() =>
                  void saveTraining()
                }
              >
                {saving
                  ? t("creatingPlan")
                  : copy.continue}
              </button>
            </div>
          </div>
        ) : null}

        {step === "summary" ? (
          <div>
            <p className={styles.eyebrow}>
              {copy.summaryEyebrow}
            </p>
            <h1 id="welcome-title">
              {copy.summaryTitle}
            </h1>
            <p className={styles.intro}>
              {copy.summaryIntro}
            </p>

            <div className={styles.summary}>
              <div>
                <span>{copy.primaryGoal}</span>
                <strong>{goalLabel}</strong>
              </div>
              <div>
                <span>{copy.modules}</span>
                <strong>{moduleLabel}</strong>
              </div>

              {trainingEnabled ? (
                <div>
                  <span>{copy.training}</span>
                  <strong>
                    {sessions}× · {duration} min ·{" "}
                    {planningHorizon === "weekly"
                      ? copy.weekly
                      : copy.monthly}
                  </strong>
                </div>
              ) : null}

              {trainingEnabled ? (
                <div>
                  <span>{copy.priorities}</span>
                  <strong>
                    {priorityMuscles.length
                      ? priorityMuscles
                          .map(
                            (muscle) =>
                              MUSCLE_LABELS[
                                muscle as keyof typeof MUSCLE_LABELS
                              ][lang],
                          )
                          .join(", ")
                      : copy.noPriority}
                  </strong>
                </div>
              ) : null}

              {foodEnabled ? (
                <div>
                  <span>{copy.nutrition}</span>
                  <strong>
                    {weightStrategy === "loss"
                      ? t("loseWeight")
                      : weightStrategy ===
                          "gain"
                        ? t("gainWeight")
                        : t("maintainWeight")}
                  </strong>
                </div>
              ) : null}
            </div>

            <div className={styles.actions}>
              <button
                type="button"
                className={styles.back}
                onClick={() =>
                  setStep(
                    trainingEnabled
                      ? "training"
                      : "food",
                  )
                }
              >
                {t("back")}
              </button>
              <button
                type="button"
                onClick={finish}
              >
                {copy.startApp}
              </button>
            </div>

            <p className={styles.consent}>
              {t("consentContinue")}{" "}
              <Link href="/privacy">
                {t("privacyPolicy")}
              </Link>{" "}
              {t("consentAnd")}{" "}
              <Link href="/terms">
                {t("terms")}
              </Link>.
            </p>
          </div>
        ) : null}
      </section>
    </div>
  );
}
