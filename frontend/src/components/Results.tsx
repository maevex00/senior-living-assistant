import { useState } from "react";
import { api } from "../services/api";
import type { RecommendationResponse } from "../types";

export function Results({
  result,
  demo,
}: {
  result: RecommendationResponse;
  demo: boolean;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [notes, setNotes] = useState("");
  const [crm, setCRM] = useState("");
  const [saving, setSaving] = useState(false);
  async function save() {
    setSaving(true);
    try {
      const r = await api<{
        crm_logged: boolean;
        crm_error?: string;
        message?: string;
      }>("/consultations/log", {
        receipt: result.receipt,
        selected_community_ids: selected,
        advisor_notes: notes,
      });
      setCRM(
        r.crm_logged
          ? "Consultation saved to Google Sheets."
          : r.crm_error || r.message || "Not saved.",
      );
    } catch (e) {
      setCRM((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  function download() {
    const blob = new Blob([JSON.stringify(result, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "community-recommendations.json";
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <section className="results" aria-label="Recommendations">
      <div className="section-heading">
        <div>
          <span className="eyebrow">YOUR SHORTLIST</span>
          <h2>Communities to consider</h2>
        </div>
        <span className="badge">
          {result.eligible_count} eligible / {result.total_communities} reviewed
        </span>
      </div>
      {result.warnings.map((w) => (
        <p className="notice" key={w}>
          {w}
        </p>
      ))}
      {!result.recommendations.length && (
        <div className="card">
          <h3>
            {result.intake.is_complete
              ? "No eligible communities"
              : "A few details are still needed"}
          </h3>
          <p>
            {result.intake.is_complete
              ? "Review the exclusion reasons or adjust the profile with the family. Eligibility rules have not been relaxed."
              : "Complete care level, budget and location before ranking."}
          </p>
        </div>
      )}
      {result.recommendations.map((r) => (
        <article className="recommendation" key={r.community_id}>
          <div className="rank-number">{String(r.rank).padStart(2, "0")}</div>
          <div className="recommendation-body">
            <div className="section-heading">
              <div>
                <h3>{r.community.name}</h3>
                <p>
                  {r.community.care_levels.join(" · ")} · ZIP{" "}
                  {r.community.zip_code}
                </p>
              </div>
              <div className="score">
                {r.final_score.toFixed(1)}
                <span>fit score / 100</span>
              </div>
            </div>
            <div className="pills">
              <span>${r.community.monthly_fee.toLocaleString()} / month</span>
              <span>
                {r.community.wait_months === null
                  ? "Availability unconfirmed"
                  : `${r.community.wait_months} month estimated wait`}
              </span>
            </div>
            <p className="explanation">{r.explanation}</p>
            <span className="hint">
              {r.explanation_source === "gemini"
                ? "AI-written summary · verify against evidence below"
                : "Evidence-based summary"}
            </span>
            <details>
              <summary>Why this community · score breakdown</summary>
              <div className="breakdown">
                {Object.entries(r.score_breakdown).map(([key, d]) => (
                  <div key={key}>
                    <div className="section-heading">
                      <strong>{key.replaceAll("_", " ")}</strong>
                      <span>
                        {d.score.toFixed(1)} ·{" "}
                        {((r.active_weights[key] || 0) * 100).toFixed(1)}%
                        weight
                      </span>
                    </div>
                    <meter min="0" max="100" value={d.score} />
                    <p>{d.reason}</p>
                  </div>
                ))}
              </div>
              <p className="hint">
                Business relationship only breaks equal suitability scores. Not
                scored: {r.unscored_dimensions.join(", ") || "none"}.
              </p>
            </details>
            <label className="select-community">
              <input
                type="checkbox"
                checked={selected.includes(r.community_id)}
                onChange={(e) =>
                  setSelected(
                    e.target.checked
                      ? [...selected, r.community_id]
                      : selected.filter((id) => id !== r.community_id),
                  )
                }
              />{" "}
              Include in CRM shortlist
            </label>
          </div>
        </article>
      ))}
      {!!result.exclusions.length && (
        <details className="card">
          <summary>{result.exclusions.length} communities excluded</summary>
          {result.exclusions.map((e) => (
            <p key={e.community_id}>
              <strong>{e.community_id}</strong> — {e.reasons.join(" ")}
            </p>
          ))}
        </details>
      )}
      <div className="card">
        <h3>Pipeline metrics</h3>
        <div className="metrics">
          <div>
            <strong>{result.metrics.total_ms.toFixed(0)} ms</strong>
            <span>This recommendation request</span>
          </div>
          <div>
            <strong>{result.metrics.ranking_ms.toFixed(1)} ms</strong>
            <span>Deterministic ranking</span>
          </div>
          <div>
            <strong>{result.metrics.ai_calls}</strong>
            <span>Explanation API calls</span>
          </div>
        </div>
        <p className="hint">
          Request timings, not a benchmark. Intake time is separate.
        </p>
      </div>
      {!!result.receipt && (
        <div className="card">
          <h3>Keep the next step in view</h3>
          <label>
            Advisor notes
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={5000}
              rows={3}
              placeholder="Tour preferences, follow-up plans, facts to confirm…"
            />
          </label>
          <div className="actions">
            <button disabled={saving} onClick={save}>
              {saving
                ? "Saving…"
                : demo
                  ? "Preview CRM save"
                  : "Save consultation to CRM"}
            </button>
            <button className="secondary" onClick={download}>
              Download results
            </button>
          </div>
          <p role="status">{crm}</p>
        </div>
      )}
    </section>
  );
}
