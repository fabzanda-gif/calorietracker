import { expect, test, type Page } from "@playwright/test";
import type { HomeSummaryResponse } from "../lib/api/day";

// Real AuthProvider, Supabase SDK, AuthGate and UI; mocked network boundaries.
// These tests always run in CI without production accounts or secrets.
const user = {
  id: "00000000-0000-0000-0000-000000000001", aud: "authenticated",
  role: "authenticated", email: "test@sanosync.example",
  app_metadata: { provider: "email" }, user_metadata: { name: "Test" },
  created_at: "2026-01-01T00:00:00Z",
};
const accessToken = [
  { alg: "HS256", typ: "JWT" },
  { sub: user.id, exp: 4102444800, role: "authenticated", aud: "authenticated" },
].map((value) => Buffer.from(JSON.stringify(value)).toString("base64url")).join(".") + ".test-signature";

function summary(withMeal: boolean): HomeSummaryResponse {
  return {
    date: "2026-11-08", context: null,
    engagement: { state: "active", days_since_last_meal: 0 }, special_period: null,
    hero: { kind: "normal", title: "La tua giornata", message: "Tutto aggiornato", icon: "✓" },
    budget: { daily_budget_kcal: 2000, consumed_kcal: withMeal ? 300 : 0,
      available_kcal: withMeal ? 1700 : 2000, maintenance_kcal: 2200,
      protein_consumed_g: 20, protein_target_g: 100, protein_remaining_g: 80 },
    profile_goal: { goal_mode: "loss", goal_adjustment_kcal: 200, bmr: 1600,
      protein_target_g: 100, profile_complete_for_budget: true },
    latest_weight: null,
    meals: withMeal ? [{ id: "meal-1", meal_type: "Colazione", name: "Yogurt di prova", calories: 300 }] : [],
    activities: [], planned_today: [], planned_tomorrow: [],
    meta: { history_days_used: 0, ai_calls: 0, average_activity_kcal_7d: 0 },
  };
}

async function mockServices(page: Page, options: { failActivityOnce?: boolean; previewError?: boolean; loggedMealType?: string } = {}) {
  let aiMealLogged = false;
  let failActivity = options.failActivityOnce ?? false;
  const activity = { id: "activity-1", date: new Date().toISOString().slice(0, 10),
    activity_name: "Corsa del parco", activity_type: "Corsa", burned_calories: 300,
    duration_seconds: 1800, distance_meters: 5000, route_points: [], series_points: [] };
  let withMeal = true;
  const routine: Record<string, string> = { monday: "home" };
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/rest/v1/strength_load_profiles**", (route) => route.fulfill({ json: [] }));
  await page.route("**/auth/v1/**", async (route) => {
    if (route.request().url().includes("/logout")) {
      await route.fulfill({ status: 204 });
      return;
    }
    await route.fulfill({ json: route.request().url().includes("/token") ? {
      access_token: accessToken, refresh_token: "test-refresh-token",
      token_type: "bearer", expires_in: 3600, user,
    } : user });
  });
  await page.route("http://localhost:8000/**", async (route) => {
    expect(route.request().headers().authorization).toBe(`Bearer ${accessToken}`);
    const path = new URL(route.request().url()).pathname;
    let json: unknown;
    if (path === "/profile") json = { id: user.id, metadata: user.user_metadata };
    else if (path === "/onboarding/status") json = { completed: true, preferred_days: [], priority_muscles: [] };
    else if (path.startsWith("/home-summary/")) {
      const home = summary(withMeal);
      if (options.loggedMealType) home.meals = home.meals.map((meal) => ({ ...meal, meal_type: options.loggedMealType! }));
      if (aiMealLogged) home.meals.push({ id: "ai-meal", meal_type: "Pranzo", name: "Pasta al pomodoro", calories: 500 });
      json = home;
    }
    else if (path === "/meals/conversational/day-preview") {
      if (options.previewError) { await route.fulfill({ status: 503, json: { detail: "AI unavailable" } }); return; }
      json = { status: "preview", needs_review: false, requires_confirmation: true, actions: [
        { id: "meal-ai", kind: "meal", date: "2026-11-08", meal_type: "Pranzo", items: [{ name: "Pasta al pomodoro", calories: 500, protein: 15, carbs: 80, fat: 10 }], totals: { calories: 500 }, requires_confirmation: true },
        { id: "activity-ai", kind: "activity", date: "2026-11-08", activity_name: "Corsa AI", activity_type: "Corsa", burned_calories: 250, duration_seconds: 1800, distance_meters: 5000, requires_confirmation: true },
        { id: "weight-ai", kind: "weight", date: "2026-11-08", weight_kg: 77, requires_confirmation: true },
      ] };
    }
    else if (path === "/meals/conversational/confirm") { aiMealLogged = true; json = { created: true, item: {} }; }
    else if (path === "/activities" && route.request().method() === "POST") {
      if (failActivity) { failActivity = false; await route.fulfill({ status: 503, json: { detail: "Try again" } }); return; }
      json = { created: true, item: {} };
    }
    else if (path === "/weight" && route.request().method() === "POST") json = { created: true, item: {} };
    else if (path === "/meals/meal-1" && route.request().method() === "DELETE") {
      withMeal = false;
      json = { deleted: true };
    } else if (path === "/weekly-schedule") {
      if (route.request().method() === "PUT") {
        const labels = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
        for (const day of route.request().postDataJSON().days) routine[labels[day.day_of_week - 1]] = day.context;
      }
      json = { days: routine, items: [], week_start: "2026-11-02" };
    }
    else if (path === "/progress/nutrition") json = { items: [], summary: {
      logged_days: 0, average_consumed_kcal: 0, days_within_budget: 0, days_with_budget: 0,
    } };
    else if (path === "/activities/overview") json = { items: [activity], energy_days: [], summary: {} };
    else if (path === "/activities/range") json = { items: [activity], count: 1 };
    else if (path === "/activities/comment") json = { comment: "Attività registrata.", source: "fallback" };
    else if (path === "/activities/training-plans" || path === "/strength/plans") json = { items: [], count: 0 };
    else if (path.startsWith("/activities/movement/")) json = { total_steps: 0, net_daily_steps: 0, estimated_training_steps: 0, applied_step_offset: 0, step_calories: 0 };
    else if (path === "/coach/reconcile") json = { policy: "balanced", load_events: [], adjustments: [], history: [], summary: { events: 0, proposed: 0, auto_applied: 0 } };
    else if (path === "/coach/preferences") json = { priority: "balanced" };
    else if (path === "/weight/latest") json = { item: null };
    else if (path.endsWith("/status") && path.startsWith("/integrations/")) json = { connected: false, configured: false };
    else if (path === "/auth-events/login") json = { notified: true };
    else if (path === "/notifications/vapid-public-key") json = { public_key: "test" };
    else if (["/activities/planned", "/special-periods", "/weight"].includes(path)) json = { items: [], count: 0 };
    else throw new Error(`Missing API fixture: ${route.request().method()} ${path}`);
    await route.fulfill({ json });
  });
  return errors;
}

async function signIn(page: Page) {
  await page.goto("/");
  await page.getByLabel("Email").fill(user.email);
  await page.getByLabel("Password").fill("test-password");
  await page.getByRole("button", { name: "Accedi", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Test");
  await expect(page.getByText("Yogurt di prova", { exact: true })).toBeVisible();
}

test("login and public legal pages remain accessible", async ({ page }) => {
  await mockServices(page);
  await page.goto("/");
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByRole("button", { name: "Accedi", exact: true })).toBeVisible();
  for (const path of ["/privacy", "/terms"]) {
    await page.goto(path);
    await expect(page.getByLabel("Password")).toHaveCount(0);
    await expect(page.locator("main")).toBeVisible();
  }
});

test("signed-in users can navigate the current primary areas", async ({ page }) => {
  const errors = await mockServices(page);
  await signIn(page);
  for (const path of ["/activities", "/food", "/insights", "/"]) {
    await page.locator(`a[href="${path}"]`).first().click();
    await expect(page).toHaveURL(new RegExp(path === "/" ? "/$" : `${path}$`));
    await expect(page.locator("main h1")).toBeVisible();
  }
  expect(errors).toEqual([]);
});

test("meal deletion updates the current home and survives reload", async ({ page }) => {
  const errors = await mockServices(page);
  await signIn(page);
  page.on("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Elimina", exact: true }).click();
  await expect(page.getByText("Yogurt di prova", { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Test");
  await expect(page.getByRole("heading", { name: "Giornata sotto controllo", exact: true })).toBeVisible();
  await expect(page.getByText("Yogurt di prova", { exact: true })).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("logout removes access to authenticated pages", async ({ page }) => {
  await mockServices(page);
  await signIn(page);
  await page.getByRole("button", { name: /Esci/i }).click();
  await expect(page.getByLabel("Password")).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Password")).toBeVisible();
});


for (const viewport of [{ name: "desktop", width: 1280, height: 900 }, { name: "mobile", width: 390, height: 844 }]) {
  test(`activity recap and nested programs on ${viewport.name}`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport);
    const errors = await mockServices(page);
    const futureCalls: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/activities/planned")) futureCalls.push(request.url());
    });
    await signIn(page);
    await page.locator('a[href="/activities"]:visible').first().click();
    await expect(page.getByRole("heading", { name: "Attività", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Ultimi 30 giorni", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Attività registrate", exact: true })).toBeVisible();
    await expect(page.getByText("Corsa del parco", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("tab", { name: "Palestra", exact: true })).toHaveCount(0);
    await expect(page.locator('a[href="/plan"]')).toHaveCount(0);
    expect(futureCalls).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`activity-recap-${viewport.name}.png`), fullPage: false });
    await page.getByRole("link", { name: "Programmi di allenamento →", exact: true }).click();
    await expect(page).toHaveURL(/\/activities\/programs$/);
    await expect(page.getByRole("heading", { name: "Programmi", exact: true })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Corsa", exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("heading", { name: "Attività registrate", exact: true })).toHaveCount(0);
    await page.getByRole("tab", { name: "Palestra", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Il tuo programma in palestra", exact: true })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Palestra", exact: true })).toHaveAttribute("aria-selected", "true");
    await page.getByRole("tab", { name: "Palestra", exact: true }).press("ArrowLeft");
    await expect(page.getByRole("tab", { name: "Corsa", exact: true })).toHaveAttribute("aria-selected", "true");
    await page.getByRole("tab", { name: "Corsa", exact: true }).press("ArrowRight");
    await expect(page.getByRole("tab", { name: "Palestra", exact: true })).toHaveAttribute("aria-selected", "true");
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: testInfo.outputPath(`activity-programs-${viewport.name}.png`), fullPage: false });
    await page.getByRole("link", { name: "← Attività", exact: true }).click();
    await expect(page).toHaveURL(/\/activities$/);
    expect(errors).toEqual([]);
  });
}

test("old Plan links redirect to Activities", async ({ page }) => {
  await mockServices(page);
  await signIn(page);
  await page.goto("/plan");
  await expect(page).toHaveURL(/\/activities$/);
  await expect(page.getByRole("heading", { name: "Attività", exact: true })).toBeVisible();
});

test("weekly exceptions and special periods stay in the profile", async ({ page }) => {
  const errors = await mockServices(page);
  await signIn(page);
  await page.goto("/profile#planning-settings");
  const weekly = page.locator("#planning-settings");
  await weekly.locator("summary").click();
  await weekly.getByLabel("Lunedì", { exact: true }).selectOption("office");
  await weekly.getByRole("button", { name: "Salva questa settimana", exact: true }).click();
  await expect(weekly.getByRole("status")).toContainText("Routine della settimana aggiornata");
  await expect(page.locator("#periodi-speciali")).toBeVisible();
  await page.reload();
  await weekly.locator("summary").click();
  await expect(weekly.getByLabel("Lunedì", { exact: true })).toHaveValue("office");
  expect(errors).toEqual([]);
});


for (const viewport of [{ name: "desktop", width: 1280, height: 900 }, { name: "mobile", width: 390, height: 844 }]) {
  test(`AI tile previews and saves from Home on ${viewport.name}`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport);
    const errors = await mockServices(page);
    const writes: string[] = [];
    page.on("request", (r) => { if (r.method() === "POST") writes.push(new URL(r.url()).pathname); });
    await signIn(page);
    await expect(page.locator('a[href="/ai"]')).toHaveCount(0);
    const tile = page.getByRole("region", { name: "SanoSync AI", exact: true });
    await tile.getByLabel("Pasti, attività o peso", { exact: true }).fill("Pasta a pranzo, corsa di 5 km e peso 77 kg");
    await tile.getByRole("button", { name: "Analizza con SanoSync AI", exact: true }).click();
    await expect(tile.getByRole("heading", { name: "Controlla prima di registrare", exact: true })).toBeVisible();
    expect(writes.filter((p) => ["/meals/conversational/confirm", "/activities", "/weight"].includes(p))).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`home-ai-${viewport.name}.png`), fullPage: true });
    await tile.getByRole("button", { name: "Conferma e registra", exact: true }).click();
    await expect(tile.getByRole("status")).toHaveText("3 registrazioni completate.");
    await expect(page.getByText("Pasta al pomodoro", { exact: true })).toBeVisible();
    await expect(page).toHaveURL(/\/$/);
    expect(errors).toEqual([]);
  });
}

test("AI retry keeps only unsaved actions", async ({ page }) => {
  await mockServices(page, { failActivityOnce: true });
  const mealWrites: string[] = [];
  page.on("request", (r) => { if (r.url().endsWith("/meals/conversational/confirm")) mealWrites.push(r.url()); });
  await signIn(page);
  const tile = page.getByRole("region", { name: "SanoSync AI", exact: true });
  await tile.getByLabel("Pasti, attività o peso", { exact: true }).fill("Pasta, corsa e peso");
  await tile.getByRole("button", { name: "Analizza con SanoSync AI", exact: true }).click();
  await tile.getByRole("button", { name: "Conferma e registra", exact: true }).click();
  await expect(tile.getByRole("status")).toContainText("Ho registrato 1 elemento");
  await tile.getByRole("button", { name: "Conferma e registra", exact: true }).click();
  await expect(tile.getByRole("status")).toHaveText("2 registrazioni completate.");
  expect(mealWrites).toHaveLength(1);
});

test("AI errors leave the message editable and old AI links open the home tile", async ({ page }) => {
  await mockServices(page, { previewError: true });
  await signIn(page);
  await page.goto("/ai");
  await expect(page).toHaveURL(/\/#home-ai$/);
  const tile = page.getByRole("region", { name: "SanoSync AI", exact: true });
  await tile.getByLabel("Pasti, attività o peso", { exact: true }).fill("Messaggio da conservare");
  await tile.getByRole("button", { name: "Analizza con SanoSync AI", exact: true }).click();
  await expect(tile.getByRole("status")).toBeVisible();
  await expect(tile.getByLabel("Pasti, attività o peso", { exact: true })).toHaveValue("Messaggio da conservare");
  await expect(tile.getByRole("button", { name: "Analizza con SanoSync AI", exact: true })).toBeEnabled();
});


for (const scenario of [
  { name: "morning without breakfast", hour: 8, logged: "Pranzo", expected: "Colazione" },
  { name: "morning after breakfast", hour: 9, logged: "Colazione", expected: "Snack" },
  { name: "lunchtime", hour: 12, logged: "Colazione", expected: "Pranzo" },
  { name: "afternoon", hour: 16, logged: "Pranzo", expected: "Snack" },
  { name: "evening", hour: 20, logged: "Colazione", expected: "Cena" },
  { name: "after dinner", hour: 21, logged: "Cena", expected: "Snack" },
]) {
  test(`AI infers the unspecified meal: ${scenario.name}`, async ({ page }) => {
    await page.clock.setFixedTime(new Date(2026, 10, 8, scenario.hour));
    await mockServices(page, { loggedMealType: scenario.logged });
    await signIn(page);
    const tile = page.getByRole("region", { name: "SanoSync AI", exact: true });
    await expect(tile.getByRole("combobox")).toHaveCount(0);
    await expect(tile.getByText("Pasto predefinito", { exact: true })).toHaveCount(0);
    await tile.getByLabel("Pasti, attività o peso", { exact: true }).fill("Ho mangiato yogurt e cereali");
    const request = page.waitForRequest((r) => r.url().endsWith("/meals/conversational/day-preview"));
    await tile.getByRole("button", { name: "Analizza con SanoSync AI", exact: true }).click();
    expect((await request).postDataJSON().default_meal_type).toBe(scenario.expected);
    await expect(tile.getByRole("heading", { name: "Controlla prima di registrare", exact: true })).toBeVisible();
  });
}

async function mockGuidedStrength(page: Page, failSave = false, uncalibrated = false) {
  const exercise = (id: string, name: string, position: number, pattern: string) => ({
    id, exercise_id: `${id}-library`, exercise_key: id, exercise_name: name, position, movement_pattern: pattern,
    strength_workout_id: "workout-1", target_sets: 1, target_reps_min: 6, target_reps_max: 10,
    target_rir: 2, rest_seconds: 90, prescribed_load_kg: null,
  });
  const exercises = [exercise("bench", "Bench Press", 2, "horizontal_push"), exercise("squat", "Back Squat", 1, "squat")];
  const plan = { id: "plan-1", goal: "hypertrophy", experience_level: "beginner", program_style: "full_body", sessions_per_week: 3, start_date: "2026-11-08", total_weeks: 8, status: "active" };
  const workouts = Array.from({ length: 24 }, (_, index) => ({ id: `workout-${index + 1}`, strength_plan_id: plan.id, scheduled_date: new Date(Date.UTC(2026, 10, 8 + Math.floor(index / 3) * 7 + index % 3 * 2)).toISOString().slice(0, 10), training_week: Math.floor(index / 3) + 1, workout_index: index + 1, title: "Full Body A", focus: "full_body", status: "planned", workout_kind: "planned", estimated_duration_minutes: 45, exercises }));
  const profiles: Array<Record<string, unknown>> = uncalibrated ? [] : ["squat", "bench"].map((id) => ({ user_id: user.id, exercise_ref: `library:${id}-library`, exercise_name: id, one_rep_max_kg: null, working_load_kg: id === "squat" ? 30 : 20, reference_reps: 8, reserve_reps: 2, source: "guided_test", updated_at: "2026-11-08T08:00:00Z" }));
  await page.route("**/rest/v1/strength_load_profiles**", async (route) => {
    expect(route.request().headers().authorization).toBe(`Bearer ${accessToken}`);
    if (route.request().method() === "POST") {
      const profile = route.request().postDataJSON();
      expect(profile.user_id).toBe(user.id);
      const index = profiles.findIndex((item) => item.exercise_ref === profile.exercise_ref);
      if (index >= 0) profiles[index] = profile; else profiles.push(profile);
      await route.fulfill({ status: 201, json: [] });
    } else await route.fulfill({ json: profiles });
  });
  await page.route("http://localhost:8000/exercises/*", async (route) => {
    const language = new URL(route.request().url()).searchParams.get("language");
    await route.fulfill({ json: { id: "squat-library", name: language === "it" ? "Squat con bilanciere" : "Barbell Back Squat", instructions: language === "it" ? "Mantieni il busto stabile e la schiena neutra." : "Keep your torso stable and your back neutral.", steps: language === "it" ? ["Piega anche e ginocchia."] : ["Bend your hips and knees."], media: [] } });
  });
  let sessionStarts = 0;
  let completions = 0;
  const saved = new Map<string, Record<string, unknown>>();
  await page.route("http://localhost:8000/strength/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let json: unknown;
    if (path === "/strength/plans") json = { items: [plan], count: 1 };
    else if (path === "/strength/plans/plan-1") json = { plan, workouts, workout_count: 24 };
    else if (path.endsWith("/history")) json = { items: [], count: 0 };
    else if (path.endsWith("/session")) {
      sessionStarts++;
      json = { status: "draft", workout: workouts[0], workout_log: { id: "log-1", notes: null, duration_minutes: null }, exercises, sets: [...saved.values()] };
    } else if (/\/sets\/1$/.test(path)) {
      if (failSave) { await route.fulfill({ status: 503, json: { detail: "Salvataggio non disponibile" } }); return; }
      const id = path.split("/")[5];
      const item = { ...route.request().postDataJSON(), strength_workout_exercise_id: id, set_index: 1 };
      saved.set(id, item);
      json = { saved: true, workout_log_id: "log-1", set: item };
    } else if (path.endsWith("/complete")) { completions++; json = { completed: true }; }
    else if (path.endsWith("/outcome")) json = { status: "evaluated", outcome: { outcome: "on_target", message: "Allenamento salvato", exercises: [] } };
    else if (path.endsWith("/progression-preview")) json = { proposals: [] };
    else throw new Error(`Missing strength fixture: ${path}`);
    await route.fulfill({ json });
  });
  return { sessionStarts: () => sessionStarts, completions: () => completions, saved, profiles };
}

for (const viewport of [{ name: "desktop", width: 1440, height: 1100 }, { name: "mobile", width: 390, height: 844 }]) {
  test(`gym program stays compact and workout is guided on ${viewport.name}`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport);
    const errors = await mockServices(page);
    const strength = await mockGuidedStrength(page);
    await signIn(page);
    await page.goto("/activities/programs");
    await page.getByRole("tab", { name: "Palestra", exact: true }).click();
    await expect(page.getByText("3 allenamenti a settimana per 8 settimane", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Giorni del programma").getByRole("button")).toHaveCount(24);
    await expect(page.getByLabel("Scheda del giorno").getByRole("cell", { name: /1\. Back Squat/ })).toBeVisible();
    await expect(page.getByText("Full Body A", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("group", { name: "Come è andata la serie 1?" })).toHaveCount(0);
    expect(strength.sessionStarts()).toBe(0);
    await page.screenshot({ path: testInfo.outputPath(`gym-compact-${viewport.name}.png`), fullPage: true });
    await page.getByRole("link", { name: "Inizia allenamento", exact: true }).click();
    await expect(page).toHaveURL(/\/activities\/workout\/plan-1\/workout-1$/);
    await expect(page.getByRole("heading", { name: "Back Squat", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Bench Press", exact: true })).toHaveCount(0);
    expect(strength.sessionStarts()).toBe(1);
    await page.getByRole("button", { name: "Salva e prossimo esercizio →" }).click();
    await expect(page.getByText(/Indica le ripetizioni/)).toBeVisible();
    await page.getByLabel("Ripetizioni serie 1").fill("8");
    await page.getByLabel("Peso in kg serie 1").fill("30");
    await page.getByRole("button", { name: "Giusto", exact: true }).click();
    await expect.poll(() => strength.saved.size).toBe(1);
    await page.screenshot({ path: testInfo.outputPath(`gym-guided-${viewport.name}.png`), fullPage: true });
    await page.getByRole("button", { name: "Salva e prossimo esercizio →" }).click();
    await expect(page.getByRole("heading", { name: "Bench Press", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Back Squat", exact: true })).toHaveCount(0);
    await page.getByLabel("Ripetizioni serie 1").fill("9");
    await page.getByLabel("Peso in kg serie 1").fill("20");
    await page.getByRole("button", { name: "Facile", exact: true }).click();
    await expect.poll(() => strength.saved.size).toBe(2);
    await page.getByRole("button", { name: "Riepilogo allenamento →" }).click();
    await expect(page.getByRole("heading", { name: "Hai finito gli esercizi" })).toBeVisible();
    await page.getByRole("button", { name: "Completa seduta", exact: true }).click();
    await expect(page.getByText("Seduta completata e salvata.", { exact: true })).toBeVisible();
    expect(strength.completions()).toBe(1);
    expect(errors).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}

test("failed set saves keep the current exercise and cannot complete the workout", async ({ page }) => {
  await mockServices(page);
  const strength = await mockGuidedStrength(page, true);
  await signIn(page);
  await page.goto("/activities/workout/plan-1/workout-1");
  await page.getByLabel("Ripetizioni serie 1").fill("8");
  await page.getByRole("button", { name: "Giusto", exact: true }).click();
  await expect(page.getByText("Non riesco a salvare la serie. Controlla la connessione e riprova.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Salva e prossimo esercizio →" }).click();
  await expect(page.getByText(/Non tutte le serie sono state salvate/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Back Squat", exact: true })).toBeVisible();
  expect(strength.completions()).toBe(0);
});

test("workout resumes saved series and history remains a separate read-only page", async ({ page }) => {
  await mockServices(page);
  const strength = await mockGuidedStrength(page);
  await signIn(page);
  await page.goto("/activities/workout/history/plan-1");
  await expect(page.getByRole("heading", { name: "Sedute completate", exact: true })).toBeVisible();
  expect(strength.sessionStarts()).toBe(0);
  await page.goto("/activities/workout/plan-1/workout-1");
  await page.getByLabel("Ripetizioni serie 1").fill("8");
  await page.getByRole("button", { name: "Giusto", exact: true }).click();
  await expect.poll(() => strength.saved.size).toBe(1);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Bench Press", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "← Precedente", exact: true }).click();
  await expect(page.getByLabel("Ripetizioni serie 1")).toHaveValue("8");
  await expect(page.getByRole("button", { name: "Giusto", exact: true })).toHaveAttribute("aria-pressed", "true");
});

test("every scheduled day opens its sheet without starting a session, and known maximum persists", async ({ page }, testInfo) => {
  await mockServices(page);
  const strength = await mockGuidedStrength(page, false, true);
  await signIn(page);
  await page.goto("/activities/programs");
  await page.getByRole("tab", { name: "Palestra", exact: true }).click();
  const days = page.getByLabel("Giorni del programma").getByRole("button");
  await expect(days).toHaveCount(24);
  await days.nth(23).click();
  await expect(days.nth(23)).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByLabel("Scheda del giorno").getByRole("cell", { name: /1\. Back Squat/ })).toBeVisible();
  await expect(page.getByLabel("Scheda del giorno").getByRole("cell", { name: "1 × 8 Fascia 6–10", exact: true })).toHaveCount(2);
  expect(strength.sessionStarts()).toBe(0);
  await page.getByRole("button", { name: "Imposta massimale · Back Squat", exact: true }).click();
  await page.getByRole("button", { name: "Conosco già il mio massimale", exact: true }).click();
  await page.getByLabel("Massimale conosciuto (kg)").fill("100");
  await page.getByRole("button", { name: "Calcola e salva il peso consigliato", exact: true }).click();
  await expect(page.getByRole("cell", { name: "75 kg Dal tuo riferimento salvato", exact: true })).toBeVisible();
  expect(strength.profiles[0].one_rep_max_kg).toBe(100);
  expect(strength.saved.size).toBe(0);
  expect(strength.sessionStarts()).toBe(0);
  await page.screenshot({ path: testInfo.outputPath("all-days-with-loads.png"), fullPage: true });
  await page.getByRole("link", { name: /Inizia il prossimo allenamento/ }).click();
  await expect(page).toHaveURL(/\/workout\/plan-1\/workout-1$/);
  await expect(page.getByLabel("Peso in kg serie 1")).toHaveValue("75");
  await expect(page.getByLabel("Ripetizioni serie 1")).toHaveValue("8");
  await page.reload();
  await expect(page.getByLabel("Peso in kg serie 1")).toHaveValue("75");
});

test("first exercise guides a submaximal test, saves its reference and pre-fills the prescription", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockServices(page);
  const strength = await mockGuidedStrength(page, false, true);
  await signIn(page);
  await page.goto("/activities/workout/plan-1/workout-1");
  await expect(page.getByLabel("Troviamo il tuo peso iniziale")).toBeVisible();
  await expect(page.getByLabel("Peso in kg serie 1")).toHaveCount(0);
  await page.getByRole("button", { name: "Non lo conosco: guidami", exact: true }).click();
  await page.getByLabel("Peso provato (kg)").fill("20");
  await expect(page.getByLabel("Ripetizioni della prova")).toHaveValue("8");
  await page.getByRole("button", { name: "0–1", exact: true }).click();
  await expect(page.getByText(/Il carico è troppo impegnativo/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Usa questo peso nella scheda", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Dolore o tecnica instabile", exact: true }).click();
  await expect(page.getByText(/Interrompi la prova/)).toBeVisible();
  await page.getByLabel("Ripetizioni della prova").fill("6");
  await page.getByRole("button", { name: "2–3", exact: true }).click();
  await page.screenshot({ path: testInfo.outputPath("load-calibration-mobile.png"), fullPage: true });
  await page.getByRole("button", { name: "Usa questo peso nella scheda", exact: true }).click();
  await expect(page.getByLabel("Ripetizioni serie 1")).toHaveValue("8");
  await expect(page.getByLabel("Peso in kg serie 1")).toHaveValue("18.5");
  expect(strength.profiles[0].source).toBe("guided_test");
  expect(strength.profiles[0].one_rep_max_kg).toBeCloseTo(25.3, 1);
  expect(strength.saved.size).toBe(0); // Calibration is not falsely recorded as a completed work set.
  await page.getByRole("button", { name: "Giusto", exact: true }).click();
  await expect.poll(() => strength.saved.size).toBe(1);
  expect(strength.saved.get("squat")?.rir).toBe(2);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Bench Press", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "← Precedente", exact: true }).click();
  await expect(page.getByLabel("Peso in kg serie 1")).toHaveValue("18.5");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("exercise demo uses the selected language and Italian instructions", async ({ page }) => {
  await mockServices(page);
  await mockGuidedStrength(page);
  await signIn(page);
  await page.goto("/activities/workout/plan-1/workout-1");
  await page.getByRole("button", { name: "Demo", exact: true }).click();
  await expect(page.getByText("Mantieni il busto stabile e la schiena neutra.", { exact: true })).toBeVisible();
  await expect(page.getByText("Piega anche e ginocchia.", { exact: true })).toBeVisible();
  await page.evaluate(() => localStorage.setItem("sanosync-language", "en"));
  await page.reload();
  await page.getByRole("button", { name: "Demo", exact: true }).click();
  await expect(page.getByText("Keep your torso stable and your back neutral.", { exact: true })).toBeVisible();
});

async function startTrainingOnboarding(page: Page, sport: "strength" | "running", failSetupOnce = false) {
  await page.clock.install({ time: new Date("2026-11-08T10:00:00Z") });
  await mockServices(page);
  let completed = false;
  let created = 0;
  let failure = failSetupOnce;
  let program: Record<string, unknown> | null = null;
  let createInput: Record<string, unknown> | null = null;
  const workouts: Array<Record<string, unknown>> = [];
  const setupWrites: Array<Record<string, unknown>> = [];
  await page.route("http://localhost:8000/onboarding/**", async (route) => {
    if (route.request().method() === "PUT") {
      if (failure) { failure = false; await route.fulfill({ status: 503, json: { detail: "Setup unavailable" } }); return; }
      setupWrites.push(route.request().postDataJSON()); completed = true;
    }
    await route.fulfill({ json: { completed, next_step: completed ? null : "training_setup", preferences: { primary_goal: "hypertrophy", food_enabled: false, training_enabled: true }, preferred_days: [], priority_muscles: [] } });
  });
  await page.route("http://localhost:8000/strength/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let json: unknown;
    if (path === "/strength/plans" && route.request().method() === "POST") {
      created++; createInput = route.request().postDataJSON();
      program = { ...createInput, id: "onboard-plan", status: "active", program_style: "full_body" };
      const count = Number(createInput!.sessions_per_week);
      for (let week = 0; week < Number(createInput!.total_weeks); week++) for (let index = 0; index < count; index++) {
        const date = new Date(`${createInput!.start_date}T12:00:00`); date.setDate(date.getDate() + week * 7 + index * 3);
        workouts.push({ id: `onboard-${week}-${index}`, scheduled_date: date.toISOString().slice(0, 10), training_week: week + 1, workout_index: index + 1, exercises: [], status: "planned", title: "Full Body A", focus: "full_body", estimated_duration_minutes: 45 });
      }
      json = { plan: program, workouts, workout_count: workouts.length };
    } else if (path === "/strength/plans") json = { items: program && sport === "strength" ? [program] : [], count: program ? 1 : 0 };
    else if (path.endsWith("/history")) json = { items: [], count: 0 };
    else json = { plan: program, workouts, workout_count: workouts.length };
    await route.fulfill({ json });
  });
  await page.route("**/rest/v1/strength_workouts**", async (route) => {
    const id = new URL(route.request().url()).searchParams.get("id")!.slice(3);
    const row = workouts.find((workout) => workout.id === id)!;
    Object.assign(row, route.request().postDataJSON());
    await route.fulfill({ json: { id } });
  });
  await page.route(/^http:\/\/localhost:8000\/activities\/training-plans(?:\/.*)?$/, async (route) => {
    if (route.request().method() === "POST") {
      created++; createInput = route.request().postDataJSON();
      program = { ...createInput, id: "onboard-run", sport: "running", status: "active", total_weeks: 8 };
      await route.fulfill({ json: { created: true, plan: program, session_count: 24, sessions: [] } });
    } else await route.fulfill({ json: { items: program && sport === "running" ? [program] : [], count: program ? 1 : 0 } });
  });
  await page.goto("/");
  await page.getByLabel("Email").fill(user.email);
  await page.getByLabel("Password").fill("test-password");
  await page.getByRole("button", { name: "Accedi", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Creiamo il tuo programma.", exact: true })).toBeVisible();
  await page.getByLabel("Come vuoi allenarti?").selectOption(sport);
  await page.getByLabel("Quando vuoi iniziare?").fill("2026-11-16");
  return { created: () => created, input: () => createInput!, workouts, setupWrites };
}

test("gym onboarding creates the dated fixed-day program and retry does not duplicate it", async ({ page }) => {
  const result = await startTrainingOnboarding(page, "strength", true);
  await page.getByLabel("Sedute a settimana").selectOption("2");
  await page.getByLabel("I tuoi giorni").selectOption("fixed");
  await page.getByRole("button", { name: "Ven", exact: true }).click();
  await page.getByRole("button", { name: "Crea il mio programma", exact: true }).click();
  await expect(page.getByText(/503/)).toBeVisible();
  expect(result.created()).toBe(1);
  expect(result.setupWrites).toHaveLength(0);
  await page.getByRole("button", { name: "Crea il mio programma", exact: true }).click();
  await expect(page.getByText("Il tuo programma è stato creato. Puoi già consultare tutte le sedute.", { exact: true })).toBeVisible();
  expect(result.created()).toBe(1);
  expect(result.input()).toMatchObject({ start_date: "2026-11-16", sessions_per_week: 2, total_weeks: 8, goal: "hypertrophy" });
  expect(result.workouts[0].scheduled_date).toBe("2026-11-16");
  expect(result.workouts[1].scheduled_date).toBe("2026-11-18");
  expect(result.workouts[2].scheduled_date).toBe("2026-11-23");
  await page.getByRole("button", { name: "Apri il mio programma", exact: true }).click();
  await expect(page).toHaveURL(/\/activities\/programs#palestra$/);
  await expect(page.getByRole("tab", { name: "Palestra", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByLabel("Giorni del programma").getByRole("button")).toHaveCount(16);
});

test("running onboarding creates a program from the chosen start, frequency and current ability", async ({ page }) => {
  const result = await startTrainingOnboarding(page, "running");
  await page.getByLabel("Sedute a settimana").selectOption("4");
  await page.getByLabel("Quanto corri oggi (km)?").fill("5");
  await page.getByLabel("Obiettivo distanza (km)").fill("10");
  await page.getByRole("button", { name: "Crea il mio programma", exact: true }).click();
  await expect(page.getByText("Il tuo programma è stato creato. Puoi già consultare tutte le sedute.", { exact: true })).toBeVisible();
  expect(result.input()).toMatchObject({ start_date: "2026-11-16", target_date: "2027-01-11", sessions_per_week: 4, current_distance_meters: 5000, target_distance_meters: 10000, current_pace_seconds_per_km: 360 });
  expect(result.created()).toBe(1);
  expect(result.setupWrites).toHaveLength(1);
});

for (const width of [360, 390, 430]) test(`program calendar and exercise sheet fit mobile width ${width}`, async ({ page }, testInfo) => {
  await page.setViewportSize({ width, height: 844 });
  await mockServices(page);
  await mockGuidedStrength(page);
  await signIn(page);
  await page.goto("/activities/programs#palestra");
  await expect(page.getByLabel("Scheda del giorno")).toBeVisible();
  await page.addStyleTag({ content: "html { font-size: 20px; }" });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const days = page.getByLabel("Giorni del programma").getByRole("button");
  await expect(days).toHaveCount(24);
  const bounds = await days.evaluateAll((buttons) => buttons.every((button) => button.getBoundingClientRect().right <= window.innerWidth && button.getBoundingClientRect().left >= 0));
  expect(bounds).toBe(true);
  await days.nth(23).click();
  await expect(page.getByLabel("Scheda del giorno").getByRole("cell", { name: /1\. Back Squat/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath(`program-mobile-${width}.png`), fullPage: true });
});
