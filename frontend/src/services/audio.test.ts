import { describe, it, expect } from "vitest";
import { pcm16, decodePCM } from "./audio";
import { mergeProfile } from "./geminiLive";
import { emptyProfile } from "../types";

describe("audio conversion", () => {
  it("encodes signed little-endian PCM and clamps extremes", () => {
    const encoded = pcm16(new Float32Array([-2, -1, 0, 0.5, 1, 2]));
    const bytes = Uint8Array.from(atob(encoded), (x) => x.charCodeAt(0));
    expect(Array.from(bytes.slice(0, 4))).toEqual([0, 128, 0, 128]);
    expect(Array.from(decodePCM(encoded))).toEqual([
      -1,
      -1,
      0,
      0.5,
      32767 / 32768,
      32767 / 32768,
    ]);
  });
  it("supports silence and empty buffers", () => {
    expect(pcm16(new Float32Array())).toBe("");
    expect(Array.from(decodePCM("AAA="))).toEqual([0]);
  });
});
describe("live profile boundary", () => {
  it("preserves facts when an update omits or nulls fields", () => {
    const before = {
      ...emptyProfile,
      patient_name: "Resident",
      max_budget: 4500,
      preferred_locations: ["14618"],
      enhanced_required: true,
    };
    const after = mergeProfile(before, {
      patient_name: null,
      preferred_locations: [],
      max_budget: 5000,
      enhanced_required: false,
    });
    expect(after.patient_name).toBe("Resident");
    expect(after.preferred_locations).toEqual(["14618"]);
    expect(after.max_budget).toBe(5000);
    expect(after.enhanced_required).toBe(false);
  });
  it("never accepts rankings or unknown keys from a live function", () => {
    const after = mergeProfile(emptyProfile, {
      rankings: ["invented"],
      final_score: 100,
      care_level: "AL",
    });
    expect(after).not.toHaveProperty("rankings");
    expect(after).not.toHaveProperty("final_score");
  });
});
