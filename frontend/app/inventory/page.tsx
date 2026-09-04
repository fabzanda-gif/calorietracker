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
  getIngredients,
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

const EMPTY_PANTRY_FORM = {
  ingredientId: "",
  quantity: "",
  unit: "g",
  expiresAt: "",
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

  async function savePantry(event: FormEvent) {
    event.preventDefault();

    if (!accessToken) {
      return;
    }

    const quantity = Number(pantryForm.quantity);

    if (
      !pantryForm.ingredientId ||
      !Number.isFinite(quantity) ||
      quantity <= 0
    ) {
      setError("Seleziona un alimento e inserisci una quantità valida.");
      return;
    }

    setPantrySaving(true);
    setError(null);

    try {
      if (editingPantryId) {
        await updatePantryItem(
          accessToken,
          editingPantryId,
          {
            quantity,
            unit: pantryForm.unit,
            expires_at: pantryForm.expiresAt || null,
          },
        );
      } else {
        await createPantryItem(
          accessToken,
          {
            ingredient_id: pantryForm.ingredientId,
            quantity,
            unit: pantryForm.unit,
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
    setEditingPantryId(item.id);
    setPantryForm({
      ingredientId: item.ingredient_id,
      quantity: String(item.quantity),
      unit: item.unit,
      expiresAt: item.expires_at || "",
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

          <button
            type="button"
            className={styles.refresh}
            onClick={() => void refresh()}
            disabled={loading}
          >
            Aggiorna
          </button>
        </div>

        {error && (
          <section className={styles.error}>
            {error}
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
              <strong>Prima aggiungi un ingrediente alla libreria.</strong>
              <p>
                Gli alimenti della dispensa fanno riferimento alla tua libreria
                nutrizionale.
              </p>
              <a href="/ingredients">Vai agli ingredienti</a>
            </div>
          ) : (
            <form
              className={styles.pantryForm}
              onSubmit={savePantry}
            >
              <label className={styles.pantryFood}>
                <span>Alimento</span>

                <select
                  required
                  disabled={Boolean(editingPantryId)}
                  value={pantryForm.ingredientId}
                  onChange={(event) =>
                    setPantryForm({
                      ...pantryForm,
                      ingredientId: event.target.value,
                    })
                  }
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
                <span>Quantità</span>
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
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
                  <option value="pz">pz</option>
                </select>
              </label>

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
                  <div>
                    <p className={styles.pantryKicker}>
                      Alimento
                    </p>

                    <h3>
                      {item.ingredient_name || "Alimento"}
                    </h3>

                    <strong>
                      {item.quantity} {item.unit}
                    </strong>

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
                  <div className={styles.photo}>
                    {item.image_url ? (
                      <img
                        src={item.image_url}
                        alt={item.name}
                        loading="lazy"
                      />
                    ) : (
                      <div className={styles.photoPlaceholder}>
                        <span>🍽️</span>
                        <small>Nessuna foto</small>
                      </div>
                    )}
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
