"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import {
  createIngredient,
  getIngredients,
  type Ingredient,
} from "@/lib/api/ingredients";
import {
  createRecipe,
  getRecipe,
  getRecipes,
  updateRecipe,
  type Recipe,
} from "@/lib/api/recipes";

import styles from "./RecipesPage.module.css";

interface DraftIngredient {
  ingredientId: string;
  quantityG: number;
}

interface IngredientDraft {
  name: string;
  calories: string;
  protein: string;
  carbs: string;
  fat: string;
}

const EMPTY_INGREDIENT: IngredientDraft = {
  name: "",
  calories: "",
  protein: "",
  carbs: "",
  fat: "",
};

export default function RecipesPage() {
  const { accessToken } = useAuth();

  const [recipes, setRecipes] =
    useState<Recipe[]>([]);
  const [ingredients, setIngredients] =
    useState<Ingredient[]>([]);

  const [editingId, setEditingId] =
    useState<string | null>(null);

  const [name, setName] = useState("");
  const [mealType, setMealType] =
    useState("Cena");
  const [servings, setServings] =
    useState("1");

  const [draftIngredients, setDraftIngredients] =
    useState<DraftIngredient[]>([]);

  const [ingredientDraft, setIngredientDraft] =
    useState<IngredientDraft>(
      EMPTY_INGREDIENT,
    );

  const [showIngredientCreator, setShowIngredientCreator] =
    useState(false);

  const [loading, setLoading] =
    useState(true);
  const [saving, setSaving] =
    useState(false);
  const [message, setMessage] =
    useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    void refresh();
  }, [accessToken]);

  async function refresh() {
    if (!accessToken) {
      return;
    }

    setLoading(true);
    setMessage(null);

    try {
      const [recipePayload, ingredientPayload] =
        await Promise.all([
          getRecipes(accessToken),
          getIngredients(accessToken),
        ]);

      setRecipes(recipePayload.items);
      setIngredients(ingredientPayload.items);
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Errore durante il caricamento.",
      );
    } finally {
      setLoading(false);
    }
  }

  function resetEditor() {
    setEditingId(null);
    setName("");
    setMealType("Cena");
    setServings("1");
    setDraftIngredients([]);
    setMessage(null);
  }

  async function editRecipe(recipeId: string) {
    if (!accessToken) {
      return;
    }

    setMessage(null);

    try {
      const response = await getRecipe(
        recipeId,
        accessToken,
      );

      const recipe = response.item;

      setEditingId(recipe.id);
      setName(recipe.name);
      setMealType(
        recipe.meal_type || "Cena",
      );
      setServings(
        String(recipe.recipe_servings || 1),
      );

      setDraftIngredients(
        (recipe.structured_ingredients ?? []).map(
          (item) => ({
            ingredientId: item.ingredient_id,
            quantityG: item.quantity_g,
          }),
        ),
      );
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Non riesco ad aprire la ricetta.",
      );
    }
  }

  function addIngredientRow() {
    const first = ingredients[0];

    if (!first) {
      setShowIngredientCreator(true);
      return;
    }

    setDraftIngredients((current) => [
      ...current,
      {
        ingredientId: first.id,
        quantityG: 100,
      },
    ]);
  }

  function updateDraftIngredient(
    index: number,
    changes: Partial<DraftIngredient>,
  ) {
    setDraftIngredients((current) =>
      current.map((item, itemIndex) =>
        itemIndex === index
          ? { ...item, ...changes }
          : item,
      ),
    );
  }

  function removeDraftIngredient(
    index: number,
  ) {
    setDraftIngredients((current) =>
      current.filter(
        (_, itemIndex) =>
          itemIndex !== index,
      ),
    );
  }

  const nutrition = useMemo(() => {
    return draftIngredients.reduce(
      (total, row) => {
        const ingredient = ingredients.find(
          (item) =>
            item.id === row.ingredientId,
        );

        if (!ingredient) {
          return total;
        }

        const factor =
          Math.max(0, row.quantityG) / 100;

        return {
          calories:
            total.calories +
            ingredient.calories_per_100g *
              factor,
          protein:
            total.protein +
            ingredient.protein_per_100g *
              factor,
          carbs:
            total.carbs +
            ingredient.carbs_per_100g *
              factor,
          fat:
            total.fat +
            ingredient.fat_per_100g *
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
  }, [draftIngredients, ingredients]);

  async function saveRecipe() {
    if (
      !accessToken ||
      !name.trim() ||
      draftIngredients.length === 0
    ) {
      setMessage(
        "Inserisci nome e almeno un ingrediente.",
      );
      return;
    }

    setSaving(true);
    setMessage(null);

    const payload = {
      name: name.trim(),
      meal_type: mealType,
      recipe_servings:
        Math.max(
          1,
          Number(servings) || 1,
        ),
      structured_ingredients:
        draftIngredients.map((item) => ({
          ingredient_id:
            item.ingredientId,
          quantity: item.quantityG,
          unit: "g",
          quantity_g:
            item.quantityG,
        })),
    };

    try {
      if (editingId) {
        await updateRecipe(
          editingId,
          payload,
          accessToken,
        );
        setMessage("Ricetta aggiornata.");
      } else {
        await createRecipe(
          payload,
          accessToken,
        );
        setMessage("Ricetta creata.");
      }

      resetEditor();
      await refresh();
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Non riesco a salvare la ricetta.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function saveIngredient() {
    if (!accessToken) {
      return;
    }

    const ingredientName =
      ingredientDraft.name.trim();

    if (!ingredientName) {
      setMessage(
        "Inserisci il nome dell'ingrediente.",
      );
      return;
    }

    try {
      const result = await createIngredient(
        {
          name: ingredientName,
          calories_per_100g:
            Number(
              ingredientDraft.calories,
            ) || 0,
          protein_per_100g:
            Number(
              ingredientDraft.protein,
            ) || 0,
          carbs_per_100g:
            Number(
              ingredientDraft.carbs,
            ) || 0,
          fat_per_100g:
            Number(
              ingredientDraft.fat,
            ) || 0,
          default_unit: "g",
        },
        accessToken,
      );

      setIngredients((current) => [
        ...current,
        result.item,
      ]);

      setDraftIngredients((current) => [
        ...current,
        {
          ingredientId: result.item.id,
          quantityG: 100,
        },
      ]);

      setIngredientDraft(
        EMPTY_INGREDIENT,
      );
      setShowIngredientCreator(false);
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Non riesco a creare l'ingrediente.",
      );
    }
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.kicker}>
            SanoSync
          </p>
          <h1>Ricette</h1>
        </div>

        <a
          href="/"
          className={styles.homeLink}
        >
          Home
        </a>
      </header>

      {message ? (
        <p className={styles.message}>
          {message}
        </p>
      ) : null}

      <section className={styles.editorCard}>
        <div className={styles.sectionHeader}>
          <div>
            <p className={styles.kicker}>
              {editingId
                ? "Modifica"
                : "Nuova"}
            </p>
            <h2>
              {editingId
                ? "Modifica ricetta"
                : "Crea ricetta"}
            </h2>
          </div>

          {editingId ? (
            <button
              type="button"
              onClick={resetEditor}
              className={styles.secondaryButton}
            >
              Nuova
            </button>
          ) : null}
        </div>

        <label className={styles.field}>
          Nome
          <input
            value={name}
            placeholder="Chicken rice"
            onChange={(event) => {
              setName(event.target.value);
            }}
          />
        </label>

        <div className={styles.twoColumns}>
          <label className={styles.field}>
            Tipo
            <select
              value={mealType}
              onChange={(event) => {
                setMealType(
                  event.target.value,
                );
              }}
            >
              <option>Colazione</option>
              <option>Pranzo</option>
              <option>Cena</option>
            </select>
          </label>

          <label className={styles.field}>
            Porzioni
            <input
              type="number"
              min="1"
              value={servings}
              onChange={(event) => {
                setServings(
                  event.target.value,
                );
              }}
            />
          </label>
        </div>

        <div className={styles.ingredientsHeader}>
          <strong>Ingredienti</strong>

          <div className={styles.smallActions}>
            <button
              type="button"
              className={styles.secondaryButton}
              onClick={addIngredientRow}
            >
              + Esistente
            </button>

            <button
              type="button"
              className={styles.secondaryButton}
              onClick={() => {
                setShowIngredientCreator(
                  true,
                );
              }}
            >
              + Nuovo
            </button>
          </div>
        </div>

        {draftIngredients.map(
          (row, index) => (
            <div
              key={`${row.ingredientId}-${index}`}
              className={styles.ingredientRow}
            >
              <select
                value={row.ingredientId}
                onChange={(event) => {
                  updateDraftIngredient(
                    index,
                    {
                      ingredientId:
                        event.target.value,
                    },
                  );
                }}
              >
                {ingredients.map(
                  (ingredient) => (
                    <option
                      key={ingredient.id}
                      value={ingredient.id}
                    >
                      {ingredient.name}
                    </option>
                  ),
                )}
              </select>

              <div
                className={
                  styles.quantityField
                }
              >
                <input
                  type="number"
                  min="1"
                  value={row.quantityG}
                  onChange={(event) => {
                    updateDraftIngredient(
                      index,
                      {
                        quantityG:
                          Number(
                            event.target.value,
                          ) || 0,
                      },
                    );
                  }}
                />
                <span>g</span>
              </div>

              <button
                type="button"
                className={styles.removeButton}
                onClick={() => {
                  removeDraftIngredient(
                    index,
                  );
                }}
                aria-label="Rimuovi ingrediente"
              >
                ×
              </button>
            </div>
          ),
        )}

        {showIngredientCreator ? (
          <div className={styles.newIngredientCard}>
            <strong>
              Nuovo ingrediente
            </strong>

            <label className={styles.field}>
              Nome
              <input
                value={
                  ingredientDraft.name
                }
                placeholder="Riso basmati"
                onChange={(event) => {
                  setIngredientDraft(
                    (current) => ({
                      ...current,
                      name:
                        event.target.value,
                    }),
                  );
                }}
              />
            </label>

            <div className={styles.macroInputs}>
              {[
                ["calories", "kcal / 100 g"],
                ["protein", "Proteine"],
                ["carbs", "Carboidrati"],
                ["fat", "Grassi"],
              ].map(([key, label]) => (
                <label
                  key={key}
                  className={styles.field}
                >
                  {label}
                  <input
                    type="number"
                    min="0"
                    value={
                      ingredientDraft[
                        key as keyof IngredientDraft
                      ]
                    }
                    onChange={(event) => {
                      setIngredientDraft(
                        (current) => ({
                          ...current,
                          [key]:
                            event.target.value,
                        }),
                      );
                    }}
                  />
                </label>
              ))}
            </div>

            <div className={styles.smallActions}>
              <button
                type="button"
                className={styles.primarySmallButton}
                onClick={() => {
                  void saveIngredient();
                }}
              >
                Salva ingrediente
              </button>

              <button
                type="button"
                className={styles.secondaryButton}
                onClick={() => {
                  setShowIngredientCreator(
                    false,
                  );
                }}
              >
                Annulla
              </button>
            </div>
          </div>
        ) : null}

        <div className={styles.nutritionCard}>
          <span>
            {Math.round(
              nutrition.calories,
            )} kcal
          </span>
          <span>
            {nutrition.protein.toFixed(
              1,
            )} g proteine
          </span>
          <span>
            {nutrition.carbs.toFixed(
              1,
            )} g carbo
          </span>
          <span>
            {nutrition.fat.toFixed(
              1,
            )} g grassi
          </span>
        </div>

        <button
          type="button"
          className={styles.saveButton}
          disabled={saving}
          onClick={() => {
            void saveRecipe();
          }}
        >
          {saving
            ? "Salvo…"
            : editingId
              ? "Salva modifiche"
              : "Salva ricetta"}
        </button>
      </section>

      <section>
        <div className={styles.sectionHeader}>
          <div>
            <p className={styles.kicker}>
              Libreria
            </p>
            <h2>Le tue ricette</h2>
          </div>
        </div>

        {loading ? (
          <p>Caricamento…</p>
        ) : recipes.length ? (
          <div className={styles.recipeList}>
            {recipes.map((recipe) => (
              <article
                key={recipe.id}
                className={styles.recipeCard}
              >
                <div>
                  <strong>
                    {recipe.name}
                  </strong>
                  <p>
                    {recipe.meal_type ||
                      "Ricetta"}{" "}
                    ·{" "}
                    {Math.round(
                      Number(
                        recipe.calories ||
                          0,
                      ),
                    )}{" "}
                    kcal
                  </p>
                </div>

                <button
                  type="button"
                  className={styles.secondaryButton}
                  onClick={() => {
                    void editRecipe(
                      recipe.id,
                    );
                  }}
                >
                  Modifica
                </button>
              </article>
            ))}
          </div>
        ) : (
          <p>
            Nessuna ricetta salvata.
          </p>
        )}
      </section>
    </main>
  );
}
