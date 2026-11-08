"use client";
import { useAuth } from "@/components/auth/AuthProvider";
import { getStrengthLoadProfiles, saveStrengthLoadProfile, type StrengthLoadProfile } from "@/lib/api/strengthLoads";
import { useEffect, useState } from "react";
import { getStrengthPlans, getStrengthPlanHistory } from "@/lib/api/strength";
import { referencesFromHistory, type LoadReference } from "@/lib/strengthRecommendations";

export function useStrengthReferences(accessToken: string | null, planId?: string | null) {
  const { user } = useAuth();
  const userId = user?.id;
  const [state, setState] = useState<{ loading: boolean; error: string | null; references: LoadReference[]; profiles: StrengthLoadProfile[] }>({ loading: true, error: null, references: [], profiles: [] });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!accessToken || !userId) return;
    let active = true;
    setState({ loading: true, error: null, references: [], profiles: [] });
    async function load() {
      try {
        const [plans, profiles] = await Promise.all([getStrengthPlans(accessToken), getStrengthLoadProfiles(userId!)]);
        const ids = [...new Set([...(planId ? [planId] : []), ...plans.items.map((plan) => plan.id)])];
        const histories = [];
        // Bound concurrent requests when an account has many past programs.
        for (let i = 0; i < ids.length; i += 3) histories.push(...await Promise.all(ids.slice(i, i + 3).map((id) => getStrengthPlanHistory(id, accessToken))));
        if (active) setState({ loading: false, error: null, profiles, references: referencesFromHistory(histories.flatMap((history) => history.items)) });
      } catch {
        if (active) setState({ loading: false, error: "Non riesco a recuperare i carichi precedenti. Riprova prima di impostare nuovi pesi.", references: [], profiles: [] });
      }
    }
    void load();
    return () => { active = false; };
  }, [accessToken, userId, planId, retry]);
  async function save(profile: Omit<StrengthLoadProfile, "user_id" | "updated_at">) {
    if (!userId) throw new Error("Accedi per salvare il carico.");
    const item = { ...profile, user_id: userId, updated_at: new Date().toISOString() };
    await saveStrengthLoadProfile(item);
    setState((current) => ({ ...current, profiles: [...current.profiles.filter((value) => value.exercise_ref !== item.exercise_ref), item] }));
  }
  return { ...state, save, retry: () => setRetry((value) => value + 1) };
}
