"use client";

import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { getDay } from "@/lib/api/day";
import type { DayResponse } from "@/lib/api/types";

import styles from "./HomeShell.module.css";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function greeting(): string {
  const hour = new Date().getHours();

  if (hour < 12) {
    return "Buongiorno";
  }

  if (hour < 18) {
    return "Buon pomeriggio";
  }

  return "Buonasera";
}

function mealLabel(slot: string): string {
  return {
    breakfast: "Colazione",
    lunch: "Pranzo",
    dinner: "Cena",
  }[slot] ?? slot;
}

export function HomeShell() {
  const {
    user,
    accessToken,
    signOut,
  } = useAuth();

  const [day, setDay] =
    useState<DayResponse | null>(null);
  const [loading, setLoading] =
    useState(true);
  const [error, setError] =
    useState<string | null>(null);

  const firstName = useMemo(() => {
    const metadataName =
      user?.user_metadata?.first_name ||
      user?.user_metadata?.name;

    if (
      typeof metadataName === "string" &&
      metadataName.trim()
    ) {
      return metadataName.trim();
    }

    if (user?.email) {
      return user.email.split("@")[0];
    }

    return "";
  }, [user]);

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    let active = true;

    async function load() {
      setLoading(true);
      setError(null);

      try {
        const payload = await getDay(
          todayIso(),
          accessToken,
        );

        if (active) {
          setDay(payload);
        }
      } catch (err) {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Impossibile caricare la giornata.",
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [accessToken]);

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.brand}>
            SANOSYNC
          </p>
          <h1>
            {greeting()}
            {firstName
              ? `, ${firstName}`
              : ""}
          </h1>
        </div>

        <button
          type="button"
          className={styles.signOut}
          onClick={() => {
            void signOut();
          }}
        >
          Esci
        </button>
      </header>

      {loading ? (
        <section className={styles.card}>
          <p className={styles.muted}>
            Sto preparando la tua giornata…
          </p>
        </section>
      ) : null}

      {error ? (
        <section className={styles.errorCard}>
          <strong>
            Non riesco a caricare la giornata.
          </strong>
          <p>{error}</p>
        </section>
      ) : null}

      {day ? (
        <>
          <section className={styles.dayIntro}>
            <p className={styles.kicker}>
              Oggi
            </p>

            <h2>
              {day.context.value ||
                "Giornata da definire"}
            </h2>

            <p className={styles.subtitle}>
              {day.activity_plan.value
                ? `${day.activity_plan.value} prevista`
                : "Attività non ancora prevista"}
            </p>
          </section>

          <section
            className={styles.metricsGrid}
          >
            <article className={styles.metricCard}>
              <span>Peso</span>
              <strong>
                {day.actual.weight != null
                  ? `${day.actual.weight} kg`
                  : "—"}
              </strong>
            </article>

            <article className={styles.metricCard}>
              <span>Passi</span>
              <strong>
                {day.actual.steps != null
                  ? day.actual.steps.toLocaleString(
                      "it-IT",
                    )
                  : "—"}
              </strong>
            </article>
          </section>

          <section className={styles.section}>
            <div className={styles.sectionHeader}>
              <div>
                <p className={styles.kicker}>
                  Routine prevista
                </p>
                <h2>I tuoi pasti</h2>
              </div>
            </div>

            <div className={styles.mealList}>
              {Object.entries(day.meals).map(
                ([slot, meal]) => (
                  <article
                    key={slot}
                    className={styles.mealCard}
                  >
                    <div
                      className={
                        styles.mealCardTop
                      }
                    >
                      <span
                        className={
                          styles.mealLabel
                        }
                      >
                        {mealLabel(slot)}
                      </span>

                      <span
                        className={
                          meal.state ===
                          "predicted"
                            ? styles.predictedBadge
                            : styles.unknownBadge
                        }
                      >
                        {meal.state ===
                        "predicted"
                          ? "Previsto"
                          : "Da decidere"}
                      </span>
                    </div>

                    <strong
                      className={styles.mealName}
                    >
                      {meal.value ||
                        "Nessuna routine abbastanza forte"}
                    </strong>

                    {typeof meal.estimated_calories ===
                      "number" ? (
                      <p
                        className={
                          styles.mealMeta
                        }
                      >
                        {Math.round(
                          meal.estimated_calories,
                        )}{" "}
                        kcal
                        {typeof meal.estimated_protein_g ===
                        "number"
                          ? ` · ${Math.round(
                              meal.estimated_protein_g,
                            )} g proteine`
                          : ""}
                      </p>
                    ) : null}
                  </article>
                ),
              )}
            </div>
          </section>
        </>
      ) : null}
    </main>
  );
}
