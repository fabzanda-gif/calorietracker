"use client";

import { useEffect, useMemo, useState } from "react";

import {
  createSpecialPeriod,
  deleteSpecialPeriod,
  getSpecialPeriods,
  type SpecialPeriod,
  type SpecialPeriodType,
} from "@/lib/api/special-periods";

import styles from "./SpecialPeriodsCard.module.css";

interface Props {
  accessToken: string;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function formatDate(value: string): string {
  const parsed = new Date(`${value}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("it-IT", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(parsed);
}

const COPY: Record<SpecialPeriodType, {
  icon: string;
  title: string;
  description: string;
}> = {
  vacation: {
    icon: "🏖️",
    title: "Vacanza",
    description:
      "Niente routine casa/ufficio, pasti più flessibili e attività quotidiana presumibilmente più alta. Gli allenamenti restano pianificati.",
  },
  illness: {
    icon: "🤒",
    title: "Malattia",
    description:
      "Sospende gli allenamenti nelle date indicate e mette SanoSync in modalità recupero. Gli allenamenti non vengono cancellati e tornano pianificati se rimuovi il periodo.",
  },
};

export function SpecialPeriodsCard({ accessToken }: Props) {
  const [items, setItems] = useState<SpecialPeriod[]>([]);
  const [periodType, setPeriodType] = useState<SpecialPeriodType>("vacation");
  const [startDate, setStartDate] = useState(todayIso());
  const [endDate, setEndDate] = useState(todayIso());
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function load() {
    try {
      setLoading(true);
      const response = await getSpecialPeriods(accessToken);
      setItems(response.items);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Impossibile caricare i periodi speciali.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // accessToken changes only when the authenticated session changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

  const visibleItems = useMemo(
    () => [...items].sort((a, b) => a.start_date.localeCompare(b.start_date)),
    [items],
  );

  async function addPeriod() {
    if (saving) return;
    if (!startDate || !endDate) {
      setError("Inserisci una data di inizio e una data di fine.");
      return;
    }
    if (endDate < startDate) {
      setError("La data di fine non può precedere la data di inizio.");
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const created = await createSpecialPeriod(accessToken, {
        period_type: periodType,
        start_date: startDate,
        end_date: endDate,
        notes: notes.trim() || null,
      });
      setItems((current) => [...current, created]);
      setNotes("");
      setSuccess(
        periodType === "illness"
          ? "Periodo salvato. Gli allenamenti in queste date sono sospesi, non cancellati."
          : "Vacanza salvata. SanoSync userà un contesto più flessibile in queste date.",
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Impossibile salvare il periodo speciale.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function removePeriod(item: SpecialPeriod) {
    setError(null);
    setSuccess(null);
    try {
      await deleteSpecialPeriod(accessToken, item.id);
      setItems((current) => current.filter((entry) => entry.id !== item.id));
      setSuccess(
        item.period_type === "illness"
          ? "Periodo rimosso. Gli allenamenti sospesi tornano pianificati."
          : "Periodo rimosso.",
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Impossibile rimuovere il periodo speciale.",
      );
    }
  }

  const selected = COPY[periodType];

  return (
    <section className={styles.card} aria-labelledby="special-periods-title">
      <div className={styles.header}>
        <div>
          <span className={styles.eyebrow}>CALENDARIO</span>
          <h2 id="special-periods-title">Periodi speciali</h2>
          <p>
            Comunica a SanoSync quando la tua routine cambia per più giorni.
          </p>
        </div>
      </div>

      <div className={styles.typePicker}>
        {(["vacation", "illness"] as SpecialPeriodType[]).map((type) => (
          <button
            key={type}
            type="button"
            className={periodType === type ? styles.typeActive : styles.typeButton}
            onClick={() => setPeriodType(type)}
          >
            <span aria-hidden="true">{COPY[type].icon}</span>
            {COPY[type].title}
          </button>
        ))}
      </div>

      <div className={styles.contextBox}>
        <strong>{selected.icon} {selected.title}</strong>
        <span>{selected.description}</span>
      </div>

      <div className={styles.formGrid}>
        <label>
          <span>Dal</span>
          <input
            type="date"
            value={startDate}
            onChange={(event) => {
              const value = event.target.value;
              setStartDate(value);
              if (endDate < value) setEndDate(value);
            }}
          />
        </label>

        <label>
          <span>Al</span>
          <input
            type="date"
            min={startDate}
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
          />
        </label>

        <label className={styles.notesLabel}>
          <span>Nota opzionale</span>
          <input
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder={periodType === "vacation" ? "Es. weekend a Lisbona" : "Es. influenza"}
          />
        </label>
      </div>

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.addButton}
          disabled={saving}
          onClick={() => void addPeriod()}
        >
          {saving ? "Salvataggio…" : "Aggiungi al calendario"}
        </button>
      </div>

      {error && <div className={styles.error}>{error}</div>}
      {success && <div className={styles.success}>{success}</div>}

      <div className={styles.listSection}>
        <div className={styles.listTitle}>Periodi inseriti</div>
        {loading ? (
          <p className={styles.empty}>Caricamento…</p>
        ) : visibleItems.length === 0 ? (
          <p className={styles.empty}>Nessun periodo speciale inserito.</p>
        ) : (
          <div className={styles.list}>
            {visibleItems.map((item) => {
              const copy = COPY[item.period_type];
              return (
                <div key={item.id} className={styles.item}>
                  <div className={styles.itemIcon} aria-hidden="true">{copy.icon}</div>
                  <div className={styles.itemCopy}>
                    <strong>{copy.title}</strong>
                    <span>{formatDate(item.start_date)} → {formatDate(item.end_date)}</span>
                    <small>
                      {item.period_type === "illness"
                        ? "Allenamenti sospesi · attività ridotta · recupero"
                        : "Routine libera · pasti flessibili · allenamenti mantenuti"}
                    </small>
                    {item.notes && <small>{item.notes}</small>}
                  </div>
                  <button
                    type="button"
                    className={styles.removeButton}
                    onClick={() => void removePeriod(item)}
                  >
                    Rimuovi
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
