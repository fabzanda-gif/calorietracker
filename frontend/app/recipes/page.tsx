"use client";

import Link from "next/link";

import { AppNav } from "@/components/navigation/AppNav";
import { RecipeShareButton } from "@/components/recipes/RecipeShareButton";

import {
  useRef,
  useEffect,
  useMemo,
  useState,
} from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { useExperienceMode } from "@/components/experience/ExperienceModeProvider";
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

import { createMealPrep } from "@/lib/api/mealPrep";

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
  const { experienceMode } = useExperienceMode();
  const zero = experienceMode === "zero";

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
  const [tasteRating, setTasteRating] =
    useState("");
  const [easeRating, setEaseRating] =
    useState("");

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

  const [recipeSearch, setRecipeSearch] =
    useState("");

  const [recipeMealFilter, setRecipeMealFilter] =
    useState("Tutte");
  const [recipeSort, setRecipeSort] =
    useState<"recent" | "taste" | "ease">("recent");


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
  const [cookRecipe, setCookRecipe] =
    useState<Recipe | null>(null);
  const [cookPortions, setCookPortions] =
    useState("1");
  const [cooking, setCooking] =
    useState(false);
  const actionPanelRef = useRef<HTMLElement | null>(null);
  const editorRef = useRef<HTMLElement | null>(null);

  function reveal(ref: React.RefObject<HTMLElement | null>) {
    window.requestAnimationFrame(() => {
      ref.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }

  const availableRecipeMealTypes = useMemo(() => {
    const values = recipes
      .map((recipe) =>
        String(recipe.meal_type || "").trim(),
      )
      .filter(Boolean);

    return Array.from(
      new Set(values),
    ).sort((a, b) =>
      a.localeCompare(
        b,
        "it",
        {
          sensitivity: "base",
        },
      ),
    );
  }, [recipes]);

  const filteredRecipes = useMemo(() => {
    const query = recipeSearch
      .trim()
      .toLocaleLowerCase("it");

    const matches = recipes.filter((recipe) => {
      const recipeType =
        String(
          recipe.meal_type || "",
        ).trim();

      const matchesMealType =
        recipeMealFilter === "Tutte" ||
        recipeType.localeCompare(
          recipeMealFilter,
          "it",
          {
            sensitivity: "base",
          },
        ) === 0;

      if (!matchesMealType) {
        return false;
      }

      if (!query) {
        return true;
      }

      const searchableText = [
        recipe.name,
        recipe.meal_type,
        recipe.category,
        recipe.notes,
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("it");

      return searchableText.includes(query);
    });

    if (recipeSort === "taste") {
      return matches.sort((a, b) => Number(b.taste_rating || 0) - Number(a.taste_rating || 0));
    }

    if (recipeSort === "ease") {
      return matches.sort((a, b) => Number(b.ease_rating || 0) - Number(a.ease_rating || 0));
    }

    return matches;
  }, [
    recipes,
    recipeSearch,
    recipeMealFilter,
    recipeSort,
  ]);

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
    setTasteRating("");
    setEaseRating("");
    setImageUrl(null);
    setNotes("");
    setDraftIngredients([]);
    setMessage(null);
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

  function openCookDialog(recipe: Recipe) {
    setMealDraft(null);
    setCookRecipe(recipe);
    reveal(actionPanelRef);
    setCookPortions("1");
    setMessage(null);
  }

  function closeCookDialog() {
    if (cooking) {
      return;
    }

    setCookRecipe(null);
    setCookPortions("1");
  }

  async function confirmCook() {
    if (!accessToken || !cookRecipe) {
      return;
    }

    const portions = Number(cookPortions);

    if (
      !Number.isInteger(portions) ||
      portions <= 0
    ) {
      setMessage(
        "Inserisci un numero intero di porzioni.",
      );
      return;
    }

    setCooking(true);
    setMessage(null);

    try {
      await createMealPrep(accessToken, {
        recipe_id: cookRecipe.id,
        prepared_at: todayLocalIso(),
        portions_prepared: portions,
      });

      setCookRecipe(null);
      setCookPortions("1");

      setMessage(
        `${cookRecipe.name}: ${portions} ${
          portions === 1
            ? "porzione aggiunta"
            : "porzioni aggiunte"
        } all'inventario.`,
      );
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Impossibile aggiungere la preparazione all'inventario.",
      );
    } finally {
      setCooking(false);
    }
  }

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

      setCookRecipe(null);
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
      reveal(actionPanelRef);
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

  async function rateRecipe(
    recipe: Recipe,
    field: "taste_rating" | "ease_rating",
    rating: number,
  ) {
    if (!accessToken) {
      return;
    }

    setMessage(null);

    try {
      await updateRecipe(
        recipe.id,
        { [field]: rating },
        accessToken,
      );
      setRecipes((current) =>
        current.map((item) =>
          item.id === recipe.id
            ? { ...item, [field]: rating }
            : item,
        ),
      );
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Non riesco a salvare la valutazione.",
      );
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
      taste_rating: tasteRating ? Number(tasteRating) : null,
      ease_rating: easeRating ? Number(easeRating) : null,
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
            Ricette
          </p>

          <h1>
            {zero
              ? "Le ricette che almeno sai già gestire"
              : "Le tue ricette"}
          </h1>
            <Link
              href="/inventory"
              className={styles.inventoryLink}
            >
              Apri dispensa
            </Link>
            <Link
              href="/ingredients"
              className={styles.inventoryLink}
            >
              Gestisci ingredienti
            </Link>

          <p className={styles.headerSubtitle}>
            {zero
              ? "Piatti già collaudati. Almeno qui evitiamo esperimenti inutili."
              : "I piatti che conosci già, pronti da registrare quando servono."}
          </p>
        </div>
      </header>

      {message ? (
        <p className={styles.message}>
          {message}
        </p>
      ) : null}

      {cookRecipe ? (
        <section ref={actionPanelRef} className={styles.editorCard}>
          <div className={styles.sectionHeader}>
            <div>
              <p className={styles.kicker}>
                Meal prep
              </p>
              <h2>Cucina</h2>
            </div>

            <button
              type="button"
              className={styles.secondaryButton}
              onClick={closeCookDialog}
              disabled={cooking}
            >
              Annulla
            </button>
          </div>

          <p>
            <strong>{cookRecipe.name}</strong>
          </p>

          <label className={styles.field}>
            <span>Quante porzioni hai cucinato?</span>
            <input
              type="number"
              min="1"
              step="1"
              value={cookPortions}
              onChange={(event) => {
                setCookPortions(
                  event.target.value,
                );
              }}
              disabled={cooking}
            />
          </label>

          <button
            type="button"
            className={styles.saveButton}
            onClick={() => {
              void confirmCook();
            }}
            disabled={cooking}
          >
            {cooking
              ? "Salvataggio..."
              : "Aggiungi all'inventario"}
          </button>
        </section>
      ) : null}

      {mealDraft ? (
        <section ref={actionPanelRef} className={styles.editorCard}>
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

      <section>
        <div className={styles.sectionHeader}>
          <div>
            <p className={styles.kicker}>
              Libreria personale
            </p>
            <h2>
              {zero ? "Le solite affidabili" : "Pronte quando ti servono"}
            </h2>
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

        <div className={styles.recipeToolbar}>
          <label className={styles.recipeSearch}>
            <span className={styles.searchIcon}>
              ⌕
            </span>

            <input
              type="search"
              value={recipeSearch}
              placeholder="Cerca una ricetta…"
              aria-label="Cerca una ricetta"
              onChange={(event) => {
                setRecipeSearch(
                  event.target.value,
                );
              }}
            />

            {recipeSearch ? (
              <button
                type="button"
                className={styles.clearSearch}
                aria-label="Cancella ricerca"
                onClick={() => {
                  setRecipeSearch("");
                }}
              >
                ×
              </button>
            ) : null}
          </label>

          <div
            className={styles.recipeFilters}
            aria-label="Filtra per tipo di pasto"
          >
            <button
              type="button"
              className={
                recipeMealFilter === "Tutte"
                  ? styles.recipeFilterActive
                  : styles.recipeFilter
              }
              onClick={() => {
                setRecipeMealFilter("Tutte");
              }}
            >
              Tutte
            </button>

            {availableRecipeMealTypes.map(
              (type) => (
                <button
                  key={type}
                  type="button"
                  className={
                    recipeMealFilter === type
                      ? styles.recipeFilterActive
                      : styles.recipeFilter
                  }
                  onClick={() => {
                    setRecipeMealFilter(type);
                  }}
                >
                  {type}
                </button>
              ),
            )}
          </div>

          <div className={styles.recipeResultCount}>
            <strong>
              {filteredRecipes.length}
            </strong>{" "}
            {filteredRecipes.length === 1
              ? "ricetta"
              : "ricette"}
          </div>
          <label className={styles.recipeSort}>
            <span>Ordina</span>
            <select value={recipeSort} onChange={(event) => setRecipeSort(event.target.value as "recent" | "taste" | "ease")}>
              <option value="recent">Più recenti</option>
              <option value="taste">Gusto</option>
              <option value="ease">Facilità</option>
            </select>
          </label>
        </div>

        {loading ? (
          <p>Caricamento…</p>
        ) : filteredRecipes.length ? (
          <div className={styles.recipeList}>
            {filteredRecipes.map((recipe) => (
              <article
                key={recipe.id}
                className={styles.recipeCard}
              >
                <div className={styles.recipeVisual}>
                  {recipe.image_url ? (
                    <img
                      src={recipe.image_url}
                      alt={recipe.name}
                      className={styles.recipeThumb}
                    />
                  ) : (
                    <div
                      className={
                        styles.recipePlaceholder
                      }
                    >
                      <span>S</span>
                    </div>
                  )}

                  <span className={styles.recipeTypeBadge}>
                    {recipe.meal_type || "Ricetta"}
                  </span>
                </div>

                <div className={styles.recipeContent}>
                  <div className={styles.recipeMain}>
                    <strong className={styles.recipeTitle}>
                      {recipe.name}
                    </strong>

                    <div className={styles.recipeNutrition}>
                      <div className={styles.recipeRating}>
                        <span>Gusto</span>
                        <div aria-label={`Valuta il gusto di ${recipe.name}`}>
                          {[1, 2, 3, 4, 5].map((rating) => (
                            <button
                              key={rating}
                              type="button"
                              aria-label={`${rating} su 5`}
                              className={rating <= Number(recipe.taste_rating || 0) ? styles.starActive : styles.star}
                              onClick={() => void rateRecipe(recipe, "taste_rating", rating)}
                            >
                              ★
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className={styles.recipeRating}>
                        <span>Facilità</span>
                        <div aria-label={`Valuta la facilità di ${recipe.name}`}>
                          {[1, 2, 3, 4, 5].map((rating) => (
                            <button
                              key={rating}
                              type="button"
                              aria-label={`${rating} su 5`}
                              className={rating <= Number(recipe.ease_rating || 0) ? styles.starActive : styles.star}
                              onClick={() => void rateRecipe(recipe, "ease_rating", rating)}
                            >
                              ★
                            </button>
                          ))}
                        </div>
                      </div>
                      <span>
                        <strong>
                          {Math.round(
                            Number(
                              recipe.calories || 0,
                            ),
                          )}
                        </strong>
                        kcal totali
                      </span>

                      {recipe.protein != null ? (
                        <span>
                          <strong>
                            {Math.round(
                              Number(
                                recipe.protein || 0,
                              ),
                            )}
                          </strong>
                          g proteine totali
                        </span>
                      ) : null}

                      <span>
                        <strong>
                          {Math.max(
                            1,
                            Number(
                              recipe.recipe_servings || 1,
                            ),
                          )}
                        </strong>
                        {Number(
                          recipe.recipe_servings || 1,
                        ) === 1
                          ? " porzione"
                          : " porzioni"}
                      </span>

                      <span className={styles.recipePerServing}>
                        <strong>
                          {Math.round(
                            Number(
                              recipe.calories || 0,
                            ) /
                              Math.max(
                                1,
                                Number(
                                  recipe.recipe_servings || 1,
                                ),
                              ),
                          )}
                        </strong>{" "}
                        kcal / porzione
                      </span>

                      {recipe.protein != null ? (
                        <span className={styles.recipePerServing}>
                          <strong>
                            {Math.round(
                              Number(
                                recipe.protein || 0,
                              ) /
                                Math.max(
                                  1,
                                  Number(
                                    recipe.recipe_servings || 1,
                                  ),
                                ),
                            )}
                          </strong>{" "}
                          g proteine / porzione
                        </span>
                      ) : null}
                    </div>

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

                  <div className={styles.recipeActions}>
                    <RecipeShareButton
                      name={recipe.name}
                      imageUrl={recipe.image_url}
                      calories={Number(recipe.calories || 0)}
                      protein={
                        recipe.protein != null
                          ? Number(recipe.protein)
                          : null
                      }
                      servings={recipe.recipe_servings}
                      preparation={recipe.preparation}
                    />
                    <button
                      type="button"
                      className={styles.secondaryButton}
                      onClick={() => {
                        openCookDialog(recipe);
                      }}
                    >
                      Cucina
                    </button>
<button
                      type="button"
                      className={
                        styles.primarySmallButton
                      }
                      onClick={() => {
                        void startMealFromRecipe(
                          recipe.id,
                        );
                      }}
                    >
                      Registra
                    </button>

                    <Link
                      className={styles.secondaryButton}
                      href={`/recipes/${encodeURIComponent(recipe.id)}`}
                    >
                      Dettaglio
                    </Link>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className={styles.recipeEmptyState}>
            <strong>
              {recipes.length
                ? zero
                  ? "Niente. I filtri hanno lavorato fin troppo bene."
                  : "Nessuna ricetta trovata"
                : zero
                  ? "Libreria vuota. Minimalismo non richiesto."
                  : "La tua libreria è ancora vuota"}
            </strong>

            <p>
              {recipes.length
                ? zero
                  ? "Cambia ricerca o filtro. Magari compare qualcosa."
                  : "Prova a cambiare ricerca o filtro."
                : zero
                  ? "Salva una ricetta. Prima o poi servirà anche questa organizzazione."
                  : "Salva una ricetta e la troverai qui pronta da riutilizzare."}
            </p>

            {recipes.length ? (
              <button
                type="button"
                className={styles.resetFiltersButton}
                onClick={() => {
                  setRecipeSearch("");
                  setRecipeMealFilter("Tutte");
                }}
              >
                Azzera filtri
              </button>
            ) : null}
          </div>
        )}
      </section>


<section ref={editorRef} className={styles.editorCard}>
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

        <div className={styles.twoColumns}>
          <label className={styles.field}>
            Gusto
            <select value={tasteRating} onChange={(event) => setTasteRating(event.target.value)}>
              <option value="">Non valutato</option>
              {[1, 2, 3, 4, 5].map((rating) => <option key={rating} value={rating}>{rating}/5</option>)}
            </select>
          </label>
          <label className={styles.field}>
            Facilità
            <select value={easeRating} onChange={(event) => setEaseRating(event.target.value)}>
              <option value="">Non valutata</option>
              {[1, 2, 3, 4, 5].map((rating) => <option key={rating} value={rating}>{rating}/5</option>)}
            </select>
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

      </main>
    </>
  );
}
