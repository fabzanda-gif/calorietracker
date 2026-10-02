"use client";

import Link from "next/link";

import { RunningPlanBuilder } from "@/components/activity/RunningPlanBuilder";
import { AppNav } from "@/components/navigation/AppNav";

import styles from "../TrainingPage.module.css";

export default function RunningPlanPage() {
  return (
    <>
      <AppNav />
      <main className={styles.page}>
        <Link className={styles.back} href="/activities">← Torna alle attività</Link>
        <header className={styles.intro}>
          <p>IL TUO PERCORSO</p>
          <h1>Piano di corsa</h1>
          <span>Ogni sessione è un passo verso il tuo obiettivo.</span>
        </header>
        <RunningPlanBuilder />
      </main>
    </>
  );
}
