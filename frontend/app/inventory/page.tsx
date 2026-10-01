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
  previewIngredientFromText,
  scanNutritionLabel,
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
import { ApiError } from "@/lib/api/client";

import styles from "./InventoryPage.module.css";

type PantryMealSlot =
  | "breakfast"
  | "lunch"
  | "snack"
  | "dinner";

type InventoryFilter =
  | "all"
  | "breakfast_snack"
  | "lunch_dinner"
  | "meal_prep"
  | "expiring";

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

function fileToBase64(
  file: File,
): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = () => {
      const value = String(
        reader.result ?? "",
      );
      const comma = value.indexOf(",");

      resolve(
        comma >= 0
          ? value.slice(comma + 1)
          : value,
      );
    };

    reader.onerror = () =>
      reject(
        new Error(
          "Non riesco a leggere la foto.",
        ),
      );

    reader.readAsDataURL(file);
  });
}

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

  const [foodAIText, setFoodAIText] = useState("");
  const [foodAIWorking, setFoodAIWorking] = useState(false);
  const [foodAIMessage, setFoodAIMessage] = useState<string | null>(null);
  const [foodAIPhoto, setFoodAIPhoto] = useState<File | null>(null);
  const [foodAIPhotoPreview, setFoodAIPhotoPreview] =
    useState<string | null>(null);
  const [foodAIListening, setFoodAIListening] = useState(false);

  const [inventorySearch, setInventorySearch] = useState("");
  const [inventoryFilter, setInventoryFilter] =
    useState<InventoryFilter>("all");

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

  function applyFoodAIPreview(result: {
    name?: string | null;
    calories_per_100g?: number | null;
    protein_per_100g?: number | null;
    carbs_per_100g?: number | null;
    fat_per_100g?: number | null;
    kind?: "ingredient" | "product" | "prepared_food";
    meal_slots?: PantryMealSlot[];
    confidence?: "high" | "medium" | "low";
    estimated?: boolean;
    notes?: string | null;
    ready_for_form?: boolean;
  }) {
    setNewFoodForm((current) => ({
      ...current,
      name: result.name ?? current.name,
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
      kind: result.kind ?? current.kind,
      mealSlots:
        result.meal_slots != null
          ? result.meal_slots
          : current.mealSlots,
    }));

    const confidence =
      result.confidence === "high"
        ? "alta"
        : result.confidence === "medium"
          ? "media"
          : "bassa";

    setFoodAIMessage(
      [
        result.ready_for_form
          ? "Proposta pronta da controllare."
          : "Ho compilato quello che riesco: completa i campi mancanti.",
        result.estimated
          ? "I valori nutrizionali sono una stima."
          : null,
        `Affidabilità ${confidence}.`,
        result.notes ?? null,
      ]
        .filter(Boolean)
        .join(" "),
    );
  }

  async function analyzeFoodAIText(
    value?: string,
  ) {
    if (!accessToken) {
      return;
    }

    const textValue = (
      value ?? foodAIText
    ).trim();

    if (!textValue) {
      setFoodAIMessage(
        "Descrivi l'alimento prima di analizzarlo.",
      );
      return;
    }

    setFoodAIWorking(true);
    setFoodAIMessage(null);
    setError(null);

    try {
      const response =
        await previewIngredientFromText(
          textValue,
          accessToken,
        );

      applyFoodAIPreview(
        response.result,
      );
    } catch (err) {
      setFoodAIMessage(
        err instanceof Error
          ? err.message
          : "Non riesco ad analizzare l'alimento.",
      );
    } finally {
      setFoodAIWorking(false);
    }
  }

  async function analyzeFoodAIPhoto() {
    if (
      !accessToken ||
      !foodAIPhoto
    ) {
      return;
    }

    setFoodAIWorking(true);
    setFoodAIMessage(null);
    setError(null);

    try {
      const contentBase64 =
        await fileToBase64(
          foodAIPhoto,
        );

      const response =
        await scanNutritionLabel(
          {
            content_base64:
              contentBase64,
            mime_type:
              foodAIPhoto.type,
          },
          accessToken,
        );

      const result = response.result;

      applyFoodAIPreview({
        name: result.name,
        calories_per_100g:
          result.calories,
        protein_per_100g:
          result.protein,
        carbs_per_100g:
          result.carbs,
        fat_per_100g:
          result.fat,
        kind: newFoodForm.kind,
        meal_slots:
          newFoodForm.mealSlots,
        confidence:
          result.confidence,
        estimated: false,
        notes: result.notes,
        ready_for_form:
          result.ready_for_form,
      });
    } catch (err) {
      setFoodAIMessage(
        err instanceof Error
          ? err.message
          : "Non riesco a leggere l'etichetta.",
      );
    } finally {
      setFoodAIWorking(false);
    }
  }

  function startFoodAIVoice() {
    const speechWindow =
      window as typeof window & {
        SpeechRecognition?: new () => any;
        webkitSpeechRecognition?: new () => any;
      };

    const Recognition =
      speechWindow.SpeechRecognition ??
      speechWindow.webkitSpeechRecognition;

    if (!Recognition) {
      setFoodAIMessage(
        "La dettatura non è supportata da questo browser.",
      );
      return;
    }

    const recognition =
      new Recognition();

    recognition.lang = "it-IT";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setFoodAIListening(true);
      setFoodAIMessage(
        "Ti ascolto…",
      );
    };

    recognition.onend = () => {
      setFoodAIListening(false);
    };

    recognition.onerror = () => {
      setFoodAIListening(false);
      setFoodAIMessage(
        "Non riesco a usare il microfono.",
      );
    };

    recognition.onresult = (
      event: any,
    ) => {
      const transcript =
        String(
          event.results?.[0]?.[0]
            ?.transcript ?? "",
        ).trim();

      if (!transcript) {
        return;
      }

      setFoodAIText(transcript);
      void analyzeFoodAIText(
        transcript,
      );
    };

    recognition.start();
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
      if (
        err instanceof ApiError &&
        err.status === 409 &&
        err.payload &&
        typeof err.payload === "object" &&
        "detail" in err.payload &&
        typeof err.payload.detail === "string"
      ) {
        setError(err.payload.detail);
      } else {
        setError(
          err instanceof Error
            ? err.message
            : "Impossibile creare l'alimento.",
        );
      }
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

  function pantrySlots(item: PantryItem) {
    return (
      ingredientForPantryId(item.ingredient_id)
        ?.meal_slots ?? []
    );
  }

  function expiresSoon(expiresAt: string | null) {
    if (!expiresAt) {
      return false;
    }

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const expires = new Date(`${expiresAt}T00:00:00`);

    if (Number.isNaN(expires.getTime())) {
      return false;
    }

    const diffDays = Math.ceil(
      (expires.getTime() - today.getTime()) /
        (1000 * 60 * 60 * 24),
    );

    return diffDays >= 0 && diffDays <= 7;
  }

  const normalizedInventorySearch =
    inventorySearch.trim().toLowerCase();

  const breakfastSnackCount = pantryItems.filter(
    (item) => {
      const slots = pantrySlots(item);

      return (
        slots.includes("breakfast") ||
        slots.includes("snack")
      );
    },
  ).length;

  const lunchDinnerCount =
    pantryItems.filter(
      (item) => {
        const slots = pantrySlots(item);

        return (
          slots.includes("lunch") ||
          slots.includes("dinner")
        );
      },
    ).length +
    items.filter(
      (item) => item.portions_remaining > 0,
    ).length;

  const cookedPortionsCount = items.reduce(
    (total, item) =>
      total + item.portions_remaining,
    0,
  );

  const expiringCount = pantryItems.filter((item) =>
    expiresSoon(item.expires_at),
  ).length;

  const filteredPantryItems = pantryItems.filter(
    (item) => {
      if (inventoryFilter === "meal_prep") {
        return false;
      }

      const name =
        item.ingredient_name?.toLowerCase() ?? "";

      if (
        normalizedInventorySearch &&
        !name.includes(normalizedInventorySearch)
      ) {
        return false;
      }

      const slots = pantrySlots(item);

      if (
        inventoryFilter === "breakfast_snack"
      ) {
        return (
          slots.includes("breakfast") ||
          slots.includes("snack")
        );
      }

      if (
        inventoryFilter === "lunch_dinner"
      ) {
        return (
          slots.includes("lunch") ||
          slots.includes("dinner")
        );
      }

      if (inventoryFilter === "expiring") {
        return expiresSoon(item.expires_at);
      }

      return true;
    },
  );

  const filteredMealPrepItems = items.filter(
    (item) => {
      if (
        inventoryFilter !== "all" &&
        inventoryFilter !== "meal_prep" &&
        inventoryFilter !== "lunch_dinner"
      ) {
        return false;
      }

      if (
        normalizedInventorySearch &&
        !item.name
          .toLowerCase()
          .includes(normalizedInventorySearch)
      ) {
        return false;
      }

      return true;
    },
  );

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

        <section className={styles.inventorySummary}>
          <button
            type="button"
            className={
              inventoryFilter === "breakfast_snack"
                ? styles.inventorySummaryActive
                : undefined
            }
            onClick={() =>
              setInventoryFilter(
                inventoryFilter === "breakfast_snack"
                  ? "all"
                  : "breakfast_snack",
              )
            }
          >
            <span className={styles.summaryCoral}>☕</span>
            <span>
              <strong>{breakfastSnackCount}</strong>
              <small>Colazione / Snack</small>
            </span>
          </button>

          <button
            type="button"
            className={
              inventoryFilter === "lunch_dinner"
                ? styles.inventorySummaryActive
                : undefined
            }
            onClick={() =>
              setInventoryFilter(
                inventoryFilter === "lunch_dinner"
                  ? "all"
                  : "lunch_dinner",
              )
            }
          >
            <span className={styles.summaryGreen}>🍴</span>
            <span>
              <strong>{lunchDinnerCount}</strong>
              <small>Pranzo / Cena</small>
            </span>
          </button>

          <button
            type="button"
            className={
              inventoryFilter === "meal_prep"
                ? styles.inventorySummaryActive
                : undefined
            }
            onClick={() =>
              setInventoryFilter(
                inventoryFilter === "meal_prep"
                  ? "all"
                  : "meal_prep",
              )
            }
          >
            <span className={styles.summaryBlue}>▣</span>
            <span>
              <strong>{cookedPortionsCount}</strong>
              <small>Porzioni cucinate</small>
            </span>
          </button>

          <button
            type="button"
            className={
              inventoryFilter === "expiring"
                ? styles.inventorySummaryActive
                : undefined
            }
            onClick={() =>
              setInventoryFilter(
                inventoryFilter === "expiring"
                  ? "all"
                  : "expiring",
              )
            }
          >
            <span className={styles.summaryAmber}>◷</span>
            <span>
              <strong>{expiringCount}</strong>
              <small>In scadenza</small>
            </span>
          </button>
        </section>

        <section className={styles.inventoryToolbar}>
          <label className={styles.inventorySearch}>
            <span aria-hidden="true">⌕</span>
            <input
              type="search"
              value={inventorySearch}
              placeholder="Cerca nella dispensa..."
              onChange={(event) =>
                setInventorySearch(
                  event.target.value,
                )
              }
            />
          </label>

          <div className={styles.inventoryFilters}>
            {[
              ["all", "Tutti"],
              [
                "breakfast_snack",
                "Colazione / Snack",
              ],
              [
                "lunch_dinner",
                "Pranzo / Cena",
              ],
              ["meal_prep", "Porzioni cucinate"],
              ["expiring", "In scadenza"],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                className={
                  inventoryFilter === value
                    ? styles.inventoryFilterActive
                    : undefined
                }
                onClick={() =>
                  setInventoryFilter(
                    value as InventoryFilter,
                  )
                }
              >
                {label}
              </button>
            ))}
          </div>
        </section>

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

            <section className={styles.foodAIAssistant}>
              <div className={styles.foodAIHead}>
                <div>
                  <strong>✦ Compila con SanoSync AI</strong>
                  <span>
                    Descrivi il prodotto, fotografa l'etichetta o dettalo.
                    Controllerai sempre i valori prima di salvarli.
                  </span>
                </div>
              </div>

              <div className={styles.foodAIComposer}>
                <textarea
                  value={foodAIText}
                  placeholder="Es. Yogurt greco Fage 0%, vasetto 170 g..."
                  onChange={(event) =>
                    setFoodAIText(
                      event.target.value,
                    )
                  }
                />

                <button
                  type="button"
                  className={styles.foodAIVoice}
                  disabled={
                    foodAIWorking ||
                    foodAIListening
                  }
                  onClick={startFoodAIVoice}
                >
                  {foodAIListening
                    ? "Ascolto…"
                    : "🎙 Voce"}
                </button>

                <button
                  type="button"
                  className={styles.foodAIAnalyze}
                  disabled={
                    foodAIWorking ||
                    !foodAIText.trim()
                  }
                  onClick={() => {
                    void analyzeFoodAIText();
                  }}
                >
                  {foodAIWorking
                    ? "Analizzo…"
                    : "Analizza testo"}
                </button>
              </div>

              <div className={styles.foodAIPhotoRow}>
                <label className={styles.foodAIPhotoButton}>
                  <span>▧ Foto etichetta</span>
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    capture="environment"
                    onChange={(event) => {
                      const file =
                        event.target.files?.[0] ??
                        null;

                      setFoodAIPhoto(file);
                      setFoodAIMessage(null);

                      if (!file) {
                        setFoodAIPhotoPreview(null);
                        return;
                      }

                      if (
                        file.size >
                        8 * 1024 * 1024
                      ) {
                        setFoodAIPhoto(null);
                        setFoodAIPhotoPreview(null);
                        setFoodAIMessage(
                          "La foto supera il limite di 8 MB.",
                        );
                        return;
                      }

                      const reader =
                        new FileReader();

                      reader.onload = () => {
                        if (
                          typeof reader.result ===
                          "string"
                        ) {
                          setFoodAIPhotoPreview(
                            reader.result,
                          );
                        }
                      };

                      reader.readAsDataURL(file);
                    }}
                  />
                </label>

                <button
                  type="button"
                  className={styles.foodAIPhotoAnalyze}
                  disabled={
                    foodAIWorking ||
                    !foodAIPhoto
                  }
                  onClick={() => {
                    void analyzeFoodAIPhoto();
                  }}
                >
                  {foodAIWorking
                    ? "Analizzo…"
                    : "Leggi etichetta"}
                </button>

                {foodAIPhotoPreview ? (
                  <img
                    className={styles.foodAIPhotoPreview}
                    src={foodAIPhotoPreview}
                    alt="Anteprima etichetta nutrizionale"
                  />
                ) : null}
              </div>

              {foodAIMessage ? (
                <p className={styles.foodAIMessage}>
                  {foodAIMessage}
                </p>
              ) : null}
            </section>

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
                  <option value="product">
                    Prodotto / alimento da consumare
                  </option>
                  <option value="ingredient">
                    Ingrediente per ricette
                  </option>
                  <option value="prepared_food">
                    Preparato / piatto pronto
                  </option>
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

        <section
          className={`${styles.pantrySection} ${
            inventoryFilter === "meal_prep"
              ? styles.inventorySectionHidden
              : ""
          }`}
        >
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

          {!loading &&
            filteredPantryItems.length > 0 && (
            <div className={styles.pantryList}>
              {filteredPantryItems.map((item) => (
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
            filteredPantryItems.length === 0 &&
            inventoryFilter !== "meal_prep" && (
              <div className={styles.pantryEmpty}>
                <strong>
                  {pantryItems.length === 0
                    ? "Nessun alimento registrato."
                    : "Nessun alimento corrisponde ai filtri."}
                </strong>
                <p>
                  {pantryItems.length === 0
                    ? "Usa “Aggiungi scorta” per inserire il primo alimento."
                    : "Prova un altro filtro o modifica la ricerca."}
                </p>
              </div>
            )}
        </section>

        <section
          className={`${styles.pantrySection} ${
            inventoryFilter !== "all" &&
            inventoryFilter !== "meal_prep"
              ? styles.inventorySectionHidden
              : ""
          }`}
        >
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
          ) : filteredMealPrepItems.length === 0 ? (
            <section className={styles.empty}>
              <h2>Nessuna porzione disponibile</h2>
              <p>
                Quando cucini più porzioni di una ricetta,
                quelle non ancora mangiate appariranno qui.
              </p>
            </section>
          ) : (
            <div className={styles.list}>
              {filteredMealPrepItems.map((item) => (
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
