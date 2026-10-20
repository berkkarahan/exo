---
name: dashboard-ui
description: Build and run the wEXO dashboard, and capture headless screenshots with Playwright. Use when changing dashboard/ Svelte 5 code, testing the UI, taking UI screenshots, or attaching screenshots to a PR.
---

# wEXO Dashboard UI

Svelte 5 + TypeScript in `dashboard/`. Build output goes to `dashboard/build/` and is served by the API.

## Build and run

```bash
# Build (required before running wEXO serves the dashboard)
cd dashboard && npm install && npm run build && cd ..
# or: just build-dashboard

# Start wEXO (serves dashboard + API at http://localhost:52416)
uv run exo &
sleep 8
```

## Headless screenshots with Playwright

Use Playwright + headless Chromium; no manual browser interaction.

One-time setup:

```bash
npx --yes playwright install chromium
cd "$TMPDIR" && npm init -y && npm install playwright
```

Capture (run from the dir where playwright is installed):

```javascript
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto('http://localhost:52416', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  // Seed test data in localStorage if needed (e.g. recent models)
  await page.evaluate(() => {
    localStorage.setItem('exo-recent-models', JSON.stringify([
      { modelId: 'Qwen/Qwen2.5-0.5B-Instruct-GGUF', launchedAt: Date.now() },
    ]));
  });
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  await page.locator('text=SELECT MODEL').click();
  await page.waitForTimeout(1000);

  await page.screenshot({ path: 'screenshot.png', fullPage: false });
  await browser.close();
})();
```

## Attaching screenshots to a GitHub PR

GitHub's API cannot upload images for PR comments. Workaround:

1. Commit the image to the branch temporarily, push, and capture the commit SHA:
   ```bash
   cp screenshot.png . && git add screenshot.png
   git commit -m "chore: add screenshots for PR" && git push origin <branch>
   COMMIT_SHA=$(git rev-parse HEAD)
   ```
2. Comment with the raw URL pinned to that SHA (survives deleting the file):
   ```bash
   gh pr comment <PR> --body "![Screenshot](https://raw.githubusercontent.com/exo-explore/exo/${COMMIT_SHA}/screenshot.png)"
   ```
3. Remove the temp file:
   ```bash
   git rm screenshot.png && git commit -m "chore: remove temporary screenshot files" && git push origin <branch>
   ```
