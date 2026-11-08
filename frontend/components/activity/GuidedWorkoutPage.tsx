"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppNav } from "@/components/navigation/AppNav";
import { useAuth } from "@/components/auth/AuthProvider";
import { getStrengthPlanDetail, type StrengthPlanDetailResponse, type StrengthWorkout } from "@/lib/api/strength";
import { StrengthWorkoutHistory } from "./StrengthWorkoutHistory";
import { StrengthWorkoutLoggerV2 } from "./StrengthWorkoutLoggerV2";
import styles from "./GuidedWorkoutPage.module.css";

export function GuidedWorkoutPage({ session }: { session: string[] }) {
  const { accessToken } = useAuth();
  const [workout, setWorkout] = useState<StrengthWorkout | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(session[0] !== "free");
  const isHistory = session[0] === "history";
  const [detail, setDetail] = useState<StrengthPlanDetailResponse | null>(null);
  const planId = isHistory ? session[1] : session[0];
  const workoutId = session[1];
  useEffect(() => {
    if (!accessToken || planId === "free") return;
    let active = true;
    getStrengthPlanDetail(planId, accessToken).then((detail) => {
      if (!active) return;
      if (isHistory) { setDetail(detail); return; }
      const selected = detail.workouts.find((item) => item.id === workoutId);
      if (!selected || selected.status !== "planned") throw new Error("Questa seduta non è disponibile. Torna al programma per scegliere il prossimo allenamento.");
      setWorkout(selected);
    }).catch((err: unknown) => { if (active) setError(err instanceof Error ? err.message : "Non riesco a caricare la seduta."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [accessToken, planId, workoutId, isHistory]);
  return <><AppNav /><main className={styles.main}>
    <Link href="/activities/programs">← Torna ai programmi</Link>
    <h1>{isHistory ? "I tuoi allenamenti completati" : "Il tuo allenamento"}</h1>
    {!isHistory ? <p>Segui l’ordine consigliato, registra le serie e passa al prossimo esercizio.</p> : null}
    {loading ? <p>Carico la seduta…</p> : error ? <p role="alert">{error}</p> : detail && isHistory ? <StrengthWorkoutHistory detail={detail} /> : <StrengthWorkoutLoggerV2 workout={workout} />}
  </main></>;
}
