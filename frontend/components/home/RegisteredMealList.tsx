"use client";

import type { LoggedMeal } from "@/lib/api/meals";

import styles from "./HomeShell.module.css";

type RegisteredMealCopy = {
  portions: string;
  edit: string;
  delete: string;
  proteins: string;
  carbs: string;
  fats: string;
  mealLogged: string;
  lowProtein: string;
  highProtein: string;
};

type RegisteredMealListProps = {
  meals: LoggedMeal[];
  copy: RegisteredMealCopy;
  deletingMealId: LoggedMeal["id"] | null;
  editingMealId: LoggedMeal["id"] | null;
  savingMealEdit: boolean;
  formatNumber: (value: number) => string;
  onAdjustPortions: (meal: LoggedMeal, delta: number) => void;
  onEdit: (meal: LoggedMeal) => void;
  onDelete: (meal: LoggedMeal) => void;
};

export function RegisteredMealList({
  meals,
  copy,
  deletingMealId,
  editingMealId,
  savingMealEdit,
  formatNumber,
  onAdjustPortions,
  onEdit,
  onDelete,
}: RegisteredMealListProps) {
  const totals = meals.reduce(
    (sum, meal) => ({
      calories: sum.calories + Number(meal.calories || 0),
      protein: sum.protein + Number(meal.protein || 0),
      carbs: sum.carbs + Number(meal.carbs || 0),
      fat: sum.fat + Number(meal.fat || 0),
    }),
    { calories: 0, protein: 0, carbs: 0, fat: 0 },
  );

  return (
    <>
      <div className={styles.registeredMealList}>
        {meals.map((registeredMeal) => (
          <div
            key={String(
              registeredMeal.id ?? registeredMeal.name,
            )}
            className={styles.registeredMealRow}
          >
            <div className={styles.registeredMealRowInfo}>
              <strong>
                {registeredMeal.name.replace(
                  /\s*\([^)]*porz\.\)\s*$/i,
                  "",
                )}
              </strong>

              <span>
                {registeredMeal.recipe_servings
                  ? `${formatNumber(
                      registeredMeal.recipe_servings,
                    )} ${copy.portions}`
                  : `1 ${copy.portions}`}
              </span>
            </div>

            <div className={styles.registeredMealRowActions}>
              <div
                className={
                  styles.registeredMealPortionControl
                }
              >
                <button
                  type="button"
                  aria-label="Togli una porzione"
                  disabled={
                    deletingMealId !== null ||
                    savingMealEdit
                  }
                  onClick={() =>
                    onAdjustPortions(registeredMeal, -1)
                  }
                >
                  −
                </button>

                <span>
                  {formatNumber(
                    Math.max(
                      1,
                      Number(
                        registeredMeal.recipe_servings,
                      ) || 1,
                    ),
                  )}
                </span>

                <button
                  type="button"
                  aria-label="Aggiungi una porzione"
                  disabled={
                    deletingMealId !== null ||
                    savingMealEdit
                  }
                  onClick={() =>
                    onAdjustPortions(registeredMeal, 1)
                  }
                >
                  +
                </button>
              </div>

              <button
                type="button"
                disabled={
                  deletingMealId !== null ||
                  savingMealEdit
                }
                onClick={() => onEdit(registeredMeal)}
              >
                ✎{" "}
                {editingMealId === registeredMeal.id
                  ? "Chiudi"
                  : copy.edit}
              </button>

              <button
                type="button"
                className={styles.registeredMealRowDelete}
                disabled={
                  deletingMealId !== null ||
                  savingMealEdit
                }
                onClick={() => onDelete(registeredMeal)}
              >
                🗑{" "}
                {deletingMealId === registeredMeal.id
                  ? "Elimino…"
                  : copy.delete}
              </button>
            </div>
          </div>
        ))}
      </div>

      {meals.length > 0 ? (
        <div className={styles.registeredMealNutrition}>
          <div className={styles.nutritionItem}>
            <strong>{formatNumber(totals.calories)}</strong>
            <span>kcal</span>
          </div>

          <div className={styles.nutritionItem}>
            <strong>{formatNumber(totals.protein)}</strong>
            <span>{copy.proteins}</span>
          </div>

          <div className={styles.nutritionItem}>
            <strong>{formatNumber(totals.carbs)}</strong>
            <span>{copy.carbs}</span>
          </div>

          <div className={styles.nutritionItem}>
            <strong>{formatNumber(totals.fat)}</strong>
            <span>{copy.fats}</span>
          </div>
        </div>
      ) : null}

      {meals.length > 0 ? (
        <div className={styles.registeredMealInsights}>
          <span
            className={
              styles.registeredMealInsightSuccess
            }
          >
            {copy.mealLogged}
          </span>

          {totals.protein < 15 ? (
            <span
              className={
                styles.registeredMealInsightWarning
              }
            >
              {copy.lowProtein}
            </span>
          ) : totals.protein <= 30 ? (
            <span
              className={
                styles.registeredMealInsightSuccess
              }
            >
              ✓ Buon apporto proteico
            </span>
          ) : (
            <span
              className={
                styles.registeredMealInsightSuccess
              }
            >
              {copy.highProtein}
            </span>
          )}
        </div>
      ) : null}
    </>
  );
}
