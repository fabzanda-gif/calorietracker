"use client";

import Link from "next/link";

import { StrengthPlanPanel } from "@/components/activity/StrengthPlanPanel";
import { AppNav } from "@/components/navigation/AppNav";

import styles from "../TrainingPage.module.css";

export default function StrengthPlanPage() {
  return (
    <>
      <AppNav />
      <main className={styles.page}>
        <Link className={styles.back} href="/activities">← Torna alle attività</Link>
        <header className={styles.intro}>
          <p>IL TUO PERCORSO</p>
          <h1>Programma forza</h1>
          <span>Le sedute completate raccontano la tua progressione.</span>
        </header>
        <StrengthPlanPanel />
      </main>
    </>
  );
}
