---
description: Rules for creating Playwright/TypeScript browser tests for workbench IDE functionality using testcontainers and page objects
globs: "tests/browser/tests/**/*.spec.ts"
alwaysApply: false
---

# Playwright Browser Tests Rules

Browser tests in the notebooks repository validate workbench IDE user interfaces (Code Server, JupyterLab, RStudio) using Playwright and TypeScript.

## When to Write Browser Tests

Write Playwright browser tests when you need to:
- Test UI functionality in workbench IDEs
- Validate terminal operations and command execution
- Test file operations through the browser
- Verify UI rendering and visual elements
- Test user workflows and interactions
- Validate DOM stability and loading states
- Test keyboard interactions and shortcuts
- Capture screenshots for visual regression

## Framework and Tools

| Tool | Purpose |
|------|---------|
| **Playwright** | Browser automation framework |
| **@playwright/test** | Test runner and assertions |
| **testcontainers** | Docker container management for IDE images |
| **TypeScript** | Type-safe test code |
| **tslog** | Structured logging |

## Test File Structure

### File Naming and Location

**Pattern**: `*.spec.ts`

**Location**: `tests/browser/tests/`

**Examples**:
- `tests/browser/tests/codeserver.spec.ts` - Code Server tests
- `tests/browser/tests/openshift_console.spec.ts` - OpenShift Console tests

### Test Organization

```typescript
import * as path from "node:path";
import { test as base, expect } from '@playwright/test';
import { GenericContainer } from "testcontainers";
import { HttpWaitStrategy } from "testcontainers/build/wait-strategies/http-wait-strategy.js";

import { CodeServer } from "./models/codeserver";
import { log } from "./logger";
import { setupTestcontainers } from "./testcontainers";
import * as utils from './utils';

// Extend base test with custom fixtures
type MyFixtures = {
  codeServer: CodeServer;
  connectCDP: false | number;
  codeServerSource: {url?: string, image?: string};
};

const test = base.extend<MyFixtures>({
  // Define fixtures here
});

test.beforeAll(setupTestcontainers);

test('@tag test name', async ({codeServer, page}) => {
  // Test implementation
});
```

## Playwright Test Patterns

### 1. Custom Fixtures with Testcontainers

```typescript
type MyFixtures = {
  connectCDP: false | number;
  codeServerSource: {url?: string, image?: string};
  codeServer: CodeServer;
};

const test = base.extend<MyFixtures>({
  connectCDP: [false, {option: true}],
  codeServerSource: [{url:'http://localhost:8787'}, {option: true}],
  
  codeServer: [async ({ page, codeServerSource }, use) => {
    if (codeServerSource?.url) {
      await use(new CodeServer(page, codeServerSource.url));
    } else {
      const image = codeServerSource.image ?? (() => {
        throw new Error("invalid config: codeserver image not specified");
      })();
      
      const container = await new GenericContainer(image)
        .withExposedPorts(8787)
        .withWaitStrategy(
          new HttpWaitStrategy('/?folder=/opt/app-root/src', 8787, {
            abortOnContainerExit: true
          })
        )
        .start();
      
      await use(new CodeServer(
        page,
        `http://${container.getHost()}:${container.getMappedPort(8787)}`
      ));
      
      await container.stop();
    }
  }, {timeout: 10 * 60 * 1000}],
});
```

**Key Points**:
- Define custom fixtures with `base.extend<Type>()`
- Fixtures can be options (configurable) or auto-initialized
- Use testcontainers to start IDE containers
- `HttpWaitStrategy` ensures container is ready before tests
- Clean up containers in fixture teardown
- Set appropriate timeouts (10 min for container startup)

### 2. Basic Test Structure

```typescript
test('@codeserver open codeserver', async ({codeServer, page}) => {
  await page.goto(codeServer.url);
  await codeServer.isEditorVisible();
});
```

**Key Points**:
- Use descriptive test names prefixed with `@tag` for categorization
- Fixtures are injected as function parameters
- `page` is Playwright's Page object
- Use page objects (`codeServer`) for IDE interactions
- Use `await` for all async operations

### 3. Test Steps for Complex Workflows

```typescript
test('@codeserver use the terminal to run command', async ({codeServer, page}, testInfo) => {
  await page.goto(codeServer.url);

  await test.step("Should always see the code-server editor", async () => {
    expect(await codeServer.isEditorVisible()).toBe(true);
  });

  await test.step("should show the Integrated Terminal", async () => {
    await codeServer.focusTerminal();
    expect(await page.isVisible("#terminal")).toBe(true);
  });

  await test.step("should execute Terminal command successfully", async () => {
    await page.keyboard.type('echo The answer is $(( 6 * 7 )). > answer.txt', {delay: 100});
    await page.keyboard.press('Enter', {delay: 100});
  });

  await test.step("should open the file", async() => {
    const file = path.join('/opt/app-root/src', 'answer.txt');
    await codeServer.openFile(file);
    await expect(page.getByText("The answer is 42.")).toBeVisible();
  });
});
```

**Key Points**:
- Use `test.step()` to organize complex tests into logical sections
- Each step has a descriptive name
- Steps show up separately in test reports
- Use `expect()` for assertions
- Add delays with `{delay: ms}` for keyboard input
- Use `testInfo` parameter for metadata and screenshots

### 4. Waiting for DOM Stability

```typescript
test('@codeserver wait for welcome screen to load', async ({codeServer, page}, testInfo) => {
  await page.goto(codeServer.url);
  
  await codeServer.isEditorVisible();
  page.on("console", (msg) => log.info(msg.text()));
  
  await codeServer.isEditorVisible();
  await utils.waitForStableDOM(page, "div.monaco-workbench", 1000, 10000);
  await utils.waitForNextRender(page);
  
  await utils.takeScreenshot(page, testInfo, "welcome.png");
});
```

**Key Points**:
- Use `waitForStableDOM()` to ensure UI is fully loaded
- Parameters: `(page, selector, stabilityMs, timeoutMs)`
- Listen to console with `page.on("console")` for debugging
- Use `waitForNextRender()` for frame-perfect timing
- Take screenshots with `utils.takeScreenshot()`

### 5. Page Object Pattern

**Model Definition** (`tests/browser/tests/models/codeserver.ts`):

```typescript
import {Page} from "@playwright/test";
import * as path from "node:path";
import {log as rootLog} from "../logger";

export class CodeServer {
    private readonly logger = rootLog.getSubLogger({name: "CodeServer"});

    constructor(public readonly page: Page, public readonly url: string) {
    }

    async isEditorVisible(): Promise<boolean> {
        let editorSelector = "div.monaco-workbench";
        await this.page.waitForSelector(editorSelector, {timeout: 10000});
        const visible = await this.page.isVisible(editorSelector);
        this.logger.debug(`Editor is ${visible ? "visible" : "not visible"}!`);
        return visible;
    }

    async focusTerminal() {
        const doFocus = async (): Promise<boolean> => {
            await this.executeCommandViaMenus("Terminal: Create New Terminal");
            try {
                await this.page.waitForLoadState("load");
                await this.page.waitForSelector(
                    "textarea.xterm-helper-textarea:focus-within",
                    { timeout: 5000 }
                );
                return true;
            } catch (error) {
                return false;
            }
        };

        let attempts = 1;
        while (!(await doFocus())) {
            ++attempts;
            this.logger.debug(`no focused terminal textarea, retrying (${attempts}/∞)`);
        }

        this.logger.debug(`opening terminal took ${attempts} attempt(s)`);
    }

    async openFile(file: string) {
        await this.navigateMenus(["File", "Open File..."]);
        await this.navigateQuickInput([path.basename(file)]);
        await this.waitForTab(file);
    }

    private async executeCommandViaMenus(command: string) {
        await this.navigateMenus(["View", "Command Palette..."]);
        await this.page.keyboard.type(command);
        await this.page.hover(`text=${command}`);
        await this.page.click(`text=${command}`);
    }

    private async navigateMenus(menus: string[]): Promise<void> {
        // Implementation with retry logic
    }
}
```

**Key Points**:
- Page objects encapsulate IDE-specific interactions
- Use logger for debugging
- Store `page` and `url` as class properties
- Methods return `Promise<T>` for async operations
- Implement retry logic for flaky UI operations
- Use descriptive method names (`openFile`, `focusTerminal`)
- Add timeouts to waitForSelector calls

### 6. Retry Logic for Flaky UI

```typescript
async focusTerminal() {
    const doFocus = async (): Promise<boolean> => {
        await this.executeCommandViaMenus("Terminal: Create New Terminal");
        try {
            await this.page.waitForLoadState("load");
            await this.page.waitForSelector(
                "textarea.xterm-helper-textarea:focus-within",
                { timeout: 5000 }
            );
            return true;
        } catch (error) {
            return false;
        }
    };

    let attempts = 1;
    while (!(await doFocus())) {
        ++attempts;
        this.logger.debug(`no focused terminal textarea, retrying (${attempts}/∞)`);
    }

    this.logger.debug(`opening terminal took ${attempts} attempt(s)`);
}
```

**Key Points**:
- Wrap flaky operations in retry loops
- Return boolean from attempt function
- Log retry attempts for debugging
- Continue until success (or add max attempts limit)
- Use try/catch for timeout errors

### 7. Navigation with Retry

```typescript
async navigateMenus(menus: string[]): Promise<void> {
    await this.navigateItems(
        menus,
        '[aria-label="Application Menu"]',
        async (selector) => {
            await this.page.click(selector);
        }
    );
}

async navigateItems(
    items: string[],
    selector: string,
    open?: (selector: string) => void
): Promise<void> {
    const navigate = async (ctx: Context) => {
        const steps: Array<{ fn: () => Promise<unknown>; name: string }> = [
            {
                fn: () => this.page.waitForSelector(`${selector}:focus-within`),
                name: "focus",
            },
        ];

        for (const item of items) {
            steps.push({
                fn: () => this.page.hover(`${selector} :text-is("${item}")`, { trial: true }),
                name: `${item}:hover:trial`,
            });
            steps.push({
                fn: () => this.page.hover(`${selector} :text-is("${item}")`, { force: true }),
                name: `${item}:hover:force`,
            });
            steps.push({
                fn: () => this.page.click(`${selector} :text-is("${item}")`, { trial: true }),
                name: `${item}:click:trial`,
            });
            steps.push({
                fn: () => this.page.click(`${selector} :text-is("${item}")`, { force: true }),
                name: `${item}:click:force`,
            });
        }

        for (const step of steps) {
            try {
                await step.fn();
                if (ctx.canceled()) {
                    return false;
                }
            } catch (error) {
                return false;
            }
        }
        return true;
    };

    let attempts = 1;
    let context = new Context();
    while (!(await navigate(context))) {
        ++attempts;
        context.cancel();
        context = new Context();
    }
    context.finish();
}
```

**Key Points**:
- Complex navigation needs retry logic
- Use `trial: true` to check before forcing
- Use `:text-is()` for exact text matching
- Cancel and retry on errors
- Track context state to prevent race conditions

## Playwright Configuration

**File**: `tests/browser/playwright.config.ts`

```typescript
import { defineConfig, devices } from '@playwright/test';

export const DEFAULT_TEST_IMAGE = "quay.io/modh/codeserver:tag";

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : 1,
  reporter: [
    ['html', { open: 'never' }],
    ['line'],
    ['junit', { outputFile: 'results/junit.xml' }],
  ],
  outputDir: 'results/playwright-output',
  use: {
    codeServerSource: {
      image: process.env['TEST_TARGET'],
    },
    trace: 'on-first-retry',
    screenshot: "only-on-failure",
  },
  projects: getProjects(),
});
```

**Key Points**:
- Define default test image as exported constant
- Use environment variables for test targets
- Configure retries (2 on CI, 0 locally)
- Set workers (1 on CI for stability)
- Multiple reporters: HTML, line, JUnit
- Artifacts in `results/` directory
- Screenshots and traces on failure/retry

## Utility Functions

### Waiting for Stable DOM

```typescript
export async function waitForStableDOM(
    page: Page,
    selector: string,
    stabilityMs: number,
    timeoutMs: number
): Promise<void> {
    // Wait for selector to appear
    await page.waitForSelector(selector, { timeout: timeoutMs });
    
    // Wait for DOM to stop changing
    const startTime = Date.now();
    let lastHTML = '';
    
    while (Date.now() - startTime < timeoutMs) {
        const currentHTML = await page.innerHTML(selector);
        if (currentHTML === lastHTML) {
            await page.waitForTimeout(stabilityMs);
            const finalHTML = await page.innerHTML(selector);
            if (finalHTML === currentHTML) {
                return;
            }
        }
        lastHTML = currentHTML;
        await page.waitForTimeout(100);
    }
    
    throw new Error(`DOM did not stabilize within ${timeoutMs}ms`);
}
```

### Taking Screenshots

```typescript
export async function takeScreenshot(
    page: Page,
    testInfo: TestInfo,
    filename: string
): Promise<void> {
    const screenshot = await page.screenshot({ fullPage: true });
    await testInfo.attach(filename, {
        body: screenshot,
        contentType: 'image/png',
    });
}
```

## Best Practices Summary

### DO ✅
- Use page objects to encapsulate IDE interactions
- Add retry logic for flaky UI operations
- Use `test.step()` for complex workflows
- Wait for DOM stability before assertions
- Take screenshots on important steps
- Use structured logging for debugging
- Set appropriate timeouts for operations
- Clean up containers in fixture teardown
- Use TypeScript for type safety
- Tag tests with `@category` prefixes
- Use `{delay: ms}` for keyboard input
- Use `:text-is()` for exact text matching

### DON'T ❌
- Don't use `sleep()` - use `waitForSelector()` or `waitForStableDOM()`
- Don't hardcode selectors - use data-testid or semantic selectors
- Don't duplicate page object logic
- Don't forget to stop containers
- Don't use fixed waits instead of conditional waits
- Don't leave containers running on failure
- Don't skip error handling in retry loops
- Don't use generic error messages
- Don't commit screenshots to git (they're in gitignore)
- Don't test without proper logging

## Implementation Checklist

### Before writing tests
- [ ] Identify which IDE to test (Code Server, JupyterLab, RStudio)
- [ ] Determine if new page object is needed
- [ ] Check if existing fixtures can be reused
- [ ] Plan test scenarios and edge cases

### During implementation
- [ ] Create or extend fixtures for IDE container
- [ ] Implement page object methods if needed
- [ ] Write test with descriptive `@tag` and name
- [ ] Use `test.step()` for complex workflows
- [ ] Add retry logic for flaky operations
- [ ] Use `waitForStableDOM()` for loading states
- [ ] Add logging for debugging
- [ ] Take screenshots at key points

### After implementation
- [ ] Run tests locally with `pnpm test`
- [ ] Verify containers are cleaned up
- [ ] Check test output and screenshots
- [ ] Ensure tests pass on all browsers (chromium, firefox, webkit)
- [ ] Review retry logic for infinite loops
- [ ] Verify error messages are helpful
- [ ] Clean up any debug code

## Running Playwright Tests

```bash
# Install dependencies
pnpm install

# Run all tests
pnpm test

# Run specific test file
pnpm exec playwright test codeserver.spec.ts

# Run with UI mode
pnpm exec playwright test --ui

# Run with specific browser
pnpm exec playwright test --project=chromium

# Run with headed mode (see browser)
pnpm exec playwright test --headed

# Debug mode
pnpm exec playwright test --debug

# Generate report
pnpm exec playwright show-report
```

## Common Selectors

### Code Server Selectors

| Element | Selector |
|---------|----------|
| Editor | `div.monaco-workbench` |
| Terminal | `#terminal` |
| Terminal textarea | `textarea.xterm-helper-textarea` |
| Application menu | `[aria-label="Application Menu"]` |
| Quick input | `.quick-input-widget` |
| File tab | `.tab :text("filename")` |

### Wait Strategies

```typescript
// Wait for selector to appear
await page.waitForSelector('.element');

// Wait for selector to be visible
await page.waitForSelector('.element', { state: 'visible' });

// Wait for load state
await page.waitForLoadState('load');

// Wait for network idle
await page.waitForLoadState('networkidle');

// Wait for custom condition
await page.waitForFunction(() => document.querySelector('.element')?.textContent === 'Ready');
```

## Logging

```typescript
import { log } from "./logger";

// Info level
log.info("Test started");

// Debug level
log.debug("Detailed debug info", { data: value });

// Error level
log.error("Something went wrong", error);

// Sub-logger for context
const logger = log.getSubLogger({ name: "ComponentName" });
logger.debug("Component-specific log");
```
