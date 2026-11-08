export type MealSlot =
  | "breakfast"
  | "lunch"
  | "snack"
  | "dinner";

export type MealType =
  | "Colazione"
  | "Pranzo"
  | "Snack"
  | "Cena";

export const MEAL_SLOT_TYPES: ReadonlyArray<{
  slot: MealSlot;
  mealType: MealType;
}> = [
  { slot: "breakfast", mealType: "Colazione" },
  { slot: "lunch", mealType: "Pranzo" },
  { slot: "snack", mealType: "Snack" },
  { slot: "dinner", mealType: "Cena" },
];

export function normalizeMealType(
  value: unknown,
): string {
  const mealType = String(
    value ?? "",
  ).trim();

  return mealType.toLocaleLowerCase("it-IT") ===
    "spuntino"
    ? "Snack"
    : mealType;
}

export function nextMealType(
  loggedMealTypes: readonly unknown[],
): MealType {
  const logged = new Set(
    loggedMealTypes.map(normalizeMealType),
  );

  return (
    MEAL_SLOT_TYPES.find(
      ({ mealType }) =>
        !logged.has(mealType),
    )?.mealType ?? "Cena"
  );
}

/** Default only: an explicit meal in the message takes precedence in the interpreter. */
export function mealTypeForNow(
  loggedMealTypes: readonly unknown[],
  now = new Date(),
): MealType {
  const logged = new Set(loggedMealTypes.map((value) => normalizeMealType(value).toLocaleLowerCase("it-IT")));
  const hour = now.getHours();
  const current: MealType = hour < 5 ? "Snack"
    : hour < 11 ? "Colazione"
    : hour < 15 ? "Pranzo"
    : hour < 18 ? "Snack" : "Cena";
  return current !== "Snack" && logged.has(current.toLocaleLowerCase("it-IT")) ? "Snack" : current;
}
