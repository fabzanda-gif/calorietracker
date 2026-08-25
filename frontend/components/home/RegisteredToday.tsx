"use client";

import { useState } from "react";

import {
  deleteActivity,
  updateActivity,
  type Activity,
} from "@/lib/api/activities";

import {
  deleteMeal,
  updateMeal,
  type LoggedMeal,
} from "@/lib/api/meals";

import styles from "./RegisteredToday.module.css";


interface RegisteredTodayProps {
  meals: LoggedMeal[];
  activities: Activity[];
  accessToken?: string | null;
  onChanged: () => Promise<void> | void;
}


type EditingItem =
  | {
      kind: "meal";
      id: string | number;
    }
  | {
      kind: "activity";
      id: string | number;
    }
  | null;


function roundNumber(
  value: number | null | undefined,
): number {
  return Math.round(Number(value) || 0);
}


export function RegisteredToday({
  meals,
  activities,
  accessToken,
  onChanged,
}: RegisteredTodayProps) {
  const [editing, setEditing] =
    useState<EditingItem>(null);

  const [name, setName] =
    useState("");

  const [calories, setCalories] =
    useState("");

  const [protein, setProtein] =
    useState("");

  const [carbs, setCarbs] =
    useState("");

  const [fat, setFat] =
    useState("");

  const [saving, setSaving] =
    useState(false);

  const [message, setMessage] =
    useState<string | null>(null);


  const extraMeals =
    meals.filter(
      (meal) =>
        meal.meal_type !== "Colazione" &&
        meal.meal_type !== "Pranzo" &&
        meal.meal_type !== "Cena",
    );


  const hasItems =
    extraMeals.length > 0 ||
    activities.length > 0;


  function startMealEdit(
    meal: LoggedMeal,
  ) {
    if (
      meal.id === null ||
      meal.id === undefined
    ) {
      return;
    }

    setEditing({
      kind: "meal",
      id: meal.id,
    });

    setName(meal.name ?? "");
    setCalories(
      String(
        roundNumber(meal.calories),
      ),
    );
    setProtein(
      String(
        roundNumber(meal.protein),
      ),
    );
    setCarbs(
      String(
        roundNumber(meal.carbs),
      ),
    );
    setFat(
      String(
        roundNumber(meal.fat),
      ),
    );

    setMessage(null);
  }


  function startActivityEdit(
    activity: Activity,
  ) {
    if (
      activity.id === null ||
      activity.id === undefined
    ) {
      return;
    }

    setEditing({
      kind: "activity",
      id: activity.id,
    });

    setName(activity.activity_name);
    setCalories(
      String(
        roundNumber(
          activity.burned_calories,
        ),
      ),
    );

    setMessage(null);
  }


  function closeEditor() {
    setEditing(null);
    setMessage(null);
  }


  async function saveEdit() {
    if (
      !editing ||
      !accessToken
    ) {
      return;
    }

    const cleanName =
      name.trim();

    const kcal =
      Number(calories);

    if (!cleanName) {
      setMessage(
        "Inserisci un nome.",
      );
      return;
    }

    if (
      !Number.isFinite(kcal) ||
      kcal < 0
    ) {
      setMessage(
        "Inserisci calorie valide.",
      );
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      if (
        editing.kind === "activity"
      ) {
        await updateActivity(
          editing.id,
          {
            activity_name:
              cleanName,
            burned_calories:
              Math.round(kcal),
          },
          accessToken,
        );
      } else {
        await updateMeal(
          editing.id,
          {
            name: cleanName,
            calories: kcal,
            protein:
              Number(protein) || 0,
            carbs:
              Number(carbs) || 0,
            fat:
              Number(fat) || 0,
          },
          accessToken,
        );
      }

      setEditing(null);
      await onChanged();
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Non riesco a salvare le modifiche.",
      );
    } finally {
      setSaving(false);
    }
  }


  async function toggleMealReusable(
    meal: LoggedMeal,
  ) {
    if (
      !accessToken ||
      meal.id === null ||
      meal.id === undefined
    ) {
      return;
    }

    const nextReusable =
      meal.is_reusable === false;

    setSaving(true);
    setMessage(null);

    try {
      await updateMeal(
        meal.id,
        {
          is_reusable: nextReusable,
        },
        accessToken,
      );

      setMessage(
        nextReusable
          ? `"${meal.name}" può essere usato di nuovo nei suggerimenti.`
          : `"${meal.name}" resta nello storico ma non verrà più usato nei suggerimenti.`,
      );

      await onChanged();
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Non riesco ad aggiornare il pasto.",
      );
    } finally {
      setSaving(false);
    }
  }


  async function removeMeal(
    meal: LoggedMeal,
  ) {
    if (
      !accessToken ||
      meal.id === null ||
      meal.id === undefined
    ) {
      return;
    }

    if (
      !window.confirm(
        `Eliminare "${meal.name}"?`,
      )
    ) {
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      await deleteMeal(
        meal.id,
        accessToken,
      );

      await onChanged();
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Non riesco a eliminare il pasto.",
      );
    } finally {
      setSaving(false);
    }
  }


  async function removeActivity(
    activity: Activity,
  ) {
    if (
      !accessToken ||
      activity.id === null ||
      activity.id === undefined
    ) {
      return;
    }

    if (
      !window.confirm(
        `Eliminare "${activity.activity_name}"?`,
      )
    ) {
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      await deleteActivity(
        activity.id,
        accessToken,
      );

      await onChanged();
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Non riesco a eliminare l’attività.",
      );
    } finally {
      setSaving(false);
    }
  }


  if (!hasItems) {
    return null;
  }


  return (
    <section className={styles.section}>
      <div className={styles.header}>
        <div>
          <p className={styles.kicker}>
            Registrato oggi
          </p>

          <h2>
            Extra &amp; attività
          </h2>

          <p className={styles.subtitle}>
            Quello che hai aggiunto oltre ai
            pasti principali.
          </p>
        </div>
      </div>

      {message ? (
        <div className={styles.message}>
          {message}
        </div>
      ) : null}

      <div className={styles.list}>
        {extraMeals.map((meal) => (
          <article
            key={`meal-${meal.id}`}
            className={styles.item}
          >
            <div className={styles.itemMain}>
              <span className={styles.badge}>
                {meal.meal_type === "Spuntino"
                  ? "Snack"
                  : meal.meal_type}
              </span>

              <strong>
                {meal.name}
              </strong>

              <span className={styles.meta}>
                {roundNumber(
                  meal.calories,
                )}{" "}
                kcal
              </span>
            </div>

            <div className={styles.itemActions}>
              <button
                type="button"
                disabled={saving}
                onClick={() => {
                  void toggleMealReusable(meal);
                }}
              >
                {meal.is_reusable === false
                  ? "Riusa nei suggerimenti"
                  : "Non suggerire più"}
              </button>

              <button
                type="button"
                onClick={() => {
                  startMealEdit(meal);
                }}
              >
                Modifica
              </button>

              <button
                type="button"
                disabled={saving}
                onClick={() => {
                  void removeMeal(meal);
                }}
              >
                Elimina
              </button>
            </div>
          </article>
        ))}

        {activities.map(
          (activity) => (
            <article
              key={`activity-${activity.id}`}
              className={styles.item}
            >
              <div className={styles.itemMain}>
                <span
                  className={
                    styles.activityBadge
                  }
                >
                  Attività
                </span>

                <strong>
                  {activity.activity_name}
                </strong>

                <span className={styles.meta}>
                  {roundNumber(
                    activity.burned_calories,
                  )}{" "}
                  kcal
                </span>
              </div>

              <div
                className={styles.itemActions}
              >
                <button
                  type="button"
                  onClick={() => {
                    startActivityEdit(
                      activity,
                    );
                  }}
                >
                  Modifica
                </button>

                <button
                  type="button"
                  disabled={saving}
                  onClick={() => {
                    void removeActivity(
                      activity,
                    );
                  }}
                >
                  Elimina
                </button>
              </div>
            </article>
          ),
        )}
      </div>

      {editing ? (
        <div className={styles.editor}>
          <div className={styles.editorHeader}>
            <strong>
              {editing.kind === "activity"
                ? "Modifica attività"
                : "Modifica snack"}
            </strong>

            <button
              type="button"
              onClick={closeEditor}
            >
              Chiudi
            </button>
          </div>

          <label>
            <span>Nome</span>

            <input
              value={name}
              onChange={(event) => {
                setName(
                  event.target.value,
                );
              }}
            />
          </label>

          <label>
            <span>
              {editing.kind === "activity"
                ? "Calorie bruciate"
                : "Calorie"}
            </span>

            <input
              type="number"
              min="0"
              value={calories}
              onChange={(event) => {
                setCalories(
                  event.target.value,
                );
              }}
            />
          </label>

          {editing.kind === "meal" ? (
            <div className={styles.macroGrid}>
              <label>
                <span>Proteine</span>
                <input
                  type="number"
                  min="0"
                  value={protein}
                  onChange={(event) => {
                    setProtein(
                      event.target.value,
                    );
                  }}
                />
              </label>

              <label>
                <span>Carbo</span>
                <input
                  type="number"
                  min="0"
                  value={carbs}
                  onChange={(event) => {
                    setCarbs(
                      event.target.value,
                    );
                  }}
                />
              </label>

              <label>
                <span>Grassi</span>
                <input
                  type="number"
                  min="0"
                  value={fat}
                  onChange={(event) => {
                    setFat(
                      event.target.value,
                    );
                  }}
                />
              </label>
            </div>
          ) : null}

          <button
            type="button"
            className={styles.saveButton}
            disabled={saving}
            onClick={() => {
              void saveEdit();
            }}
          >
            {saving
              ? "Salvo…"
              : "Salva modifiche"}
          </button>
        </div>
      ) : null}
    </section>
  );
}
