import { expect, test, type Page } from "@playwright/test";

const testEmail = process.env.E2E_TEST_EMAIL?.trim();
const testPassword = process.env.E2E_TEST_PASSWORD?.trim();
const hasTestAccount = Boolean(testEmail && testPassword);

async function signIn(page: Page) {
  await page.goto("/");
  await page.getByLabel("Email").fill(testEmail!);
  await page.getByLabel("Password").fill(testPassword!);
  await page.getByRole("button", { name: "Accedi", exact: true }).click();
  await expect(page.getByText(/Buongiorno,/)).toBeVisible({
    timeout: 30_000,
  });
}

test.describe("public entry points", () => {
  test("shows the login form and protects the home", async ({ page }) => {
    await page.goto("/");

    await expect(
      page.getByRole("heading", { name: "Bentornato." }),
    ).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Accedi", exact: true }),
    ).toBeVisible();
  });

  test("keeps privacy and terms publicly reachable", async ({ page }) => {
    await page.goto("/privacy");
    await expect(page).toHaveURL(/\/privacy$/);
    await expect(page.locator("body")).not.toContainText(
      "Caricamento sessione…",
    );

    await page.goto("/terms");
    await expect(page).toHaveURL(/\/terms$/);
    await expect(page.locator("body")).not.toContainText(
      "Caricamento sessione…",
    );
  });
});

test.describe("authenticated critical paths", () => {
  test.skip(
    !hasTestAccount,
    "Set E2E_TEST_EMAIL and E2E_TEST_PASSWORD to run authenticated checks.",
  );

  test.beforeEach(async ({ page }) => {
    await signIn(page);
  });

  test("opens the four primary application areas", async ({ page }) => {
    const destinations = [
      { name: "Attività", path: "/activities" },
      { name: "Progressi", path: "/progress" },
      { name: "Ricette", path: "/recipes" },
      { name: "Oggi", path: "/" },
    ];

    for (const destination of destinations) {
      await page
        .getByRole("link", { name: destination.name, exact: true })
        .first()
        .click();
      await expect(page).toHaveURL(
        new RegExp(
          destination.path === "/"
            ? "/$"
            : destination.path + "$",
        ),
      );
    }
  });

  test("opens the quick activity logger without mutating data", async ({
    page,
  }) => {
    await page
      .getByRole("button", { name: /attività/i })
      .first()
      .click();

    await expect(
      page.getByRole("heading", { name: "Registra attività" }),
    ).toBeVisible();
    await expect(page.getByText("Passi", { exact: true })).toBeVisible();
  });
});
