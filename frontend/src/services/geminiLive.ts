import type { Session, LiveServerMessage } from "@google/genai";
import { api } from "./api";
import { AudioPlayback, pcm16 } from "./audio";
import {
  emptyProfile,
  type ClientProfile,
  type IntakeResponse,
} from "../types";

export type LiveState =
  "disconnected" | "connecting" | "active" | "paused" | "processing" | "error";
export function mergeProfile(
  current: ClientProfile,
  update: Record<string, unknown>,
): ClientProfile {
  const merged = { ...current };
  for (const key of Object.keys(emptyProfile) as (keyof ClientProfile)[]) {
    const value = update[key];
    if (
      value !== undefined &&
      value !== null &&
      value !== "" &&
      !(Array.isArray(value) && value.length === 0)
    )
      Object.assign(merged, { [key]: value });
  }
  return merged;
}

interface Callbacks {
  state: (s: LiveState) => void;
  transcript: (text: string) => void;
  intake: (r: IntakeResponse) => void;
  guidance: (items: string[]) => void;
  error: (message: string) => void;
}

export class LiveConsultationService {
  private session?: Session;
  private context?: AudioContext;
  private stream?: MediaStream;
  private capture?: AudioWorkletNode;
  private source?: MediaStreamAudioSourceNode;
  private playback?: AudioPlayback;
  private closed = false;
  private paused = false;
  private queue = Promise.resolve();
  private cancelled = new Set<string>();
  private profile: ClientProfile;
  constructor(
    private callbacks: Callbacks,
    initial: ClientProfile,
  ) {
    this.profile = { ...initial };
  }

  async start(mode: "conversation" | "assist") {
    this.callbacks.state("connecting");
    try {
      this.context = new AudioContext({ sampleRate: 16000 });
      this.playback = new AudioPlayback(this.context);
      await this.context.resume();
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      if (this.closed) {
        this.cleanup();
        return;
      }
      await this.context.audioWorklet.addModule("/pcm-worklet.js");
      const token = await api<{ token: string; model: string }>("/live/token", {
        mode,
      });
      if (this.closed) {
        this.cleanup();
        return;
      }
      const { GoogleGenAI, Modality } = await import("@google/genai");
      if (this.closed) {
        this.cleanup();
        return;
      }
      const client = new GoogleGenAI({
        apiKey: token.token,
        httpOptions: { apiVersion: "v1beta" },
      });
      this.session = await client.live.connect({
        model: token.model,
        config: { responseModalities: [Modality.AUDIO] },
        callbacks: {
          onmessage: (message: LiveServerMessage) =>
            this.message(message, mode),
          onerror: () =>
            this.fail(
              "Live connection failed. End the call and reconnect; your reviewed profile is preserved.",
            ),
          onclose: () => {
            if (!this.closed) {
              this.closed = true;
              this.cleanup();
              this.callbacks.state("disconnected");
            }
          },
        },
      });
      if (this.closed) {
        this.session.close();
        this.cleanup();
        return;
      }
      this.source = this.context.createMediaStreamSource(this.stream);
      this.capture = new AudioWorkletNode(this.context, "pcm-capture");
      this.capture.port.onmessage = (e: MessageEvent<Float32Array>) => {
        if (!this.closed && !this.paused)
          this.session?.sendRealtimeInput({
            audio: { data: pcm16(e.data), mimeType: "audio/pcm;rate=16000" },
          });
      };
      this.source.connect(this.capture);
      // The worklet has no output, so it cannot play the microphone back.
      this.capture.connect(this.context.destination);
      this.callbacks.state("active");
    } catch {
      this.fail(
        "Unable to start voice. Check microphone permission, advisor access and Gemini configuration.",
      );
    }
  }

  private message(message: LiveServerMessage, mode: "conversation" | "assist") {
    if (this.closed) return;
    const content = message.serverContent;
    if (content?.interrupted) this.playback?.clear();
    if (content?.inputTranscription?.text)
      this.callbacks.transcript(content.inputTranscription.text);
    if (mode === "conversation" && !this.paused)
      for (const part of content?.modelTurn?.parts || [])
        if (part.inlineData?.data) this.playback?.play(part.inlineData.data);
    for (const id of message.toolCallCancellation?.ids || [])
      this.cancelled.add(id);
    for (const call of message.toolCall?.functionCalls || []) {
      this.queue = this.queue
        .then(async () => {
          if (this.closed || this.cancelled.has(call.id || "")) return;
          let response: Record<string, unknown> = { error: "Unknown function" };
          if (call.name === "updateDashboard") {
            try {
              this.callbacks.state("processing");
              const args = call.args || {};
              const update = args.clientProfile;
              if (
                !update ||
                typeof update !== "object" ||
                Array.isArray(update)
              )
                throw new Error("Invalid profile");
              const merged = mergeProfile(
                this.profile,
                update as Record<string, unknown>,
              );
              const validated = await api<IntakeResponse>(
                "/intake/manual",
                merged,
              );
              if (this.closed || this.cancelled.has(call.id || "")) return;
              this.profile = validated.profile;
              this.callbacks.intake(validated);
              const guidance = Array.isArray(args.advisorGuidance)
                ? args.advisorGuidance
                    .filter((x): x is string => typeof x === "string")
                    .slice(0, 5)
                : [];
              this.callbacks.guidance(guidance);
              response = {
                accepted: true,
                missing_fields: validated.intake.missing_fields,
                suggested_questions: validated.intake.suggested_questions,
              };
            } catch {
              response = {
                error:
                  "Profile validation failed. Ask the advisor to review fields.",
              };
              this.callbacks.error(
                "A live profile update could not be validated. Existing fields have been kept.",
              );
            }
          }
          if (!this.closed) {
            this.session?.sendToolResponse({
              functionResponses: [{ id: call.id, name: call.name, response }],
            });
            this.callbacks.state(this.paused ? "paused" : "active");
          }
        })
        .catch(() => this.fail("Live update failed. Reconnect to continue."));
    }
  }
  async pause() {
    this.paused = true;
    this.stream?.getTracks().forEach((t) => (t.enabled = false));
    this.session?.sendRealtimeInput({ audioStreamEnd: true });
    this.playback?.clear();
    await this.context?.suspend();
    if (!this.closed) this.callbacks.state("paused");
  }
  async resume() {
    await this.context?.resume();
    this.stream?.getTracks().forEach((t) => (t.enabled = true));
    this.paused = false;
    if (!this.closed) this.callbacks.state("active");
  }
  stop() {
    this.closed = true;
    this.session?.close();
    this.cleanup();
    this.callbacks.state("disconnected");
  }
  private fail(message: string) {
    if (this.closed) return;
    this.closed = true;
    this.session?.close();
    this.cleanup();
    this.callbacks.error(message);
    this.callbacks.state("error");
  }
  private cleanup() {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.capture?.disconnect();
    this.source?.disconnect();
    this.playback?.clear();
    if (this.context?.state !== "closed") void this.context?.close();
  }
}
