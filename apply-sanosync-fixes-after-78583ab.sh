#!/usr/bin/env bash
set -euo pipefail

repo_dir="/workspaces/calorietracker"
cd "$repo_dir"

git am --abort 2>/dev/null || true
git switch codex/landing-redesign
git fetch origin main

git show "origin/main:0001-Fix-onboarding-home-meals-and-ingredients-after-78583ab.patch" > /tmp/sanosync-original.patch

# Apply every non-conflicting part of the patch. The three excluded files are
# adapted below to the exact mobile-navigation/onboarding variant at 78583ab.
git apply --index \
  --exclude=frontend/components/home/HomeShell.tsx \
  --exclude=frontend/components/navigation/AppNav.tsx \
  --exclude=frontend/components/onboarding/WelcomeJourney.tsx \
  /tmp/sanosync-original.patch

python - <<'PY'
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Blocco atteso non trovato in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


home = Path("frontend/components/home/HomeShell.tsx")

replace_once(home, '''  getMeal,
  getMealsForDate,''', '''  getMeal,
  getMealHistory,
  getMealsForDate,''')

replace_once(home, '''} from "@/lib/api/meals";
import {
  getDay,''', '''} from "@/lib/api/meals";
import {
  getAvailableRecipes,
  type Recipe,
} from "@/lib/api/recipes";
import {
  getDay,''')

replace_once(home, '''  const {
    user,
    accessToken,
  } = useAuth();

  const [day, setDay] =''', '''  const {
    user,
    accessToken,
  } = useAuth();
  const [onboardingTestCompleted] = useState(
    () =>
      typeof window !== "undefined" &&
      window.sessionStorage.getItem(
        "sanosync-onboarding-test-token",
      ) === accessToken,
  );

  const [day, setDay] =''')

replace_once(home, '''  const [alternateFat, setAlternateFat] =
    useState("");
  const [savingAlternate, setSavingAlternate] =''', '''  const [alternateFat, setAlternateFat] =
    useState("");
  const [knownAlternates, setKnownAlternates] = useState<Array<{
    key: string;
    name: string;
    mealType: string;
    calories: number;
    protein: number;
    carbs: number;
    fat: number;
  }>>([]);
  const [savingAlternate, setSavingAlternate] =''')

anchor = '''  useEffect(() => {
    if (
      conversationPreview ||'''
known_effect = '''  useEffect(() => {
    if (!accessToken) return;
    let active = true;

    Promise.allSettled([
      getAvailableRecipes(accessToken),
      getMealHistory(accessToken),
    ]).then(([recipesResult, historyResult]) => {
      if (!active) return;
      const recipes = recipesResult.status === "fulfilled" ? recipesResult.value.items : [];
      const history = historyResult.status === "fulfilled" ? historyResult.value.items : [];
      const seen = new Set<string>();
      const items = [
        ...recipes.map((recipe: Recipe) => {
          const servings = Math.max(1, Number(recipe.recipe_servings) || 1);
          return {
            key: `recipe:${recipe.id}`,
            name: recipe.name,
            mealType: recipe.meal_type || "Pranzo",
            calories: Number(recipe.calories || 0) / servings,
            protein: Number(recipe.protein || 0) / servings,
            carbs: Number(recipe.carbs || 0) / servings,
            fat: Number(recipe.fat || 0) / servings,
          };
        }),
        ...history.map((meal) => {
          const quantity = Math.max(0.01, Number(meal.quantity) || 1);
          const factor = meal.is_per_100g ? 100 / quantity : 1 / quantity;
          return {
            key: `history:${meal.id ?? `${meal.date}:${meal.name}`}`,
            name: meal.base_name || meal.name,
            mealType: meal.meal_type || "Pranzo",
            calories: Number(meal.base_calories ?? Number(meal.calories || 0) * factor),
            protein: Number(meal.base_protein ?? Number(meal.protein || 0) * factor),
            carbs: Number(meal.base_carbs ?? Number(meal.carbs || 0) * factor),
            fat: Number(meal.base_fat ?? Number(meal.fat || 0) * factor),
          };
        }),
      ].filter((item) => {
        const key = item.name.trim().toLocaleLowerCase("it");
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return true;
      });
      setKnownAlternates(items);
    });

    return () => { active = false; };
  }, [accessToken]);

'''
replace_once(home, anchor, known_effect + anchor)

replace_once(home, '''          setShowWelcomeJourney(
            !metadata.gender ||
              !metadata.birth_date ||
              !metadata.height ||
              !metadata.goal_mode ||
              latestWeightPayload.item?.weight == null,
          );''', '''          setShowWelcomeJourney(
            metadata.onboarding_completed !== true &&
              (!metadata.gender ||
                !metadata.birth_date ||
                !metadata.height ||
                latestWeightPayload.item?.weight == null),
          );''')

replace_once(home, '''  const bmr = Number(budgetResult?.profile?.bmr ?? 0);
  const needsWelcomeJourney =
    showWelcomeJourney ||
    budgetResult?.status === "profile_incomplete";''', '''  const bmr = Number(budgetResult?.profile?.bmr ?? 0);
  const onboardingTestEmails = [
    process.env.NEXT_PUBLIC_ONBOARDING_TEST_EMAIL,
    process.env.NEXT_PUBLIC_ONBOARDING_TEST_EMAILS,
  ]
    .filter(Boolean)
    .flatMap((value) => String(value).split(","))
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);
  const onboardingTestIds = String(
    process.env.NEXT_PUBLIC_ONBOARDING_TEST_USER_IDS ??
      process.env.NEXT_PUBLIC_ONBOARDING_TEST_USER_ID ??
      "",
  ).split(",").map((value) => value.trim()).filter(Boolean);
  const isOnboardingTestAccount = Boolean(
    (user?.email && onboardingTestEmails.includes(user.email.trim().toLowerCase())) ||
      (user?.id && onboardingTestIds.includes(user.id)),
  );
  const needsWelcomeJourney =
    (((showWelcomeJourney || budgetResult?.status === "profile_incomplete") &&
      profile?.metadata.onboarding_completed !== true) ||
      (isOnboardingTestAccount && !onboardingTestCompleted));''')

replace_once(home, '''    setDayPlannerSaving(true);
    setDayPlannerMessage(null);

    try {''', '''    setDayPlannerSaving(true);
    setDayPlannerMessage(null);

    const previousDay = day;
    setDay((current) => current ? {
      ...current,
      context: changes.day_type
        ? { ...current.context, value: changes.day_type, state: "confirmed", source: "user" }
        : current.context,
      activity_plan: changes.activity_plan
        ? { ...current.activity_plan, value: changes.activity_plan, state: "confirmed", source: "user" }
        : current.activity_plan,
    } : current);

    try {''')

replace_once(home, '''      setDayPlannerMessage("Giornata aggiornata.");

      await refreshHome();
    } catch (err) {
      setDayPlannerMessage(''', '''      setDayPlannerMessage("Giornata aggiornata.");

      void refreshHome().catch(() => undefined);
    } catch (err) {
      setDay(previousDay);
      setDayPlannerMessage(''')

replace_once(home, '''                            <label>
                              Cosa hai mangiato?
                              <input''', '''                            <label>
                              Cosa hai mangiato?
                              <select
                                value=""
                                onChange={(event) => {
                                  const selected = knownAlternates.find((item) => item.key === event.target.value);
                                  if (!selected) return;
                                  setAlternateName(selected.name);
                                  setAlternateCalories(String(Math.round(selected.calories)));
                                  setAlternateProtein(String(Math.round(selected.protein)));
                                  setAlternateCarbs(String(Math.round(selected.carbs)));
                                  setAlternateFat(String(Math.round(selected.fat)));
                                }}
                              >
                                <option value="">Scegli da ricette e pasti recenti…</option>
                                {knownAlternates.filter((item) => {
                                  const isSnack = ["spuntino", "snack"].includes(item.mealType.toLowerCase());
                                  return slot === "snack" ? isSnack : !isSnack;
                                }).map((item) => (
                                  <option key={item.key} value={item.key}>{item.name}</option>
                                ))}
                              </select>
                              <span className={styles.manualMealLabel}>oppure scrivi manualmente</span>
                              <input''')

replace_once(home, '''          initialName={
            typeof profile?.metadata?.name === "string"
              ? profile.metadata.name
              : firstName
          }
        />''', '''          initialName={
            typeof profile?.metadata?.name === "string"
              ? profile.metadata.name
              : firstName
          }
          testMode={isOnboardingTestAccount}
        />''')


nav = Path("frontend/components/navigation/AppNav.tsx")
replace_once(nav, '''  {
    href: "/recipes",
    label: "Ricette",
    icon: "⌑",
  },
];''', '''  {
    href: "/recipes",
    label: "Ricette",
    icon: "⌑",
  },
  { href: "/inventory", label: "Dispensa", icon: "·", subLink: true },
  { href: "/ingredients", label: "Ingredienti", icon: "·", subLink: true },
];''')
replace_once(nav, '''const MOBILE_ITEMS = [
  ...ITEMS,''', '''const MOBILE_ITEMS = [
  ...ITEMS.slice(0, 4),''')
replace_once(nav, '''  if (href === "#") {
    return false;
  }

  return pathname''', '''  if (href === "#") {
    return false;
  }

  if (href === "/recipes" && (pathname.startsWith("/inventory") || pathname.startsWith("/ingredients"))) {
    return true;
  }

  return pathname''')
replace_once(nav, '''            const separatorBefore = index === 5;''', '''            const separatorBefore = index === 4;''')
replace_once(nav, '''                      item.href === "/inventory"''', '''                      "subLink" in item && item.subLink''')


welcome = Path("frontend/components/onboarding/WelcomeJourney.tsx")
replace_once(welcome, '''  initialName?: string;
};''', '''  initialName?: string;
  testMode?: boolean;
};''')
replace_once(welcome, '''  accessToken,
  initialName = "",
}: WelcomeJourneyProps) {''', '''  accessToken,
  initialName = "",
  testMode = false,
}: WelcomeJourneyProps) {''')
replace_once(welcome, '''      await updateProfile(accessToken, {
        name:''', '''      await updateProfile(accessToken, {
        onboarding_completed: true,
        name:''')
replace_once(welcome, '''      window.location.reload();''', '''      if (testMode) {
        window.sessionStorage.setItem(
          "sanosync-onboarding-test-token",
          accessToken,
        );
      }
      window.location.reload();''')
PY

git add \
  frontend/components/home/HomeShell.tsx \
  frontend/components/navigation/AppNav.tsx \
  frontend/components/onboarding/WelcomeJourney.tsx

git diff --cached --check
git commit -m "Stabilize onboarding and simplify meal planning"

echo
echo "Applicazione completata. Nuovo commit:"
git log -1 --oneline
