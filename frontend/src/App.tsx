import { useEffect, useState } from "react";
import { api, setAdvisorToken } from "./services/api";
import {
  emptyProfile,
  type ClientProfile,
  type Intake,
  type IntakeResponse,
  type InputMode,
  type RecommendationResponse,
} from "./types";
import { ProfileForm } from "./components/ProfileForm";
import { IntakeModes } from "./components/IntakeModes";
import { Results } from "./components/Results";

export default function App() {
  const [config, setConfig] = useState<{
    demo_mode: boolean;
    auth_required: boolean;
  } | null>(null);
  const [mode, setMode] = useState<InputMode>("manual");
  const [profile, setProfile] = useState<ClientProfile>(emptyProfile);
  const [intake, setIntake] = useState<Intake | null>(null);
  const [result, setResult] = useState<RecommendationResponse | null>(null);
  const [busy, setBusy] = useState(false),
    [liveActive, setLiveActive] = useState(false);
  const [error, setError] = useState(""),
    [warnings, setWarnings] = useState<string[]>([]);
  const [token, setToken] = useState("");
  const [intakeMetrics, setIntakeMetrics] = useState<Record<
    string,
    number
  > | null>(null);
  useEffect(() => {
    api<{ demo_mode: boolean; auth_required: boolean }>("/config")
      .then(setConfig)
      .catch((e) => setError(e.message));
  }, []);
  function change(p: ClientProfile) {
    setProfile(p);
    setResult(null);
    setIntake(null);
  }
  function accepted(r: IntakeResponse) {
    change(r.profile);
    setIntake(r.intake);
    setWarnings(r.warnings || []);
    setIntakeMetrics(r.metrics || null);
  }
  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function loadDemo() {
    accepted(await api<IntakeResponse>("/demo"));
  }
  async function recommend() {
    const checked = await api<IntakeResponse>("/intake/manual", profile);
    accepted(checked);
    const r = await api<RecommendationResponse>("/recommend", {
      profile: checked.profile,
      input_mode: mode,
    });
    setIntake(r.intake);
    setResult(r);
  }
  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Haven home">
          <span className="brand-mark">h</span> haven
          <span className="brand-sub">ADVISOR WORKSPACE</span>
        </a>
        <div className="topbar-right">
          <span className="connection-dot" />
          {config?.demo_mode ? "Offline demo" : "Placement assistant"}
          <span className="avatar">AL</span>
        </div>
      </header>
      <main>
        <div className="hero">
          <div>
            <div className="eyebrow">SENIOR LIVING · THOUGHTFULLY MATCHED</div>
            <h1>
              A better next chapter
              <br />
              <em>starts with listening.</em>
            </h1>
            <p>
              Understand their needs. Explore the right communities.
              <br />
              Make every recommendation clear and considered.
            </p>
          </div>
          <div className="hero-side">
            <span className="leaf">✳</span>
            <p>
              Human understanding.
              <br />
              Transparent recommendations.
            </p>
            {config?.demo_mode && (
              <button
                className="secondary"
                disabled={busy || liveActive}
                onClick={() =>
                  run(async () => {
                    setMode("manual");
                    const r = await api<IntakeResponse>("/demo");
                    accepted(r);
                    setResult(
                      await api<RecommendationResponse>("/recommend", {
                        profile: r.profile,
                        input_mode: "demo",
                      }),
                    );
                  })
                }
              >
                Launch Demo <span aria-hidden="true">↗</span>
              </button>
            )}
          </div>
        </div>
        {config?.auth_required && (
          <div className="access">
            <label>
              Advisor access token
              <input
                type="password"
                autoComplete="off"
                value={token}
                onChange={(e) => {
                  setToken(e.target.value);
                  setAdvisorToken(e.target.value);
                }}
                placeholder="Provided by your administrator"
              />
            </label>
            <span className="hint">Kept in this tab's memory only.</span>
          </div>
        )}
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <div className="workspace-grid">
          <section className="card intake-card">
            <div className="section-heading">
              <div>
                <span className="eyebrow">01 / UNDERSTAND</span>
                <h2>The client conversation</h2>
              </div>
              <span className="badge">
                {config?.demo_mode ? "Sample data" : "New consultation"}
              </span>
            </div>
            <IntakeModes
              mode={mode}
              setMode={(m) => {
                setMode(m);
                setResult(null);
              }}
              demo={config?.demo_mode ?? true}
              busy={busy}
              onIntake={accepted}
              run={(fn) => void run(fn)}
              loadDemo={loadDemo}
              profile={profile}
              onActive={setLiveActive}
            />
            {warnings.map((w) => (
              <p className="notice" key={w}>
                {w}
              </p>
            ))}
            <div className="profile-heading">
              <h3>Review the client profile</h3>
              <p>
                Confirm extracted facts with the family. * Required to
                recommend.
              </p>
            </div>
            <ProfileForm
              profile={profile}
              onChange={change}
              disabled={busy || liveActive}
            />
            <div className="actions profile-actions">
              <button
                disabled={busy || liveActive || !config}
                onClick={() => run(recommend)}
              >
                {busy ? "Working…" : "Find matching communities"}{" "}
                <span aria-hidden="true">→</span>
              </button>
              <button
                className="text-button"
                disabled={busy || liveActive}
                onClick={() => {
                  change(emptyProfile);
                  setWarnings([]);
                  setIntakeMetrics(null);
                }}
              >
                Clear profile
              </button>
            </div>
          </section>
          <aside className="sidebar">
            <section className="card">
              <span className="eyebrow">02 / CLARIFY</span>
              <h3>
                Good questions.
                <br />
                Better placement.
              </h3>
              <p className="hint">
                Complete the profile to find communities that meet their needs.
              </p>
              <ul className="question-list">
                {(
                  intake?.suggested_questions || [
                    "What level of care is needed?",
                    "What is the monthly budget?",
                    "Which areas feel close to home?",
                    "When would they like to move?",
                  ]
                ).map((q) => (
                  <li key={q}>{q}</li>
                ))}
              </ul>
              {intake?.is_complete && (
                <p className="complete">✓ Essential details complete</p>
              )}
            </section>
            <section className="principle-card">
              <span className="eyebrow">HOW MATCHING WORKS</span>
              <h3>Care comes first.</h3>
              <p>
                Every community must meet care and budget requirements before it
                is scored.
              </p>
              <p>
                Compare affordability, location, availability and supported
                preferences. Inspect the evidence behind every score.
              </p>
              <span className="small-rule" />
              <p className="hint">
                AI helps capture and explain. The ranking follows explicit,
                reproducible rules.
              </p>
            </section>
            {intakeMetrics && (
              <details className="card">
                <summary>Intake metrics</summary>
                <p>
                  {intakeMetrics.intake_ms?.toFixed(0)} ms ·{" "}
                  {intakeMetrics.ai_calls} AI calls
                </p>
              </details>
            )}
          </aside>
        </div>
        {result && (
          <Results
            key={result.consultation_id}
            result={result}
            demo={config?.demo_mode ?? true}
          />
        )}
        <footer>
          Haven · Senior Living Placement Assistant{" "}
          <span>
            Confirm current care services, fees and availability before
            placement.
          </span>
        </footer>
      </main>
    </div>
  );
}
