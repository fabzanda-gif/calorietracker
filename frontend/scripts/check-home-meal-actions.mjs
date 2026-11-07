import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");

const home = readFileSync(
  resolve(root, "components/home/HomeShell.tsx"),
  "utf8",
);
const css = readFileSync(
  resolve(root, "components/home/HomeShell.module.css"),
  "utf8",
);

const checks = [
  {
    ok: home.includes("styles.dailyMealSummaryActions"),
    message: "Home meal summary must render the stable actions wrapper.",
  },
  {
    ok: home.includes("styles.dailyMealDeleteButton"),
    message: "Home meal summary must render the delete button.",
  },
  {
    ok: css.includes(".dailyMealSummaryActions {"),
    message: "Home CSS must define the actions wrapper.",
  },
  {
    ok: css.includes(
      ".dailyMealSummaryActions .dailyMealDeleteButton",
    ),
    message:
      "Home CSS must keep the delete control inside the stable actions wrapper.",
  },
  {
    ok:
      css.includes("grid-column: 4 !important;") &&
      css.includes("display: inline-flex !important;"),
    message:
      "Home actions wrapper must occupy the final visible grid cell.",
  },
];

const failures = checks.filter((check) => !check.ok);

if (failures.length) {
  for (const failure of failures) {
    console.error(`Home meal actions regression: ${failure.message}`);
  }

  process.exit(1);
}

console.log("Home meal action layout regression check passed.");
