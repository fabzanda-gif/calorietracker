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
