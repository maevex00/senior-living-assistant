import { useState } from "react";
import { api } from "../services/api";
import type { ClientProfile, IntakeResponse, InputMode } from "../types";
import { LiveConsultation } from "./LiveConsultation";

export function IntakeModes({
  mode,
  setMode,
  demo,
  busy,
  onIntake,
  run,
  loadDemo,
  profile,
  onActive,
}: {
  mode: InputMode;
  setMode: (m: InputMode) => void;
  demo: boolean;
  busy: boolean;
  onIntake: (r: IntakeResponse) => void;
  run: (fn: () => Promise<void>) => void;
  loadDemo: () => Promise<void>;
  profile: ClientProfile;
  onActive: (active: boolean) => void;
}) {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  return (
    <>
      <div className="modes" role="tablist" aria-label="Consultation input">
        {(
          [
            ["live", "Live consultation"],
            ["audio", "Audio upload"],
            ["text", "Text / transcript"],
            ["manual", "Manual intake"],
          ] as const
        ).map(([id, label]) => (
          <button
            role="tab"
            aria-selected={mode === id}
            disabled={busy}
            className={mode === id ? "active" : ""}
            key={id}
            onClick={() => setMode(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {mode === "text" && (
        <div className="mode-panel">
          <label>
            Consultation notes
            <textarea
              rows={6}
              value={text}
              maxLength={50000}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste your conversation or advisor notes…"
            />
          </label>
          <button
            disabled={busy || !text.trim()}
            onClick={() =>
              run(async () =>
                onIntake(await api<IntakeResponse>("/intake/text", { text })),
              )
            }
          >
            Extract profile
          </button>
        </div>
      )}
      {mode === "audio" && (
        <div className="mode-panel upload">
          <span className="eyebrow">CONSULTATION RECORDING</span>
          <h3>Turn a conversation into a care profile.</h3>
          <p>MP3, WAV, M4A, WEBM, OGG or FLAC · up to 10 MB</p>
          <label>
            Choose recording
            <input
              type="file"
              accept=".mp3,.wav,.m4a,.webm,.ogg,.flac"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </label>
          <button
            disabled={busy || !file || demo}
            onClick={() =>
              run(async () => {
                if (!file) return;
                if (file.size > 10 * 1024 * 1024)
                  throw new Error("Choose a file smaller than 10 MB.");
                const form = new FormData();
                form.append("audio", file);
                onIntake(await api<IntakeResponse>("/intake/audio", form));
              })
            }
          >
            Understand audio
          </button>
          {demo && (
            <p>
              Offline demo uses the sample consultation. Audio is not sent to an
              AI service.
            </p>
          )}
        </div>
      )}
      {mode === "live" && (
        <LiveConsultation
          demo={demo}
          profile={profile}
          onIntake={onIntake}
          loadDemo={loadDemo}
          onActive={onActive}
        />
      )}
      {mode === "manual" && (
        <p className="mode-note">
          Start with what you know. Review the profile below before finding
          communities.
        </p>
      )}
    </>
  );
}
