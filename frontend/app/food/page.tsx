"use client";

import Link from "next/link";

import { AppNav } from "@/components/navigation/AppNav";
import styles from "./FoodPage.module.css";

const FOOD_AREAS = [
  {
    href: "/recipes",
    icon: "🍽️",
    eyebrow: "MANGIA",
    title: "Ricette",
    description:
      "Apri le ricette solo quando ti servono. Cerca, modifica e riutilizza i pasti che conosci già.",
    action: "Apri ricette",
  },
  {
    href: "/inventory",
    icon: "🥬",
    eyebrow: "DISPENSA",
    title: "Cosa ho a casa",
    description:
      "Pantry, prodotti disponibili, scadenze e porzioni meal prep in un unico posto.",
    action: "Apri dispensa",
  },
  {
    href: "/ingredients",
    icon: "🥕",
    eyebrow: "ALIMENTI",
    title: "Ingredienti",
    description:
      "Gestisci gli alimenti di base e i valori nutrizionali usati da ricette e registrazioni.",
    action: "Apri ingredienti",
  },
] as const;

export default function FoodPage() {
  return (
    <>
      <AppNav />
      <main className={styles.page}>
        <header className={styles.header}>
          <div>
            <span className={styles.eyebrow}>FOOD</span>
            <h1>Mangia, scegli, organizza.</h1>
            <p>
              Tutto il mondo alimentare di SanoSync vive qui. La Home non
              carica più ricette, dispensa o ingredienti finché non li apri.
            </p>
          </div>

          <Link href="/ai" className={styles.aiShortcut}>
            <span aria-hidden="true">✦</span>
            <div>
              <small>SANOSYNC AI</small>
              <strong>Registra quello che hai mangiato</strong>
              <span>Scrivilo come lo diresti a una persona →</span>
            </div>
          </Link>
        </header>

        <section className={styles.primaryGrid} aria-label="Sezioni Food">
          {FOOD_AREAS.map((area) => (
            <Link key={area.href} href={area.href} className={styles.areaCard}>
              <span className={styles.areaIcon} aria-hidden="true">
                {area.icon}
              </span>
              <div className={styles.areaCopy}>
                <small>{area.eyebrow}</small>
                <h2>{area.title}</h2>
                <p>{area.description}</p>
                <strong>{area.action} →</strong>
              </div>
            </Link>
          ))}
        </section>

        <section className={styles.workflowCard}>
          <div className={styles.workflowIntro}>
            <span className={styles.eyebrow}>ORGANIZZA</span>
            <h2>Dal cibo disponibile al pasto</h2>
            <p>
              La parte più pesante viene caricata solo quando la richiedi.
              Così puoi usare Food senza rallentare la Home.
            </p>
          </div>

          <div className={styles.workflowSteps}>
            <Link href="/inventory" className={styles.workflowStep}>
              <span>1</span>
              <div>
                <strong>Controlla la dispensa</strong>
                <small>Prodotti, quantità, scadenze e meal prep.</small>
              </div>
            </Link>
            <Link href="/recipes" className={styles.workflowStep}>
              <span>2</span>
              <div>
                <strong>Scegli una ricetta</strong>
                <small>Usa ciò che hai oppure cerca un’alternativa.</small>
              </div>
            </Link>
            <Link href="/ai" className={styles.workflowStep}>
              <span>3</span>
              <div>
                <strong>Logga in modo naturale</strong>
                <small>“Ho mangiato…” e SanoSync prepara la registrazione.</small>
              </div>
            </Link>
          </div>
        </section>
      </main>
    </>
  );
}
