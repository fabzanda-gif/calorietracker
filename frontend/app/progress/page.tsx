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

type RangeKey = "30" | "90" | "180" | "all";
type NutritionRangeKey = "7" | "30" | "90";
type NutritionMetric =
  | "calories"
  | "macros"
  | "activity"
  | "meals";

const NUTRITION_METRICS: Array<{
  key: NutritionMetric;
  label: string;
}> = [
  {
    key: "calories",
    label: "Calorie & budget",
  },
  {
    key: "macros",
    label: "Macros",
  },
  {
    key: "activity",
    label: "Attività",
  },
  {
    key: "meals",
    label: "Distribuzione pasti",
  },
];


const NUTRITION_RANGE_OPTIONS: Array<{
  key: NutritionRangeKey;
  label: string;
}> = [
  { key: "7", label: "7g" },
  { key: "30", label: "30g" },
  { key: "90", label: "90g" },
];


const RANGE_OPTIONS: Array<{
  key: RangeKey;
  label: string;
}> = [
  { key: "30", label: "30g" },
  { key: "90", label: "90g" },
  { key: "180", label: "6 mesi" },
  { key: "all", label: "Tutto" },
];

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
): string {
  return (
    NUTRITION_METRICS.find(
      (item) => item.key === metric,
    )?.label ?? "Andamento"
  );
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
): string {
  switch (metric) {
    case "macros":
      return "Come si distribuiscono proteine, carboidrati e grassi nelle tue giornate.";
    case "activity":
      return "Le calorie registrate dalle tue attività.";
    case "meals":
      return "Come si distribuiscono le calorie tra i pasti della giornata.";
    default:
      return "Quanto mangi rispetto al budget che SanoSync calcola per te.";
  }
}

function roundKcal(value: number): string {
  return Math.round(value).toLocaleString(
    "it-IT",
  );
}

function formatWeight(value: number): string {
  return value.toLocaleString("it-IT", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00`);

  return date.toLocaleDateString("it-IT", {
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
  const width = 900;
  const height = 360;
  const paddingX = 54;
  const paddingTop = 32;
  const paddingBottom = 54;

  if (items.length === 0) {
    return (
      <div className={styles.emptyChart}>
        <strong>Nessuna pesata nel periodo.</strong>
        <span>
          Aggiungi una misurazione per iniziare a vedere il trend.
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
          Misurazioni
        </span>

        <span>
          <i className={styles.legendTrend} />
          Trend 7 misurazioni
        </span>
      </div>

      <svg
        className={styles.chart}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Andamento del peso"
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
                {formatWeight(value)}
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
              {formatDate(item.date)}
              {": "}
              {formatWeight(
                Number(item.weight),
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
            {formatDate(items[index].date)}
          </text>
        ))}
      </svg>
    </div>
  );
}

function HeroWeightChart({ items }: { items: WeightEntry[] }) {
  if (items.length < 2) {
    return (
      <div className={styles.heroChartEmpty}>
        Registra almeno due pesate per vedere la direzione.
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

  return (
    <div className={styles.heroChartWrap}>
      <div className={styles.heroChartTitle}>
        <span>Andamento peso · ultimi 90 giorni</span>
        <strong>{formatWeight(values[0])} → {formatWeight(values[values.length - 1])} kg</strong>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Trend del peso negli ultimi 90 giorni">
        {[0.25, 0.5, 0.75].map((ratio) => (
          <line key={ratio} x1={padding} x2={width - padding} y1={height * ratio} y2={height * ratio} className={styles.heroGridLine} />
        ))}
        <polyline points={points} fill="none" className={styles.heroTrendLine} />
        {items.map((item, index) => (
          <circle key={`${item.id}-hero`} cx={xFor(index)} cy={yFor(Number(item.weight))} r="3.5" className={styles.heroTrendPoint} />
        ))}
      </svg>
      <div className={styles.heroChartDates}><span>90 giorni fa</span><span>Oggi</span></div>
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
          Nessun dato nel periodo.
        </strong>
        <span>
          Quando registri i tuoi dati li vedrai qui.
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
              Proteine
            </span>

            <span>
              <i className={styles.legendCarbs} />
              Carboidrati
            </span>

            <span>
              <i className={styles.legendFat} />
              Grassi
            </span>
          </>
        ) : metric === "meals" ? (
          <>
            <span>
              <i className={styles.legendBreakfast} />
              Colazione
            </span>

            <span>
              <i className={styles.legendLunch} />
              Pranzo
            </span>

            <span>
              <i className={styles.legendDinner} />
              Cena
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
                ? "Consumate"
                : metricLabel(metric)}
            </span>

            {metric === "calories" ? (
              <span>
                <i className={styles.legendBudget} />
                Budget
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
          aria-label={metricLabel(metric)}
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
                        {formatDate(item.date)}
                        {": Proteine "}
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
                        {formatDate(item.date)}
                        {": Carboidrati "}
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
                        {formatDate(item.date)}
                        {": Grassi "}
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
                        {formatDate(item.date)}
                        {": Colazione "}
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
                        {formatDate(item.date)}
                        {": Pranzo "}
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
                        {formatDate(item.date)}
                        {": Cena "}
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
                          {formatDate(item.date)}
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
                    )}
                    {": "}
                    {Math.round(value)}
                    {" "}
                    {metricUnit(metric)}
                    {metric === "activity"
                      ? value < 500
                        ? " · fascia < 500"
                        : " · fascia ≥ 500"
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
          : "Non riesco a caricare le calorie.",
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
          : "Non riesco a caricare il peso.",
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
          eyebrow: "Peso",
          title: decreasing
            ? `Peso in calo di ${formatWeight(
                Math.abs(stats.change),
              )} kg`
            : `Peso in aumento di ${formatWeight(
                Math.abs(stats.change),
              )} kg`,
          body:
            "Variazione tra la prima e l’ultima misurazione del periodo selezionato.",
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
          eyebrow: "Budget",
          title:
            percentage >= 70
              ? `${within} giorni su ${total} entro budget`
              : `${total - within} giorni su ${total} sopra budget`,
          body:
            percentage >= 70
              ? `Nel ${percentage}% dei giorni con un budget disponibile sei rimasto entro il valore calcolato da SanoSync.`
              : `Sei rimasto entro budget nel ${percentage}% dei giorni per cui era disponibile un confronto.`,
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
            label: "colazione",
            value:
              mealDistributionStats.breakfast,
          },
          {
            label: "pranzo",
            value:
              mealDistributionStats.lunch,
          },
          {
            label: "cena",
            value:
              mealDistributionStats.dinner,
          },
          {
            label: "altri pasti",
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
            eyebrow: "Distribuzione",
            title: `${
              dominant.label === "cena"
                ? "La cena"
                : dominant.label === "pranzo"
                  ? "Il pranzo"
                  : dominant.label ===
                      "colazione"
                    ? "La colazione"
                    : "Gli altri pasti"
            } concentra il ${Math.round(
              dominant.value,
            )}% delle calorie`,
            body:
              "È il momento della giornata che pesa maggiormente sulla distribuzione calorica del periodo selezionato.",
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
          eyebrow: "Proteine",
          title: `${roundKcal(
            macroStats.protein,
          )} g di proteine al giorno`,
          body:
            "Media giornaliera calcolata sui giorni registrati nel periodo nutrizionale selezionato.",
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
          eyebrow: "Attività",
          title: `${metricStats.activeDays} ${
            metricStats.activeDays === 1
              ? "giorno attivo"
              : "giorni attivi"
          } nel periodo`,
          body: `${roundKcal(
            metricStats.total,
          )} kcal registrate complessivamente · ${roundKcal(
            averageActivity,
          )} kcal per giorno attivo.`,
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
        "Inserisci un peso valido.",
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
          : "Non riesco a salvare il peso.",
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
            Progressi
          </p>

          <h1>
            {zero
              ? "Vediamo cosa dicono i numeri."
              : "La tua direzione"}
          </h1>

          <p className={styles.subtitle}>
            {zero
              ? "Trend, dati e nessuna favola motivazionale."
              : "Guarda la direzione, non il singolo numero."}
          </p>
        </div>
      </header>

      {error ? (
        <section className={styles.errorCard}>
          <strong>
            Qualcosa non ha funzionato.
          </strong>
          <p>{error}</p>
        </section>
      ) : null}

      <section className={styles.hero}>
        <div className={styles.heroSummary}>
          <p className={styles.kicker}>
            Peso attuale
          </p>

          <div className={styles.currentWeight}>
            {stats
              ? formatWeight(stats.latest)
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
              {formatWeight(stats.change)} kg nel periodo
            </p>
          ) : (
            <p className={styles.muted}>
              Nessuna misurazione disponibile.
            </p>
          )}
          <div className={styles.directionNote}>
            <span aria-hidden="true">↘</span>
            <div>
              <strong>
                {zero
                  ? stats && stats.change < 0
                    ? "Sta scendendo. Non fare il fenomeno."
                    : stats && stats.change > 0
                      ? "Sta salendo. I grafici non hanno tatto."
                      : "Fermo lì. Almeno qualcuno."
                  : stats && stats.change < 0
                    ? "Direzione costante"
                    : "Il trend prende forma"}
              </strong>
              <small>
                {zero
                  ? "Un dato fa scena. Il trend almeno prova a dire qualcosa."
                  : "Conta la direzione, non la singola giornata."}
              </small>
            </div>
          </div>
        </div>

        <HeroWeightChart items={visibleItems} />

        <form
          className={styles.weightForm}
          onSubmit={(event) => {
            event.preventDefault();
            void saveWeight();
          }}
        >
          <label>
            Data
            <input
              type="date"
              value={date}
              onChange={(event) => {
                setDate(event.target.value);
              }}
            />
          </label>

          <label>
            Peso
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
              ? "Salvo…"
              : "Registra peso"}
          </button>
        </form>
      </section>

      <section className={styles.topStatsGrid}>
        <article><span className={styles.statIcon}>↗</span><div><strong>{stats ? `${stats.change > 0 ? "+" : ""}${formatWeight(stats.change)} kg` : "—"}</strong><span>Variazione nel periodo</span></div></article>
        <article><span className={styles.statIcon}>▣</span><div><strong>{stats?.count ?? 0}</strong><span>Misurazioni totali</span></div></article>
        <article><span className={`${styles.statIcon} ${styles.statIconWarm}`}>◎</span><div><strong>{nutritionStats?.days_with_budget ? `${nutritionStats.days_within_budget}/${nutritionStats.days_with_budget}` : "—"}</strong><span>Giorni nel budget</span></div></article>
        <article><span className={`${styles.statIcon} ${styles.statIconLilac}`}>◇</span><div><strong>{macroStats ? `${roundKcal(macroStats.protein)} g` : "—"}</strong><span>Proteine medie</span></div></article>
      </section>

      <section className={styles.overviewSection}>
        <div className={styles.sectionHeader}>
          <div>
            <p className={styles.kicker}>
              La tua storia
            </p>
            <h2>
              {zero ? "I numeri non dimenticano" : "Il quadro completo"}
            </h2>
            <p className={styles.sectionSubtitle}>
              {zero
                ? "Peso, calorie e abitudini. Tutto nello stesso fascicolo."
                : "Peso, bilancio calorico e abitudini letti insieme."}
            </p>
          </div>

          <div
            className={styles.rangeSelector}
            aria-label="Periodo"
          >
            {RANGE_OPTIONS.map((option) => (
              <button
                key={option.key}
                type="button"
                className={
                  range === option.key
                    ? styles.rangeActive
                    : ""
                }
                onClick={() => {
                  setRange(option.key);
                }}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
        <div className={styles.overviewGrid}>
          <div className={styles.overviewChart}>
            {loading ? <div className={styles.loadingChart}>Carico lo storico…</div> : <WeightChart items={visibleItems} />}
          </div>
          <aside className={styles.insightPanel}>
            <p className={styles.kicker}>Insight</p>
            <h3>
              {zero ? "Cosa non è andato storto" : "Cosa sta funzionando"}
            </h3>
            {progressInsights.length ? progressInsights.slice(0, 3).map((insight, index) => (
              <article key={`${insight.eyebrow}-summary-${index}`}>
                <span aria-hidden="true">{index === 0 ? "↓" : index === 1 ? "◔" : "✓"}</span>
                <div><strong>{insight.title}</strong><p>{insight.body}</p></div>
              </article>
            )) : (
              <p className={styles.muted}>
                {zero
                  ? "Continua a registrare. Prima o poi i dati avranno qualcosa da confessare."
                  : "Continua a registrare: presto troverai qui una lettura dei tuoi progressi."}
              </p>
            )}
            <Link href="#nutrition-detail" className={styles.insightLink}>Vedi dettaglio nutrizione →</Link>
          </aside>
        </div>
      </section>

      <section className={styles.analyticsSection} id="nutrition-detail">
        <div className={styles.sectionHeader}>
          <div>
            <p className={styles.kicker}>
              Andamento
            </p>

            <h2>
              Nutrizione &amp; attività
            </h2>

            <p className={styles.sectionSubtitle}>
              {metricDescription(
                nutritionMetric,
              )}
            </p>
          </div>
        </div>

        <div className={styles.analyticsControls}>
          <label>
            <span>Visualizzazione</span>

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
                    key={option.key}
                    value={option.key}
                  >
                    {option.label}
                  </option>
                ),
              )}
            </select>
          </label>

          <label>
            <span>Periodo</span>

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
                    {option.key} giorni
                  </option>
                ),
              )}
            </select>
          </label>
        </div>

        {nutritionLoading ? (
          <div className={styles.loadingChart}>
            Carico i tuoi dati…
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
            <span>Media consumata</span>
            <strong>
              {nutritionStats
                ? `${roundKcal(
                    nutritionStats
                      .average_consumed_kcal,
                  )} kcal`
                : "—"}
            </strong>
          </article>

          <article>
            <span>Budget medio</span>
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
                  )} kcal`
                : "—"}
            </strong>
          </article>

          <article>
            <span>Entro budget</span>
            <strong>
              {nutritionStats &&
              nutritionStats.days_with_budget >
                0
                ? `${nutritionStats.days_within_budget}/${nutritionStats.days_with_budget}`
                : "—"}
            </strong>
          </article>

          <article>
            <span>Scostamento medio</span>
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
                  )} kcal`
                : "—"}
            </strong>
          </article>
        </section>
      ) : nutritionMetric === "macros" ? (
        <section className={styles.nutritionStatsGrid}>
          <article>
            <span>Proteine medie</span>
            <strong>
              {macroStats
                ? `${roundKcal(
                    macroStats.protein,
                  )} g`
                : "—"}
            </strong>
          </article>

          <article>
            <span>Carboidrati medi</span>
            <strong>
              {macroStats
                ? `${roundKcal(
                    macroStats.carbs,
                  )} g`
                : "—"}
            </strong>
          </article>

          <article>
            <span>Grassi medi</span>
            <strong>
              {macroStats
                ? `${roundKcal(
                    macroStats.fat,
                  )} g`
                : "—"}
            </strong>
          </article>

          <article>
            <span>Macro medi totali</span>
            <strong>
              {macroStats
                ? `${roundKcal(
                    macroStats.total,
                  )} g`
                : "—"}
            </strong>
          </article>
        </section>
      ) : nutritionMetric === "meals" ? (
        <section className={styles.nutritionStatsGrid}>
          <article>
            <span>Colazione</span>
            <strong>
              {mealDistributionStats
                ? `${Math.round(
                    mealDistributionStats.breakfast,
                  )}%`
                : "—"}
            </strong>
          </article>

          <article>
            <span>Pranzo</span>
            <strong>
              {mealDistributionStats
                ? `${Math.round(
                    mealDistributionStats.lunch,
                  )}%`
                : "—"}
            </strong>
          </article>

          <article>
            <span>Cena</span>
            <strong>
              {mealDistributionStats
                ? `${Math.round(
                    mealDistributionStats.dinner,
                  )}%`
                : "—"}
            </strong>
          </article>

          <article>
            <span>Altro</span>
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
            <span>Media giornaliera</span>
            <strong>
              {metricStats
                ? `${roundKcal(
                    metricStats.average,
                  )} ${metricUnit(
                    nutritionMetric,
                  )}`
                : "—"}
            </strong>
          </article>

          <article>
            <span>Totale periodo</span>
            <strong>
              {metricStats
                ? `${roundKcal(
                    metricStats.total,
                  )} ${metricUnit(
                    nutritionMetric,
                  )}`
                : "—"}
            </strong>
          </article>

          <article>
            <span>Giorni attivi</span>
            <strong>
              {metricStats
                ? metricStats.activeDays
                : "—"}
            </strong>
          </article>

          <article>
            <span>Massimo giornaliero</span>
            <strong>
              {metricStats
                ? `${roundKcal(
                    metricStats.maximum,
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
            {zero ? "Sette giorni di prove" : "Costanza"}
          </p>
          <h2>Gli ultimi 7 giorni</h2>
          <p className={styles.sectionSubtitle}>
            {zero
              ? "Abbastanza per un trend. Troppo pochi per una leggenda."
              : "Una settimana è fatta di direzioni, non di giornate perfette."}
          </p>
        </div>
        <div className={styles.consistencyDays}>
          {(nutrition?.items ?? []).slice(-7).map((item) => {
            const difference = item.difference_kcal;
            const state = difference === null ? "empty" : difference > 100 ? "surplus" : difference < -100 ? "deficit" : "maintenance";
            return (
              <article key={`consistency-${item.date}`}>
                <span className={`${styles.dayRing} ${styles[`dayRing_${state}`]}`}>{state === "deficit" ? "↓" : state === "surplus" ? "↑" : state === "maintenance" ? "=" : "·"}</span>
                <strong>{new Date(`${item.date}T00:00:00`).toLocaleDateString("it-IT", { weekday: "short" })}</strong>
                <small>{formatDate(item.date)}</small>
              </article>
            );
          })}
          {!nutrition?.items.length ? <p className={styles.muted}>Nessun dato disponibile per questa settimana.</p> : null}
        </div>
      </section>

      </main>
    </>
  );
}
