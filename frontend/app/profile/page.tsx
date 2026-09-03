 "use client";

import {
  useEffect,
  useState,
} from "react";

import { AppNav } from "@/components/navigation/AppNav";
import { useAuth } from "@/components/auth/AuthProvider";
import {
  getProfile,
  deleteAccount,
  updateProfile,
  getWeeklySchedule,
  updateWeeklySchedule,
  type ProfileUpdate,
  type WeeklyScheduleContext,
} from "@/lib/api/profile";

import {
  getOuraAuthorization,
  getOuraStatus,
} from "@/lib/api/oura";

import styles from "./ProfilePage.module.css";

function firstNameValue(value: unknown): string {
  const name = stringValue(value).trim();

  if (!name) {
    return "";
  }

  return name.split(/\s+/)[0];
}

interface FormState {
  name: string;
  gender: string;
  birth_date: string;
  height: string;
  target_weight: string;
  goal_mode: string;
  deficit_plan: string;
  goal_adjustment_kcal: string;
  protein_goal_enabled: boolean;
  protein_goal_g: string;
  language: string;
  city: string;
  office_lunch: boolean;
  weekly_schedule: Record<string, "home" | "office" | "free">;
}

const WEEK_DAYS = [
  { key: "monday", label: "Lunedì", number: 1 },
  { key: "tuesday", label: "Martedì", number: 2 },
  { key: "wednesday", label: "Mercoledì", number: 3 },
  { key: "thursday", label: "Giovedì", number: 4 },
  { key: "friday", label: "Venerdì", number: 5 },
  { key: "saturday", label: "Sabato", number: 6 },
  { key: "sunday", label: "Domenica", number: 7 },
] as const;

function getCurrentWeekStart(): string {
  const today = new Date();
  const day = today.getDay();
  const diff = day === 0 ? -6 : 1 - day;

  today.setDate(today.getDate() + diff);

  return today.toISOString().slice(0, 10);
}

function contextLabel(
  context: WeeklyScheduleContext,
): string {
  return {
    home: "Casa",
    office: "Ufficio",
    free: "Libero",
  }[context];
}

const EMPTY_FORM: FormState = {
  name: "",
  gender: "",
  birth_date: "",
  height: "",
  target_weight: "",
  goal_mode: "",
  deficit_plan: "balanced",
  goal_adjustment_kcal: "",
  protein_goal_enabled: false,
  protein_goal_g: "",
  language: "it",
  city: "",
  office_lunch: false,
  weekly_schedule: {
    monday: "home",
    tuesday: "office",
    wednesday: "home",
    thursday: "office",
    friday: "home",
    saturday: "home",
    sunday: "home",
  },
};

const DEFICIT_BY_PLAN = {
  slow: 100,
  balanced: 300,
  fast: 500,
} as const;

function deficitPlanFromCalories(value: unknown): keyof typeof DEFICIT_BY_PLAN {
  const calories = Number(value);
  if (calories <= 150) return "slow";
  if (calories >= 400) return "fast";
  return "balanced";
}

function normalizedDeficitPlan(
  value: unknown,
  calories?: unknown,
): keyof typeof DEFICIT_BY_PLAN {
  if (value === "slow" || value === "balanced" || value === "fast") {
    return value;
  }
  return deficitPlanFromCalories(calories);
}

function deficitCalories(value: unknown): number {
  return DEFICIT_BY_PLAN[normalizedDeficitPlan(value)];
}

function stringValue(
  value: unknown,
): string {
  return typeof value === "string"
    ? value
    : "";
}

function numberString(
  value: unknown,
): string {
  return typeof value === "number"
    ? String(value)
    : "";
}

export default function ProfilePage() {
  const {
    user,
    accessToken,
    signOut,
  } = useAuth();

  const [form, setForm] =
    useState<FormState>(EMPTY_FORM);
  const [loading, setLoading] =
    useState(true);
  const [saving, setSaving] =
    useState(false);
  const [deletingAccount, setDeletingAccount] =
    useState(false);
  const [error, setError] =
    useState<string | null>(null);
  const [success, setSuccess] =
    useState<string | null>(null);
  const [ouraConnected, setOuraConnected] =
    useState(false);
  const [ouraStatusLoading, setOuraStatusLoading] =
    useState(true);
  const [ouraConnecting, setOuraConnecting] =
    useState(false);

  const [currentWeekSchedule, setCurrentWeekSchedule] =
    useState<Record<string, WeeklyScheduleContext> | null>(null);

  const [currentWeekOverrides, setCurrentWeekOverrides] =
    useState<Record<string, WeeklyScheduleContext>>({});

  const [currentWeekStart, setCurrentWeekStart] =
    useState<string>("");

  const [savingWeek, setSavingWeek] =
    useState(false);


  useEffect(() => {
    if (!accessToken) {
      return;
    }

    let active = true;

    async function loadProfile() {
      try {
        setLoading(true);
        setError(null);

        const response =
          await getProfile(accessToken);

        if (!active) {
          return;
        }

        const metadata =
          response.metadata ?? {};

        const storedSchedule =
          metadata.weekly_schedule;

        const weeklySchedule: FormState["weekly_schedule"] =
          storedSchedule &&
          typeof storedSchedule === "object"
            ? {
                monday:
                  (storedSchedule as Record<string, string>).monday === "office"
                    ? "office"
                    : "home",
                tuesday:
                  (storedSchedule as Record<string, string>).tuesday === "office"
                    ? "office"
                    : "home",
                wednesday:
                  (storedSchedule as Record<string, string>).wednesday === "office"
                    ? "office"
                    : "home",
                thursday:
                  (storedSchedule as Record<string, string>).thursday === "office"
                    ? "office"
                    : "home",
                friday:
                  (storedSchedule as Record<string, string>).friday === "office"
                    ? "office"
                    : "home",
                saturday:
                  (storedSchedule as Record<string, string>).saturday === "office"
                    ? "office"
                    : "home",
                sunday:
                  (storedSchedule as Record<string, string>).sunday === "office"
                    ? "office"
                    : "home",
              }
            : EMPTY_FORM.weekly_schedule;

        setForm({
          name:
            firstNameValue(
              metadata.name ??
                metadata.first_name,
            ),
          gender:
            stringValue(metadata.gender),
          birth_date:
            stringValue(metadata.birth_date),
          height:
            numberString(metadata.height),
          target_weight:
            numberString(metadata.target_weight),
          goal_mode:
            stringValue(metadata.goal_mode),
          deficit_plan:
            normalizedDeficitPlan(
              metadata.deficit_plan,
              metadata.goal_adjustment_kcal ?? metadata.deficit_target_kcal,
            ),
          goal_adjustment_kcal:
            numberString(
              metadata.goal_adjustment_kcal ??
                metadata.deficit_target_kcal,
            ),
          protein_goal_enabled:
            metadata.protein_goal_enabled === true,
          protein_goal_g:
            numberString(metadata.protein_goal_g),
          language:
            stringValue(metadata.language) ||
            "it",
          city:
            stringValue(metadata.city),
          office_lunch:
            metadata.office_lunch === true,
          weekly_schedule: weeklySchedule,
        });
      } catch (err) {
        if (!active) {
          return;
        }

        setError(
          err instanceof Error
            ? err.message
            : "Impossibile caricare il profilo.",
        );
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadProfile();

    return () => {
      active = false;
    };
  }, [accessToken]);

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    const token = accessToken;
    let active = true;

    async function loadOuraStatus() {
      try {
        setOuraStatusLoading(true);

        const response = await getOuraStatus(
          token,
        );

        if (active) {
          setOuraConnected(
            response.connected,
          );
        }
      } catch {
        if (active) {
          setOuraConnected(false);
        }
      } finally {
        if (active) {
          setOuraStatusLoading(false);
        }
      }
    }

    void loadOuraStatus();

    return () => {
      active = false;
    };
  }, [accessToken]);

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    const token = accessToken;
    let active = true;

    async function loadCurrentWeek() {
      try {
        const weekStart = getCurrentWeekStart();

        const response = await getWeeklySchedule(
          token,
          weekStart,
        );

        if (!active) {
          return;
        }

        setCurrentWeekStart(response.week_start);
        setCurrentWeekSchedule(response.days);
        setCurrentWeekOverrides(response.overrides);
      } catch (err) {
        if (!active) {
          return;
        }

        setError(
          err instanceof Error
            ? err.message
            : "Impossibile caricare la settimana corrente.",
        );
      }
    }

    void loadCurrentWeek();

    return () => {
      active = false;
    };
  }, [accessToken]);

  function updateCurrentWeekDay(
    day: string,
    context: WeeklyScheduleContext,
  ) {
    setCurrentWeekSchedule((current) => {
      if (!current) {
        return current;
      }

      return {
        ...current,
        [day]: context,
      };
    });

    setCurrentWeekOverrides((current) => ({
      ...current,
      [day]: context,
    }));

    setSuccess(null);
  }

  async function saveCurrentWeek() {
    if (!accessToken || !currentWeekStart || !currentWeekSchedule) {
      return;
    }

    setSavingWeek(true);
    setError(null);
    setSuccess(null);

    try {
      const days = WEEK_DAYS
        .filter((day) =>
          Object.prototype.hasOwnProperty.call(
            currentWeekOverrides,
            day.key,
          ),
        )
        .map((day) => ({
          day_of_week: day.number,
          context: currentWeekOverrides[day.key],
        }));

      const response = await updateWeeklySchedule(
        accessToken,
        {
          week_start: currentWeekStart,
          days,
        },
      );

      setCurrentWeekSchedule(response.days);
      setCurrentWeekOverrides(response.overrides);
      setSuccess("Settimana corrente salvata.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Impossibile salvare la settimana corrente.",
      );
    } finally {
      setSavingWeek(false);
    }
  }

  function updateField<K extends keyof FormState>(
    field: K,
    value: FormState[K],
  ) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
    setSuccess(null);
  }

  async function connectOura() {
    if (!accessToken) {
      return;
    }

    setOuraConnecting(true);
    setError(null);

    try {
      const response =
        await getOuraAuthorization(
          accessToken,
        );

      window.location.assign(
        response.authorization_url,
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Impossibile collegare Oura.",
      );
      setOuraConnecting(false);
    }
  }

  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!accessToken) {
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(null);

    const payload: ProfileUpdate = {
      name: firstNameValue(form.name) || null,
      gender: form.gender || null,
      birth_date:
        form.birth_date || null,
      height:
        form.height
          ? Number(form.height)
          : null,
      target_weight:
        form.target_weight
          ? Number(form.target_weight)
          : null,
      goal_mode:
        form.goal_mode || null,
      goal_adjustment_kcal:
        form.goal_mode === "loss"
          ? deficitCalories(form.deficit_plan)
          : form.goal_mode === "maintenance"
          ? 0
          : form.goal_adjustment_kcal
          ? Number(form.goal_adjustment_kcal)
          : null,
      protein_goal_enabled:
        form.protein_goal_enabled,
      protein_goal_g:
        form.protein_goal_enabled &&
        form.protein_goal_g
          ? Number(form.protein_goal_g)
          : null,
      language:
        form.language || null,
      city:
        form.city.trim() || null,
      office_lunch:
        form.office_lunch,
      weekly_schedule:
        form.weekly_schedule,
    };

    try {
      const response =
        await updateProfile(
          accessToken,
          payload,
        );



      setSuccess(
        "Profilo salvato.",
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Impossibile salvare il profilo.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteAccount() {
    if (!accessToken || deletingAccount) {
      return;
    }

    const confirmation = window.prompt(
      "Questa operazione è definitiva. Scrivi ELIMINA per cancellare il tuo account e tutti i dati associati.",
    );

    if (confirmation !== "ELIMINA") {
      return;
    }

    setDeletingAccount(true);
    setError(null);
    setSuccess(null);

    try {
      await deleteAccount(accessToken);
      await signOut();
      window.location.assign("/");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Impossibile eliminare l’account.",
      );
      setDeletingAccount(false);
    }
  }

  if (!accessToken) {
    return (
      <>
        <AppNav />
        <main className={styles.page}>
          <div className={styles.card}>
            <h1>Profilo</h1>
            <p>
              Effettua l'accesso per visualizzare
              il tuo profilo.
            </p>
          </div>
        </main>
      </>
    );
  }

  return (
    <>
      <AppNav />

      <main className={styles.page}>
        <div className={styles.header}>
          <div>
            <p className={styles.eyebrow}>
              Account
            </p>
            <h1>Profilo</h1>
            <p className={styles.subtitle}>
              Personalizza i dati che SanoSync
              usa per costruire le tue giornate.
            </p>
          </div>

          {user?.email && (
            <div className={styles.email}>
              {user.email}
            </div>
          )}
        </div>

        {loading ? (
          <div className={styles.card}>
            <p>Caricamento profilo...</p>
          </div>
        ) : (
          <form
            className={styles.form}
            onSubmit={handleSubmit}
          >
            <section className={styles.card}>
              <div className={styles.sectionHeader}>
                <h2>Dati personali</h2>
                <p>
                  Le informazioni di base del tuo
                  profilo.
                </p>
              </div>

              <div className={styles.grid}>
                <label>
                  <span>Nome</span>
                  <input
                    value={form.name}
                    onChange={(event) =>
                      updateField(
                        "name",
                        event.target.value,
                      )
                    }
                    placeholder="Il tuo nome"
                  />
                </label>

                <label>
                  <span>Città</span>
                  <input
                    value={form.city}
                    onChange={(event) =>
                      updateField(
                        "city",
                        event.target.value,
                      )
                    }
                    placeholder="Es. Zaandam"
                    autoComplete="address-level2"
                  />
                </label>

                <label>
                  <span>Genere</span>
                  <select
                    value={form.gender}
                    onChange={(event) =>
                      updateField(
                        "gender",
                        event.target.value,
                      )
                    }
                  >
                    <option value="">
                      Seleziona
                    </option>
                    <option value="female">
                      Donna
                    </option>
                    <option value="male">
                      Uomo
                    </option>
                    <option value="other">
                      Altro
                    </option>
                  </select>
                </label>

                <label>
                  <span>Data di nascita</span>
                  <input
                    type="date"
                    value={form.birth_date}
                    onChange={(event) =>
                      updateField(
                        "birth_date",
                        event.target.value,
                      )
                    }
                  />
                </label>

                <label>
                  <span>Altezza (cm)</span>
                  <input
                    type="number"
                    min="1"
                    value={form.height}
                    onChange={(event) =>
                      updateField(
                        "height",
                        event.target.value,
                      )
                    }
                  />
                </label>

                <label>
                  <span>Peso obiettivo (kg)</span>
                  <input
                    type="number"
                    min="1"
                    step="0.1"
                    value={form.target_weight}
                    onChange={(event) =>
                      updateField(
                        "target_weight",
                        event.target.value,
                      )
                    }
                  />
                </label>
              </div>
            </section>

            <section className={styles.card}>
              <div className={styles.sectionHeader}>
                <h2>Obiettivi nutrizionali</h2>
                <p>
                  I parametri usati dal Budget Engine.
                </p>
              </div>

              <div className={styles.grid}>
                <label>
                  <span>Obiettivo</span>
                  <select
                    value={form.goal_mode}
                    onChange={(event) =>
                      updateField(
                        "goal_mode",
                        event.target.value,
                      )
                    }
                  >
                    <option value="">
                      Seleziona
                    </option>
                    <option value="loss">
                      Perdere peso
                    </option>
                    <option value="maintenance">
                      Mantenere il peso
                    </option>
                    <option value="gain">
                      Aumentare il peso
                    </option>
                  </select>
                </label>

                  {form.goal_mode === "loss" && (
                    <label>
                      <span>
                        Velocità di perdita
                      </span>
                      <select
                        value={form.deficit_plan || "balanced"}
                        onChange={(event) =>
                          updateField(
                            "deficit_plan",
                            event.target.value,
                          )
                        }
                      >
                        <option value="slow">
                          Lento
                        </option>
                        <option value="balanced">
                          Bilanciato
                        </option>
                        <option value="fast">
                          Rapido
                        </option>
                      </select>
                      <small className={styles.fieldHint}>
                        Verrà applicato un deficit di{" "}
                        {deficitCalories(form.deficit_plan)}{" "}
                        kcal, adattabile nelle giornate reali.
                      </small>
                    </label>
                  )}


                <label className={styles.checkbox}>
                  <input
                    type="checkbox"
                    checked={
                      form.protein_goal_enabled
                    }
                    onChange={(event) =>
                      updateField(
                        "protein_goal_enabled",
                        event.target.checked,
                      )
                    }
                  />
                  <span>
                    Attiva obiettivo proteico
                  </span>
                </label>

                {form.protein_goal_enabled && (
                  <label>
                    <span>
                      Goal proteico (g)
                    </span>
                    <input
                      type="number"
                      min="1"
                      step="1"
                      value={
                        form.protein_goal_g
                      }
                      onChange={(event) =>
                        updateField(
                          "protein_goal_g",
                          event.target.value,
                        )
                      }
                    />
                  </label>
                )}
              </div>
            </section>

            <section className={styles.card}>
              <div className={styles.sectionHeader}>
                <h2>Preferenze</h2>
                <p>
                  Come vuoi usare SanoSync.
                </p>
              </div>

              <div className={styles.grid}>
                <label>
                  <span>Lingua</span>
                  <select
                    value={form.language}
                    onChange={(event) =>
                      updateField(
                        "language",
                        event.target.value,
                      )
                    }
                  >
                    <option value="it">
                      Italiano
                    </option>
                    <option value="en">
                      English
                    </option>
                  </select>
                </label>

                <label className={styles.checkbox}>
                  <input
                    type="checkbox"
                    checked={form.office_lunch}
                    onChange={(event) =>
                      updateField(
                        "office_lunch",
                        event.target.checked,
                      )
                    }
                  />
                  <span>
                    Pranzo abitualmente in ufficio
                  </span>
                </label>
              </div>
            </section>

            <section className={styles.card}>
              <div className={styles.sectionHeader}>
                <h2>La mia settimana</h2>
                <p>
                  Indica dove ti trovi normalmente.
                  Potremo usare questa informazione
                  per personalizzare i pasti.
                </p>
              </div>

              <div className={styles.schedule}>
                {[
                  ["monday", "Lunedì"],
                  ["tuesday", "Martedì"],
                  ["wednesday", "Mercoledì"],
                  ["thursday", "Giovedì"],
                  ["friday", "Venerdì"],
                  ["saturday", "Sabato"],
                  ["sunday", "Domenica"],
                ].map(([day, label]) => (
                  <div
                    key={day}
                    className={styles.scheduleRow}
                  >
                    <strong>{label}</strong>

                    <div className={styles.scheduleToggle}>
                      <button
                        type="button"
                        className={
                          form.weekly_schedule[day] === "home"
                            ? styles.scheduleActive
                            : styles.scheduleButton
                        }
                        onClick={() =>
                          updateField(
                            "weekly_schedule",
                            {
                              ...form.weekly_schedule,
                              [day]: "home",
                            },
                          )
                        }
                      >
                        Casa
                      </button>

                      <button
                        type="button"
                        className={
                          form.weekly_schedule[day] === "office"
                            ? styles.scheduleActive
                            : styles.scheduleButton
                        }
                        onClick={() =>
                          updateField(
                            "weekly_schedule",
                            {
                              ...form.weekly_schedule,
                              [day]: "office",
                            },
                          )
                        }
                      >
                        Ufficio
                      </button>

                      <button
                        type="button"
                        className={
                          form.weekly_schedule[day] === "free"
                            ? styles.scheduleActive
                            : styles.scheduleButton
                        }
                        onClick={() =>
                          updateField(
                            "weekly_schedule",
                            {
                              ...form.weekly_schedule,
                              [day]: "free",
                            },
                          )
                        }
                      >
                        Libero
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className={styles.card}>
              <div className={styles.sectionHeader}>
                <h2>Integrazioni</h2>
                <p>
                  Collega i servizi che vuoi usare
                  con SanoSync.
                </p>
              </div>

              <div className={styles.integrations}>
                <div className={styles.integration}>
                  <div>
                    <strong>Oura</strong>
                    <span>
                      Sonno, recupero e attività
                    </span>
                    <small>
                      {ouraStatusLoading
                        ? "Ver connessione…"
                        : ouraConnected
                        ? "Account collegato"
                        : "Account non collegato"}
                    </small>
                  </div>

                  <button
                    type="button"
                    disabled={
                      ouraStatusLoading ||
                      ouraConnecting ||
                      ouraConnected
                    }
                    onClick={() => {
                      void connectOura();
                    }}
                  >
                    {ouraConnecting
                      ? "Apro Oura…"
                      : ouraConnected
                      ? "Connesso"
                      : "Collega"}
                  </button>
                </div>
              </div>
            </section>

            {error && (
              <div
                className={styles.error}
                role="alert"
              >
                {error}
              </div>
            )}

            {success && (
              <div
                className={styles.success}
                role="status"
              >
                {success}
              </div>
            )}

            <div className={styles.actions}>
              <button
                type="submit"
                disabled={saving}
                className={styles.save}
              >
                {saving
                  ? "Salvataggio..."
                  : "Salva modifiche"}
              </button>
            </div>

            <section className={`${styles.card} ${styles.logoutZone}`}>
              <div className={styles.sectionHeader}>
                <h2>Sessione</h2>
                <p>Puoi uscire da SanoSync su questo dispositivo.</p>
              </div>
              <button
                type="button"
                className={styles.logoutButton}
                onClick={() => {
                  window.sessionStorage.removeItem(
                    "sanosync-onboarding-test-completed",
                  );
                  void signOut();
                }}
              >
                Esci dall’account
              </button>
            </section>

            <section className={`${styles.card} ${styles.dangerZone}`}>
              <div className={styles.sectionHeader}>
                <h2>Elimina account</h2>
                <p>
                  Cancella definitivamente il tuo account SanoSync e i dati associati.
                  Questa operazione non può essere annullata.
                </p>
              </div>
              <button
                type="button"
                className={styles.deleteAccount}
                disabled={deletingAccount}
                onClick={() => void handleDeleteAccount()}
              >
                {deletingAccount ? "Eliminazione…" : "Elimina il mio account"}
              </button>
            </section>
          </form>
        )}
      </main>
    </>
  );
}
