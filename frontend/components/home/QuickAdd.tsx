"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import { createActivity } from "@/lib/api/activities";
import {
  getIngredients,
  type Ingredient,
} from "@/lib/api/ingredients";
import { createMeal } from "@/lib/api/meals";

import styles from "./QuickAdd.module.css";


type QuickAddMode =
  | null
  | "meal"
  | "snack"
  | "activity";

type MealEntryMode =
  | "quick"
  | "ingredients";


interface QuickAddProps {
  date: string;
  accessToken?: string | null;
  onSaved: () => Promise<void> | void;
}


interface IngredientRow {
  ingredientId: string;
  amount: string;
  unitMode: "g" | "unit";
}


function defaultIngredientAmount(
  ingredient: Ingredient,
): string {
  if (
    ingredient.default_quantity !== null &&
    ingredient.default_quantity !== undefined &&
    Number(ingredient.default_quantity) > 0
  ) {
    return String(
      Number(ingredient.default_quantity),
    );
  }

  return ingredient.grams_per_unit
    ? "1"
    : "100";
}


function ingredientQuantityG(
  row: IngredientRow,
  ingredients: Ingredient[],
): number {
  const ingredient =
    ingredients.find(
      (item) =>
        item.id === row.ingredientId,
    );

  const amount =
    Number(row.amount);

  if (
    !ingredient ||
    !Number.isFinite(amount) ||
    amount <= 0
  ) {
    return 0;
  }

  if (
    row.unitMode === "unit" &&
    ingredient.grams_per_unit
  ) {
    return (
      amount *
      Number(
        ingredient.grams_per_unit,
      )
    );
  }

  return amount;
}


function ingredientUnitLabel(
  ingredient: Ingredient,
  amount: number,
): string {
  const unit =
    ingredient.default_unit || "unità";

  if (unit === "egg") {
    return amount === 1
      ? "uovo"
      : "uova";
  }

  return unit;
}


function roundValue(
  value: number,
  digits = 0,
): string {
  return value.toLocaleString(
    "it-IT",
    {
      maximumFractionDigits: digits,
    },
  );
}


export function QuickAdd({
  date,
  accessToken,
  onSaved,
}: QuickAddProps) {
  const [mode, setMode] =
    useState<QuickAddMode>(null);

  const [mealEntryMode, setMealEntryMode] =
    useState<MealEntryMode>("quick");

  const [mealType, setMealType] =
    useState("Colazione");

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

  const [quantityMode, setQuantityMode] =
    useState<"portion" | "grams">("portion");

  const [mealQuantity, setMealQuantity] =
    useState("1");

  const [ingredients, setIngredients] =
    useState<Ingredient[]>([]);

  const [
    ingredientRows,
    setIngredientRows,
  ] =
    useState<IngredientRow[]>([]);

  const [
    ingredientsLoading,
    setIngredientsLoading,
  ] =
    useState(false);

  const [activityName, setActivityName] =
    useState("");

  const [
    activityCalories,
    setActivityCalories,
  ] =
    useState("");

  const [saving, setSaving] =
    useState(false);

  const [message, setMessage] =
    useState<string | null>(null);


  useEffect(() => {
    if (
      mode !== "meal" ||
      mealEntryMode !== "ingredients" ||
      !accessToken ||
      ingredients.length > 0
    ) {
      return;
    }

    let active = true;

    async function loadIngredients() {
      setIngredientsLoading(true);
      setMessage(null);

      try {
        const response =
          await getIngredients(
            accessToken,
          );

        if (active) {
          setIngredients(
            response.items,
          );
        }
      } catch (err) {
        if (active) {
          setMessage(
            err instanceof Error
              ? err.message
              : "Non riesco a caricare gli ingredienti.",
          );
        }
      } finally {
        if (active) {
          setIngredientsLoading(false);
        }
      }
    }

    void loadIngredients();

    return () => {
      active = false;
    };
  }, [
    mode,
    mealEntryMode,
    accessToken,
    ingredients.length,
  ]);


  const structuredPreview =
    useMemo(() => {
      return ingredientRows.reduce(
        (total, row) => {
          const ingredient =
            ingredients.find(
              (item) =>
                item.id ===
                row.ingredientId,
            );

          const quantityG =
            ingredientQuantityG(
              row,
              ingredients,
            );

          if (
            !ingredient ||
            quantityG <= 0
          ) {
            return total;
          }

          const factor =
            quantityG / 100;

          return {
            calories:
              total.calories +
              Number(
                ingredient
                  .calories_per_100g,
              ) *
                factor,

            protein:
              total.protein +
              Number(
                ingredient
                  .protein_per_100g,
              ) *
                factor,

            carbs:
              total.carbs +
              Number(
                ingredient
                  .carbs_per_100g,
              ) *
                factor,

            fat:
              total.fat +
              Number(
                ingredient
                  .fat_per_100g,
              ) *
                factor,
          };
        },
        {
          calories: 0,
          protein: 0,
          carbs: 0,
          fat: 0,
        },
      );
    }, [
      ingredientRows,
      ingredients,
    ]);


  function close() {
    setMode(null);
    setMessage(null);
  }


  function resetMealFields() {
    setName("");
    setCalories("");
    setProtein("");
    setCarbs("");
    setFat("");
    setIngredientRows([]);
    setMealEntryMode("quick");
  }


  function resetActivityFields() {
    setActivityName("");
    setActivityCalories("");
  }


  function addIngredientRow() {
    const first =
      ingredients[0];

    if (!first) {
      setMessage(
        "Non hai ancora ingredienti disponibili.",
      );
      return;
    }

    setIngredientRows(
      (current) => [
        ...current,
        {
          ingredientId: first.id,
          amount:
            defaultIngredientAmount(
              first,
            ),
          unitMode:
            first.grams_per_unit
              ? "unit"
              : "g",
        },
      ],
    );
  }


  function updateIngredientRow(
    index: number,
    changes: Partial<IngredientRow>,
  ) {
    setIngredientRows(
      (current) =>
        current.map(
          (row, rowIndex) =>
            rowIndex === index
              ? {
                  ...row,
                  ...changes,
                }
              : row,
        ),
    );
  }


  function removeIngredientRow(
    index: number,
  ) {
    setIngredientRows(
      (current) =>
        current.filter(
          (_, rowIndex) =>
            rowIndex !== index,
        ),
    );
  }


  async function saveQuickMeal(
    type: "meal" | "snack",
  ) {
    if (!accessToken) {
      return;
    }

    const cleanName =
      name.trim();

    const kcal =
      Number(calories);

    if (!cleanName) {
      setMessage(
        "Inserisci cosa hai mangiato.",
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
      await createMeal(
        {
          date,
          meal_type:
            type === "snack"
              ? "Spuntino"
              : mealType,
          name: cleanName,
          quantity: Number(mealQuantity) || 1,
          is_per_100g:
            quantityMode === "grams",
          base_name: cleanName,
          base_calories: kcal,
          base_protein:
            Number(protein) || 0,
          base_carbs:
            Number(carbs) || 0,
          base_fat:
            Number(fat) || 0,
          calories: Math.round(
            kcal *
              (quantityMode === "grams"
                ? (Number(mealQuantity) || 1) / 100
                : Number(mealQuantity) || 1),
          ),
          protein: Math.round(
            (Number(protein) || 0) *
              (quantityMode === "grams"
                ? (Number(mealQuantity) || 1) / 100
                : Number(mealQuantity) || 1),
          ),
          carbs: Math.round(
            (Number(carbs) || 0) *
              (quantityMode === "grams"
                ? (Number(mealQuantity) || 1) / 100
                : Number(mealQuantity) || 1),
          ),
          fat: Math.round(
            (Number(fat) || 0) *
              (quantityMode === "grams"
                ? (Number(mealQuantity) || 1) / 100
                : Number(mealQuantity) || 1),
          ),
        },
        accessToken,
      );

      resetMealFields();
      setMode(null);

      await onSaved();
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Non riesco a registrare il pasto.",
      );
    } finally {
      setSaving(false);
    }
  }


  async function saveStructuredMeal(
    type: "meal" | "snack" = "meal",
  ) {
    if (!accessToken) {
      return;
    }

    const cleanName =
      name.trim();

    if (!cleanName) {
      setMessage(
        "Inserisci il nome del pasto.",
      );
      return;
    }

    if (!ingredientRows.length) {
      setMessage(
        "Aggiungi almeno un ingrediente.",
      );
      return;
    }

    const structured =
      ingredientRows.map(
        (row) => {
          const ingredient =
            ingredients.find(
              (item) =>
                item.id ===
                row.ingredientId,
            );

          const amount =
            Number(row.amount);

          const quantityG =
            ingredientQuantityG(
              row,
              ingredients,
            );

          return {
            ingredient_id:
              row.ingredientId,
            quantity:
              amount,
            unit:
              row.unitMode === "unit"
                ? ingredient
                    ?.default_unit ||
                  "unit"
                : "g",
            quantity_g:
              quantityG,
          };
        },
      );

    if (
      structured.some(
        (row) =>
          !row.ingredient_id ||
          !Number.isFinite(
            row.quantity_g,
          ) ||
          row.quantity_g <= 0,
      )
    ) {
      setMessage(
        "Controlla le quantità degli ingredienti.",
      );
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      await createMeal(
        {
          date,
          meal_type:
            type === "snack"
              ? "Spuntino"
              : mealType,
          name: cleanName,

          // Preview values.
          // StructuredMealService recalculates
          // the authoritative totals server-side.
          calories:
            structuredPreview.calories,
          protein:
            structuredPreview.protein,
          carbs:
            structuredPreview.carbs,
          fat:
            structuredPreview.fat,

          structured_ingredients:
            structured,
        },
        accessToken,
      );

      resetMealFields();
      setMode(null);

      await onSaved();
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Non riesco a registrare il pasto.",
      );
    } finally {
      setSaving(false);
    }
  }


  async function saveActivity() {
    if (!accessToken) {
      return;
    }

    const cleanName =
      activityName.trim();

    const burned =
      Number(activityCalories);

    if (!cleanName) {
      setMessage(
        "Inserisci il nome dell’attività.",
      );
      return;
    }

    if (
      !Number.isFinite(burned) ||
      burned < 0
    ) {
      setMessage(
        "Inserisci calorie valide.",
      );
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      await createActivity(
        {
          date,
          activity_name:
            cleanName,
          burned_calories:
            Math.round(burned),
        },
        accessToken,
      );

      resetActivityFields();
      setMode(null);

      await onSaved();
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Non riesco a registrare l’attività.",
      );
    } finally {
      setSaving(false);
    }
  }


  return (
    <section className={styles.section}>
      <div className={styles.header}>
        <div>
          <p className={styles.kicker}>
            Registra
          </p>

          <h2>
            Aggiungi qualcosa alla giornata
          </h2>

          <p className={styles.subtitle}>
            Registra ciò che è successo davvero,
            anche fuori dai suggerimenti.
          </p>
        </div>
      </div>

      <div className={styles.actions}>
        <button
          type="button"
          className={
            mode === "meal"
              ? styles.actionActive
              : styles.action
          }
          onClick={() => {
            setMessage(null);
            setMode(
              mode === "meal"
                ? null
                : "meal",
            );
          }}
        >
          <span className={styles.actionIcon} aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M7 3v7M4.5 3v4.5A2.5 2.5 0 0 0 7 10M9.5 3v4.5A2.5 2.5 0 0 1 7 10v11M16 3v18M16 3c2.5 2.2 3.5 5.2 3 9h-3" />
            </svg>
          </span>
          <span className={styles.actionLabel}>+ Pasto</span>
        </button>

        <button
          type="button"
          className={
            mode === "snack"
              ? styles.actionActive
              : styles.action
          }
          onClick={() => {
            setMessage(null);
            setMode(
              mode === "snack"
                ? null
                : "snack",
            );
          }}
        >
          <span className={styles.actionIcon} aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M12.3 7.2c-1.6-2.3-4.3-2.4-5.8-.8-2 2.1-1.5 7.3.6 10.7 1.2 2 2.4 3.6 4 3.6.7 0 1.2-.3 1.9-.3s1.2.3 1.9.3c1.6 0 2.8-1.6 4-3.6 2.1-3.4 2.6-8.6.6-10.7-1.5-1.6-4.2-1.5-5.8.8" />
              <path d="M12.2 6.7c0-2 1.4-3.7 3.5-4.2.1 2.1-1.2 3.8-3.5 4.2Z" />
            </svg>
          </span>
          <span className={styles.actionLabel}>+ Snack</span>
        </button>

        <button
          type="button"
          className={
            mode === "activity"
              ? styles.actionActive
              : styles.action
          }
          onClick={() => {
            setMessage(null);
            setMode(
              mode === "activity"
                ? null
                : "activity",
            );
          }}
        >
          <span className={styles.actionIcon} aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <circle cx="15.5" cy="4.5" r="2" />
              <path d="m13 8-2.2 3.2 3.2 2.3 1.8 3.3M13 8l3.2 2 2.8-.7M10.8 11.2 8 10M14 13.5l-3 2.2-1.5 4M15.8 16.8l2.8 3" />
            </svg>
          </span>
          <span className={styles.actionLabel}>+ Attività</span>
        </button>
      </div>

      {message ? (
        <div className={styles.message}>
          {message}
        </div>
      ) : null}

      {mode === "meal" || mode === "snack" ? (
        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <strong>
              {mode === "snack"
                ? "Aggiungi snack"
                : "Aggiungi pasto"}
            </strong>

            <button
              type="button"
              className={styles.closeButton}
              onClick={close}
            >
              Chiudi
            </button>
          </div>

          <div className={styles.modeSwitch}>
            <button
              type="button"
              className={
                mealEntryMode === "quick"
                  ? styles.modeActive
                  : styles.modeButton
              }
              onClick={() => {
                setMealEntryMode(
                  "quick",
                );
                setMessage(null);
              }}
            >
              Rapido
            </button>

            <button
              type="button"
              className={
                mealEntryMode ===
                "ingredients"
                  ? styles.modeActive
                  : styles.modeButton
              }
              onClick={() => {
                setMealEntryMode(
                  "ingredients",
                );
                setMessage(null);
              }}
            >
              Con ingredienti
            </button>
          </div>

          {mode === "meal" ? (
            <label>
              <span>Tipo di pasto</span>

              <select
                value={mealType}
                onChange={(event) => {
                  setMealType(
                    event.target.value,
                  );
                }}
              >
                <option value="Colazione">
                  Colazione
                </option>
                <option value="Pranzo">
                  Pranzo
                </option>
                <option value="Cena">
                  Cena
                </option>
              </select>
            </label>
          ) : null}

          <label>
            <span>
              Nome del pasto
            </span>

            <input
              value={name}
              placeholder="Es. Pollo e riso"
              onChange={(event) => {
                setName(
                  event.target.value,
                );
              }}
            />
          </label>

          {mealEntryMode === "quick" ? (
            <>
              <label>
                <span>Unità</span>

                <select
                  value={quantityMode}
                  onChange={(event) => {
                    const nextMode =
                      event.target.value === "grams"
                        ? "grams"
                        : "portion";

                    setQuantityMode(nextMode);
                    setMealQuantity(
                      nextMode === "grams"
                        ? "100"
                        : "1",
                    );
                  }}
                >
                  <option value="portion">
                    Porzioni
                  </option>
                  <option value="grams">
                    Grammi
                  </option>
                </select>
              </label>

              <label>
                <span>
                  {quantityMode === "grams"
                    ? "Grammi"
                    : "Porzioni"}
                </span>

                <input
                  type="number"
                  min={
                    quantityMode === "grams"
                      ? "1"
                      : "0.25"
                  }
                  step={
                    quantityMode === "grams"
                      ? "1"
                      : "0.25"
                  }
                  value={mealQuantity}
                  onChange={(event) => {
                    setMealQuantity(
                      event.target.value,
                    );
                  }}
                />
              </label>

              <label>
                <span>
                  {quantityMode === "grams"
                    ? "Calorie per 100 g"
                    : "Calorie per porzione"}
                </span>

                <input
                  type="number"
                  min="0"
                  value={calories}
                  placeholder="650"
                  onChange={(event) => {
                    setCalories(
                      event.target.value,
                    );
                  }}
                />
              </label>

              <div className={styles.macroGrid}>
                <label>
                  <span>
                    {quantityMode === "grams"
                      ? "Proteine per 100 g"
                      : "Proteine per porzione"}
                  </span>
                  <input
                    type="number"
                    min="0"
                    value={protein}
                    placeholder="25"
                    onChange={(event) => {
                      setProtein(
                        event.target.value,
                      );
                    }}
                  />
                </label>

                <label>
                  <span>
                    {quantityMode === "grams"
                      ? "Carbo per 100 g"
                      : "Carbo per porzione"}
                  </span>
                  <input
                    type="number"
                    min="0"
                    value={carbs}
                    placeholder="70"
                    onChange={(event) => {
                      setCarbs(
                        event.target.value,
                      );
                    }}
                  />
                </label>

                <label>
                  <span>
                    {quantityMode === "grams"
                      ? "Grassi per 100 g"
                      : "Grassi per porzione"}
                  </span>
                  <input
                    type="number"
                    min="0"
                    value={fat}
                    placeholder="18"
                    onChange={(event) => {
                      setFat(
                        event.target.value,
                      );
                    }}
                  />
                </label>
              </div>

              <button
                type="button"
                className={styles.saveButton}
                disabled={saving}
                onClick={() => {
                  void saveQuickMeal(
                    mode === "snack"
                      ? "snack"
                      : "meal",
                  );
                }}
              >
                {saving
                  ? "Salvo…"
                  : mode === "snack"
                    ? "Salva snack"
                    : "Salva pasto"}
              </button>
            </>
          ) : (
            <>
              {ingredientsLoading ? (
                <div className={styles.helper}>
                  Carico gli ingredienti…
                </div>
              ) : ingredients.length ? (
                <>
                  <div className={styles.ingredientList}>
                    {ingredientRows.map(
                      (row, index) => (
                        <div
                          key={index}
                          className={
                            styles.ingredientRow
                          }
                        >
                          <select
                            value={
                              row.ingredientId
                            }
                            onChange={(event) => {
                              const ingredient =
                                ingredients.find(
                                  (item) =>
                                    item.id ===
                                    event.target
                                      .value,
                                );

                              updateIngredientRow(
                                index,
                                {
                                  ingredientId:
                                    event.target
                                      .value,
                                  amount:
                                    ingredient
                                      ? defaultIngredientAmount(
                                          ingredient,
                                        )
                                      : "100",
                                  unitMode:
                                    ingredient
                                      ?.grams_per_unit
                                      ? "unit"
                                      : "g",
                                },
                              );
                            }}
                          >
                            {ingredients.map(
                              (ingredient) => (
                                <option
                                  key={
                                    ingredient.id
                                  }
                                  value={
                                    ingredient.id
                                  }
                                >
                                  {
                                    ingredient.name
                                  }
                                </option>
                              ),
                            )}
                          </select>

                          <div
                            className={
                              styles.quantity
                            }
                          >
                            <input
                              type="number"
                              min="0"
                              step={
                                row.unitMode ===
                                "unit"
                                  ? "0.5"
                                  : "1"
                              }
                              value={
                                row.amount
                              }
                              onChange={(event) => {
                                updateIngredientRow(
                                  index,
                                  {
                                    amount:
                                      event
                                        .target
                                        .value,
                                  },
                                );
                              }}
                            />

                            {(() => {
                              const ingredient =
                                ingredients.find(
                                  (item) =>
                                    item.id ===
                                    row.ingredientId,
                                );

                              if (
                                !ingredient ||
                                !ingredient
                                  .grams_per_unit
                              ) {
                                return (
                                  <span>g</span>
                                );
                              }

                              return (
                                <select
                                  value={
                                    row.unitMode
                                  }
                                  onChange={(
                                    event,
                                  ) => {
                                    updateIngredientRow(
                                      index,
                                      {
                                        unitMode:
                                          event
                                            .target
                                            .value as
                                            | "g"
                                            | "unit",
                                      },
                                    );
                                  }}
                                >
                                  <option value="unit">
                                    {ingredientUnitLabel(
                                      ingredient,
                                      Number(
                                        row.amount,
                                      ),
                                    )}
                                  </option>

                                  <option value="g">
                                    g
                                  </option>
                                </select>
                              );
                            })()}
                          </div>

                          <button
                            type="button"
                            className={
                              styles.removeIngredient
                            }
                            aria-label="Rimuovi ingrediente"
                            onClick={() => {
                              removeIngredientRow(
                                index,
                              );
                            }}
                          >
                            ×
                          </button>
                        </div>
                      ),
                    )}
                  </div>

                  <button
                    type="button"
                    className={
                      styles.addIngredientButton
                    }
                    onClick={
                      addIngredientRow
                    }
                  >
                    + Aggiungi ingrediente
                  </button>

                  {ingredientRows.length ? (
                    <div
                      className={
                        styles.nutritionPreview
                      }
                    >
                      <div>
                        <span>
                          Stima pasto
                        </span>
                        <strong>
                          {roundValue(
                            structuredPreview.calories,
                          )}{" "}
                          kcal
                        </strong>
                      </div>

                      <div>
                        <span>Proteine</span>
                        <strong>
                          {roundValue(
                            structuredPreview.protein,
                            1,
                          )}{" "}
                          g
                        </strong>
                      </div>

                      <div>
                        <span>Carbo</span>
                        <strong>
                          {roundValue(
                            structuredPreview.carbs,
                            1,
                          )}{" "}
                          g
                        </strong>
                      </div>

                      <div>
                        <span>Grassi</span>
                        <strong>
                          {roundValue(
                            structuredPreview.fat,
                            1,
                          )}{" "}
                          g
                        </strong>
                      </div>
                    </div>
                  ) : null}

                  <button
                    type="button"
                    className={
                      styles.saveButton
                    }
                    disabled={
                      saving ||
                      !ingredientRows.length
                    }
                    onClick={() => {
                      void saveStructuredMeal(
                        mode === "snack"
                          ? "snack"
                          : "meal",
                      );
                    }}
                  >
                    {saving
                      ? "Salvo…"
                      : mode === "snack"
                        ? "Salva snack"
                        : "Salva pasto"}
                  </button>
                </>
              ) : (
                <div className={styles.helper}>
                  Non hai ancora ingredienti
                  nella libreria SanoSync.
                </div>
              )}
            </>
          )}
        </div>
      ) : null}

      {mode === "activity" ? (
        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <strong>
              Aggiungi attività
            </strong>

            <button
              type="button"
              className={styles.closeButton}
              onClick={close}
            >
              Chiudi
            </button>
          </div>

          <label>
            <span>Cosa hai fatto?</span>

            <input
              value={activityName}
              placeholder="Es. Padel"
              onChange={(event) => {
                setActivityName(
                  event.target.value,
                );
              }}
            />
          </label>

          <label>
            <span>
              Calorie bruciate
            </span>

            <input
              type="number"
              min="0"
              value={activityCalories}
              placeholder="450"
              onChange={(event) => {
                setActivityCalories(
                  event.target.value,
                );
              }}
            />
          </label>

          <button
            type="button"
            className={styles.saveButton}
            disabled={saving}
            onClick={() => {
              void saveActivity();
            }}
          >
            {saving
              ? "Salvo…"
              : "Registra attività"}
          </button>
        </div>
      ) : null}
    </section>
  );
}
