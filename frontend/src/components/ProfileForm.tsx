import type { ClientProfile } from "../types";

export function ProfileForm({
  profile,
  onChange,
  disabled,
}: {
  profile: ClientProfile;
  onChange: (p: ClientProfile) => void;
  disabled: boolean;
}) {
  const set = (key: keyof ClientProfile, value: unknown) =>
    onChange({ ...profile, [key]: value });
  const textField = (
    key: keyof ClientProfile,
    label: string,
    type = "text",
  ) => (
    <label key={key}>
      {label}
      <input
        type={type}
        value={String(profile[key] ?? "")}
        maxLength={300}
        onChange={(e) => set(key, e.target.value || null)}
      />
    </label>
  );
  return (
    <fieldset disabled={disabled} className="profile-grid">
      {textField("patient_name", "Resident name")}
      <label>
        Age
        <input
          type="number"
          min="0"
          max="120"
          value={profile.age ?? ""}
          onChange={(e) =>
            set("age", e.target.value ? Number(e.target.value) : null)
          }
        />
      </label>
      <label>
        Care level *
        <select
          value={profile.care_level ?? ""}
          onChange={(e) => set("care_level", e.target.value || null)}
        >
          <option value="">Choose care level</option>
          {[
            "Independent Living",
            "Assisted Living",
            "Enhanced Assisted Living",
            "Memory Care",
          ].map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
      </label>
      <label>
        Monthly budget ($) *
        <input
          type="number"
          min="1"
          max="1000000"
          value={profile.max_budget ?? ""}
          onChange={(e) =>
            set("max_budget", e.target.value ? Number(e.target.value) : null)
          }
        />
      </label>
      <label className="span-2">
        Preferred locations *{" "}
        <span className="hint">Separate areas with ;</span>
        <input
          value={profile.preferred_locations.join("; ")}
          onChange={(e) =>
            set("preferred_locations", e.target.value.split(";"))
          }
          placeholder="Rochester, NY; Brighton, NY"
        />
      </label>
      <label>
        Move-in timeline
        <select
          value={profile.move_in_window ?? ""}
          onChange={(e) => set("move_in_window", e.target.value || null)}
        >
          <option value="">Not yet known</option>
          {["Immediate", "Near-term", "Flexible"].map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
      </label>
      <label>
        Pet preference
        <select
          value={
            profile.pet_required === null ? "" : String(profile.pet_required)
          }
          onChange={(e) =>
            set(
              "pet_required",
              e.target.value === "" ? null : e.target.value === "true",
            )
          }
        >
          <option value="">Not yet known</option>
          <option value="true">Pet-friendly needed</option>
          <option value="false">No pet requirement</option>
        </select>
      </label>
      <label>
        Apartment preference
        <select
          value={profile.apartment_preference ?? ""}
          onChange={(e) => set("apartment_preference", e.target.value || null)}
        >
          <option value="">No preference</option>
          {["Studio", "1-Bedroom", "2-Bedroom"].map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
      </label>
      <div className="checks">
        <label>
          <input
            type="checkbox"
            checked={profile.enhanced_required}
            onChange={(e) => set("enhanced_required", e.target.checked)}
          />{" "}
          Enhanced care required
        </label>
        <label>
          <input
            type="checkbox"
            checked={profile.enriched_required}
            onChange={(e) => set("enriched_required", e.target.checked)}
          />{" "}
          Enriched care required
        </label>
      </div>
      {(["mobility_needs", "other_preferences"] as const).map((key) => (
        <label className="span-2" key={key}>
          {key === "mobility_needs" ? "Mobility needs" : "Other preferences"}
          <input
            value={profile[key].join("; ")}
            onChange={(e) => set(key, e.target.value.split(";"))}
            placeholder="Separate entries with ;"
          />
        </label>
      ))}
      {textField("primary_contact_name", "Contact name")}
      {textField("primary_contact_phone", "Contact phone", "tel")}
      {textField("primary_contact_email", "Contact email", "email")}
    </fieldset>
  );
}
