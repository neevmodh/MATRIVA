import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs/promises";
import { spawnSync } from "node:child_process";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const require = createRequire(path.join(ROOT, "frontend/package.json"));
const { chromium, expect: baseExpect } = require("@playwright/test");
const expect = baseExpect.configure({ timeout: 15000 });
const screenshots = path.join(ROOT, "Material/screenshots");
const browser = await chromium.launch();
const records = [];
const errors = [];
await fs.mkdir(screenshots, { recursive: true });

async function renderDiagrams() {
  const directory = path.join(ROOT, "Material/diagrams");
  const page = await browser.newPage({ deviceScaleFactor: 2 });
  for (const name of (await fs.readdir(directory)).filter(name => name.endsWith(".svg"))) {
    const svg = await fs.readFile(path.join(directory, name), "utf8");
    const [, width, height] = svg.match(/viewBox="0 0 (\d+) (\d+)"/);
    await page.setViewportSize({ width: Number(width), height: Number(height) });
    await page.setContent(`<style>html,body{margin:0}</style>${svg}`);
    await page.screenshot({ path: path.join(directory, name.replace(".svg", ".png")) });
  }
  await page.close();
}

async function capture(page, name, description, fullPage = false) {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: path.join(screenshots, name), fullPage, type: "jpeg", quality: 92,
    animations: "disabled", style: "nextjs-portal { display: none !important; }" });
  records.push({ file: `screenshots/${name}`, description, viewport: page.viewportSize() });
  console.log(`Captured ${name}`);
}

async function api(request, method, route, token, data) {
  const response = await request[method](process.env.MATERIAL_API_URL + route, {
    headers: token ? { Authorization: `Bearer ${token}` } : {}, data,
  });
  expect(response.ok(), `${method.toUpperCase()} ${route}: ${response.status()}`).toBeTruthy();
  return response.json();
}

try {
  await renderDiagrams();
  if (!process.argv.includes("--diagrams-only")) {
    if (!process.env.MATERIAL_API_URL || !process.env.MATERIAL_WEB_URL) {
      throw new Error("Run python3 Material/tools/capture.py for isolated UI captures");
    }
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, baseURL: process.env.MATERIAL_WEB_URL });
    const page = await context.newPage();
    page.on("pageerror", error => errors.push(error.message));
    await page.goto("/");
    await capture(page, "01-landing.jpg", "Public landing page; actual application, desktop");
    await page.goto("/signup");
    await capture(page, "02-signup.jpg", "Account creation before any personal information is entered");
    await page.getByLabel(/Full name/).fill("Demo Mother");
    await page.getByLabel("Email", { exact: true }).fill("material-demo@example.com");
    await page.getByLabel("Password", { exact: true }).fill("SyntheticCapture123!");
    await page.getByRole("button", { name: /Sign up/ }).click();
    await expect(page).toHaveURL(/\/onboarding$/);
    await page.getByLabel(/How many weeks pregnant/).fill("20");
    await capture(page, "03-onboarding.jpg", "Synthetic week-20 profile; explicit storage-consent step");
    await page.getByRole("checkbox", { name: /I agree that MATRIVA stores/ }).check();
    await page.getByRole("button", { name: "Start chatting" }).click();
    await expect(page).toHaveURL(/\/chat$/);
    await capture(page, "04-chat-workspace.jpg", "Signed-in chat workspace with synthetic profile");
    const token = await page.evaluate(() => localStorage.getItem("matriva_token"));
    await api(context.request, "put", "/profile", token, {
      consent: true, full_name: "Demo Mother", region: "Gujarat", diet_type: "vegetarian",
      allergies: ["peanut"], health_notes: "Synthetic demonstration profile. No real patient data.",
    });
    const today = new Date();
    for (const [days, value] of [[14, 10.6], [7, 10.9], [0, 11.2]]) {
      const day = new Date(today); day.setUTCDate(day.getUTCDate() - days);
      await api(context.request, "post", "/care/readings", token, { kind: "hb", value, date: day.toISOString().slice(0, 10), note: "Synthetic capture value" });
    }
    await api(context.request, "post", "/care/meals", token, { text: "2 roti, 1 katori dal, curd, banana", meal_type: "lunch" });
    await api(context.request, "put", "/care/checkin", token, { mood: 4, symptoms: [], baby_movement: "normal", ifa_taken: true, note: "Synthetic check-in" });
    async function card(command, heading, filename, description, height = 1000) {
      await page.setViewportSize({ width: 1440, height });
      await page.goto("/chat");
      await page.getByPlaceholder(/Ask anything/).fill(command);
      await page.getByRole("button", { name: "Send", exact: true }).click();
      const title = page.getByRole("heading", { name: heading, exact: true }).last();
      await expect(title).toBeVisible();
      await page.waitForLoadState("networkidle");
      await title.scrollIntoViewIfNeeded();
      await capture(page, filename, description);
    }
    await card("/plan", "My plan", "05-weekly-plan.jpg", "Week-20 visit schedule, reminders and educational tasks", 1300);
    await card("/readings", "Health readings", "06-health-readings.jpg", "Real readings UI with three synthetic haemoglobin measurements");
    await card("/meals", "What I ate today", "07-meal-journal.jpg", "Real parser output for a synthetic vegetarian meal", 1150);
    await card("/foods", "What to eat", "08-food-guide.jpg", "Traditional book material and nutrient guidance shown separately", 1250);
    await card("/summary", "Summary for my doctor", "09-doctor-summary.jpg", "Printable summary of the synthetic care profile", 1250);
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto("/chat");
    await page.getByPlaceholder(/Ask anything/).fill("I have heavy bleeding");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(page.getByText(/112|emergency medical help|emergency care/i).last()).toBeVisible();
    await expect(page.getByRole("button", { name: "Stop generating" })).not.toBeVisible();
    await capture(page, "10-emergency-response.jpg", "Scripted demonstration of the real emergency short-circuit; no model call");
    await page.goto("/settings");
    await expect(page.getByText(/Data-sharing consent granted/)).toBeVisible();
    await capture(page, "11-privacy-settings.jpg", "Consent, export, safety profile and account controls", true);
    const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true, baseURL: process.env.MATERIAL_WEB_URL });
    await mobile.addInitScript(token => localStorage.setItem("matriva_token", token), token);
    const mobilePage = await mobile.newPage();
    mobilePage.on("pageerror", error => errors.push(error.message));
    await mobilePage.goto("/chat");
    await expect(mobilePage.getByPlaceholder(/Ask anything/)).toBeVisible();
    await capture(mobilePage, "12-mobile-workspace.jpg", "Actual responsive chat workspace at 390 × 844");
    await api(context.request, "post", "/auth/register", null, {
      email: "material-reviewer@example.com", password: "SyntheticReviewer123!", full_name: "Demo Reviewer",
    });
    const promotion = spawnSync(path.join(ROOT, "backend/.venv/bin/python"), ["-c", `from app.core.db import SessionLocal
from app.models import User
with SessionLocal() as db:
    user = db.query(User).filter_by(email="material-reviewer@example.com").one()
    user.role = "admin"
    db.commit()
`], { cwd: path.join(ROOT, "backend"), env: process.env, encoding: "utf8" });
    if (promotion.status !== 0) throw new Error("Could not promote isolated synthetic reviewer");
    const reviewer = await api(context.request, "post", "/auth/login", null, { email: "material-reviewer@example.com", password: "SyntheticReviewer123!" });
    expect((await api(context.request, "get", "/auth/me", reviewer.access_token)).role).toBe("admin");
    for (const title of ["Demo: meal journal workflow", "Demo: source review practice", "Demo: care-plan checklist"]) {
      const response = await context.request.post(process.env.MATERIAL_API_URL + "/admin/documents", {
        headers: { Authorization: `Bearer ${reviewer.access_token}` },
        multipart: {
          metadata: JSON.stringify({ title, domain: "nutrition", source_type: "internal", source_name: "Synthetic capture fixture", evidence_level: "uncertain" }),
          file: { name: "synthetic-demo.txt", mimeType: "text/plain", buffer: Buffer.from("Synthetic demonstration document. This fixture illustrates the source review queue and is not clinical guidance. No real source has been approved for these screenshots.") },
        },
      });
      expect(response.ok()).toBeTruthy();
    }
    const staff = await browser.newContext({ viewport: { width: 1440, height: 1100 }, baseURL: process.env.MATERIAL_WEB_URL });
    const staffPage = await staff.newPage();
    staffPage.on("pageerror", error => errors.push(error.message));
    await staffPage.goto("/login");
    await staffPage.getByLabel("Email", { exact: true }).fill("material-reviewer@example.com");
    await staffPage.getByLabel("Password", { exact: true }).fill("SyntheticReviewer123!");
    await staffPage.getByRole("button", { name: "Continue", exact: true }).click();
    await expect(staffPage).toHaveURL(/\/chat$/);
    await staffPage.goto("/admin/documents");
    await expect(staffPage.getByRole("heading", { name: "Review queue", exact: true })).toBeVisible();
    await capture(staffPage, "13-source-review.jpg", "Admin review queue containing only pending synthetic demonstration documents");
    expect(errors, "Browser page errors during capture").toEqual([]);
    const commit = spawnSync("git", ["rev-parse", "HEAD"], { cwd: ROOT, encoding: "utf8" }).stdout.trim();
    await fs.writeFile(path.join(ROOT, "Material/capture-manifest.json"), JSON.stringify({
      captured_at: new Date().toISOString(), source_commit: commit,
      mode: "Real local UI + real API; disposable SQLite; offline RAG; provider keys and tracing disabled",
      data: "Entirely synthetic; no patient records or real credentials; no real clinical sources approved",
      rendering: "Chromium JPEG quality 92; animations disabled; development indicator omitted; application content unchanged",
      browser_page_errors: errors, screenshots: records,
    }, null, 2) + "\n");
    console.log(`Captured ${records.length} real screens; no browser page errors`);
  }
} finally {
  await browser.close();
}
