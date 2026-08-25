"use client";

import { AppNav } from "@/components/navigation/AppNav";

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
  uploadRecipeImage,
} from "@/lib/api/recipeImages";

import {
  createRecipe,
  getRecipe,
  getRecipes,
  migrateLegacyRecipes,
  updateRecipe,
  type Recipe,
} from "@/lib/api/recipes";

import {
  createMeal,
} from "@/lib/api/meals";

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


function todayLocalIso(): string {
  const now = new Date();

  const year = now.getFullYear();
  const month = String(
    now.getMonth() + 1,
  ).padStart(2, "0");
  const day = String(
    now.getDate(),
  ).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

export default function RecipesPage() {
  const { accessToken, user } = useAuth();

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

  const [imageUrl, setImageUrl] =
    useState<string | null>(null);

  const [notes, setNotes] =
    useState("");

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


  const [mealDraft, setMealDraft] =
    useState<{
      recipeId: string;
      name: string;
      mealType: string;
      recipeServings: number;
      selectedServings: number;
      baseIngredients: DraftIngredient[];
      ingredients: DraftIngredient[];
    } | null>(null);

  const [loggingMeal, setLoggingMeal] =
    useState(false);

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
    setImageUrl(null);
    setNotes("");
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
      setImageUrl(
        recipe.image_url || null,
      );
      setNotes(
        recipe.notes || "",
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

  async function startMealFromRecipe(
    recipeId: string,
  ) {
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
      const structured =
        recipe.structured_ingredients ?? [];

      if (!structured.length) {
        setMessage(
          "Questa ricetta è ancora in formato legacy. Aprila con Modifica e aggiungi gli ingredienti strutturati prima di registrarla come pasto.",
        );
        return;
      }

      const recipeServings = Math.max(
        1,
        Number(
          recipe.recipe_servings || 1,
        ),
      );

      const baseIngredients =
        structured.map(
          (item) => ({
            ingredientId:
              item.ingredient_id,
            quantityG:
              item.quantity_g,
          }),
        );

      const initialScale =
        1 / recipeServings;

      setMealDraft({
        recipeId: recipe.id,
        name: recipe.name,
        mealType:
          recipe.meal_type || "Cena",
        recipeServings,
        selectedServings: 1,
        baseIngredients,
        ingredients:
          baseIngredients.map(
            (item) => ({
              ...item,
              quantityG:
                item.quantityG *
                initialScale,
            }),
          ),
      });
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Non riesco ad aprire la ricetta.",
      );
    }
  }

  function updateMealDraftServings(
    nextServings: number,
  ) {
    setMealDraft((current) => {
      if (!current) {
        return current;
      }

      const safeServings = Math.max(
        0.1,
        nextServings,
      );

      const scale =
        safeServings /
        current.recipeServings;

      return {
        ...current,
        selectedServings:
          safeServings,
        ingredients:
          current.baseIngredients.map(
            (item) => ({
              ...item,
              quantityG:
                item.quantityG *
                scale,
            }),
          ),
      };
    });
  }

  function updateMealDraftQuantity(
    index: number,
    quantityG: number,
  ) {
    setMealDraft((current) => {
      if (!current) {
        return current;
      }

      return {
        ...current,
        ingredients:
          current.ingredients.map(
            (item, itemIndex) =>
              itemIndex === index
                ? {
                    ...item,
                    quantityG,
                  }
                : item,
          ),
      };
    });
  }

  const mealDraftNutrition = useMemo(() => {
    if (!mealDraft) {
      return {
        calories: 0,
        protein: 0,
        carbs: 0,
        fat: 0,
      };
    }

    return mealDraft.ingredients.reduce(
      (total, row) => {
        const ingredient =
          ingredients.find(
            (item) =>
              item.id ===
              row.ingredientId,
          );

        if (!ingredient) {
          return total;
        }

        const factor =
          Math.max(
            0,
            row.quantityG,
          ) / 100;

        return {
          calories:
            total.calories +
            ingredient
              .calories_per_100g *
              factor,
          protein:
            total.protein +
            ingredient
              .protein_per_100g *
              factor,
          carbs:
            total.carbs +
            ingredient
              .carbs_per_100g *
              factor,
          fat:
            total.fat +
            ingredient
              .fat_per_100g *
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
  }, [mealDraft, ingredients]);

  async function saveMealFromRecipe() {
    if (
      !accessToken ||
      !mealDraft
    ) {
      return;
    }

    if (
      mealDraft.ingredients.some(
        (item) =>
          item.quantityG <= 0,
      )
    ) {
      setMessage(
        "Le grammature devono essere maggiori di zero.",
      );
      return;
    }

    setLoggingMeal(true);
    setMessage(null);

    try {
      await createMeal(
        {
          date: todayLocalIso(),
          meal_type:
            mealDraft.mealType,
          name: mealDraft.name,

          // StructuredMealService recalculates these
          // from the ingredient snapshots.
          calories: 0,
          protein: 0,
          carbs: 0,
          fat: 0,

          structured_ingredients:
            mealDraft.ingredients.map(
              (item) => ({
                ingredient_id:
                  item.ingredientId,
                quantity:
                  item.quantityG,
                unit: "g",
                quantity_g:
                  item.quantityG,
              }),
            ),
        },
        accessToken,
      );

      setMealDraft(null);

      setMessage(
        `${mealDraft.name} registrato come ${mealDraft.mealType.toLowerCase()}.`,
      );
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Non riesco a registrare il pasto.",
      );
    } finally {
      setLoggingMeal(false);
    }
  }

  async function migrateLegacyLibrary() {
    if (!accessToken) {
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      const result = await migrateLegacyRecipes(
        accessToken,
      );

      await refresh();

      setMessage(
        `Migrazione completata: ${result.migrated_recipes} ricette, ${result.created_ingredients} ingredienti creati, ${result.created_links} collegamenti creati.`,
      );
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Non riesco a migrare le ricette.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleRecipeImage(
    file: File,
  ) {
    if (!user) {
      setMessage(
        "Sessione utente non disponibile.",
      );
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      const url = await uploadRecipeImage(
        file,
        user.id,
      );

      setImageUrl(url);

      setMessage(
        "Foto caricata. Salva la ricetta per confermare.",
      );
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Non riesco a caricare la foto.",
      );
    } finally {
      setSaving(false);
    }
  }

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
      image_url: imageUrl,
      notes: notes.trim() || null,
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
    <>
      <AppNav />

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

      {mealDraft ? (
        <section className={styles.editorCard}>
          <div className={styles.sectionHeader}>
            <div>
              <p className={styles.kicker}>
                Pasto di oggi
              </p>
              <h2>
                {mealDraft.name}
              </h2>
            </div>

            <button
              type="button"
              className={styles.secondaryButton}
              onClick={() => {
                setMealDraft(null);
              }}
            >
              Annulla
            </button>
          </div>

          <p>
            {mealDraft.mealType} · modifica
            liberamente le quantità. La ricetta
            originale non verrà cambiata.
          </p>


          <div className={styles.twoColumns}>
            <label className={styles.field}>
              Porzioni da mangiare
              <input
                type="number"
                min="0.1"
                step="0.5"
                value={
                  mealDraft.selectedServings
                }
                onChange={(event) => {
                  updateMealDraftServings(
                    Number(
                      event.target.value,
                    ) || 0.1,
                  );
                }}
              />
            </label>

            <div className={styles.field}>
              Ricetta originale
              <div>
                {mealDraft.recipeServings}{" "}
                porzioni
              </div>
            </div>
          </div>

          {mealDraft.ingredients.map(
            (row, index) => {
              const ingredient =
                ingredients.find(
                  (item) =>
                    item.id ===
                    row.ingredientId,
                );

              return (
                <div
                  key={`${row.ingredientId}-${index}`}
                  className={
                    styles.ingredientRow
                  }
                >
                  <strong>
                    {ingredient?.name ||
                      "Ingrediente"}
                  </strong>

                  <div
                    className={
                      styles.quantityField
                    }
                  >
                    <input
                      type="number"
                      min="1"
                      value={
                        row.quantityG
                      }
                      onChange={(
                        event,
                      ) => {
                        updateMealDraftQuantity(
                          index,
                          Number(
                            event.target
                              .value,
                          ) || 0,
                        );
                      }}
                    />
                    <span>g</span>
                  </div>

                  <span />
                </div>
              );
            },
          )}

          <div
            className={
              styles.nutritionCard
            }
          >
            <span>
              {Math.round(
                mealDraftNutrition.calories,
              )} kcal
            </span>

            <span>
              {mealDraftNutrition.protein.toFixed(
                1,
              )} g proteine
            </span>

            <span>
              {mealDraftNutrition.carbs.toFixed(
                1,
              )} g carbo
            </span>

            <span>
              {mealDraftNutrition.fat.toFixed(
                1,
              )} g grassi
            </span>
          </div>

          <button
            type="button"
            className={styles.saveButton}
            disabled={loggingMeal}
            onClick={() => {
              void saveMealFromRecipe();
            }}
          >
            {loggingMeal
              ? "Registro…"
              : "Registra questo pasto"}
          </button>
        </section>
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

        {imageUrl ? (
          <div className={styles.recipeImageWrap}>
            <img
              src={imageUrl}
              alt={name || "Ricetta"}
              className={styles.recipeImage}
            />
          </div>
        ) : null}


        <label className={styles.secondaryButton}>
          {imageUrl
            ? "Sostituisci foto"
            : "Aggiungi foto"}
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            onChange={(event) => {
              const file =
                event.target.files?.[0];

              if (file) {
                void handleRecipeImage(file);
              }

              event.target.value = "";
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

        <label className={styles.field}>
          Preparazione
          <textarea
            className={styles.preparationTextarea}
            value={notes}
            rows={8}
            placeholder="Descrivi la preparazione, i passaggi, i tempi di cottura, eventuali sostituzioni o suggerimenti..."
            onChange={(event) => {
              setNotes(event.target.value);
            }}
          />
        </label>

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

          <button
            type="button"
            className={styles.secondaryButton}
            disabled={saving}
            onClick={() => {
              void migrateLegacyLibrary();
            }}
          >
            Aggiorna ricette legacy
          </button>
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
                {recipe.image_url ? (
                  <img
                    src={recipe.image_url}
                    alt={recipe.name}
                    className={styles.recipeThumb}
                  />
                ) : null}

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

                  {recipe.notes ? (
                    <p
                      className={
                        styles.recipeDescription
                      }
                    >
                      {recipe.notes}
                    </p>
                  ) : null}
                </div>

                <div className={styles.smallActions}>
                  <button
                    type="button"
                    className={styles.primarySmallButton}
                    onClick={() => {
                      void startMealFromRecipe(
                        recipe.id,
                      );
                    }}
                  >
                    Registra
                  </button>

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
                </div>
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
    </>
  );
}
