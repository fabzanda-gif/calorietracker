"use client";

import { AppNav } from "@/components/navigation/AppNav";

import Link from "next/link";
import {
  useEffect,
  useMemo,
  useState,
} from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { useExperienceMode } from "@/components/experience/ExperienceModeProvider";
import { useI18n } from "@/components/i18n/I18nProvider";
import {
  createWeight,
  getWeightHistory,
  type WeightEntry,
} from "@/lib/api/weight";
import {
  getNutritionProgress,
  type NutritionProgressItem,
  type NutritionProgressResponse,
} from "@/lib/api/progress";

import styles from "./ProgressPage.module.css";
import { progressCopy, progressLocale } from "./progressI18n";

const insightCopy = {
  it: { weight: "Peso", weightDown: (value: string) => `Peso in calo di ${value} kg`, weightUp: (value: string) => `Peso in aumento di ${value} kg`, weightBody: "Variazione tra la prima e l’ultima misurazione del periodo selezionato.", budget: "Budget", within: (a: number, b: number) => `${a} giorni su ${b} entro budget`, over: (a: number, b: number) => `${a} giorni su ${b} sopra budget`, budgetGood: (p: number) => `Nel ${p}% dei giorni con un budget disponibile sei rimasto entro il valore calcolato da SanoSync.`, budgetOther: (p: number) => `Sei rimasto entro budget nel ${p}% dei giorni per cui era disponibile un confronto.`, mealLabels: ["colazione", "pranzo", "cena", "altri pasti"], distribution: "Distribuzione", mealTitle: (label: string, p: number) => `${label === "cena" ? "La cena" : label === "pranzo" ? "Il pranzo" : label === "colazione" ? "La colazione" : "Gli altri pasti"} concentra il ${p}% delle calorie`, mealBody: "È il momento della giornata che pesa maggiormente sulla distribuzione calorica del periodo selezionato.", protein: "Proteine", proteinTitle: (value: string) => `${value} g di proteine al giorno`, proteinBody: "Media giornaliera calcolata sui giorni registrati nel periodo nutrizionale selezionato.", activity: "Attività", activityTitle: (days: number) => `${days} ${days === 1 ? "giorno attivo" : "giorni attivi"} nel periodo`, activityBody: (total: string, average: string) => `${total} kcal registrate complessivamente · ${average} kcal per giorno attivo.` },
  en: { weight: "Weight", weightDown: (value: string) => `Weight down ${value} kg`, weightUp: (value: string) => `Weight up ${value} kg`, weightBody: "Change between the first and last measurement in the selected period.", budget: "Budget", within: (a: number, b: number) => `${a} of ${b} days within budget`, over: (a: number, b: number) => `${a} of ${b} days over budget`, budgetGood: (p: number) => `You stayed within SanoSync's calculated budget on ${p}% of comparable days.`, budgetOther: (p: number) => `You stayed within budget on ${p}% of days where a comparison was available.`, mealLabels: ["breakfast", "lunch", "dinner", "other meals"], distribution: "Distribution", mealTitle: (label: string, p: number) => `${label.charAt(0).toUpperCase()}${label.slice(1)} accounts for ${p}% of calories`, mealBody: "This is the part of the day with the greatest weight in the selected period's calorie distribution.", protein: "Protein", proteinTitle: (value: string) => `${value} g of protein per day`, proteinBody: "Daily average across logged days in the selected nutrition period.", activity: "Activity", activityTitle: (days: number) => `${days} active ${days === 1 ? "day" : "days"} in the period`, activityBody: (total: string, average: string) => `${total} kcal logged in total · ${average} kcal per active day.` },
  nl: { weight: "Gewicht", weightDown: (value: string) => `Gewicht ${value} kg gedaald`, weightUp: (value: string) => `Gewicht ${value} kg gestegen`, weightBody: "Verandering tussen de eerste en laatste meting in de geselecteerde periode.", budget: "Budget", within: (a: number, b: number) => `${a} van ${b} dagen binnen budget`, over: (a: number, b: number) => `${a} van ${b} dagen boven budget`, budgetGood: (p: number) => `Op ${p}% van de vergelijkbare dagen bleef je binnen het door SanoSync berekende budget.`, budgetOther: (p: number) => `Je bleef binnen budget op ${p}% van de dagen waarvoor een vergelijking beschikbaar was.`, mealLabels: ["ontbijt", "lunch", "avondeten", "overige maaltijden"], distribution: "Verdeling", mealTitle: (label: string, p: number) => `${label.charAt(0).toUpperCase()}${label.slice(1)} vormt ${p}% van de calorieën`, mealBody: "Dit dagdeel weegt het zwaarst in de calorieverdeling van de geselecteerde periode.", protein: "Eiwitten", proteinTitle: (value: string) => `${value} g eiwit per dag`, proteinBody: "Dagelijks gemiddelde over geregistreerde dagen in de geselecteerde voedingsperiode.", activity: "Activiteit", activityTitle: (days: number) => `${days} actieve ${days === 1 ? "dag" : "dagen"} in de periode`, activityBody: (total: string, average: string) => `${total} kcal in totaal geregistreerd · ${average} kcal per actieve dag.` },
  fr: { weight: "Poids", weightDown: (value: string) => `Poids en baisse de ${value} kg`, weightUp: (value: string) => `Poids en hausse de ${value} kg`, weightBody: "Variation entre la première et la dernière mesure de la période sélectionnée.", budget: "Budget", within: (a: number, b: number) => `${a} jours sur ${b} dans le budget`, over: (a: number, b: number) => `${a} jours sur ${b} au-dessus du budget`, budgetGood: (p: number) => `Vous êtes resté dans le budget calculé par SanoSync pendant ${p}% des jours comparables.`, budgetOther: (p: number) => `Vous êtes resté dans le budget pendant ${p}% des jours où une comparaison était disponible.`, mealLabels: ["petit-déjeuner", "déjeuner", "dîner", "autres repas"], distribution: "Répartition", mealTitle: (label: string, p: number) => `${label.charAt(0).toUpperCase()}${label.slice(1)} représente ${p}% des calories`, mealBody: "C'est le moment de la journée qui pèse le plus dans la répartition calorique de la période sélectionnée.", protein: "Protéines", proteinTitle: (value: string) => `${value} g de protéines par jour`, proteinBody: "Moyenne quotidienne calculée sur les jours enregistrés de la période nutritionnelle sélectionnée.", activity: "Activité", activityTitle: (days: number) => `${days} ${days === 1 ? "jour actif" : "jours actifs"} sur la période`, activityBody: (total: string, average: string) => `${total} kcal enregistrées au total · ${average} kcal par jour actif.` },
} as const;

type RangeKey = "30" | "90" | "180" | "all";
type NutritionRangeKey = "7" | "30" | "90";
type NutritionMetric =
  | "calories"
  | "macros"
  | "activity"
  | "meals";

const NUTRITION_METRICS: NutritionMetric[] = ["calories", "macros", "activity", "meals"];


const NUTRITION_RANGE_OPTIONS: Array<{
  key: NutritionRangeKey;
  label: string;
}> = [
  { key: "7", label: "7g" },
  { key: "30", label: "30g" },
  { key: "90", label: "90g" },
];


const RANGE_OPTIONS: RangeKey[] = ["30", "90", "180", "all"];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function nutritionDateRange(
  range: NutritionRangeKey,
): {
  startDate: string;
  endDate: string;
} {
  const end = new Date();
  const start = new Date();

  start.setDate(
    end.getDate() - Number(range) + 1,
  );

  return {
    startDate: start.toISOString().slice(0, 10),
    endDate: end.toISOString().slice(0, 10),
  };
}

function metricValue(
  item: NutritionProgressItem,
  metric: NutritionMetric,
): number {
  switch (metric) {
    case "activity":
      return item.activity_kcal;
    case "macros":
      return (
        item.protein_g +
        item.carbs_g +
        item.fat_g
      );
    default:
      return item.consumed_kcal;
  }
}

function metricLabel(
  metric: NutritionMetric,
  copy: typeof progressCopy.it | typeof progressCopy.en | typeof progressCopy.nl | typeof progressCopy.fr,
): string {
  return metric === "calories" ? copy.caloriesBudget : metric === "macros" ? copy.macros : metric === "activity" ? copy.activity : metric === "meals" ? copy.mealDistribution : copy.metricFallback;
}

function metricUnit(
  metric: NutritionMetric,
): string {
  return metric === "macros"
    ? "g"
    : "kcal";
}

function metricDescription(
  metric: NutritionMetric,
  copy: typeof progressCopy.it | typeof progressCopy.en | typeof progressCopy.nl | typeof progressCopy.fr,
): string {
  switch (metric) {
    case "macros":
      return copy.macrosDescription;
    case "activity":
      return copy.activityDescription;
    case "meals":
      return copy.mealsDescription;
    default:
      return copy.caloriesDescription;
  }
}

function roundKcal(value: number, locale = "it-IT"): string {
  return Math.round(value).toLocaleString(
    locale,
  );
}

function formatWeight(value: number, locale = "it-IT"): string {
  return value.toLocaleString(locale, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

function formatDate(value: string, locale = "it-IT"): string {
  const date = new Date(`${value}T00:00:00`);

  return date.toLocaleDateString(locale, {
    day: "numeric",
    month: "short",
  });
}

function filterByRange(
  items: WeightEntry[],
  range: RangeKey,
): WeightEntry[] {
  if (range === "all") {
    return items;
  }

  const days = Number(range);
  const end = new Date();
  const start = new Date();

  start.setDate(end.getDate() - days + 1);
  start.setHours(0, 0, 0, 0);

  return items.filter((item) => {
    const date = new Date(`${item.date}T00:00:00`);
    return date >= start;
  });
}

function movingAverage(
  values: number[],
  windowSize = 7,
): Array<number | null> {
  return values.map((_, index) => {
    const start = Math.max(
      0,
      index - windowSize + 1,
    );

    const window = values.slice(
      start,
      index + 1,
    );

    if (!window.length) {
      return null;
    }

    return (
      window.reduce(
        (sum, value) => sum + value,
        0,
      ) / window.length
    );
  });
}

function WeightChart({
  items,
}: {
  items: WeightEntry[];
}) {
  const { locale } = useI18n();
  const copy = progressCopy[locale];
  const displayLocale = progressLocale[locale];
  const width = 900;
  const height = 360;
  const paddingX = 54;
  const paddingTop = 32;
  const paddingBottom = 54;

  if (items.length === 0) {
    return (
      <div className={styles.emptyChart}>
        <strong>{copy.noWeights}</strong>
        <span>
          {copy.addMeasurement}
        </span>
      </div>
    );
  }

  const weights = items.map(
    (item) => Number(item.weight),
  );

  const trendWeights = movingAverage(
    weights,
    7,
  );

  let minWeight = Math.min(...weights);
  let maxWeight = Math.max(...weights);

  if (minWeight === maxWeight) {
    minWeight -= 1;
    maxWeight += 1;
  } else {
    const margin = Math.max(
      0.5,
      (maxWeight - minWeight) * 0.15,
    );
    minWeight -= margin;
    maxWeight += margin;
  }

  const innerWidth =
    width - paddingX * 2;

  const innerHeight =
    height - paddingTop - paddingBottom;

  function xFor(index: number): number {
    if (items.length === 1) {
      return width / 2;
    }

    return (
      paddingX +
      (index / (items.length - 1)) *
        innerWidth
    );
  }

  function yFor(weight: number): number {
    const ratio =
      (weight - minWeight) /
      (maxWeight - minWeight);

    return (
      paddingTop +
      innerHeight -
      ratio * innerHeight
    );
  }

  const points = items
    .map(
      (item, index) =>
        `${xFor(index)},${yFor(
          Number(item.weight),
        )}`,
    )
    .join(" ");

  const trendPoints = trendWeights
    .map((value, index) => {
      if (value === null) {
        return null;
      }

      return `${xFor(index)},${yFor(
        value,
      )}`;
    })
    .filter(
      (value): value is string =>
        value !== null,
    )
    .join(" ");

  const gridValues = Array.from(
    { length: 4 },
    (_, index) =>
      minWeight +
      ((maxWeight - minWeight) * index) / 3,
  ).reverse();

  const labelIndexes = Array.from(
    new Set([
      0,
      Math.floor((items.length - 1) / 2),
      items.length - 1,
    ]),
  );

  return (
    <div className={styles.chartScroll}>
      <div className={styles.chartLegend}>
        <span>
          <i className={styles.legendActual} />
          {copy.measurements}
        </span>

        <span>
          <i className={styles.legendTrend} />
          {copy.sevenTrend}
        </span>
      </div>

      <svg
        className={styles.chart}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={copy.weightTrend}
      >
        {gridValues.map((value) => {
          const y = yFor(value);

          return (
            <g key={value}>
              <line
                x1={paddingX}
                x2={width - paddingX}
                y1={y}
                y2={y}
                className={styles.gridLine}
              />
              <text
                x={paddingX - 12}
                y={y + 5}
                textAnchor="end"
                className={styles.axisLabel}
              >
                {formatWeight(value, displayLocale)}
              </text>
            </g>
          );
        })}

        <polyline
          points={points}
          fill="none"
          className={styles.weightLine}
        />

        {trendPoints ? (
          <polyline
            points={trendPoints}
            fill="none"
            className={styles.trendLine}
          />
        ) : null}

        {items.map((item, index) => (
          <circle
            key={`${item.id}-${item.date}`}
            cx={xFor(index)}
            cy={yFor(Number(item.weight))}
            r="6"
            className={styles.weightPoint}
          >
            <title>
              {formatDate(item.date, displayLocale)}
              {": "}
              {formatWeight(
                Number(item.weight),
                displayLocale,
              )}
              {" kg"}
            </title>
          </circle>
        ))}

        {labelIndexes.map((index) => (
          <text
            key={index}
            x={xFor(index)}
            y={height - 18}
            textAnchor={
              index === 0
                ? "start"
                : index === items.length - 1
                  ? "end"
                  : "middle"
            }
            className={styles.dateLabel}
          >
            {formatDate(items[index].date, displayLocale)}
          </text>
        ))}
      </svg>
    </div>
  );
}

function HeroWeightChart({
  items,
  range,
}: {
  items: WeightEntry[];
  range: RangeKey;
}) {
  const { locale } = useI18n();
  const copy = progressCopy[locale];
  const displayLocale = progressLocale[locale];
  if (items.length < 2) {
    return (
      <div className={styles.heroChartEmpty}>
        {copy.needTwo}
      </div>
    );
  }

  const width = 560;
  const height = 170;
  const padding = 18;
  const values = items.map((item) => Number(item.weight));
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const spread = Math.max(1, maximum - minimum);
  const xFor = (index: number) =>
    padding + (index / (items.length - 1)) * (width - padding * 2);
  const yFor = (value: number) =>
    padding + (1 - (value - minimum) / spread) * (height - padding * 2);
  const points = values
    .map((value, index) => `${xFor(index)},${yFor(value)}`)
    .join(" ");

  const rangeTitle =
    range === "30"
      ? copy.last30
      : range === "90"
        ? copy.last90
        : range === "180"
          ? copy.last6Months
          : copy.wholePeriod;

  const rangeStartLabel =
    range === "30"
      ? `30 ${copy.daysAgo}`
      : range === "90"
        ? `90 ${copy.daysAgo}`
        : range === "180"
          ? `6 ${copy.monthsAgo}`
          : formatDate(items[0].date, displayLocale);

  return (
    <div className={styles.heroChartWrap}>
      <div className={styles.heroChartTitle}>
        <span>{copy.weightHeading} · {rangeTitle}</span>
        <strong>{formatWeight(values[0], displayLocale)} → {formatWeight(values[values.length - 1], displayLocale)} kg</strong>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${copy.weightTrend}: ${rangeTitle}`}>
        {[0.25, 0.5, 0.75].map((ratio) => (
          <line key={ratio} x1={padding} x2={width - padding} y1={height * ratio} y2={height * ratio} className={styles.heroGridLine} />
        ))}
        <polyline points={points} fill="none" className={styles.heroTrendLine} />
        {items.map((item, index) => (
          <circle key={`${item.id}-hero`} cx={xFor(index)} cy={yFor(Number(item.weight))} r="3.5" className={styles.heroTrendPoint} />
        ))}
      </svg>
      <div className={styles.heroChartDates}>
        <span>{rangeStartLabel}</span>
        <span>{copy.today}</span>
      </div>
    </div>
  );
}

function DailyMetricsChart({
  items,
  metric,
}: {
  items: NutritionProgressItem[];
  metric: NutritionMetric;
}) {
  const { locale } = useI18n();
  const copy = progressCopy[locale];
  const displayLocale = progressLocale[locale];
  const relevantItems =
    metric === "activity"
      ? items.filter(
          (item) =>
            item.meal_count > 0 ||
            item.activity_count > 0,
        )
      : items.filter(
          (item) => item.meal_count > 0,
        );

  if (!relevantItems.length) {
    return (
      <div className={styles.emptyChart}>
        <strong>
          {copy.noPeriodData}
        </strong>
        <span>
          {copy.loggedDataHere}
        </span>
      </div>
    );
  }

  const width = 900;
  const height = 370;
  const paddingX = 54;
  const paddingTop = 34;
  const paddingBottom = 58;

  const values = relevantItems.flatMap(
    (item) => {
      if (metric === "macros") {
        return [
          item.protein_g +
            item.carbs_g +
            item.fat_g,
        ];
      }

      if (metric === "meals") {
        return [
          item.breakfast_kcal +
            item.lunch_kcal +
            item.dinner_kcal +
            item.other_kcal,
        ];
      }

      const primary = metricValue(
        item,
        metric,
      );

      if (
        metric === "calories" &&
        item.budget_kcal !== null
      ) {
        return [
          primary,
          item.budget_kcal,
        ];
      }

      return [primary];
    },
  );

  const minimumScale =
    metric === "calories" ||
    metric === "meals"
      ? 500
      : metric === "activity"
        ? 100
        : 25;

  const maxValue = Math.max(
    minimumScale,
    ...values,
  );

  const step =
    metric === "calories" ||
    metric === "meals"
      ? 250
      : metric === "activity"
        ? 100
        : 25;

  const chartMax =
    Math.ceil(
      (maxValue * 1.12) / step,
    ) * step;

  const innerWidth =
    width - paddingX * 2;

  const innerHeight =
    height -
    paddingTop -
    paddingBottom;

  function xFor(index: number): number {
    if (relevantItems.length === 1) {
      return width / 2;
    }

    return (
      paddingX +
      (index /
        (relevantItems.length - 1)) *
        innerWidth
    );
  }

  function yFor(value: number): number {
    return (
      paddingTop +
      innerHeight -
      (value / chartMax) *
        innerHeight
    );
  }

  const barWidth = Math.max(
    7,
    Math.min(
      28,
      (innerWidth /
        Math.max(
          relevantItems.length,
          1,
        )) *
        0.52,
    ),
  );

  const budgetPoints =
    metric === "calories"
      ? relevantItems
          .map((item, index) => {
            if (
              item.budget_kcal === null
            ) {
              return null;
            }

            return `${xFor(
              index,
            )},${yFor(
              item.budget_kcal,
            )}`;
          })
          .filter(
            (
              value,
            ): value is string =>
              value !== null,
          )
          .join(" ")
      : "";

  const gridValues = Array.from(
    { length: 5 },
    (_, index) =>
      (chartMax / 4) * index,
  ).reverse();

  const labelIndexes = Array.from(
    new Set([
      0,
      Math.floor(
        (relevantItems.length - 1) /
          2,
      ),
      relevantItems.length - 1,
    ]),
  );

  return (
    <div className={styles.calorieChartWrap}>
      <div className={styles.chartLegend}>
        {metric === "macros" ? (
          <>
            <span>
              <i className={styles.legendProtein} />
              {copy.protein}
            </span>

            <span>
              <i className={styles.legendCarbs} />
              {copy.carbs}
            </span>

            <span>
              <i className={styles.legendFat} />
              {copy.fat}
            </span>
          </>
        ) : metric === "meals" ? (
          <>
            <span>
              <i className={styles.legendBreakfast} />
              {copy.breakfast}
            </span>

            <span>
              <i className={styles.legendLunch} />
              {copy.lunch}
            </span>

            <span>
              <i className={styles.legendDinner} />
              {copy.dinner}
            </span>

            <span>
              <i className={styles.legendOtherMeal} />
              Altro
            </span>
          </>
        ) : metric === "activity" ? (
          <>
            <span>
              <i
                className={
                  styles.legendActivityLow
                }
              />
              Meno di 500 kcal
            </span>

            <span>
              <i
                className={
                  styles.legendActivityHigh
                }
              />
              500 kcal o più
            </span>
          </>
        ) : (
          <>
            <span>
              <i className={styles.legendCalories} />
              {metric === "calories"
                ? copy.consumed
                : metricLabel(metric, copy)}
            </span>

            {metric === "calories" ? (
              <span>
                <i className={styles.legendBudget} />
                {copy.budget}
              </span>
            ) : null}
          </>
        )}
      </div>

      <div className={styles.chartScroll}>
        <svg
          className={styles.chart}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={metricLabel(metric, copy)}
        >
          {gridValues.map((value) => {
            const y = yFor(value);

            return (
              <g key={value}>
                <line
                  x1={paddingX}
                  x2={width - paddingX}
                  y1={y}
                  y2={y}
                  className={
                    styles.gridLine
                  }
                />

                <text
                  x={paddingX - 12}
                  y={y + 5}
                  textAnchor="end"
                  className={
                    styles.axisLabel
                  }
                >
                  {Math.round(value)}
                </text>
              </g>
            );
          })}

          {relevantItems.map(
            (item, index) => {
              const x =
                xFor(index) -
                barWidth / 2;

              if (metric === "macros") {
                const protein =
                  item.protein_g;
                const carbs =
                  item.carbs_g;
                const fat =
                  item.fat_g;

                const proteinHeight =
                  (protein / chartMax) *
                  innerHeight;

                const carbsHeight =
                  (carbs / chartMax) *
                  innerHeight;

                const fatHeight =
                  (fat / chartMax) *
                  innerHeight;

                const baseline =
                  paddingTop +
                  innerHeight;

                const proteinY =
                  baseline -
                  proteinHeight;

                const carbsY =
                  proteinY -
                  carbsHeight;

                const fatY =
                  carbsY -
                  fatHeight;

                return (
                  <g
                    key={`macros-${item.date}`}
                  >
                    <rect
                      x={x}
                      y={proteinY}
                      width={barWidth}
                      height={Math.max(
                        1,
                        proteinHeight,
                      )}
                      rx="4"
                      className={
                        styles.macroProteinBar
                      }
                    >
                      <title>
                        {formatDate(item.date, displayLocale)}
                        {`: ${copy.protein} `}
                        {Math.round(protein)}
                        {" g"}
                      </title>
                    </rect>

                    <rect
                      x={x}
                      y={carbsY}
                      width={barWidth}
                      height={Math.max(
                        1,
                        carbsHeight,
                      )}
                      className={
                        styles.macroCarbsBar
                      }
                    >
                      <title>
                        {formatDate(item.date, displayLocale)}
                        {`: ${copy.carbs} `}
                        {Math.round(carbs)}
                        {" g"}
                      </title>
                    </rect>

                    <rect
                      x={x}
                      y={fatY}
                      width={barWidth}
                      height={Math.max(
                        1,
                        fatHeight,
                      )}
                      rx="4"
                      className={
                        styles.macroFatBar
                      }
                    >
                      <title>
                        {formatDate(item.date, displayLocale)}
                        {`: ${copy.fat} `}
                        {Math.round(fat)}
                        {" g"}
                      </title>
                    </rect>
                  </g>
                );
              }

              if (metric === "meals") {
                const breakfast =
                  item.breakfast_kcal;
                const lunch =
                  item.lunch_kcal;
                const dinner =
                  item.dinner_kcal;
                const other =
                  item.other_kcal;

                const breakfastHeight =
                  (breakfast / chartMax) *
                  innerHeight;

                const lunchHeight =
                  (lunch / chartMax) *
                  innerHeight;

                const dinnerHeight =
                  (dinner / chartMax) *
                  innerHeight;

                const otherHeight =
                  (other / chartMax) *
                  innerHeight;

                const baseline =
                  paddingTop +
                  innerHeight;

                const breakfastY =
                  baseline -
                  breakfastHeight;

                const lunchY =
                  breakfastY -
                  lunchHeight;

                const dinnerY =
                  lunchY -
                  dinnerHeight;

                const otherY =
                  dinnerY -
                  otherHeight;

                return (
                  <g
                    key={`meals-${item.date}`}
                  >
                    <rect
                      x={x}
                      y={breakfastY}
                      width={barWidth}
                      height={Math.max(
                        1,
                        breakfastHeight,
                      )}
                      rx="4"
                      className={
                        styles.mealBreakfastBar
                      }
                    >
                      <title>
                        {formatDate(item.date, displayLocale)}
                        {`: ${copy.breakfast} `}
                        {Math.round(breakfast)}
                        {" kcal"}
                      </title>
                    </rect>

                    <rect
                      x={x}
                      y={lunchY}
                      width={barWidth}
                      height={Math.max(
                        1,
                        lunchHeight,
                      )}
                      className={
                        styles.mealLunchBar
                      }
                    >
                      <title>
                        {formatDate(item.date, displayLocale)}
                        {`: ${copy.lunch} `}
                        {Math.round(lunch)}
                        {" kcal"}
                      </title>
                    </rect>

                    <rect
                      x={x}
                      y={dinnerY}
                      width={barWidth}
                      height={Math.max(
                        1,
                        dinnerHeight,
                      )}
                      className={
                        styles.mealDinnerBar
                      }
                    >
                      <title>
                        {formatDate(item.date, displayLocale)}
                        {`: ${copy.dinner} `}
                        {Math.round(dinner)}
                        {" kcal"}
                      </title>
                    </rect>

                    {other > 0 ? (
                      <rect
                        x={x}
                        y={otherY}
                        width={barWidth}
                        height={Math.max(
                          1,
                          otherHeight,
                        )}
                        rx="4"
                        className={
                          styles.mealOtherBar
                        }
                      >
                        <title>
                          {formatDate(item.date, displayLocale)}
                          {": Altro "}
                          {Math.round(other)}
                          {" kcal"}
                        </title>
                      </rect>
                    ) : null}
                  </g>
                );
              }

              const value =
                metricValue(
                  item,
                  metric,
                );

              const y = yFor(value);

              const barHeight =
                paddingTop +
                innerHeight -
                y;

              const overBudget =
                metric === "calories" &&
                item.budget_kcal !==
                  null &&
                value >
                  item.budget_kcal;

              return (
                <rect
                  key={`bar-${item.date}`}
                  x={x}
                  y={y}
                  width={barWidth}
                  height={Math.max(
                    2,
                    barHeight,
                  )}
                  rx="5"
                  className={
                    metric === "activity"
                      ? value < 500
                        ? styles.activityBarLow
                        : styles.activityBarHigh
                      : overBudget
                        ? styles.calorieBarOver
                        : styles.calorieBar
                  }
                >
                  <title>
                    {formatDate(
                      item.date,
                      displayLocale,
                    )}
                    {": "}
                    {Math.round(value)}
                    {" "}
                    {metricUnit(metric)}
                    {metric === "activity"
                      ? value < 500
                        ? ` · ${locale === "it" ? "fascia" : locale === "en" ? "range" : locale === "nl" ? "bereik" : "plage"} < 500`
                        : ` · ${locale === "it" ? "fascia" : locale === "en" ? "range" : locale === "nl" ? "bereik" : "plage"} ≥ 500`
                      : ""}
                  </title>
                </rect>
              );
            },
          )}

          {budgetPoints ? (
            <polyline
              points={budgetPoints}
              fill="none"
              className={
                styles.budgetLine
              }
            />
          ) : null}

          {labelIndexes.map(
            (index) => (
              <text
                key={`date-${index}`}
                x={xFor(index)}
                y={height - 18}
                textAnchor={
                  index === 0
                    ? "start"
                    : index ===
                        relevantItems.length -
                          1
                      ? "end"
                      : "middle"
                }
                className={
                  styles.dateLabel
                }
              >
                {formatDate(
                  relevantItems[index]
                    .date,
                  displayLocale,
                )}
              </text>
            ),
          )}
        </svg>
      </div>
    </div>
  );
}

export default function ProgressPage() {
  const { locale } = useI18n();
  const copy = progressCopy[locale];
  const insightText = insightCopy[locale];
  const displayLocale = progressLocale[locale];
  const zeroDirection = locale === "en"
    ? { down: "It's going down. Don't get carried away.", up: "It's going up. Charts have no tact.", flat: "Holding steady. At least someone is.", note: "One data point looks dramatic. A trend at least tries to say something." }
    : locale === "nl"
      ? { down: "Het daalt. Doe maar rustig.", up: "Het stijgt. Grafieken hebben geen tact.", flat: "Het blijft staan. Tenminste iemand.", note: "Eén meetpunt maakt indruk. Een trend probeert tenminste iets te zeggen." }
      : locale === "fr"
        ? { down: "Ça baisse. Ne vous emballez pas.", up: "Ça monte. Les graphiques manquent de tact.", flat: "Ça ne bouge pas. Au moins quelqu'un.", note: "Une donnée fait son effet. Une tendance essaie au moins de dire quelque chose." }
        : { down: "Sta scendendo. Non fare il fenomeno.", up: "Sta salendo. I grafici non hanno tatto.", flat: "Fermo lì. Almeno qualcuno.", note: "Un dato fa scena. Il trend almeno prova a dire qualcosa." };
  const { accessToken } = useAuth();
  const { experienceMode } = useExperienceMode();
  const zero = experienceMode === "zero";

  const [items, setItems] =
    useState<WeightEntry[]>([]);
  const [
    nutrition,
    setNutrition,
  ] =
    useState<NutritionProgressResponse | null>(
      null,
    );

  const [
    nutritionRange,
    setNutritionRange,
  ] =
    useState<NutritionRangeKey>("30");

  const [
    nutritionMetric,
    setNutritionMetric,
  ] =
    useState<NutritionMetric>(
      "calories",
    );

  const [
    nutritionLoading,
    setNutritionLoading,
  ] = useState(true);


  const [range, setRange] =
    useState<RangeKey>("90");

  const [loading, setLoading] =
    useState(true);

  const [saving, setSaving] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const [date, setDate] =
    useState(todayIso());

  const [weight, setWeight] =
    useState("");

  async function loadNutrition(
    selectedRange: NutritionRangeKey,
  ) {
    if (!accessToken) {
      return;
    }

    setNutritionLoading(true);

    try {
      const {
        startDate,
        endDate,
      } = nutritionDateRange(
        selectedRange,
      );

      const response =
        await getNutritionProgress(
          startDate,
          endDate,
          accessToken,
        );

      setNutrition(response);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : copy.loadCaloriesError,
      );
    } finally {
      setNutritionLoading(false);
    }
  }

  async function loadWeight() {
    if (!accessToken) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response =
        await getWeightHistory(accessToken);

      setItems(
        [...response.items].sort((a, b) =>
          a.date.localeCompare(b.date),
        ),
      );
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : copy.loadWeightError,
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadWeight();
  }, [accessToken]);

  useEffect(() => {
    void loadNutrition(
      nutritionRange,
    );
  }, [accessToken, nutritionRange]);


  const visibleItems = useMemo(
    () => filterByRange(items, range),
    [items, range],
  );

  const stats = useMemo(() => {
    if (!visibleItems.length) {
      return null;
    }

    const first =
      visibleItems[0];

    const latest =
      visibleItems[visibleItems.length - 1];

    const weights =
      visibleItems.map(
        (item) => Number(item.weight),
      );

    return {
      first: Number(first.weight),
      latest: Number(latest.weight),
      change:
        Number(latest.weight) -
        Number(first.weight),
      min: Math.min(...weights),
      max: Math.max(...weights),
      count: visibleItems.length,
    };
  }, [visibleItems]);

  const nutritionStats =
    useMemo(() => {
      if (!nutrition) {
        return null;
      }

      const logged =
        nutrition.items.filter(
          (item) => item.meal_count > 0,
        );

      const comparable =
        logged.filter(
          (item) =>
            item.budget_kcal !== null,
        );

      const averageDifference =
        comparable.length
          ? comparable.reduce(
              (sum, item) =>
                sum +
                (item.difference_kcal ??
                  0),
              0,
            ) / comparable.length
          : null;

      return {
        ...nutrition.summary,
        averageDifference,
      };
    }, [nutrition]);

  const macroStats =
    useMemo(() => {
      if (!nutrition) {
        return null;
      }

      const relevant =
        nutrition.items.filter(
          (item) => item.meal_count > 0,
        );

      if (!relevant.length) {
        return null;
      }

      const average = (
        key:
          | "protein_g"
          | "carbs_g"
          | "fat_g",
      ) =>
        relevant.reduce(
          (sum, item) =>
            sum + item[key],
          0,
        ) / relevant.length;

      const protein =
        average("protein_g");

      const carbs =
        average("carbs_g");

      const fat =
        average("fat_g");

      return {
        protein,
        carbs,
        fat,
        total:
          protein +
          carbs +
          fat,
      };
    }, [nutrition]);

  const mealDistributionStats =
    useMemo(() => {
      if (!nutrition) {
        return null;
      }

      const relevant =
        nutrition.items.filter(
          (item) => item.meal_count > 0,
        );

      if (!relevant.length) {
        return null;
      }

      const totals = relevant.reduce(
        (result, item) => ({
          breakfast:
            result.breakfast +
            item.breakfast_kcal,
          lunch:
            result.lunch +
            item.lunch_kcal,
          dinner:
            result.dinner +
            item.dinner_kcal,
          other:
            result.other +
            item.other_kcal,
        }),
        {
          breakfast: 0,
          lunch: 0,
          dinner: 0,
          other: 0,
        },
      );

      const total =
        totals.breakfast +
        totals.lunch +
        totals.dinner +
        totals.other;

      if (total <= 0) {
        return null;
      }

      return {
        breakfast:
          (totals.breakfast / total) *
          100,
        lunch:
          (totals.lunch / total) *
          100,
        dinner:
          (totals.dinner / total) *
          100,
        other:
          (totals.other / total) *
          100,
      };
    }, [nutrition]);

  const metricStats =
    useMemo(() => {
      if (!nutrition) {
        return null;
      }

      const relevant =
        nutritionMetric === "activity"
          ? nutrition.items.filter(
              (item) =>
                item.meal_count > 0 ||
                item.activity_count > 0,
            )
          : nutrition.items.filter(
              (item) =>
                item.meal_count > 0,
            );

      if (!relevant.length) {
        return null;
      }

      const values = relevant.map(
        (item) =>
          metricValue(
            item,
            nutritionMetric,
          ),
      );

      const total = values.reduce(
        (sum, value) =>
          sum + value,
        0,
      );

      const average =
        total / values.length;

      const maximum = Math.max(
        ...values,
      );

      const activeDays =
        nutrition.items.filter(
          (item) =>
            item.activity_count > 0,
        ).length;

      return {
        average,
        total,
        maximum,
        count: relevant.length,
        activeDays,
      };
    }, [
      nutrition,
      nutritionMetric,
    ]);

  const progressInsights =
    useMemo(() => {
      const result: Array<{
        eyebrow: string;
        title: string;
        body: string;
        tone: "navy" | "coral" | "neutral";
      }> = [];

      /*
       * Weight
       *
       * Descriptive only: we report the direction
       * observed in the currently selected weight
       * period. We do not claim nutrition caused it.
       */
      if (
        stats &&
        stats.count >= 2 &&
        Math.abs(stats.change) >= 0.1
      ) {
        const decreasing =
          stats.change < 0;

        result.push({
          eyebrow: insightText.weight,
          title: decreasing
            ? insightText.weightDown(formatWeight(Math.abs(stats.change), displayLocale))
            : insightText.weightUp(formatWeight(Math.abs(stats.change), displayLocale)),
          body: insightText.weightBody,
          tone: "navy",
        });
      }

      /*
       * Calories / budget
       */
      if (
        nutritionStats &&
        nutritionStats.days_with_budget > 0
      ) {
        const within =
          nutritionStats.days_within_budget;

        const total =
          nutritionStats.days_with_budget;

        const percentage =
          Math.round(
            (within / total) * 100,
          );

        result.push({
          eyebrow: insightText.budget,
          title:
            percentage >= 70
              ? insightText.within(within, total)
              : insightText.over(total - within, total),
          body:
            percentage >= 70
              ? insightText.budgetGood(percentage)
              : insightText.budgetOther(percentage),
          tone:
            percentage >= 70
              ? "navy"
              : "coral",
        });
      }

      /*
       * Meal distribution
       */
      if (mealDistributionStats) {
        const meals = [
          {
            label: insightText.mealLabels[0],
            value:
              mealDistributionStats.breakfast,
          },
          {
            label: insightText.mealLabels[1],
            value:
              mealDistributionStats.lunch,
          },
          {
            label: insightText.mealLabels[2],
            value:
              mealDistributionStats.dinner,
          },
          {
            label: insightText.mealLabels[3],
            value:
              mealDistributionStats.other,
          },
        ];

        const dominant =
          [...meals].sort(
            (a, b) => b.value - a.value,
          )[0];

        if (
          dominant &&
          dominant.value >= 35
        ) {
          result.push({
            eyebrow: insightText.distribution,
            title: insightText.mealTitle(dominant.label, Math.round(dominant.value)),
            body: insightText.mealBody,
            tone:
              dominant.value >= 50
                ? "coral"
                : "neutral",
          });
        }
      }

      /*
       * Macros
       */
      if (
        macroStats &&
        macroStats.protein > 0
      ) {
        result.push({
          eyebrow: insightText.protein,
          title: insightText.proteinTitle(roundKcal(macroStats.protein, displayLocale)),
          body: insightText.proteinBody,
          tone: "navy",
        });
      }

      /*
       * Activity
       */
      if (
        metricStats &&
        nutritionMetric === "activity" &&
        metricStats.activeDays > 0
      ) {
        const averageActivity =
          metricStats.total /
          metricStats.activeDays;

        result.push({
          eyebrow: insightText.activity,
          title: insightText.activityTitle(metricStats.activeDays),
          body: insightText.activityBody(roundKcal(metricStats.total, displayLocale), roundKcal(averageActivity, displayLocale)),
          tone:
            averageActivity >= 500
              ? "navy"
              : "coral",
        });
      }

      return result.slice(0, 4);
    }, [
      stats,
      nutritionStats,
      mealDistributionStats,
      macroStats,
      metricStats,
      nutritionMetric,
      displayLocale,
      insightText,
    ]);

  async function saveWeight() {
    if (!accessToken) {
      return;
    }

    const numericWeight =
      Number(weight.replace(",", "."));

    if (
      !Number.isFinite(numericWeight) ||
      numericWeight <= 0
    ) {
      setError(
        copy.invalidWeight,
      );
      return;
    }

    setSaving(true);
    setError(null);

    try {
      await createWeight(
        {
          date,
          weight: numericWeight,
        },
        accessToken,
      );

      setWeight("");
      await loadWeight();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : copy.saveWeightError,
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <AppNav />

      <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.brand}>
            {copy.progress}
          </p>

          <h1>
            {zero
              ? copy.zeroTitle
              : copy.title}
          </h1>

          <p className={styles.subtitle}>
            {zero
              ? copy.zeroSubtitle
              : copy.subtitle}
          </p>
        </div>
      </header>

      {error ? (
        <section className={styles.errorCard}>
          <strong>
            {copy.errorTitle}
          </strong>
          <p>{error}</p>
        </section>
      ) : null}

      <section className={styles.hero}>
        <div className={styles.heroSummary}>
          <p className={styles.kicker}>
            {copy.currentWeight}
          </p>

          <div className={styles.currentWeight}>
            {stats
              ? formatWeight(stats.latest, displayLocale)
              : "—"}
            <span>kg</span>
          </div>

          {stats ? (
            <p
              className={
                stats.change < 0
                  ? styles.changeDown
                  : stats.change > 0
                    ? styles.changeUp
                    : styles.changeNeutral
              }
            >
              {stats.change > 0 ? "+" : ""}
              {formatWeight(stats.change, displayLocale)} kg {copy.inPeriod}
            </p>
          ) : (
            <p className={styles.muted}>
              {copy.noMeasurement}
            </p>
          )}
          <div className={styles.directionNote}>
            <span aria-hidden="true">↘</span>
            <div>
              <strong>
                {zero
                  ? stats && stats.change < 0
                    ? zeroDirection.down
                    : stats && stats.change > 0
                      ? zeroDirection.up
                      : zeroDirection.flat
                  : stats && stats.change < 0
                    ? copy.down
                    : copy.forming}
              </strong>
              <small>
                {zero
                  ? zeroDirection.note
                  : copy.directionNote}
              </small>
            </div>
          </div>
        </div>

        <HeroWeightChart
          items={visibleItems}
          range={range}
        />

        <form
          className={styles.weightForm}
          onSubmit={(event) => {
            event.preventDefault();
            void saveWeight();
          }}
        >
          <label>
            {copy.date}
            <input
              type="date"
              value={date}
              onChange={(event) => {
                setDate(event.target.value);
              }}
            />
          </label>

          <label>
            {copy.weight}
            <div className={styles.weightInput}>
              <input
                type="text"
                inputMode="decimal"
                placeholder="82,4"
                value={weight}
                onChange={(event) => {
                  setWeight(event.target.value);
                }}
              />
              <span>kg</span>
            </div>
          </label>

          <button
            type="submit"
            disabled={saving}
          >
            {saving
              ? copy.saving
              : copy.saveWeight}
          </button>
        </form>
      </section>

      <section className={styles.topStatsGrid}>
        <article><span className={styles.statIcon}>↗</span><div><strong>{stats ? `${stats.change > 0 ? "+" : ""}${formatWeight(stats.change, displayLocale)} kg` : "—"}</strong><span>{copy.periodChange}</span></div></article>
        <article><span className={styles.statIcon}>▣</span><div><strong>{stats?.count ?? 0}</strong><span>{copy.measurementsTotal}</span></div></article>
        <article><span className={`${styles.statIcon} ${styles.statIconWarm}`}>◎</span><div><strong>{nutritionStats?.days_with_budget ? `${nutritionStats.days_within_budget}/${nutritionStats.days_with_budget}` : "—"}</strong><span>{copy.daysInBudget}</span></div></article>
        <article><span className={`${styles.statIcon} ${styles.statIconLilac}`}>◇</span><div><strong>{macroStats ? `${roundKcal(macroStats.protein, displayLocale)} g` : "—"}</strong><span>{copy.averageProtein}</span></div></article>
      </section>

      <section className={styles.overviewSection}>
        <div className={styles.sectionHeader}>
          <div>
            <p className={styles.kicker}>
              {copy.yourStory}
            </p>
            <h2>
              {zero ? copy.zeroPicture : copy.completePicture}
            </h2>
            <p className={styles.sectionSubtitle}>
              {zero
                ? copy.zeroStoryIntro
                : copy.storyIntro}
            </p>
          </div>

          <div
            className={styles.rangeSelector}
            aria-label={copy.period}
          >
            {RANGE_OPTIONS.map((option) => (
              <button
                key={option}
                type="button"
                className={
                  range === option
                    ? styles.rangeActive
                    : ""
                }
                onClick={() => {
                  setRange(option);
                }}
              >
                {option === "180" ? copy.months6 : option === "all" ? copy.all : `${option}${locale === "it" ? "g" : locale === "fr" ? "j" : "d"}`}
              </button>
            ))}
          </div>
        </div>
        <div className={styles.overviewGrid}>
          <div className={styles.overviewChart}>
            {loading ? <div className={styles.loadingChart}>{copy.loadingHistory}</div> : <WeightChart items={visibleItems} />}
          </div>
          <aside className={styles.insightPanel}>
            <p className={styles.kicker}>{copy.insight}</p>
            <h3>
              {zero ? copy.zeroWorking : copy.working}
            </h3>
            {progressInsights.length ? progressInsights.slice(0, 3).map((insight, index) => (
              <article key={`${insight.eyebrow}-summary-${index}`}>
                <span aria-hidden="true">{index === 0 ? "↓" : index === 1 ? "◔" : "✓"}</span>
                <div><strong>{insight.title}</strong><p>{insight.body}</p></div>
              </article>
            )) : (
              <p className={styles.muted}>
                {zero
                  ? copy.zeroKeepLogging
                  : copy.keepLogging}
              </p>
            )}
            <Link href="#nutrition-detail" className={styles.insightLink}>{copy.nutritionDetail} →</Link>
          </aside>
        </div>
      </section>

      <section className={styles.analyticsSection} id="nutrition-detail">
        <div className={styles.sectionHeader}>
          <div>
            <p className={styles.kicker}>
              {zero ? copy.zeroTrend : copy.trend}
            </p>

            <h2>
              {zero
                ? copy.zeroNutritionActivity
                : copy.nutritionActivity}
            </h2>

            <p className={styles.sectionSubtitle}>
              {zero
                ? copy.zeroNutritionIntro
                : metricDescription(
                    nutritionMetric,
                    copy,
                  )}
            </p>
          </div>
        </div>

        <div className={styles.analyticsControls}>
          <label>
            <span>{copy.view}</span>

            <select
              value={nutritionMetric}
              onChange={(event) => {
                setNutritionMetric(
                  event.target
                    .value as NutritionMetric,
                );
              }}
            >
              {NUTRITION_METRICS.map(
                (option) => (
                  <option
                    key={option}
                    value={option}
                  >
                    {metricLabel(option, copy)}
                  </option>
                ),
              )}
            </select>
          </label>

          <label>
            <span>{copy.period}</span>

            <select
              value={nutritionRange}
              onChange={(event) => {
                setNutritionRange(
                  event.target
                    .value as NutritionRangeKey,
                );
              }}
            >
              {NUTRITION_RANGE_OPTIONS.map(
                (option) => (
                  <option
                    key={option.key}
                    value={option.key}
                  >
                    {option.key} {copy.days}
                  </option>
                ),
              )}
            </select>
          </label>
        </div>

        {nutritionLoading ? (
          <div className={styles.loadingChart}>
            {copy.loadingData}
          </div>
        ) : nutrition ? (
          <DailyMetricsChart
            items={nutrition.items}
            metric={nutritionMetric}
          />
        ) : null}
      </section>

      {nutritionMetric === "calories" ? (
        <section className={styles.nutritionStatsGrid}>
          <article>
            <span>{copy.averageConsumed}</span>
            <strong>
              {nutritionStats
                ? `${roundKcal(
                    nutritionStats
                      .average_consumed_kcal,
                    displayLocale,
                  )} kcal`
                : "—"}
            </strong>
          </article>

          <article>
            <span>{copy.averageBudget}</span>
            <strong>
              {nutritionStats
                  ?.average_budget_kcal !==
                null &&
              nutritionStats
                  ?.average_budget_kcal !==
                undefined
                ? `${roundKcal(
                    nutritionStats
                      .average_budget_kcal,
                    displayLocale,
                  )} kcal`
                : "—"}
            </strong>
          </article>

          <article>
            <span>{copy.withinBudget}</span>
            <strong>
              {nutritionStats &&
              nutritionStats.days_with_budget >
                0
                ? `${nutritionStats.days_within_budget}/${nutritionStats.days_with_budget}`
                : "—"}
            </strong>
          </article>

          <article>
            <span>{copy.averageDifference}</span>
            <strong>
              {nutritionStats
                  ?.averageDifference !==
                null &&
              nutritionStats
                  ?.averageDifference !==
                undefined
                ? `${nutritionStats.averageDifference > 0 ? "+" : ""}${roundKcal(
                    nutritionStats
                      .averageDifference,
                    displayLocale,
                  )} kcal`
                : "—"}
            </strong>
          </article>
        </section>
      ) : nutritionMetric === "macros" ? (
        <section className={styles.nutritionStatsGrid}>
          <article>
            <span>{copy.averageProtein}</span>
            <strong>
              {macroStats
                ? `${roundKcal(
                    macroStats.protein,
                    displayLocale,
                  )} g`
                : "—"}
            </strong>
          </article>

          <article>
            <span>{copy.averageCarbs}</span>
            <strong>
              {macroStats
                ? `${roundKcal(
                    macroStats.carbs,
                    displayLocale,
                  )} g`
                : "—"}
            </strong>
          </article>

          <article>
            <span>{copy.averageFat}</span>
            <strong>
              {macroStats
                ? `${roundKcal(
                    macroStats.fat,
                    displayLocale,
                  )} g`
                : "—"}
            </strong>
          </article>

          <article>
            <span>{copy.averageMacros}</span>
            <strong>
              {macroStats
                ? `${roundKcal(
                    macroStats.total,
                    displayLocale,
                  )} g`
                : "—"}
            </strong>
          </article>
        </section>
      ) : nutritionMetric === "meals" ? (
        <section className={styles.nutritionStatsGrid}>
          <article>
            <span>{copy.breakfast}</span>
            <strong>
              {mealDistributionStats
                ? `${Math.round(
                    mealDistributionStats.breakfast,
                  )}%`
                : "—"}
            </strong>
          </article>

          <article>
            <span>{copy.lunch}</span>
            <strong>
              {mealDistributionStats
                ? `${Math.round(
                    mealDistributionStats.lunch,
                  )}%`
                : "—"}
            </strong>
          </article>

          <article>
            <span>{copy.dinner}</span>
            <strong>
              {mealDistributionStats
                ? `${Math.round(
                    mealDistributionStats.dinner,
                  )}%`
                : "—"}
            </strong>
          </article>

          <article>
            <span>{copy.other}</span>
            <strong>
              {mealDistributionStats
                ? `${Math.round(
                    mealDistributionStats.other,
                  )}%`
                : "—"}
            </strong>
          </article>
        </section>
      ) : (
        <section className={styles.nutritionStatsGrid}>
          <article>
            <span>{copy.dailyAverage}</span>
            <strong>
              {metricStats
                ? `${roundKcal(
                    metricStats.average,
                    displayLocale,
                  )} ${metricUnit(
                    nutritionMetric,
                  )}`
                : "—"}
            </strong>
          </article>

          <article>
            <span>{copy.periodTotal}</span>
            <strong>
              {metricStats
                ? `${roundKcal(
                    metricStats.total,
                    displayLocale,
                  )} ${metricUnit(
                    nutritionMetric,
                  )}`
                : "—"}
            </strong>
          </article>

          <article>
            <span>{copy.activeDays}</span>
            <strong>
              {metricStats
                ? metricStats.activeDays
                : "—"}
            </strong>
          </article>

          <article>
            <span>{copy.dailyMaximum}</span>
            <strong>
              {metricStats
                ? `${roundKcal(
                    metricStats.maximum,
                    displayLocale,
                  )} ${metricUnit(
                    nutritionMetric,
                  )}`
                : "—"}
            </strong>
          </article>
        </section>
      )}
      <section className={styles.consistencySection}>
        <div>
          <p className={styles.kicker}>
            {zero ? copy.zeroConsistency : copy.consistency}
          </p>
          <h2>{copy.last7}</h2>
          <p className={styles.sectionSubtitle}>
            {zero
              ? copy.zeroConsistencyIntro
              : copy.consistencyIntro}
          </p>
        </div>
        <div className={styles.consistencyDays}>
          {(nutrition?.items ?? []).slice(-7).map((item) => {
            const difference = item.difference_kcal;
            const state = difference === null ? "empty" : difference > 100 ? "surplus" : difference < -100 ? "deficit" : "maintenance";
            return (
              <article key={`consistency-${item.date}`}>
                <span className={`${styles.dayRing} ${styles[`dayRing_${state}`]}`}>{state === "deficit" ? "↓" : state === "surplus" ? "↑" : state === "maintenance" ? "=" : "·"}</span>
                <strong>{new Date(`${item.date}T00:00:00`).toLocaleDateString(displayLocale, { weekday: "short" })}</strong>
                <small>{formatDate(item.date, displayLocale)}</small>
              </article>
            );
          })}
          {!nutrition?.items.length ? <p className={styles.muted}>{copy.noWeekData}</p> : null}
        </div>
      </section>

      </main>
    </>
  );
}
