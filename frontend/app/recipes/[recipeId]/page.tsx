"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";
import { AppNav } from "@/components/navigation/AppNav";
import { RecipeShareButton } from "@/components/recipes/RecipeShareButton";
import { getIngredients, type Ingredient } from "@/lib/api/ingredients";
import { uploadRecipeImage } from "@/lib/api/recipeImages";
import { getRecipe, updateRecipe, type Recipe } from "@/lib/api/recipes";

import styles from "./RecipeDetail.module.css";

type Row = { ingredientId: string; quantityG: number };

export default function RecipeDetailPage() {
  const params = useParams<{ recipeId: string }>();
  const { accessToken, user } = useAuth();
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [rows, setRows] = useState<Row[]>([]);
  const [servings, setServings] = useState(1);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!accessToken || !params.recipeId) return;
    void Promise.all([getRecipe(params.recipeId, accessToken), getIngredients(accessToken)])
      .then(([recipeResponse, ingredientResponse]) => {
        const item = recipeResponse.item;
        setRecipe(item);
        setIngredients(ingredientResponse.items);
        setServings(Math.max(1, Number(item.recipe_servings || 1)));
        setRows((item.structured_ingredients ?? []).map((row) => ({
          ingredientId: row.ingredient_id,
          quantityG: Number(row.quantity_g),
        })));
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "Non riesco ad aprire la ricetta."));
  }, [accessToken, params.recipeId]);

  const nutrition = useMemo(() => rows.reduce((total, row) => {
    const ingredient = ingredients.find((item) => item.id === row.ingredientId);
    if (!ingredient) return total;
    const factor = Math.max(0, row.quantityG) / 100;
    return {
      calories: total.calories + ingredient.calories_per_100g * factor,
      protein: total.protein + ingredient.protein_per_100g * factor,
      carbs: total.carbs + ingredient.carbs_per_100g * factor,
      fat: total.fat + ingredient.fat_per_100g * factor,
    };
  }, { calories: 0, protein: 0, carbs: 0, fat: 0 }), [rows, ingredients]);

  function updateRow(index: number, changes: Partial<Row>) {
    setRows((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, ...changes } : row));
  }

  async function save() {
    if (!recipe || !accessToken || rows.length === 0 || rows.some((row) => row.quantityG <= 0)) {
      setMessage("Inserisci almeno un ingrediente con quantità valida.");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const response = await updateRecipe(recipe.id, {
        recipe_servings: servings,
        image_url: recipe.image_url,
        taste_rating: recipe.taste_rating,
        ease_rating: recipe.ease_rating,
        structured_ingredients: rows.map((row) => ({
          ingredient_id: row.ingredientId,
          quantity: row.quantityG,
          unit: "g",
          quantity_g: row.quantityG,
        })),
      }, accessToken);
      setRecipe((current) => current ? { ...current, ...response.item } : response.item);
      setMessage("Modifiche salvate.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Non riesco a salvare la ricetta.");
    } finally {
      setSaving(false);
    }
  }

  async function changePhoto(file?: File) {
    if (!file || !user || !recipe) return;
    setSaving(true);
    try {
      const imageUrl = await uploadRecipeImage(file, user.id);
      setRecipe({ ...recipe, image_url: imageUrl });
      setMessage("Foto caricata: salva le modifiche per confermare.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Non riesco a caricare la foto.");
    } finally {
      setSaving(false);
    }
  }

  if (!recipe) {
    return <><AppNav /><main className={styles.page}><p>{message || "Caricamento ricetta…"}</p></main></>;
  }

  const perServing = Math.max(1, servings);

  return (
    <>
      <AppNav />
      <main className={styles.page}>
        <header><h1>Le tue ricette</h1><Link href="/recipes">← Torna alle ricette</Link></header>
        {message ? <p className={styles.message}>{message}</p> : null}

        <section className={styles.hero}>
          <div className={styles.photo}>
            {recipe.image_url ? <img src={recipe.image_url} alt={recipe.name} /> : <span>S</span>}
            <label>📷 Modifica foto<input hidden type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => void changePhoto(event.target.files?.[0])} /></label>
          </div>
          <div className={styles.summary}>
            <span className={styles.badge}>{recipe.meal_type || "Ricetta"}</span>
            <h2>{recipe.name}</h2>
            {(["taste_rating", "ease_rating"] as const).map((field) => (
              <div className={styles.rating} key={field}>
                <span>{field === "taste_rating" ? "Gusto" : "Facilità"}</span>
                <div>{[1,2,3,4,5].map((value) => <button key={value} type="button" onClick={() => setRecipe({ ...recipe, [field]: value })} className={value <= Number(recipe[field] || 0) ? styles.starActive : styles.star}>★</button>)}</div>
              </div>
            ))}
            <div className={styles.pills}>
              <span><strong>{Math.round(nutrition.calories / perServing)}</strong> kcal</span>
              <span><strong>{Math.round(nutrition.protein / perServing)}</strong> g proteine</span>
              <span><strong>{Math.round(nutrition.carbs / perServing)}</strong> g carbo</span>
              <span><strong>{Math.round(nutrition.fat / perServing)}</strong> g grassi</span>
            </div>
            <div className={styles.actions}>
              <RecipeShareButton name={recipe.name} imageUrl={recipe.image_url} calories={nutrition.calories} protein={nutrition.protein} servings={servings} preparation={recipe.preparation} />
              <Link href="/recipes">Registra o cucina</Link>
            </div>
          </div>
        </section>

        <section className={styles.ingredientsCard}>
          <div className={styles.ingredientsHeader}>
            <div><p>Ingredienti</p><h2>{rows.length} ingredienti</h2></div>
            <div className={styles.stepper}><span>Porzioni</span><button type="button" onClick={() => setServings(Math.max(1, servings - 1))}>−</button><strong>{servings}</strong><button type="button" onClick={() => setServings(servings + 1)}>＋</button></div>
          </div>
          <div className={styles.editorGrid}>
            <div className={styles.rows}>
              {rows.map((row, index) => (
                <div className={styles.ingredientRow} key={`${row.ingredientId}-${index}`}>
                  <span aria-hidden="true">⠿</span>
                  <select value={row.ingredientId} onChange={(event) => updateRow(index, { ingredientId: event.target.value })}>{ingredients.map((ingredient) => <option key={ingredient.id} value={ingredient.id}>{ingredient.name}</option>)}</select>
                  <input type="number" min="1" value={row.quantityG} onChange={(event) => updateRow(index, { quantityG: Number(event.target.value) || 0 })} />
                  <span>g</span>
                  <button type="button" aria-label="Elimina ingrediente" onClick={() => setRows((current) => current.filter((_, rowIndex) => rowIndex !== index))}>×</button>
                </div>
              ))}
              <button className={styles.addButton} type="button" onClick={() => ingredients[0] && setRows((current) => [...current, { ingredientId: ingredients[0].id, quantityG: 100 }])}>＋ Aggiungi ingrediente</button>
            </div>
            <aside className={styles.totals}><h3>Totale ricetta</h3><strong>{Math.round(nutrition.calories)} kcal</strong><span>{Math.round(nutrition.protein)} g proteine</span><span>{Math.round(nutrition.carbs)} g carbo</span><span>{Math.round(nutrition.fat)} g grassi</span><button type="button" disabled={saving} onClick={() => void save()}>{saving ? "Salvataggio…" : "Salva modifiche"}</button></aside>
          </div>
        </section>
      </main>
    </>
  );
}
