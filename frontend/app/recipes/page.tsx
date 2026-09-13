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
import { useI18n } from "@/components/i18n/I18nProvider";
import { RECIPES_COPY } from "./recipesI18n";
import {
  createIngredient,
  getIngredients,
  previewIngredientFromText,
  type Ingredient,
} from "@/lib/api/ingredients";
import {
  uploadRecipeImage,
} from "@/lib/api/recipeImages";

import {
  createRecipe,
  getRecipe,
  getPersonalRecipes,
  getSharedRecipes,
  migrateLegacyRecipes,
  updateRecipe,
  previewRecipeWithAI,
  type Recipe,
  type RecipeAIPreview,
} from "@/lib/api/recipes";

import {
  createMeal,
} from "@/lib/api/meals";

import { createMealPrep } from "@/lib/api/mealPrep";

import styles from "./RecipesPage.module.css";

interface DraftIngredient {
  ingredientId: string;
  quantityG: number;

  // RECIPE INGREDIENT UNIT SWITCH V1
  // quantityG remains canonical; this only controls the editor UI.
  inputUnit?: "g" | "portion";
}

interface IngredientDraft {
  name: string;
  calories: string;
  protein: string;
  carbs: string;
  fat: string;

  // RECIPE INLINE INGREDIENT PORTION V1
  // Optional weight of one normal serving.
  portionGrams: string;
}

const EMPTY_INGREDIENT: IngredientDraft = {
  name: "",
  calories: "",
  protein: "",
  carbs: "",
  fat: "",
  portionGrams: "",
};


function ingredientPortionGrams(
  ingredient: Ingredient | undefined,
): number | null {
  const grams = Number(
    ingredient?.grams_per_unit,
  );

  return Number.isFinite(grams) &&
    grams > 0
    ? grams
    : null;
}

function ingredientDisplayQuantity(
  row: DraftIngredient,
  ingredient: Ingredient | undefined,
): number {
  const portionGrams =
    ingredientPortionGrams(ingredient);

  if (
    row.inputUnit === "portion" &&
    portionGrams
  ) {
    return row.quantityG / portionGrams;
  }

  return row.quantityG;
}

function normalizeIngredientName(
  value: string,
): string {
  return value
    .trim()
    .toLocaleLowerCase("it")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ");
}


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
  const { locale } = useI18n();
  const copy = RECIPES_COPY[locale];
  const zero = experienceMode === "zero";

  const mealTypeLabel = (value?: string | null) => {
    const normalized = String(value ?? "").trim().toLowerCase();

    if (["colazione", "breakfast"].includes(normalized)) return copy.breakfast;
    if (["pranzo", "lunch"].includes(normalized)) return copy.lunch;
    if (["cena", "dinner"].includes(normalized)) return copy.dinner;
    if (["snack", "spuntino"].includes(normalized)) return copy.snack;

    return value || copy.recipe;
  };

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
  const [finalWeight, setFinalWeight] =
    useState("");
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

  const [ingredientAiLoading, setIngredientAiLoading] =
    useState(false);

  const [ingredientAiMessage, setIngredientAiMessage] =
    useState<string | null>(null);

  const [sharedRecipes, setSharedRecipes] =
    useState<Recipe[]>([]);

  const [loading, setLoading] =
    useState(true);
  const [saving, setSaving] =
    useState(false);
  const [message, setMessage] =
    useState<string | null>(null);

  const [recipeAiText, setRecipeAiText] =
    useState("");
  const [recipeAiPreview, setRecipeAiPreview] =
    useState<RecipeAIPreview | null>(null);
  const [recipeAiLoading, setRecipeAiLoading] =
    useState(false);
  const [
    recipeAiWeightMode,
    setRecipeAiWeightMode,
  ] = useState<"ingredients" | "manual">(
    "ingredients",
  );
  const [
    recipeAiFinalWeight,
    setRecipeAiFinalWeight,
  ] = useState("");

  const [
    recipeAiServings,
    setRecipeAiServings,
  ] = useState("1");

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

  const [mealDraftPortions, setMealDraftPortions] =
    useState(1);


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
    const values = [
      ...recipes,
      ...sharedRecipes,
    ]
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
  }, [recipes, sharedRecipes]);

  function filterAndSortRecipes(
    source: Recipe[],
  ): Recipe[] {
    const query = recipeSearch
      .trim()
      .toLocaleLowerCase("it");

    const matches = source.filter((recipe) => {
      const recipeType = String(
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
      return matches.sort(
        (a, b) =>
          Number(b.taste_rating || 0) -
          Number(a.taste_rating || 0),
      );
    }

    if (recipeSort === "ease") {
      return matches.sort(
        (a, b) =>
          Number(b.ease_rating || 0) -
          Number(a.ease_rating || 0),
      );
    }

    return matches;
  }

  const filteredRecipes = useMemo(
    () => filterAndSortRecipes(recipes),
    [
      recipes,
      recipeSearch,
      recipeMealFilter,
      recipeSort,
    ],
  );

  const filteredSharedRecipes = useMemo(
    () => filterAndSortRecipes(sharedRecipes),
    [
      sharedRecipes,
      recipeSearch,
      recipeMealFilter,
      recipeSort,
    ],
  );

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    void refresh();
  }, [accessToken]);

  async function analyzeRecipeWithAI() {
    if (!accessToken) {
      return;
    }

    const text = recipeAiText.trim();

    if (!text) {
      setMessage(
        "Scrivi prima la ricetta da analizzare.",
      );
      return;
    }

    setRecipeAiLoading(true);
    setMessage(null);

    try {
      const response =
        await previewRecipeWithAI(
          text,
          accessToken,
        );

      const preview = response.result;

      setRecipeAiPreview(preview);

      setRecipeAiServings(
        String(preview.servings || 1),
      );

      const ingredientWeight =
        Number(preview.ingredient_weight_g) || 0;

      const proposedFinalWeight =
        Number(preview.final_weight_g) || 0;

      const plausibleFinalWeight =
        proposedFinalWeight > 0 &&
        (
          ingredientWeight <= 0 ||
          (
            proposedFinalWeight >=
              ingredientWeight * 0.25 &&
            proposedFinalWeight <=
              ingredientWeight * 1.5
          )
        );

      if (plausibleFinalWeight) {
        setRecipeAiWeightMode("manual");
        setRecipeAiFinalWeight(
          String(proposedFinalWeight),
        );
      } else {
        setRecipeAiWeightMode("ingredients");
        setRecipeAiFinalWeight("");
      }
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Non riesco ad analizzare la ricetta.",
      );
    } finally {
      setRecipeAiLoading(false);
    }
  }

  function updateRecipeAiIngredient(
    index: number,
    changes: Partial<
      RecipeAIPreview["ingredients"][number]
    >,
  ) {
    setRecipeAiPreview((current) => {
      if (!current) {
        return current;
      }

      const nextIngredients =
        current.ingredients.map(
          (item, itemIndex) =>
            itemIndex === index
              ? {
                  ...item,
                  ...changes,
                }
              : item,
        );

      const ingredientWeightG =
        nextIngredients.reduce(
          (sum, item) =>
            sum +
            Math.max(
              0,
              Number(item.quantity_g) || 0,
            ),
          0,
        );

      const totals =
        nextIngredients.reduce(
          (total, item) => {
            const factor =
              Math.max(
                0,
                Number(item.quantity_g) || 0,
              ) / 100;

            return {
              calories:
                total.calories +
                (
                  Number(
                    item.calories_per_100g,
                  ) || 0
                ) *
                  factor,
              protein:
                total.protein +
                (
                  Number(
                    item.protein_per_100g,
                  ) || 0
                ) *
                  factor,
              carbs:
                total.carbs +
                (
                  Number(
                    item.carbs_per_100g,
                  ) || 0
                ) *
                  factor,
              fat:
                total.fat +
                (
                  Number(
                    item.fat_per_100g,
                  ) || 0
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

      return {
        ...current,
        ingredients: nextIngredients,
        ingredient_weight_g:
          ingredientWeightG,
        totals,
      };
    });
  }

  const recipeAiCalculated = useMemo(() => {
    if (!recipeAiPreview) {
      return null;
    }

    const manualWeight =
      Number(recipeAiFinalWeight);

    const weight =
      recipeAiWeightMode === "manual" &&
      Number.isFinite(manualWeight) &&
      manualWeight > 0
        ? manualWeight
        : recipeAiPreview.ingredient_weight_g;

    const servings =
      Math.max(
        1,
        Number(recipeAiServings) || 1,
      );

    return {
      weight,
      per100g: {
        calories:
          recipeAiPreview.totals.calories *
          100 /
          weight,
        protein:
          recipeAiPreview.totals.protein *
          100 /
          weight,
        carbs:
          recipeAiPreview.totals.carbs *
          100 /
          weight,
        fat:
          recipeAiPreview.totals.fat *
          100 /
          weight,
      },
      perServing: {
        calories:
          recipeAiPreview.totals.calories /
          servings,
        protein:
          recipeAiPreview.totals.protein /
          servings,
        carbs:
          recipeAiPreview.totals.carbs /
          servings,
        fat:
          recipeAiPreview.totals.fat /
          servings,
      },
    };
  }, [
    recipeAiPreview,
    recipeAiFinalWeight,
    recipeAiWeightMode,
    recipeAiServings,
  ]);

  async function useRecipeAiPreview() {
    if (
      !accessToken ||
      !recipeAiPreview
    ) {
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      const available = [...ingredients];
      const rows: DraftIngredient[] = [];

      for (
        const aiIngredient
        of recipeAiPreview.ingredients
      ) {
        const normalized =
          normalizeIngredientName(
            aiIngredient.name,
          );

        let ingredient =
          available.find(
            (item) =>
              item.normalized_name ===
                normalized ||
              normalizeIngredientName(
                item.name,
              ) === normalized,
          );

        if (!ingredient) {
          const created =
            await createIngredient(
              {
                name: aiIngredient.name,
                calories_per_100g:
                  aiIngredient
                    .calories_per_100g,
                protein_per_100g:
                  aiIngredient
                    .protein_per_100g,
                carbs_per_100g:
                  aiIngredient
                    .carbs_per_100g,
                fat_per_100g:
                  aiIngredient
                    .fat_per_100g,
                default_unit: "g",
                default_quantity: null,
                grams_per_unit: null,
                kind: "ingredient",
                meal_slots: [],
              },
              accessToken,
            );

          ingredient = created.item;
          available.push(ingredient);
        }

        rows.push({
          ingredientId: ingredient.id,
          quantityG:
            aiIngredient.quantity_g,
          inputUnit: "g",
        });
      }

      setIngredients(available);

      setEditingId(null);
      setName(
        recipeAiPreview.name ||
          "Nuova ricetta",
      );
      setServings(
        String(
          Math.max(
            1,
            Number(recipeAiServings) || 1,
          ),
        ),
      );
      setFinalWeight(
        String(
          recipeAiCalculated?.weight ||
            recipeAiPreview
              .ingredient_weight_g,
        ),
      );
      setDraftIngredients(rows);
      setTasteRating("");
      setEaseRating("");
      setImageUrl(null);
      setNotes("");

      setMessage(
        "Ricetta caricata nell'editor. Controlla ingredienti, quantità e peso finale prima di salvarla.",
      );

      reveal(editorRef);
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Non riesco a preparare la ricetta.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function refresh() {
    if (!accessToken) {
      return;
    }

    setLoading(true);
    setMessage(null);

    try {
      const [
        personalPayload,
        sharedPayload,
        ingredientPayload,
      ] = await Promise.all([
        getPersonalRecipes(accessToken),
        getSharedRecipes(accessToken),
        getIngredients(accessToken),
      ]);

      setRecipes(personalPayload.items);
      setSharedRecipes(sharedPayload.items);
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
    setFinalWeight("");
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

    const portionGrams =
      ingredientPortionGrams(first);

    setDraftIngredients((current) => [
      ...current,
      {
        ingredientId: first.id,
        quantityG:
          portionGrams ?? 100,
        inputUnit:
          portionGrams
            ? "portion"
            : "g",
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

  async function openRecipeEditor(
    recipeId: string,
  ) {
    if (!accessToken) {
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      const response = await getRecipe(
        recipeId,
        accessToken,
      );

      const recipe = response.item;
      const structured =
        recipe.structured_ingredients ?? [];

      setEditingId(recipe.id);
      setName(recipe.name || "");
      setMealType(
        recipe.meal_type || "Cena",
      );
      setServings(
        String(
          recipe.recipe_servings || 1,
        ),
      );
      setFinalWeight(
        recipe.final_weight_g != null
          ? String(recipe.final_weight_g)
          : "",
      );
      setTasteRating(
        recipe.taste_rating != null
          ? String(recipe.taste_rating)
          : "",
      );
      setEaseRating(
        recipe.ease_rating != null
          ? String(recipe.ease_rating)
          : "",
      );
      setImageUrl(
        recipe.image_url || null,
      );
      setNotes(recipe.notes || "");

      setDraftIngredients(
        structured.map((item) => ({
          ingredientId:
            item.ingredient_id,
          quantityG:
            Number(item.quantity_g) || 0,
          inputUnit: "g",
        })),
      );

      reveal(editorRef);
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Non riesco ad aprire la ricetta.",
      );
    } finally {
      setSaving(false);
    }
  }

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
              (item) => {
                const quantityG =
                  item.quantityG *
                  mealDraftPortions;

                return {
                  ingredient_id:
                    item.ingredientId,
                  quantity:
                    quantityG,
                  unit: "g",
                  quantity_g:
                    quantityG,
                };
              },
            ),
        },
        accessToken,
      );

      setMealDraft(null);
      setMealDraftPortions(1);

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

    const parsedFinalWeight =
      finalWeight.trim()
        ? Number(finalWeight)
        : null;

    if (
      parsedFinalWeight !== null &&
      (
        !Number.isFinite(parsedFinalWeight) ||
        parsedFinalWeight <= 0
      )
    ) {
      setMessage(
        "Il peso finale deve essere maggiore di zero.",
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
      final_weight_g: parsedFinalWeight,
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

  async function fillIngredientWithAi() {
    if (!accessToken) {
      return;
    }

    const ingredientName =
      ingredientDraft.name.trim();

    if (!ingredientName) {
      setMessage(
        "Inserisci prima il nome dell'ingrediente.",
      );
      return;
    }

    setIngredientAiLoading(true);
    setIngredientAiMessage(null);
    setMessage(null);

    try {
      const response =
        await previewIngredientFromText(
          ingredientName,
          accessToken,
        );

      const result = response.result;

      setIngredientDraft((current) => ({
        ...current,
        name:
          result.name ??
          current.name,
        calories:
          result.calories_per_100g != null
            ? String(result.calories_per_100g)
            : current.calories,
        protein:
          result.protein_per_100g != null
            ? String(result.protein_per_100g)
            : current.protein,
        carbs:
          result.carbs_per_100g != null
            ? String(result.carbs_per_100g)
            : current.carbs,
        fat:
          result.fat_per_100g != null
            ? String(result.fat_per_100g)
            : current.fat,
        portionGrams:
          current.portionGrams ||
          (
            result.grams_per_unit != null
              ? String(result.grams_per_unit)
              : ""
          ),
      }));

      setIngredientAiMessage(
        result.confidence === "low"
          ? "Valori stimati con bassa confidenza: controllali prima di salvare."
          : "Valori nutrizionali compilati con AI.",
      );
    } catch (err) {
      setIngredientAiMessage(
        err instanceof Error
          ? err.message
          : "Non riesco a stimare i valori nutrizionali.",
      );
    } finally {
      setIngredientAiLoading(false);
    }
  }

  async function saveIngredient() {
    if (!accessToken) {
      return;
    }

    const ingredientName =
      ingredientDraft.name.trim();

    const portionGrams =
      ingredientDraft.portionGrams.trim()
        ? Number(ingredientDraft.portionGrams)
        : null;

    if (
      portionGrams !== null &&
      (
        !Number.isFinite(portionGrams) ||
        portionGrams <= 0
      )
    ) {
      setMessage(
        "La porzione deve essere espressa in grammi ed essere maggiore di zero.",
      );
      return;
    }

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

          default_unit:
            portionGrams !== null
              ? "porzione"
              : "g",

          default_quantity:
            portionGrams !== null
              ? 1
              : null,

          grams_per_unit:
            portionGrams,
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

          quantityG:
            result.item.default_unit !== "g" &&
            Number(result.item.grams_per_unit) > 0
              ? Number(result.item.grams_per_unit) *
                Math.max(
                  1,
                  Number(
                    result.item.default_quantity,
                  ) || 1,
                )
              : 100,

          inputUnit:
            Number(result.item.grams_per_unit) > 0
              ? "portion"
              : "g",
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
            {copy.kicker}
          </p>

          <h1>
            {zero
              ? copy.titleZero
              : copy.title}
          </h1>
            <Link
              href="/inventory"
              className={styles.inventoryLink}
            >
              {copy.openPantry}
            </Link>
            <Link
              href="/ingredients"
              className={styles.inventoryLink}
            >
              {copy.manageIngredients}
            </Link>

          <p className={styles.headerSubtitle}>
            {zero
              ? copy.subtitleZero
              : copy.subtitle}
          </p>
        </div>
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
              SanoSync AI
            </p>
            <h2>Crea una ricetta con AI</h2>
          </div>
        </div>

        <label className={styles.field}>
          <span>
            Incolla ingredienti e quantità
          </span>
          <textarea
            className={styles.recipeAiTextarea}
            rows={5}
            value={recipeAiText}
            placeholder={
              "Es. Pollo al curry: 500 g pollo, 200 g riso, 20 g olio, 1 cipolla. 4 porzioni. Peso finale 1100 g."
            }
            onChange={(event) => {
              setRecipeAiText(
                event.target.value,
              );
            }}
          />
        </label>

        <button
          type="button"
          className={styles.saveButton}
          disabled={
            recipeAiLoading ||
            !recipeAiText.trim()
          }
          onClick={() => {
            void analyzeRecipeWithAI();
          }}
        >
          {recipeAiLoading
            ? "Analizzo…"
            : "Analizza ricetta"}
        </button>

        {recipeAiPreview ? (
          <>
            <div className={styles.sectionHeader}>
              <div>
                <p className={styles.kicker}>
                  Preview
                </p>
                <h3>
                  {recipeAiPreview.name ||
                    "Ricetta"}
                </h3>
              </div>
            </div>

            <div
              className={
                styles.recipeAiIngredientList
              }
            >
              {recipeAiPreview.ingredients.map(
                (item, index) => (
                  <div
                    key={`${item.name}-${index}`}
                    className={
                      styles.recipeAiIngredientRow
                    }
                  >
                    <div
                      className={
                        styles.recipeAiIngredientName
                      }
                    >
                      <strong>
                        {item.name}
                      </strong>

                      {item.estimated ? (
                        <small>
                          Stimato da AI
                        </small>
                      ) : null}
                    </div>

                    <label
                      className={
                        styles.recipeAiMiniField
                      }
                    >
                      <span>Peso</span>
                      <div
                        className={
                          styles.recipeAiInputWithUnit
                        }
                      >
                        <input
                          type="number"
                          min="0.1"
                          step="0.1"
                          value={item.quantity_g}
                          onChange={(event) => {
                            updateRecipeAiIngredient(
                              index,
                              {
                                quantity_g:
                                  Number(
                                    event.target
                                      .value,
                                  ) || 0,
                              },
                            );
                          }}
                        />
                        <span>g</span>
                      </div>
                    </label>

                    <label
                      className={
                        styles.recipeAiMiniField
                      }
                    >
                      <span>Kcal / 100 g</span>
                      <input
                        type="number"
                        min="0"
                        step="1"
                        value={
                          item.calories_per_100g
                        }
                        onChange={(event) => {
                          updateRecipeAiIngredient(
                            index,
                            {
                              calories_per_100g:
                                Number(
                                  event.target
                                    .value,
                                ) || 0,
                            },
                          );
                        }}
                      />
                    </label>
                  </div>
                ),
              )}
            </div>

            <div
              className={
                styles.recipeAiControls
              }
            >
              <label className={styles.field}>
                <span>Porzioni</span>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={recipeAiServings}
                  onChange={(event) => {
                    setRecipeAiServings(
                      event.target.value,
                    );
                  }}
                />
              </label>

              <label className={styles.field}>
                <span>
                  Peso usato per il calcolo
                </span>

                <select
                  value={recipeAiWeightMode}
                  onChange={(event) => {
                    setRecipeAiWeightMode(
                      event.target.value as
                        | "ingredients"
                        | "manual",
                    );
                  }}
                >
                  <option value="ingredients">
                    Somma pesi ingredienti
                  </option>
                  <option value="manual">
                    Peso finale ricetta
                  </option>
                </select>
              </label>

              {recipeAiWeightMode ===
              "manual" ? (
                <label className={styles.field}>
                  <span>
                    Peso finale (g)
                  </span>
                  <input
                    type="number"
                    min="1"
                    step="1"
                    value={recipeAiFinalWeight}
                    onChange={(event) => {
                      setRecipeAiFinalWeight(
                        event.target.value,
                      );
                    }}
                  />
                </label>
              ) : (
                <div className={styles.field}>
                  <span>
                    Peso ingredienti
                  </span>
                  <strong>
                    {Math.round(
                      recipeAiPreview
                        .ingredient_weight_g,
                    )}{" "}
                    g
                  </strong>
                </div>
              )}
            </div>

            <div className={styles.nutritionCard}>
              <span>
                Totale{" "}
                {Math.round(
                  recipeAiPreview.totals
                    .calories,
                )}{" "}
                kcal
              </span>

              <span>
                {recipeAiPreview.totals
                  .protein.toFixed(1)}{" "}
                g proteine
              </span>

              <span>
                {recipeAiPreview.totals
                  .carbs.toFixed(1)}{" "}
                g carbo
              </span>

              <span>
                {recipeAiPreview.totals
                  .fat.toFixed(1)}{" "}
                g grassi
              </span>
            </div>

            {recipeAiCalculated ? (
              <div className={styles.nutritionCard}>
                <strong>
                  Per 100 g
                </strong>

                <span>
                  {Math.round(
                    recipeAiCalculated
                      .per100g.calories,
                  )}{" "}
                  kcal
                </span>

                <span>
                  P{" "}
                  {recipeAiCalculated
                    .per100g.protein.toFixed(
                      1,
                    )}{" "}
                  g
                </span>

                <span>
                  C{" "}
                  {recipeAiCalculated
                    .per100g.carbs.toFixed(
                      1,
                    )}{" "}
                  g
                </span>

                <span>
                  G{" "}
                  {recipeAiCalculated
                    .per100g.fat.toFixed(
                      1,
                    )}{" "}
                  g
                </span>
              </div>
            ) : null}

            <button
              type="button"
              className={styles.saveButton}
              disabled={saving}
              onClick={() => {
                void useRecipeAiPreview();
              }}
            >
              {saving
                ? "Preparo…"
                : "Usa questa ricetta"}
            </button>

            {recipeAiCalculated ? (
              <div className={styles.nutritionCard}>
                <strong>
                  Per porzione
                </strong>

                <span>
                  {Math.round(
                    recipeAiCalculated
                      .perServing.calories,
                  )}{" "}
                  kcal
                </span>

                <span>
                  P{" "}
                  {recipeAiCalculated
                    .perServing.protein.toFixed(
                      1,
                    )}{" "}
                  g
                </span>

                <span>
                  C{" "}
                  {recipeAiCalculated
                    .perServing.carbs.toFixed(
                      1,
                    )}{" "}
                  g
                </span>

                <span>
                  G{" "}
                  {recipeAiCalculated
                    .perServing.fat.toFixed(
                      1,
                    )}{" "}
                  g
                </span>
              </div>
            ) : null}

            {recipeAiPreview
              .needs_final_weight_confirmation ? (
              <p className={styles.message}>
                Il peso finale non era indicato.
                Per una ricetta cotta è meglio
                pesare il risultato finale e
                selezionare “Peso finale ricetta”.
              </p>
            ) : null}
          </>
        ) : null}
      </section>

      {cookRecipe ? (
        <section ref={actionPanelRef} className={styles.editorCard}>
          <div className={styles.sectionHeader}>
            <div>
              <p className={styles.kicker}>
                {copy.mealPrep}
              </p>
              <h2>{copy.cookingTitle}</h2>
            </div>

            <button
              type="button"
              className={styles.secondaryButton}
              onClick={closeCookDialog}
              disabled={cooking}
            >
              {copy.cancel}
            </button>
          </div>

          <p>
            <strong>{cookRecipe.name}</strong>
          </p>

          <label className={styles.field}>
            <span>{copy.cookedHowMany}</span>
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
              ? copy.saving
              : copy.addToInventory}
          </button>
        </section>
      ) : null}

      {mealDraft ? (
        <section ref={actionPanelRef} className={styles.editorCard}>
          <div className={styles.sectionHeader}>
            <div>
              <p className={styles.kicker}>
                {copy.todayMeal}
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
            {mealTypeLabel(mealDraft.mealType)} · {copy.editQuantities}
          </p>


          <div className={styles.twoColumns}>
            <label className={styles.field}>
              {copy.servingsToEat}
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
              {copy.originalRecipe}
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
                      copy.ingredient}
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
              ? copy.logging
              : copy.logThisMeal}
          </button>
        </section>
      ) : null}

      <section>
        <div className={styles.sectionHeader}>
          <div>
            <p className={styles.kicker}>
              {copy.personalLibrary}
            </p>
            <h2>
              {zero ? copy.reliable : copy.ready}
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
            {copy.updateLegacy}
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
              placeholder={copy.search}
              aria-label={copy.search}
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
                aria-label={copy.clearSearch}
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
            aria-label={copy.filterMeal}
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
              {copy.all}
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
                  {mealTypeLabel(type)}
                </button>
              ),
            )}
          </div>

          <div className={styles.recipeResultCount}>
            <strong>
              {filteredRecipes.length}
            </strong>{" "}
            {filteredRecipes.length === 1
              ? copy.recipe
              : copy.recipes}
          </div>
          <label className={styles.recipeSort}>
            <span>{copy.sort}</span>
            <select value={recipeSort} onChange={(event) => setRecipeSort(event.target.value as "recent" | "taste" | "ease")}>
              <option value="recent">{copy.recent}</option>
              <option value="taste">{copy.taste}</option>
              <option value="ease">{copy.ease}</option>
            </select>
          </label>
        </div>

        {loading ? (
          <p>{copy.loading}</p>
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
                    {mealTypeLabel(recipe.meal_type)}
                  </span>
                </div>

                <div className={styles.recipeContent}>
                  <div className={styles.recipeMain}>
                    <strong className={styles.recipeTitle}>
                      {recipe.name}
                    </strong>

                    <div className={styles.recipeNutrition}>
                      <div className={styles.recipeRating}>
                        <span>{copy.taste}</span>
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
                        <span>{copy.ease}</span>
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
                        {copy.totalCalories}
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
                          {copy.totalProtein}
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
                          ? ` ${copy.serving}`
                          : ` ${copy.servings}`}
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
                        {copy.perServing}
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
                          {copy.proteinPerServing}
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
                        void openRecipeEditor(
                          recipe.id,
                        );
                      }}
                    >
                      {copy.edit}
                    </button>

                    <button
                      type="button"
                      className={styles.secondaryButton}
                      onClick={() => {
                        openCookDialog(recipe);
                      }}
                    >
                      {copy.cook}
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
                      {copy.log}
                    </button>

                    <Link
                      className={styles.secondaryButton}
                      href={`/recipes/${encodeURIComponent(recipe.id)}`}
                    >
                      {copy.detail}
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
                  ? copy.noResultsZero
                  : copy.noResults
                : zero
                  ? copy.emptyZero
                  : copy.empty}
            </strong>

            <p>
              {recipes.length
                ? zero
                  ? copy.changeFilterZero
                  : copy.changeFilter
                : zero
                  ? copy.emptyHelpZero
                  : copy.emptyHelp}
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
                {copy.resetFilters}
              </button>
            ) : null}
          </div>
        )}
      </section>


      <section className={styles.communitySection}>
        <div className={styles.communityHeading}>
          <div>
            <p className={styles.kicker}>
              Community
            </p>
            <h2>{copy.communityTitle}</h2>
            <p className={styles.communitySubtitle}>
              {copy.communitySubtitle}
            </p>
          </div>

          <span className={styles.communityCount}>
            {filteredSharedRecipes.length}
          </span>
        </div>

        {loading ? (
          <p>{copy.loading}</p>
        ) : filteredSharedRecipes.length ? (
          <div className={styles.recipeList}>
            {filteredSharedRecipes.map((recipe) => (
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
                      className={styles.recipePlaceholder}
                    >
                      <span>S</span>
                    </div>
                  )}

                  <span className={styles.recipeTypeBadge}>
                    {mealTypeLabel(recipe.meal_type)}
                  </span>
                </div>

                <div className={styles.recipeContent}>
                  <div className={styles.recipeMain}>
                    <strong className={styles.recipeTitle}>
                      {recipe.name}
                    </strong>

                    <div className={styles.recipeNutrition}>
                      <span>
                        <strong>
                          {Math.round(
                            Number(recipe.calories || 0),
                          )}
                        </strong>
                        {copy.totalCalories}
                      </span>

                      {recipe.protein != null ? (
                        <span>
                          <strong>
                            {Math.round(
                              Number(recipe.protein || 0),
                            )}
                          </strong>
                          {copy.totalProtein}
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
                          ? ` ${copy.serving}`
                          : ` ${copy.servings}`}
                      </span>
                    </div>

                    {recipe.notes ? (
                      <p className={styles.recipeDescription}>
                        {recipe.notes}
                      </p>
                    ) : null}
                  </div>

                  <div className={styles.recipeActions}>
                    <button
                      type="button"
                      className={styles.secondaryButton}
                      onClick={() => {
                        openCookDialog(recipe);
                      }}
                    >
                      {copy.cook}
                    </button>

                    <button
                      type="button"
                      className={styles.primarySmallButton}
                      onClick={() => {
                        void startMealFromRecipe(recipe.id);
                      }}
                    >
                      {copy.log}
                    </button>

                    <Link
                      className={styles.secondaryButton}
                      href={`/recipes/${encodeURIComponent(
                        recipe.id,
                      )}`}
                    >
                      {copy.detail}
                    </Link>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className={styles.recipeEmptyState}>
            <strong>{copy.communityEmpty}</strong>
          </div>
        )}
      </section>



<section ref={editorRef} className={styles.editorCard}>
        <div className={styles.sectionHeader}>
          <div>
            <p className={styles.kicker}>
              {editingId
                ? copy.edit
                : copy.new}
            </p>
            <h2>
              {editingId
                ? copy.editRecipe
                : copy.createRecipe}
            </h2>
          </div>

          {editingId ? (
            <button
              type="button"
              onClick={resetEditor}
              className={styles.secondaryButton}
            >
              {copy.new}
            </button>
          ) : null}
        </div>

        <label className={styles.field}>
          {copy.name}
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
            ? copy.replacePhoto
            : copy.addPhoto}
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
            {copy.type}
            <select
              value={mealType}
              onChange={(event) => {
                setMealType(
                  event.target.value,
                );
              }}
            >
              <option value="Colazione">{copy.breakfast}</option>
              <option value="Pranzo">{copy.lunch}</option>
              <option value="Cena">{copy.dinner}</option>
            </select>
          </label>

          <label className={styles.field}>
            {copy.servings}
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

            <label className={styles.field}>
              <span>Peso finale ricetta (g)</span>
              <input
                type="number"
                min="1"
                step="1"
                value={finalWeight}
                placeholder="Es. 1200"
                onChange={(event) => {
                  setFinalWeight(
                    event.target.value,
                  );
                }}
              />
            </label>
        </div>

        <div className={styles.twoColumns}>
          <label className={styles.field}>
            {copy.taste}
            <select value={tasteRating} onChange={(event) => setTasteRating(event.target.value)}>
              <option value="">{copy.unrated}</option>
              {[1, 2, 3, 4, 5].map((rating) => <option key={rating} value={rating}>{rating}/5</option>)}
            </select>
          </label>
          <label className={styles.field}>
            {copy.ease}
            <select value={easeRating} onChange={(event) => setEaseRating(event.target.value)}>
              <option value="">{copy.unrated}</option>
              {[1, 2, 3, 4, 5].map((rating) => <option key={rating} value={rating}>{rating}/5</option>)}
            </select>
          </label>
        </div>

        <label className={styles.field}>
          {copy.preparation}
          <textarea
            className={styles.preparationTextarea}
            value={notes}
            rows={8}
            placeholder={copy.preparationPlaceholder}
            onChange={(event) => {
              setNotes(event.target.value);
            }}
          />
        </label>

        <div className={styles.ingredientsHeader}>
          <strong>{copy.ingredients}</strong>

          <div className={styles.smallActions}>
            <button
              type="button"
              className={styles.secondaryButton}
              onClick={addIngredientRow}
            >
              + {copy.existing}
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
              + {copy.newIngredient}
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
                  const nextIngredient =
                    ingredients.find(
                      (ingredient) =>
                        ingredient.id ===
                        event.target.value,
                    );

                  const portionGrams =
                    ingredientPortionGrams(
                      nextIngredient,
                    );

                  updateDraftIngredient(
                    index,
                    {
                      ingredientId:
                        event.target.value,

                      quantityG:
                        portionGrams ?? 100,

                      inputUnit:
                        portionGrams
                          ? "portion"
                          : "g",
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

              {(() => {
                const ingredient =
                  ingredients.find(
                    (item) =>
                      item.id ===
                      row.ingredientId,
                  );

                const portionGrams =
                  ingredientPortionGrams(
                    ingredient,
                  );

                const usingPortion =
                  row.inputUnit ===
                    "portion" &&
                  portionGrams !== null;

                return (
                  <div
                    className={
                      styles.quantityField
                    }
                  >
                    <input
                      type="number"
                      min={
                        usingPortion
                          ? "0.1"
                          : "1"
                      }
                      step={
                        usingPortion
                          ? "0.5"
                          : "1"
                      }
                      value={
                        ingredientDisplayQuantity(
                          row,
                          ingredient,
                        )
                      }
                      onChange={(event) => {
                        const next =
                          Number(
                            event.target.value,
                          ) || 0;

                        updateDraftIngredient(
                          index,
                          {
                            quantityG:
                              usingPortion &&
                              portionGrams
                                ? next *
                                  portionGrams
                                : next,
                          },
                        );
                      }}
                    />

                    {portionGrams ? (
                      <select
                        className={
                          styles.quantityUnitSelect
                        }
                        value={
                          usingPortion
                            ? "portion"
                            : "g"
                        }
                        onChange={(event) => {
                          updateDraftIngredient(
                            index,
                            {
                              inputUnit:
                                event.target
                                  .value ===
                                "portion"
                                  ? "portion"
                                  : "g",
                            },
                          );
                        }}
                        aria-label="Unità quantità"
                      >
                        <option value="g">
                          g
                        </option>
                        <option value="portion">
                          porzioni
                        </option>
                      </select>
                    ) : (
                      <span>g</span>
                    )}
                  </div>
                );
              })()}

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
              {copy.newIngredientTitle}
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

            <div className={styles.smallActions}>
              <button
                type="button"
                className={styles.secondaryButton}
                disabled={
                  ingredientAiLoading ||
                  !ingredientDraft.name.trim()
                }
                onClick={() => {
                  void fillIngredientWithAi();
                }}
              >
                {ingredientAiLoading
                  ? copy.aiCalculating
                  : copy.aiFill}
              </button>
            </div>

            {ingredientAiMessage ? (
              <p className={styles.aiIngredientMessage}>
                {ingredientAiMessage}
              </p>
            ) : null}

            <label className={styles.field}>
              {copy.defaultServingGrams}
              <input
                type="number"
                min="1"
                step="1"
                value={
                  ingredientDraft.portionGrams
                }
                placeholder="Es. 70"
                onChange={(event) => {
                  setIngredientDraft(
                    (current) => ({
                      ...current,
                      portionGrams:
                        event.target.value,
                    }),
                  );
                }}
              />
              <small>
                {copy.optionalServingHelp}
              </small>
            </label>

            <div className={styles.macroInputs}>
              {[
                ["calories", "kcal / 100 g"],
                ["protein", copy.protein],
                ["carbs", copy.carbs],
                ["fat", copy.fat],
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
                {copy.saveIngredient}
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
                {copy.cancel}
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

        <div className={styles.recipeSaveBar}>
          <div className={styles.recipeSaveCopy}>
            <strong>
              {editingId
                ? copy.recipeEdited
                : copy.recipeReady}
            </strong>
            <span>
              {editingId
                ? copy.saveEditHelp
                : copy.saveRecipeHelp}
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
              ? copy.saving
              : editingId
                ? copy.saveChanges
                : copy.saveRecipe}
          </button>
        </div>
      </section>

      </main>
    </>
  );
}
