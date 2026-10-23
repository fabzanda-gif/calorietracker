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

type DayMessageLocale = "it" | "en" | "nl" | "fr";

const COPY = {
  it: {
    day: { office: "una giornata in ufficio", home: "una giornata di lavoro da casa", free: "una giornata libera" },
    activity: { low: "poco attiva", moderate: "moderatamente attiva", high: "molto attiva" },
    today: "Oggi è", logged: "Hai già registrato", one: "attività", many: "attività", and: "e", burned: "kcal bruciate", suffix: "oggi",
  },
  en: {
    day: { office: "an office day", home: "a work-from-home day", free: "a free day" },
    activity: { low: "with light activity", moderate: "with moderate activity", high: "with high activity" },
    today: "Today is", logged: "You have already logged", one: "activity", many: "activities", and: "and", burned: "kcal burned", suffix: "today",
  },
  nl: {
    day: { office: "een kantoordag", home: "een thuiswerkdag", free: "een vrije dag" },
    activity: { low: "met weinig activiteit", moderate: "met matige activiteit", high: "met veel activiteit" },
    today: "Vandaag is", logged: "Je hebt al", one: "activiteit geregistreerd", many: "activiteiten geregistreerd", and: "en", burned: "kcal verbrand", suffix: "vandaag",
  },
  fr: {
    day: { office: "une journée au bureau", home: "une journée en télétravail", free: "une journée libre" },
    activity: { low: "peu active", moderate: "modérément active", high: "très active" },
    today: "Aujourd’hui, c’est", logged: "Tu as déjà enregistré", one: "activité", many: "activités", and: "et", burned: "kcal brûlées", suffix: "aujourd’hui",
  },
} as const;

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
  locale: DayMessageLocale,
): string {
  return COPY[locale].day[value];
}

function activityLabel(
  value: DayMessageActivity,
  locale: DayMessageLocale,
): string {
  return COPY[locale].activity[value];
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
  locale: DayMessageLocale = "it",
): string {
  const text = COPY[locale];
  const base = `${text.today} ${dayTypeLabel(
    context.dayType,
    locale,
  )} ${activityLabel(
    context.activityLevel,
    locale,
  )}.`;

  if (
    context.activityCount > 0 &&
    context.burnedCalories > 0
  ) {
    return `${base} ${text.logged} ${context.activityCount} ${
      context.activityCount === 1
        ? text.one
        : text.many
    } ${text.and} ${Math.round(
      context.burnedCalories,
    )} ${text.burned}.`;
  }

  if (context.activityCount > 0) {
    return `${base} ${text.logged} ${
      context.activityCount
    } ${context.activityCount === 1 ? text.one : text.many} ${text.suffix}.`;
  }

  return base;
}
