"use client";

import { useEffect, useState } from "react";

import { AppNav } from "@/components/navigation/AppNav";
import { useAuth } from "@/components/auth/AuthProvider";
import {
  discardMealPrepPortions,
  getMealPrepInventory,
  logMealPrepPortion,
  type MealPrepItem,
} from "@/lib/api/mealPrep";

import styles from "./InventoryPage.module.css";

export default function InventoryPage() {
  const { accessToken } = useAuth();

  const [items, setItems] = useState<MealPrepItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mealType, setMealType] = useState("Cena");

  async function refresh() {


  if (!accessToken) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await getMealPrepInventory(
        accessToken,
        true,
      );

      setItems(response.items);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Impossibile caricare l'inventario.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, [accessToken]);

  async function discard(item: MealPrepItem) {
    if (
      !accessToken ||
      item.portions_remaining <= 0
    ) {
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

  if (!accessToken) {
    return (
      <>
        <AppNav />
        <main className={styles.page}>
          <section className={styles.card}>
            <h1>Inventario</h1>
            <p>Effettua l'accesso per vedere l'inventario.</p>
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
            <h1>Inventario</h1>
            <p>
              Le porzioni già cucinate e ancora disponibili.
            </p>
          </div>

          <label className={styles.mealType}>
            <span>Registra come</span>
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

        {loading ? (
          <section className={styles.card}>
            <p>Caricamento inventario...</p>
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
      </main>
    </>
  );
}
