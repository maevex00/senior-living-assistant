import { defineConfig, devices } from "@playwright/test";
const python =
  process.env.TEST_PYTHON ||
  (process.platform === "win32" ? ".venv\\Scripts\\python.exe" : "python");
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:5173", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${python} -m flask --app backend.wsgi run --host 127.0.0.1 --port 5000`,
      cwd: "..",
      url: "http://127.0.0.1:5000/api/health",
      reuseExistingServer: !process.env.CI,
      env: { DEMO_MODE: "true", PYTHONPATH: "." },
      timeout: 60000,
    },
    {
      command: "npm run preview -- --port 5173 --strictPort",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 60000,
    },
  ],
});
