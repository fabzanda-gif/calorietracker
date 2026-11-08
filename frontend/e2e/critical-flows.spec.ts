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

async function mockGuidedStrength(page: Page, failSave = false) {
  const exercise = (id: string, name: string, position: number, pattern: string) => ({
    id, exercise_key: id, exercise_name: name, position, movement_pattern: pattern,
    strength_workout_id: "workout-1", target_sets: 1, target_reps_min: 6, target_reps_max: 10,
    target_rir: 2, rest_seconds: 90, prescribed_load_kg: null,
  });
  const exercises = [exercise("bench", "Bench Press", 2, "horizontal_push"), exercise("squat", "Back Squat", 1, "squat")];
  const plan = { id: "plan-1", goal: "hypertrophy", experience_level: "beginner", program_style: "full_body", sessions_per_week: 3, start_date: "2026-11-08", total_weeks: 8, status: "active" };
  const workouts = Array.from({ length: 24 }, (_, index) => ({ id: `workout-${index + 1}`, strength_plan_id: plan.id, scheduled_date: "2026-11-08", training_week: Math.floor(index / 3) + 1, workout_index: index + 1, title: "Full Body A", focus: "full_body", status: "planned", workout_kind: "planned", estimated_duration_minutes: 45, exercises }));
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
  return { sessionStarts: () => sessionStarts, completions: () => completions, saved };
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
    await expect(page.getByText("Allenamento 1", { exact: true })).toHaveCount(1);
    await expect(page.getByText("Allenamento 4", { exact: true })).toHaveCount(0);
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
