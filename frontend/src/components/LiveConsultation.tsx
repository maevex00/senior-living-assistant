import { useEffect, useRef, useState } from "react";
import {
  LiveConsultationService,
  type LiveState,
} from "../services/geminiLive";
import type { ClientProfile, IntakeResponse } from "../types";

export function LiveConsultation({
  demo,
  profile,
  onIntake,
  loadDemo,
  onActive,
}: {
  demo: boolean;
  profile: ClientProfile;
  onIntake: (r: IntakeResponse) => void;
  loadDemo: () => Promise<void>;
  onActive: (active: boolean) => void;
}) {
  const [state, setState] = useState<LiveState>("disconnected");
  const [mode, setMode] = useState<"conversation" | "assist">("conversation");
  const [transcript, setTranscript] = useState("");
  const [guidance, setGuidance] = useState<string[]>([]);
  const [error, setError] = useState("");
  const service = useRef<LiveConsultationService | null>(null);
  const current = useRef({ onIntake, onActive });
  current.current = { onIntake, onActive };
  useEffect(
    () => () => {
      service.current?.stop();
      current.current.onActive(false);
    },
    [],
  );
  const active = !["error", "disconnected"].includes(state);
  async function start() {
    setError("");
    setTranscript("");
    setGuidance([]);
    if (demo) {
      try {
        setState("processing");
        await loadDemo();
        setTranscript(
          "Offline simulation loaded: Margaret is seeking enhanced assisted living near Rochester, with a $4,500 monthly budget.",
        );
        setState("disconnected");
      } catch (e) {
        setError((e as Error).message);
        setState("error");
      }
      return;
    }
    service.current = new LiveConsultationService(
      {
        state: (s) => {
          setState(s);
          current.current.onActive(!["error", "disconnected"].includes(s));
        },
        transcript: (t) => setTranscript((old) => (old + t).slice(-50000)),
        intake: (r) => current.current.onIntake(r),
        guidance: setGuidance,
        error: setError,
      },
      profile,
    );
    await service.current.start(mode);
  }
  return (
    <div className="mode-panel live-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">
            {demo ? "OFFLINE SIMULATION" : "LIVE CONSULTATION"}
          </span>
          <h3>A conversation, with a clearer next step.</h3>
        </div>
        <span className={`status ${active ? "on" : ""}`}>{state}</span>
      </div>
      <label>
        Consultation style
        <select
          disabled={active}
          value={mode}
          onChange={(e) => setMode(e.target.value as typeof mode)}
        >
          <option value="conversation">AI conversation</option>
          <option value="assist">Agent assist · silent audio output</option>
        </select>
      </label>
      <p>
        {demo
          ? "Explore the sample without a microphone or external connection."
          : "Starting shares microphone audio with Google Gemini. Confirm participant consent before continuing. Calls may end at the service time limit; reconnect to continue."}
      </p>
      <div className="actions">
        <button disabled={active} onClick={start}>
          {demo ? "Simulate consultation" : "Start call"}
        </button>
        {active && (
          <>
            <button
              className="secondary"
              disabled={state === "connecting"}
              onClick={() =>
                void (state === "paused"
                  ? service.current?.resume()
                  : service.current?.pause())
              }
            >
              {state === "paused" ? "Resume" : "Pause"}
            </button>
            <button
              className="secondary"
              onClick={() => service.current?.stop()}
            >
              End call
            </button>
          </>
        )}
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {transcript && (
        <div className="transcript">
          <strong>{demo ? "Sample conversation" : "Live transcript"}</strong>
          <p>{transcript}</p>
        </div>
      )}
      {!!guidance.length && (
        <aside>
          <h4>Advisor guidance · AI suggestions</h4>
          {guidance.map((g, i) => (
            <p key={i}>{g}</p>
          ))}
        </aside>
      )}
    </div>
  );
}
