export type DayMessageType =
  | "office"
  | "home"
  | "free";

export type DayMessageActivity =
  | "low"
  | "moderate"
  | "high";

export type DayMessageMoment =
  | "morning"
  | "afternoon"
  | "evening";

export type DayMessageContext = {
  firstName: string;
  dayType: DayMessageType;
  activityLevel: DayMessageActivity;
  moment: DayMessageMoment;
  burnedCalories: number;
  activityCount: number;
};

function momentFromHour(hour: number): DayMessageMoment {
  if (hour < 12) {
    return "morning";
  }

  if (hour < 18) {
    return "afternoon";
  }

  return "evening";
}

function dayTypeLabel(
  value: DayMessageType,
): string {
  return {
    office: "una giornata in ufficio",
    home: "una giornata di lavoro da casa",
    free: "una giornata libera",
  }[value];
}

function activityLabel(
  value: DayMessageActivity,
): string {
  return {
    low: "poco attiva",
    moderate: "moderatamente attiva",
    high: "molto attiva",
  }[value];
}

function greeting(
  moment: DayMessageMoment,
): string {
  return {
    morning: "Buongiorno",
    afternoon: "Buon pomeriggio",
    evening: "Buonasera",
  }[moment];
}

export function buildDayMessageContext(
  firstName: string,
  dayType: DayMessageType,
  activityLevel: DayMessageActivity,
  burnedCalories: number,
  activityCount: number,
  historicalAverageCalories: number | null = null,
  historicalDays: number = 0,
  now = new Date(),
): DayMessageContext {
  return {
    firstName,
    dayType,
    activityLevel,
    moment: momentFromHour(
      now.getHours(),
    ),
    burnedCalories,
    activityCount,
  };
}

export function buildDayMessage(
  context: DayMessageContext,
): string {
  const base = `Oggi è ${dayTypeLabel(
    context.dayType,
  )} ${activityLabel(
    context.activityLevel,
  )}.`;

  if (
    context.activityCount > 0 &&
    context.burnedCalories > 0
  ) {
    return `${base} Hai già registrato ${context.activityCount} ${
      context.activityCount === 1
        ? "attività"
        : "attività"
    } e ${Math.round(
      context.burnedCalories,
    )} kcal bruciate.`;
  }

  if (context.activityCount > 0) {
    return `${base} Hai già registrato ${
      context.activityCount
    } attività oggi.`;
  }

  return base;
}
