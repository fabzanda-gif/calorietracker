"use client";

import { type FormEvent, useEffect, useState } from "react";

import { AppNav } from "@/components/navigation/AppNav";
import { useAuth } from "@/components/auth/AuthProvider";
import {
  discardMealPrepPortions,
  getMealPrepInventory,
  logMealPrepPortion,
  type MealPrepItem,
} from "@/lib/api/mealPrep";
import {
  createIngredient,
  getIngredients,
  updateIngredient,
  type Ingredient,
} from "@/lib/api/ingredients";
import {
  createPantryItem,
  deletePantryItem,
  getPantry,
  updatePantryItem,
  type PantryItem,
} from "@/lib/api/pantry";

import styles from "./InventoryPage.module.css";

type PantryMealSlot =
  | "breakfast"
  | "lunch"
  | "snack"
  | "dinner";

const EMPTY_PANTRY_FORM = {
  ingredientId: "",
  quantity: "",
  quantityMode: "weight" as "weight" | "portion",
  unit: "g",
  gramsPerPortion: "",
  expiresAt: "",
  mealSlots: [] as PantryMealSlot[],
};

const EMPTY_NEW_FOOD_FORM = {
  name: "",
  calories: "",
  protein: "",
  carbs: "",
  fat: "",
  kind: "product" as "ingredient" | "product" | "prepared_food",
  mealSlots: [] as PantryMealSlot[],
};

export default function InventoryPage() {
  const { accessToken } = useAuth();

  const [items, setItems] = useState<MealPrepItem[]>([]);
  const [pantryItems, setPantryItems] = useState<PantryItem[]>([]);
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);

  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [pantrySaving, setPantrySaving] = useState(false);
  const [editingPantryId, setEditingPantryId] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [mealType, setMealType] = useState("Cena");
  const [pantryForm, setPantryForm] = useState(EMPTY_PANTRY_FORM);

  const [showPantryForm, setShowPantryForm] = useState(false);
  const [showNewFoodForm, setShowNewFoodForm] = useState(false);
  const [newFoodSaving, setNewFoodSaving] = useState(false);
  const [newFoodForm, setNewFoodForm] = useState(EMPTY_NEW_FOOD_FORM);

  async function refresh() {
    if (!accessToken) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [mealPrepResponse, pantryResponse, ingredientsResponse] =
        await Promise.all([
          getMealPrepInventory(accessToken, true),
          getPantry(accessToken),
          getIngredients(accessToken),
        ]);

      setItems(mealPrepResponse.items);
      setPantryItems(pantryResponse.items);
      setIngredients(ingredientsResponse.items);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Impossibile caricare la dispensa.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, [accessToken]);

  async function discard(item: MealPrepItem) {
    if (!accessToken || item.portions_remaining <= 0) {
      return;
    }

    const confirmed = window.confirm(
      `Eliminare 1 porzione di "${item.name}" dall'inventario?`,
    );

    if (!confirmed) {
      return;
    }

    setBusyId(item.id);
    setError(null);

    try {
      await discardMealPrepPortions(
        accessToken,
        item.id,
        1,
      );

      await refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Impossibile eliminare la porzione.",
      );
    } finally {
      setBusyId(null);
    }
  }

  async function consume(item: MealPrepItem) {
    if (!accessToken || item.portions_remaining <= 0) {
      return;
    }

    setBusyId(item.id);
    setError(null);

    try {
      await logMealPrepPortion(
        accessToken,
        item.id,
        new Date().toISOString().slice(0, 10),
        mealType,
      );

      await refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Impossibile registrare il pasto.",
      );
    } finally {
      setBusyId(null);
    }
  }

  function ingredientForPantryId(
    ingredientId: string,
  ): Ingredient | null {
    return (
      ingredients.find(
        (ingredient) =>
          String(ingredient.id) ===
          String(ingredientId),
      ) ?? null
    );
  }

  function togglePantryMealSlot(
    slot: PantryMealSlot,
  ) {
    setPantryForm((current) => ({
      ...current,
      mealSlots: current.mealSlots.includes(slot)
        ? current.mealSlots.filter(
            (item) => item !== slot,
          )
        : [...current.mealSlots, slot],
    }));
  }

  function toggleNewFoodMealSlot(slot: PantryMealSlot) {
    setNewFoodForm((current) => ({
      ...current,
      mealSlots: current.mealSlots.includes(slot)
        ? current.mealSlots.filter((item) => item !== slot)
        : [...current.mealSlots, slot],
    }));
  }

  async function saveNewFood(event: FormEvent) {
    event.preventDefault();

    if (!accessToken) {
      return;
    }

    const calories = Number(newFoodForm.calories);
    const protein = Number(newFoodForm.protein);
    const carbs = Number(newFoodForm.carbs);
    const fat = Number(newFoodForm.fat);

    if (!newFoodForm.name.trim()) {
      setError("Inserisci il nome dell'alimento.");
      return;
    }

    if (
      [calories, protein, carbs, fat].some(
        (value) => !Number.isFinite(value) || value < 0,
      )
    ) {
      setError("Inserisci valori nutrizionali validi.");
      return;
    }

    setNewFoodSaving(true);
    setError(null);

    try {
      const response = await createIngredient(
        {
          name: newFoodForm.name.trim(),
          calories_per_100g: calories,
          protein_per_100g: protein,
          carbs_per_100g: carbs,
          fat_per_100g: fat,
          default_unit: "g",
          default_quantity: 100,
          kind: newFoodForm.kind,
          meal_slots: newFoodForm.mealSlots,
        },
        accessToken,
      );

      setIngredients((current) =>
        [...current.filter((item) => item.id !== response.item.id), response.item]
          .sort((a, b) => a.name.localeCompare(b.name)),
      );

      setPantryForm({
        ...EMPTY_PANTRY_FORM,
        ingredientId: response.item.id,
        mealSlots: response.item.meal_slots as PantryMealSlot[],
      });

      setNewFoodForm(EMPTY_NEW_FOOD_FORM);
      setShowNewFoodForm(false);
      setShowPantryForm(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Impossibile creare l'alimento.",
      );
    } finally {
      setNewFoodSaving(false);
    }
  }

  async function savePantry(event: FormEvent) {
    event.preventDefault();

    if (!accessToken) {
      return;
    }

    const quantity = Number(pantryForm.quantity);
    const gramsPerPortion =
      pantryForm.quantityMode === "portion"
        ? Number(pantryForm.gramsPerPortion)
        : null;

    if (
      !pantryForm.ingredientId ||
      !Number.isFinite(quantity) ||
      quantity <= 0
    ) {
      setError(
        "Seleziona un alimento e inserisci una quantità valida.",
      );
      return;
    }

    if (
      pantryForm.quantityMode === "portion" &&
      (
        !Number.isFinite(gramsPerPortion) ||
        Number(gramsPerPortion) <= 0
      )
    ) {
      setError(
        "Inserisci il peso in grammi di una porzione.",
      );
      return;
    }

    if (pantryForm.mealSlots.length === 0) {
      setError(
        "Scegli almeno un momento in cui questo alimento è adatto.",
      );
      return;
    }

    setPantrySaving(true);
    setError(null);

    try {
      await updateIngredient(
        pantryForm.ingredientId,
        {
          meal_slots: pantryForm.mealSlots,
        },
        accessToken,
      );

      if (editingPantryId) {
        await updatePantryItem(
          accessToken,
          editingPantryId,
          {
            quantity,
            unit:
              pantryForm.quantityMode === "portion"
                ? "portion"
                : pantryForm.unit,
            quantity_mode: pantryForm.quantityMode,
            grams_per_portion: gramsPerPortion,
            expires_at: pantryForm.expiresAt || null,
          },
        );
      } else {
        await createPantryItem(
          accessToken,
          {
            ingredient_id: pantryForm.ingredientId,
            quantity,
            unit:
              pantryForm.quantityMode === "portion"
                ? "portion"
                : pantryForm.unit,
            quantity_mode: pantryForm.quantityMode,
            grams_per_portion: gramsPerPortion,
            expires_at: pantryForm.expiresAt || null,
          },
        );
      }

      setPantryForm(EMPTY_PANTRY_FORM);
      setEditingPantryId(null);
      await refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Impossibile salvare l'alimento.",
      );
    } finally {
      setPantrySaving(false);
    }
  }

  function editPantry(item: PantryItem) {
    setShowNewFoodForm(false);
    setShowPantryForm(true);

    const ingredient =
      ingredientForPantryId(
        item.ingredient_id,
      );

    setEditingPantryId(item.id);
    setPantryForm({
      ingredientId: item.ingredient_id,
      quantity: String(item.quantity),
      quantityMode: item.quantity_mode ?? "weight",
      unit:
        item.quantity_mode === "portion"
          ? "g"
          : item.unit,
      gramsPerPortion:
        item.grams_per_portion != null
          ? String(item.grams_per_portion)
          : "",
      expiresAt: item.expires_at || "",
      mealSlots:
        (ingredient?.meal_slots ??
          []) as PantryMealSlot[],
    });
  }

  async function removePantry(item: PantryItem) {
    if (
      !accessToken ||
      !window.confirm(
        `Rimuovere "${item.ingredient_name || "alimento"}" dalla dispensa?`,
      )
    ) {
      return;
    }

    setBusyId(item.id);
    setError(null);

    try {
      await deletePantryItem(accessToken, item.id);

      if (editingPantryId === item.id) {
        setEditingPantryId(null);
        setPantryForm(EMPTY_PANTRY_FORM);
      }

      await refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Impossibile rimuovere l'alimento.",
      );
    } finally {
      setBusyId(null);
    }
  }

  if (!accessToken) {
    return (
      <>
        <AppNav />
        <main className={styles.page}>
          <section className={styles.card}>
            <h1>Dispensa</h1>
            <p>Effettua l'accesso per vedere la dispensa.</p>
          </section>
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
            <h1>Dispensa</h1>
            <p>
              Meal prep già pronti e alimenti che hai a disposizione.
            </p>
          </div>

          <label className={styles.mealType}>
            <span>Registra meal prep come</span>

            <select
              value={mealType}
              onChange={(event) => {
                setMealType(event.target.value);
              }}
            >
              <option value="Colazione">Colazione</option>
              <option value="Pranzo">Pranzo</option>
              <option value="Cena">Cena</option>
              <option value="Spuntino">Spuntino</option>
            </select>
          </label>

          <div className={styles.headerActions}>
            <button
              type="button"
              className={styles.secondaryHeaderAction}
              onClick={() => {
                setShowNewFoodForm(false);
                setShowPantryForm((current) => !current);
              }}
            >
              + Aggiungi scorta
            </button>

            <button
              type="button"
              className={styles.primaryHeaderAction}
              onClick={() => {
                setShowPantryForm(false);
                setShowNewFoodForm((current) => !current);
              }}
            >
              + Nuovo alimento
            </button>

            <button
              type="button"
              className={styles.refresh}
              onClick={() => void refresh()}
              disabled={loading}
              aria-label="Aggiorna dispensa"
            >
              ↻
            </button>
          </div>
        </div>

        {error && (
          <section className={styles.error}>
            {error}
          </section>
        )}

        {showNewFoodForm && (
          <section className={styles.newFoodPanel}>
            <div className={styles.newFoodPanelHead}>
              <div>
                <p className={styles.pantryKicker}>NUOVO ALIMENTO</p>
                <h2>Crea un alimento</h2>
                <p>
                  Inserisci i valori nutrizionali per 100 g e scegli quando usarlo.
                </p>
              </div>

              <button
                type="button"
                className={styles.panelClose}
                onClick={() => setShowNewFoodForm(false)}
                aria-label="Chiudi"
              >
                ×
              </button>
            </div>

            <form
              className={styles.newFoodForm}
              onSubmit={saveNewFood}
            >
              <label className={styles.newFoodName}>
                <span>Nome alimento</span>
                <input
                  required
                  value={newFoodForm.name}
                  placeholder="Es. Yogurt greco"
                  onChange={(event) =>
                    setNewFoodForm({
                      ...newFoodForm,
                      name: event.target.value,
                    })
                  }
                />
              </label>

              {[
                ["calories", "kcal / 100 g"],
                ["protein", "Proteine"],
                ["carbs", "Carboidrati"],
                ["fat", "Grassi"],
              ].map(([key, label]) => (
                <label key={key}>
                  <span>{label}</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    required
                    value={
                      newFoodForm[
                        key as "calories" | "protein" | "carbs" | "fat"
                      ]
                    }
                    onChange={(event) =>
                      setNewFoodForm({
                        ...newFoodForm,
                        [key]: event.target.value,
                      })
                    }
                  />
                </label>
              ))}

              <label>
                <span>Tipo</span>
                <select
                  value={newFoodForm.kind}
                  onChange={(event) =>
                    setNewFoodForm({
                      ...newFoodForm,
                      kind: event.target.value as
                        | "ingredient"
                        | "product"
                        | "prepared_food",
                    })
                  }
                >
                  <option value="product">Alimento / prodotto</option>
                  <option value="ingredient">Ingrediente ricetta</option>
                  <option value="prepared_food">Alimento preparato</option>
                </select>
              </label>

              <fieldset className={styles.newFoodSlots}>
                <legend>Usalo per</legend>

                <div>
                  {[
                    ["breakfast", "☕", "Colazione"],
                    ["snack", "🍎", "Snack"],
                    ["lunch", "🍽️", "Pranzo"],
                    ["dinner", "🥗", "Cena"],
                  ].map(([slot, icon, label]) => {
                    const value = slot as PantryMealSlot;
                    const active = newFoodForm.mealSlots.includes(value);

                    return (
                      <label
                        key={value}
                        className={
                          active ? styles.newFoodSlotActive : undefined
                        }
                      >
                        <input
                          type="checkbox"
                          checked={active}
                          onChange={() => toggleNewFoodMealSlot(value)}
                        />
                        <span>{icon}</span>
                        <strong>{label}</strong>
                      </label>
                    );
                  })}
                </div>
              </fieldset>

              <div className={styles.newFoodActions}>
                <button
                  type="submit"
                  className={styles.primaryHeaderAction}
                  disabled={newFoodSaving}
                >
                  {newFoodSaving ? "Creazione..." : "Crea alimento"}
                </button>

                <button
                  type="button"
                  className={styles.secondaryHeaderAction}
                  onClick={() => setShowNewFoodForm(false)}
                >
                  Annulla
                </button>
              </div>
            </form>
          </section>
        )}

        <section className={styles.pantrySection}>
          <div className={styles.pantrySectionHead}>
            <div>
              <p className={styles.pantryKicker}>ALIMENTI</p>
              <h2>Alimenti in dispensa</h2>
              <p>
                Registra quello che hai davvero disponibile in casa.
              </p>
            </div>
          </div>

          {ingredients.length === 0 ? (
            <div className={styles.pantryEmpty}>
              <strong>Prima aggiungi un alimento alla libreria.</strong>
              <p>
                Gli alimenti della dispensa fanno riferimento alla tua libreria
                nutrizionale.
              </p>
              <a href="/ingredients">Vai alla libreria alimenti</a>
            </div>
          ) : (
            <form
              className={`${styles.pantryForm} ${
                showPantryForm || editingPantryId
                  ? styles.pantryFormVisible
                  : styles.pantryFormHidden
              }`}
              onSubmit={savePantry}
            >
              <label className={styles.pantryFood}>
                <span>Alimento</span>

                <select
                  required
                  disabled={Boolean(editingPantryId)}
                  value={pantryForm.ingredientId}
                  onChange={(event) => {
                    const ingredientId =
                      event.target.value;

                    const ingredient =
                      ingredientForPantryId(
                        ingredientId,
                      );

                    setPantryForm({
                      ...pantryForm,
                      ingredientId,
                      mealSlots:
                        (ingredient?.meal_slots ??
                          []) as PantryMealSlot[],
                    });
                  }}
                >
                  <option value="">Seleziona alimento</option>

                  {ingredients.map((ingredient) => (
                    <option
                      key={ingredient.id}
                      value={ingredient.id}
                    >
                      {ingredient.name}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                <span>Come la conteggi?</span>

                <select
                  value={pantryForm.quantityMode}
                  onChange={(event) => {
                    const quantityMode =
                      event.target.value as
                        | "weight"
                        | "portion";

                    setPantryForm({
                      ...pantryForm,
                      quantityMode,
                      quantity: "",
                      unit:
                        quantityMode === "weight"
                          ? "g"
                          : pantryForm.unit,
                      gramsPerPortion: "",
                    });
                  }}
                >
                  <option value="weight">
                    A peso / volume
                  </option>
                  <option value="portion">
                    A porzioni / pezzi
                  </option>
                </select>
              </label>

              <label>
                <span>
                  {pantryForm.quantityMode === "portion"
                    ? "Numero di porzioni"
                    : "Quantità"}
                </span>

                <input
                  type="number"
                  min={
                    pantryForm.quantityMode === "portion"
                      ? "1"
                      : "0.01"
                  }
                  step={
                    pantryForm.quantityMode === "portion"
                      ? "1"
                      : "0.01"
                  }
                  required
                  value={pantryForm.quantity}
                  onChange={(event) =>
                    setPantryForm({
                      ...pantryForm,
                      quantity: event.target.value,
                    })
                  }
                />
              </label>

              {pantryForm.quantityMode === "portion" ? (
                <label>
                  <span>Peso per porzione</span>

                  <div>
                    <input
                      type="number"
                      min="0.01"
                      step="0.01"
                      required
                      value={pantryForm.gramsPerPortion}
                      onChange={(event) =>
                        setPantryForm({
                          ...pantryForm,
                          gramsPerPortion:
                            event.target.value,
                        })
                      }
                    />
                    <small> grammi</small>
                  </div>
                </label>
              ) : (
                <label>
                  <span>Unità</span>

                  <select
                    value={pantryForm.unit}
                    onChange={(event) =>
                      setPantryForm({
                        ...pantryForm,
                        unit: event.target.value,
                      })
                    }
                  >
                    <option value="g">g</option>
                    <option value="kg">kg</option>
                    <option value="ml">ml</option>
                    <option value="l">l</option>
                  </select>
                </label>
              )}

              <fieldset
                className={styles.pantryMealSlots}
              >
                <legend>Usalo per</legend>

                <p>
                  Colazione e snack vengono considerati
                  compatibili tra loro; lo stesso vale per
                  pranzo e cena.
                </p>

                <div
                  className={
                    styles.pantryMealSlotOptions
                  }
                >
                  {[
                    [
                      "breakfast",
                      "☕",
                      "Colazione",
                    ],
                    ["snack", "🍎", "Snack"],
                    ["lunch", "🍽️", "Pranzo"],
                    ["dinner", "🥗", "Cena"],
                  ].map(([slot, icon, label]) => {
                    const value =
                      slot as PantryMealSlot;

                    const checked =
                      pantryForm.mealSlots.includes(
                        value,
                      );

                    return (
                      <label
                        key={value}
                        className={
                          checked
                            ? styles.pantryMealSlotActive
                            : undefined
                        }
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() =>
                            togglePantryMealSlot(
                              value,
                            )
                          }
                        />

                        <span aria-hidden="true">
                          {icon}
                        </span>

                        <strong>{label}</strong>
                      </label>
                    );
                  })}
                </div>
              </fieldset>

              <label>
                <span>Scadenza</span>
                <input
                  type="date"
                  value={pantryForm.expiresAt}
                  onChange={(event) =>
                    setPantryForm({
                      ...pantryForm,
                      expiresAt: event.target.value,
                    })
                  }
                />
              </label>

              <div className={styles.pantryFormActions}>
                <button
                  type="submit"
                  className={styles.pantryPrimary}
                  disabled={pantrySaving}
                >
                  {pantrySaving
                    ? "Salvataggio..."
                    : editingPantryId
                      ? "Salva modifiche"
                      : "Aggiungi alimento"}
                </button>

                {editingPantryId && (
                  <button
                    type="button"
                    className={styles.pantrySecondary}
                    onClick={() => {
                      setEditingPantryId(null);
                      setPantryForm(EMPTY_PANTRY_FORM);
                    }}
                  >
                    Annulla
                  </button>
                )}
              </div>
            </form>
          )}

          {!loading && pantryItems.length > 0 && (
            <div className={styles.pantryList}>
              {pantryItems.map((item) => (
                <article
                  key={item.id}
                  className={styles.pantryItem}
                >
                  <div
                    className={styles.pantryItemIcon}
                    aria-hidden="true"
                  >
                    {(() => {
                      const ingredient =
                        ingredientForPantryId(
                          item.ingredient_id,
                        );

                      if (
                        ingredient?.kind ===
                        "prepared_food"
                      ) {
                        return "▣";
                      }

                      if (
                        ingredient?.kind ===
                        "ingredient"
                      ) {
                        return "◇";
                      }

                      return "○";
                    })()}
                  </div>

                  <div className={styles.pantryItemBody}>
                    <p className={styles.pantryKicker}>
                      Alimento
                    </p>

                    <h3>
                      {item.ingredient_name || "Alimento"}
                    </h3>

                    <strong>
                      {item.quantity_mode === "portion"
                        ? `${item.quantity} ${
                            item.quantity === 1
                              ? "porzione"
                              : "porzioni"
                          }`
                        : `${item.quantity} ${item.unit}`}
                    </strong>

                    {item.quantity_mode === "portion" &&
                    item.grams_per_portion != null ? (
                      <p>
                        {item.grams_per_portion} g per porzione
                        {" · "}
                        {Math.round(
                          item.quantity *
                            item.grams_per_portion,
                        )} g equivalenti
                      </p>
                    ) : null}

                    {(() => {
                      const ingredient =
                        ingredientForPantryId(
                          item.ingredient_id,
                        );

                      const labels = {
                        breakfast: "Colazione",
                        lunch: "Pranzo",
                        snack: "Snack",
                        dinner: "Cena",
                      } as const;

                      const slots =
                        ingredient?.meal_slots ?? [];

                      return slots.length > 0 ? (
                        <div
                          className={
                            styles.pantryMealSlotTags
                          }
                        >
                          {slots.map((slot) => (
                            <span key={slot}>
                              {labels[slot]}
                            </span>
                          ))}
                        </div>
                      ) : null;
                    })()}

                    {item.expires_at && (
                      <p>
                        Scadenza: {item.expires_at}
                      </p>
                    )}
                  </div>

                  <div className={styles.pantryItemActions}>
                    <button
                      type="button"
                      onClick={() => editPantry(item)}
                    >
                      Modifica
                    </button>

                    <button
                      type="button"
                      onClick={() => void removePantry(item)}
                      disabled={busyId === item.id}
                    >
                      Rimuovi
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}

          {!loading &&
            ingredients.length > 0 &&
            pantryItems.length === 0 && (
              <div className={styles.pantryEmpty}>
                <strong>Nessun alimento registrato.</strong>
                <p>
                  Usa il modulo qui sopra per aggiungere il primo alimento.
                </p>
              </div>
            )}
        </section>

        <section className={styles.pantrySection}>
          <div className={styles.pantrySectionHead}>
            <div>
              <p className={styles.pantryKicker}>MEAL PREP</p>
              <h2>Porzioni già cucinate</h2>
              <p>
                Piatti pronti che puoi consumare direttamente.
              </p>
            </div>
          </div>

          {loading ? (
            <section className={styles.card}>
              <p>Caricamento dispensa...</p>
            </section>
          ) : items.length === 0 ? (
            <section className={styles.empty}>
              <h2>Nessuna porzione disponibile</h2>
              <p>
                Quando cucini più porzioni di una ricetta,
                quelle non ancora mangiate appariranno qui.
              </p>
            </section>
          ) : (
            <div className={styles.list}>
              {items.map((item) => (
                <article
                  key={item.id}
                  className={styles.item}
                >
                  <div
                    className={styles.mealPrepVisual}
                    aria-hidden="true"
                  >
                    <span>▣</span>
                  </div>

                  <div className={styles.itemContent}>
                    <div className={styles.itemHeader}>
                      <div className={styles.itemTitle}>
                        <p className={styles.kicker}>
                          Meal prep
                        </p>

                        <h2>{item.name}</h2>

                        <p className={styles.meta}>
                          Preparato il {item.prepared_at}
                        </p>
                      </div>

                      <div className={styles.portions}>
                        <strong>
                          {item.portions_remaining}
                        </strong>

                        <span>
                          {item.portions_remaining === 1
                            ? "porzione disponibile"
                            : "porzioni disponibili"}
                        </span>
                      </div>
                    </div>

                    <div className={styles.nutrition}>
                      <span>
                        {Math.round(item.calories_per_portion)} kcal
                      </span>

                      <span>
                        {Math.round(item.protein_per_portion)} g proteine
                      </span>

                      <span>
                        {Math.round(item.carbs_per_portion)} g carboidrati
                      </span>

                      <span>
                        {Math.round(item.fat_per_portion)} g grassi
                      </span>
                    </div>

                    <div className={styles.actions}>
                      <button
                        type="button"
                        className={styles.consume}
                        onClick={() => void consume(item)}
                        disabled={busyId === item.id}
                      >
                        {busyId === item.id
                          ? "Aggiornamento..."
                          : "Ho mangiato 1 porzione"}
                      </button>

                      <button
                        type="button"
                        className={styles.discard}
                        onClick={() => void discard(item)}
                        disabled={busyId === item.id}
                      >
                        Elimina 1 porzione
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </main>
    </>
  );
}
