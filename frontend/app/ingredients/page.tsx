"use client";

import { type FormEvent, useEffect, useMemo, useState } from "react";
import { AppNav } from "@/components/navigation/AppNav";
import { useAuth } from "@/components/auth/AuthProvider";
import {
  createIngredient,
  deleteIngredient,
  getIngredients,
  scanNutritionLabel,
  updateIngredient,
  type Ingredient,
} from "@/lib/api/ingredients";
import styles from "./IngredientsPage.module.css";

const EMPTY = { name: "", calories: "", protein: "", carbs: "", fat: "", unit: "g" };

function fileToBase64(
  file: File,
): Promise<string> {
  return new Promise(
    (resolve, reject) => {
      const reader = new FileReader();

      reader.onload = () => {
        const value = String(
          reader.result ?? "",
        );

        const comma =
          value.indexOf(",");

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
    },
  );
}

export default function IngredientsPage() {
  const { accessToken } = useAuth();
  const [items, setItems] = useState<Ingredient[]>([]);
  const [query, setQuery] = useState("");
  const [form, setForm] = useState(EMPTY);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const [
    labelPhoto,
    setLabelPhoto,
  ] = useState<File | null>(null);

  const [
    labelPhotoPreview,
    setLabelPhotoPreview,
  ] = useState<string | null>(null);

  const [
    scanningLabel,
    setScanningLabel,
  ] = useState(false);

  const [
    scanMessage,
    setScanMessage,
  ] = useState<string | null>(null);

  async function refresh() {
    if (!accessToken) return;
    setLoading(true);
    try {
      const response = await getIngredients(accessToken);
      setItems(response.items);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Impossibile caricare gli alimenti.");
    } finally { setLoading(false); }
  }

  useEffect(() => { void refresh(); }, [accessToken]);

  const visible = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("it");
    return items.filter((item) => !normalized || item.name.toLocaleLowerCase("it").includes(normalized));
  }, [items, query]);

  function edit(item: Ingredient) {
    setEditingId(item.id);
    setForm({
      name: item.name,
      calories: String(item.calories_per_100g),
      protein: String(item.protein_per_100g),
      carbs: String(item.carbs_per_100g),
      fat: String(item.fat_per_100g),
      unit: item.default_unit || "g",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function scanLabel() {
    if (
      !accessToken ||
      !labelPhoto
    ) {
      return;
    }

    setScanningLabel(true);
    setMessage(null);
    setScanMessage(null);

    try {
      const contentBase64 =
        await fileToBase64(
          labelPhoto,
        );

      const response =
        await scanNutritionLabel(
          {
            content_base64:
              contentBase64,
            mime_type:
              labelPhoto.type,
          },
          accessToken,
        );

      const result =
        response.result;

      setForm({
        name:
          result.name ??
          form.name,
        calories:
          result.calories != null
            ? String(result.calories)
            : form.calories,
        protein:
          result.protein != null
            ? String(result.protein)
            : form.protein,
        carbs:
          result.carbs != null
            ? String(result.carbs)
            : form.carbs,
        fat:
          result.fat != null
            ? String(result.fat)
            : form.fat,
        unit: "g",
      });

      if (result.ready_for_form) {
        setScanMessage(
          result.confidence === "low"
            ? "Valori estratti. Controllali con attenzione prima di salvare."
            : "Etichetta letta. Controlla i valori e salva quando vuoi.",
        );
      } else {
        setScanMessage(
          "Ho letto solo parte dell'etichetta. Completa o correggi i valori manualmente.",
        );
      }
    } catch (error) {
      setScanMessage(
        error instanceof Error
          ? error.message
          : "Non riesco a leggere l'etichetta.",
      );
    } finally {
      setScanningLabel(false);
    }
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!accessToken || !form.name.trim()) return;
    const payload = {
      name: form.name.trim(),
      calories_per_100g: Number(form.calories) || 0,
      protein_per_100g: Number(form.protein) || 0,
      carbs_per_100g: Number(form.carbs) || 0,
      fat_per_100g: Number(form.fat) || 0,
      default_unit: form.unit || "g",
    };
    setSaving(true);
    setMessage(null);
    try {
      if (editingId) await updateIngredient(editingId, payload, accessToken);
      else await createIngredient(payload, accessToken);
      setForm(EMPTY);
      setEditingId(null);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Impossibile salvare l'alimento.");
    } finally { setSaving(false); }
  }

  async function remove(item: Ingredient) {
    if (!accessToken || !window.confirm(`Eliminare “${item.name}”?`)) return;
    try {
      await deleteIngredient(item.id, accessToken);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Impossibile eliminare l'alimento.");
    }
  }

  return <><AppNav /><main className={styles.page}>
    <header><p>LIBRERIA</p><h1>Alimenti</h1><span>La tua libreria nutrizionale: ingredienti, prodotti e cibi pronti.</span></header>
    <section className={styles.editor}>
      <div><p>{editingId ? "MODIFICA" : "NUOVO"}</p><h2>{editingId ? "Aggiorna alimento" : "Aggiungi alimento"}</h2></div>

      {!editingId ? (
        <div className={styles.labelScanner}>
          <div className={styles.labelScannerCopy}>
            <strong>Scansiona etichetta nutrizionale</strong>
            <span>
              Fotografa la tabella nutrizionale:
              compilerò il form, ma sarai tu a confermare i valori.
            </span>
          </div>

          <div className={styles.labelScannerActions}>
            <label className={styles.labelPhotoButton}>
              <span>Fotografa o scegli immagine</span>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                capture="environment"
                onChange={(event) => {
                  const file =
                    event.target.files?.[0] ??
                    null;

                  setLabelPhoto(file);
                  setScanMessage(null);

                  if (!file) {
                    setLabelPhotoPreview(null);
                    return;
                  }

                  if (
                    file.size >
                    8 * 1024 * 1024
                  ) {
                    setLabelPhoto(null);
                    setLabelPhotoPreview(null);
                    setScanMessage(
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
                      setLabelPhotoPreview(
                        reader.result,
                      );
                    }
                  };

                  reader.readAsDataURL(
                    file,
                  );
                }}
              />
            </label>

            <button
              type="button"
              className={styles.scanLabelButton}
              disabled={
                !labelPhoto ||
                scanningLabel
              }
              onClick={() => {
                void scanLabel();
              }}
            >
              {scanningLabel
                ? "Leggo etichetta…"
                : "Analizza"}
            </button>
          </div>

          {labelPhotoPreview ? (
            <img
              className={styles.labelPhotoPreview}
              src={labelPhotoPreview}
              alt="Anteprima etichetta nutrizionale"
            />
          ) : null}

          {scanMessage ? (
            <p className={styles.scanMessage}>
              {scanMessage}
            </p>
          ) : null}
        </div>
      ) : null}

      <form onSubmit={save}>
        <label className={styles.name}>Nome<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label>
        {(["calories", "protein", "carbs", "fat"] as const).map((field) => <label key={field}>{({calories:"Kcal",protein:"Proteine",carbs:"Carboidrati",fat:"Grassi"})[field]} / 100 g<input type="number" min="0" step="0.1" value={form[field]} onChange={(e) => setForm({ ...form, [field]: e.target.value })} /></label>)}
        <button disabled={saving}>{saving ? "Salvataggio…" : editingId ? "Salva modifiche" : "Aggiungi"}</button>
        {editingId ? <button type="button" className={styles.cancel} onClick={() => { setEditingId(null); setForm(EMPTY); }}>Annulla</button> : null}
      </form>
    </section>
    {message ? <p className={styles.message}>{message}</p> : null}
    <section className={styles.library}>
      <div className={styles.libraryHead}><div><p>ARCHIVIO</p><h2>I tuoi alimenti</h2></div><input placeholder="Cerca alimento…" value={query} onChange={(e) => setQuery(e.target.value)} /></div>
      {loading ? <p>Caricamento…</p> : <div className={styles.grid}>{visible.map((item) => <article key={item.id}><h3>{item.name}</h3><strong>{Math.round(item.calories_per_100g)} kcal</strong><dl><div><dt>Proteine</dt><dd>{item.protein_per_100g} g</dd></div><div><dt>Carboidrati</dt><dd>{item.carbs_per_100g} g</dd></div><div><dt>Grassi</dt><dd>{item.fat_per_100g} g</dd></div></dl><footer><button onClick={() => edit(item)}>Modifica</button><button onClick={() => void remove(item)}>Elimina</button></footer></article>)}</div>}
    </section>
  </main></>;
}
