import { beforeEach, describe, expect, it, vi } from "vitest";
import { emptyProfile } from "../types";
import { LiveConsultationService } from "./geminiLive";

const mocks = vi.hoisted(() => ({ connect: vi.fn(), api: vi.fn() }));
vi.mock("@google/genai", () => ({
  Modality: { AUDIO: "AUDIO" },
  GoogleGenAI: class {
    live = { connect: mocks.connect };
  },
}));
vi.mock("./api", () => ({ api: mocks.api }));

function setup() {
  const stop = vi.fn(),
    track = { enabled: true, stop };
  const context = {
    state: "running",
    resume: vi.fn(),
    suspend: vi.fn(),
    close: vi.fn(),
    destination: {},
    audioWorklet: { addModule: vi.fn() },
    createMediaStreamSource: vi.fn(() => ({
      connect: vi.fn(),
      disconnect: vi.fn(),
    })),
  };
  vi.stubGlobal(
    "AudioContext",
    class {
      constructor() {
        return context;
      }
    },
  );
  vi.stubGlobal(
    "AudioWorkletNode",
    class {
      port = { onmessage: null };
      connect = vi.fn();
      disconnect = vi.fn();
    },
  );
  vi.stubGlobal("navigator", {
    mediaDevices: {
      getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [track] }),
    },
  });
  const session = {
    close: vi.fn(),
    sendRealtimeInput: vi.fn(),
    sendToolResponse: vi.fn(),
  };
  mocks.api.mockResolvedValue({ token: "ephemeral", model: "test-live" });
  mocks.connect.mockResolvedValue(session);
  const callbacks = {
    state: vi.fn(),
    transcript: vi.fn(),
    intake: vi.fn(),
    guidance: vi.fn(),
    error: vi.fn(),
  };
  return {
    stop,
    track,
    context,
    session,
    callbacks,
    service: new LiveConsultationService(callbacks, emptyProfile),
  };
}
beforeEach(() => {
  vi.resetAllMocks();
  vi.unstubAllGlobals();
});
describe("live lifecycle", () => {
  it("pauses microphone, resumes and closes every resource", async () => {
    const { service, track, context, session, stop, callbacks } = setup();
    await service.start("assist");
    expect(callbacks.state).toHaveBeenLastCalledWith("active");
    await service.pause();
    expect(track.enabled).toBe(false);
    expect(context.suspend).toHaveBeenCalled();
    await service.resume();
    expect(track.enabled).toBe(true);
    service.stop();
    expect(stop).toHaveBeenCalled();
    expect(context.close).toHaveBeenCalled();
    expect(session.close).toHaveBeenCalled();
  });
  it("cleans microphone after token or connection failure", async () => {
    const { service, stop, context, callbacks } = setup();
    mocks.api.mockRejectedValue(new Error("upstream secret"));
    await service.start("conversation");
    expect(stop).toHaveBeenCalled();
    expect(context.close).toHaveBeenCalled();
    expect(callbacks.error).toHaveBeenCalled();
    expect(callbacks.error.mock.calls[0][0]).not.toContain("secret");
  });
  it("closes microphone on remote disconnect", async () => {
    const { service, stop, callbacks } = setup();
    await service.start("assist");
    mocks.connect.mock.calls[0][0].callbacks.onclose();
    expect(stop).toHaveBeenCalled();
    expect(callbacks.state).toHaveBeenLastCalledWith("disconnected");
  });
  it("stops a late microphone grant after an early end", async () => {
    const { service, stop, context } = setup();
    let resolveStream: (value: unknown) => void = () => {};
    vi.stubGlobal("navigator", {
      mediaDevices: {
        getUserMedia: () =>
          new Promise((resolve) => {
            resolveStream = resolve;
          }),
      },
    });
    const pending = service.start("assist");
    await Promise.resolve();
    service.stop();
    resolveStream({ getTracks: () => [{ stop }] });
    await pending;
    expect(stop).toHaveBeenCalled();
    expect(context.close).toHaveBeenCalled();
    expect(mocks.connect).not.toHaveBeenCalled();
  });
});
