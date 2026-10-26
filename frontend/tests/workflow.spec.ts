import { test, expect } from "@playwright/test";
test("login, submit real task, inspect evidence and download patch bundle", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page
    .getByLabel("访问令牌")
    .fill("web-smoke-test-token-not-for-deployment");
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("button", { name: "开始分析" })).toBeVisible();
  await page.getByRole("button", { name: "开始分析" }).click();
  await expect(
    page.getByRole("button", { name: "下载证据与补丁" }),
  ).toBeVisible({ timeout: 45000 });
  await expect(page.getByText("自建靶场", { exact: true })).toBeVisible();
  await page.screenshot({
    path: "../out/ui-inspection/workbench.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "展开证据" }).first().click();
  await expect(page.getByRole("tab", { name: "源码与 SQL" })).toBeVisible();
  await page.getByRole("tab", { name: "对象与路径" }).click();
  await expect(
    page.getByRole("heading", { name: "跨服务实参绑定" }),
  ).toBeVisible();
  await page.screenshot({
    path: "../out/ui-inspection/evidence.png",
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  const dl = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载证据与补丁" }).click();
  expect((await dl).suggestedFilename()).toMatch(/microbind-.*\.zip/);
  await page.getByRole("menuitem", { name: "技术依据与改进方向" }).click();
  await expect(page.getByText("NEO / MScan", { exact: true })).toBeVisible();
  await page.getByRole("menuitem", { name: "部署与智能分析" }).click();
  await expect(page.getByText("只读工具", { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

async function login(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page
    .getByLabel("访问令牌")
    .fill("web-smoke-test-token-not-for-deployment");
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("button", { name: "开始分析" })).toBeVisible();
}

test("original upstream sample runs via real queue and shows coverage limits", async ({
  page,
}) => {
  await login(page);
  await expect(page.getByRole("switch", { name: "智能复核" })).toBeDisabled();
  await page.getByRole("menuitem", { name: "上游样例与实测" }).click();
  await page
    .getByRole("row")
    .filter({ hasText: "NEO · 跨语言角色修改" })
    .getByRole("button", { name: "选择样例" })
    .click();
  const submitted = page.waitForResponse(
    (r) => r.url().endsWith("/api/jobs") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "开始分析" }).click();
  const job = await (await submitted).json();
  expect(job.options.smart).toBe(false);
  expect(job.options.repair).toBe(false);
  await expect(
    page.getByRole("button", { name: "下载证据与补丁" }),
  ).toBeVisible({ timeout: 45000 });
  await expect(
    page.getByText("没有形成可判定的数据操作证据，不能据此认定项目安全。", {
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "执行流程" }).click();
  await expect(page.getByText("source.analyze", { exact: true })).toBeVisible();
  const response = await page.request.get("/api/jobs/" + job.id + "/result", {
    headers: {
      Authorization: "Bearer web-smoke-test-token-not-for-deployment",
    },
  });
  const result = await response.json();
  expect(result.before.summary.operations).toBe(0);
  expect(
    result.before.coverage_gaps.some(
      (g: any) => g.kind === "unsupported_language",
    ),
  ).toBe(true);
  expect(result.smart.status).toBe("disabled");
  expect(result.skill_events.map((e: any) => e.skill_id)).toEqual([
    "source.analyze",
    "report.export",
  ]);
  await page.screenshot({
    path: "../out/ui-inspection/unsupported-sample.png",
    fullPage: true,
  });
});

test("upload original litemall subset, inspect true API result and download", async ({
  page,
}) => {
  await login(page);
  await page
    .locator("input[type=file]")
    .setInputFiles("../out/validation/paper-samples/litemall.zip");
  await expect(page.getByText("源码导入成功", { exact: true })).toBeVisible();
  const submitted = page.waitForResponse(
    (r) => r.url().endsWith("/api/jobs") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "开始分析" }).click();
  const job = await (await submitted).json();
  await expect(
    page.getByRole("button", { name: "下载证据与补丁" }),
  ).toBeVisible({ timeout: 45000 });
  await expect(
    page.getByText("存在未覆盖代码，请结合覆盖缺口审查。", { exact: true }),
  ).toBeVisible();
  const response = await page.request.get("/api/jobs/" + job.id + "/result", {
    headers: {
      Authorization: "Bearer web-smoke-test-token-not-for-deployment",
    },
  });
  const result = await response.json();
  expect(result.before.summary.entries).toBe(6);
  expect(result.before.summary.operations).toBe(8);
  expect(result.before.summary.covered).toBe(1);
  expect(result.before.summary.needs_review).toBe(7);
  const row = page.getByRole("row").filter({ hasText: "GET /wx/brand/detail" });
  await row.getByRole("button", { name: "展开证据" }).click();
  await expect(page.getByRole("tab", { name: "源码与 SQL" })).toBeVisible();
  await page.keyboard.press("Escape");
  const dl = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载证据与补丁" }).click();
  expect((await dl).suggestedFilename()).toContain(job.id.slice(0, 8));
  await page.screenshot({
    path: "../out/ui-inspection/litemall.png",
    fullPage: true,
  });
});

test("skill page is loaded from API and model switch remains disabled", async ({
  page,
}) => {
  await login(page);
  await page.getByRole("menuitem", { name: "技能与执行流程" }).click();
  await expect(page.getByText("model.review", { exact: true })).toBeVisible();
  await expect(page.getByText("lab.verify", { exact: true })).toBeVisible();
  const response = await page.request.get("/api/skills", {
    headers: {
      Authorization: "Bearer web-smoke-test-token-not-for-deployment",
    },
  });
  expect((await response.json()).length).toBe(5);
});

test("full UI runtime verification executes real Java services without model", async ({
  page,
}) => {
  test.skip(
    process.env.MICROBIND_E2E_VERIFY !== "1",
    "Enable with Maven/JDK for the complete browser regression",
  );
  test.setTimeout(240000);
  await login(page);
  await page.getByRole("switch", { name: "运行验证" }).click();
  const submitted = page.waitForResponse(
    (r) => r.url().endsWith("/api/jobs") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "开始分析" }).click();
  const job = await (await submitted).json();
  expect(job.kind).toBe("verify");
  expect(job.options.smart).toBe(false);
  await expect(
    page.getByRole("button", { name: "下载证据与补丁" }),
  ).toBeVisible({ timeout: 220000 });
  await page.getByRole("tab", { name: "运行验证", exact: true }).click();
  await expect(
    page.getByText("真实服务回归通过", { exact: true }),
  ).toBeVisible();
  const response = await page.request.get("/api/jobs/" + job.id + "/result", {
    headers: {
      Authorization: "Bearer web-smoke-test-token-not-for-deployment",
    },
  });
  const r = await response.json();
  expect(r.verification.before.summary.unauthorized_effects_observed).toBe(8);
  expect(r.verification.after.summary.unauthorized_effects_observed).toBe(0);
  expect(r.verification.after.summary.legitimate_requests_passed).toBe(18);
  expect(r.verification.after.summary.boundary_checks_passed).toBe(4);
  expect(
    r.skill_events.some(
      (e: any) => e.skill_id === "lab.verify" && e.status === "succeeded",
    ),
  ).toBe(true);
  const fs = await import("node:fs");
  fs.writeFileSync(
    "../out/validation/browser-runtime.json",
    JSON.stringify(
      {
        job_id: job.id,
        before: r.verification.before.summary,
        after: r.verification.after.summary,
        model: r.smart.status,
        skills: r.skill_events,
      },
      null,
      2,
    ),
  );
  await page.screenshot({
    path: "../out/ui-inspection/runtime.png",
    fullPage: true,
  });
});
