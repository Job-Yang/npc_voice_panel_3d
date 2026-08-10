const { chromium } = require(process.env.PLAYWRIGHT_MODULE);
const fs = require("fs");

async function main() {
  const [url, screenshotPath, resultPath] = process.argv.slice(2);
  if (!url || !screenshotPath || !resultPath) {
    throw new Error("usage: verify_web.js <url> <screenshot> <result-json>");
  }

  const errors = [];
  const warnings = [];
  const requestFailures = [];
  let browser;

  try {
    browser = await chromium.launch({
      headless: true,
      args: [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--use-gl=swiftshader",
        "--enable-unsafe-swiftshader",
      ],
    });
    const page = await browser.newPage({
      viewport: { width: 1440, height: 960 },
      deviceScaleFactor: 1,
    });
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
      if (message.type() === "warning") warnings.push(message.text());
    });
    page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
    page.on("requestfailed", (request) => {
      requestFailures.push(`${request.url()} :: ${request.failure()?.errorText || "unknown"}`);
    });

    const separator = url.includes("?") ? "&" : "?";
    const verifiedUrl = `${url}${separator}autoloop_ts=${Date.now()}`;
    await page.goto(verifiedUrl, { waitUntil: "domcontentloaded", timeout: 30000 });
    let loaderWaitError = "";
    await page
      .waitForFunction(
        () => document.querySelector("#loader")?.classList.contains("hide"),
        null,
        { timeout: 20000 },
      )
      .catch((error) => {
        loaderWaitError = error.message;
      });
    await page.waitForTimeout(1500);

    const state = await page.evaluate(() => ({
      readyState: document.readyState,
      loaderClass: document.querySelector("#loader")?.className || "",
      canvasPresent: Boolean(document.querySelector("#viewer")),
      dialogVisible: document.querySelector("#dialog")?.classList.contains("show") || false,
    }));
    await page.screenshot({ path: screenshotPath, fullPage: true });

    const result = {
      status:
        errors.length === 0 &&
        state.canvasPresent &&
        state.loaderClass.split(/\s+/).includes("hide") &&
        process.env.ONLINE_HTML_MATCH === "true"
          ? "passed"
          : "failed",
      render_url: verifiedUrl,
      published_url: process.env.PUBLISHED_URL || "",
      online_html_match: process.env.ONLINE_HTML_MATCH === "true",
      online_sha256: process.env.ONLINE_SHA256 || "",
      local_sha256: process.env.LOCAL_SHA256 || "",
      screenshot: screenshotPath,
      state,
      errors,
      warnings,
      requestFailures,
      loaderWaitError,
      verified_at: new Date().toISOString(),
    };
    fs.writeFileSync(resultPath, `${JSON.stringify(result, null, 2)}\n`);
    if (result.status !== "passed") process.exitCode = 2;
  } finally {
    if (browser) await browser.close();
  }
}

main().catch((error) => {
  const resultPath = process.argv[4];
  if (resultPath) {
    fs.writeFileSync(
      resultPath,
      `${JSON.stringify({ status: "failed", error: error.message, verified_at: new Date().toISOString() }, null, 2)}\n`,
    );
  }
  console.error(error);
  process.exit(1);
});
