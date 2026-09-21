"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { getTrainingPlans } from "@/lib/api/activities";
import { getStrengthPlans } from "@/lib/api/strength";

import styles from "./TrainingProgramLinks.module.css";

export function TrainingProgramLinks() {
  const { accessToken } = useAuth();
  const [runningActive, setRunningActive] = useState<boolean | null>(null);
  const [strengthActive, setStrengthActive] = useState<boolean | null>(null);

  useEffect(() => {
    let current = true;
    if (!accessToken) {
      setRunningActive(null);
      setStrengthActive(null);
      return;
    }

    setRunningActive(null);
    setStrengthActive(null);
    void getTrainingPlans(accessToken)
      .then(({ items }) => {
        if (current) {
          setRunningActive(items.some(
            (plan) => plan.sport === "running" && plan.status === "active",
          ));
        }
      })
      .catch(() => undefined);

    void getStrengthPlans(accessToken)
      .then(({ items }) => {
        if (current) {
          setStrengthActive(items.some(
            (plan) => plan.status === "active",
          ));
        }
      })
      .catch(() => undefined);

    return () => {
      current = false;
    };
  }, [accessToken]);

  return (
    <section className={styles.section} aria-labelledby="training-title">
      <div className={styles.heading}>
        <p>PROGRAMMI</p>
        <h2 id="training-title">Il tuo allenamento</h2>
        <span>Un posto per seguire ogni percorso, una seduta alla volta.</span>
      </div>
      <div className={styles.links}>
        <Link href="/training/running" className={styles.card}>
          <span className={styles.kind}>CORSA</span>
          <strong>{runningActive === true ? "Il tuo piano di corsa" : "Piano di corsa"}</strong>
          <span>{runningActive === true
            ? "Vedi progressi, prossima corsa e settimane del piano."
            : "Crea un percorso verso il tuo obiettivo."}</span>
          <b>{runningActive === false ? "Crea un piano" : "Apri il piano"} →</b>
        </Link>
        <Link href="/training/strength" className={styles.card}>
          <span className={styles.kind}>FORZA</span>
          <strong>{strengthActive === true ? "Il tuo programma forza" : "Programma forza"}</strong>
          <span>{strengthActive === true
            ? "Segui le sedute e la progressione dei carichi."
            : "Costruisci un programma da affiancare alla corsa."}</span>
          <b>{strengthActive === false ? "Crea un programma" : "Apri il programma"} →</b>
        </Link>
      </div>
    </section>
  );
}
