export interface ClientProfile {
  patient_name: string | null;
  age: number | null;
  care_level: string | null;
  max_budget: number | null;
  preferred_locations: string[];
  enhanced_required: boolean;
  enriched_required: boolean;
  move_in_window: string | null;
  pet_required: boolean | null;
  apartment_preference: string | null;
  mobility_needs: string[];
  other_preferences: string[];
  primary_contact_name: string | null;
  primary_contact_phone: string | null;
  primary_contact_email: string | null;
}
export const emptyProfile: ClientProfile = {
  patient_name: null,
  age: null,
  care_level: null,
  max_budget: null,
  preferred_locations: [],
  enhanced_required: false,
  enriched_required: false,
  move_in_window: null,
  pet_required: null,
  apartment_preference: null,
  mobility_needs: [],
  other_preferences: [],
  primary_contact_name: null,
  primary_contact_phone: null,
  primary_contact_email: null,
};
export interface Intake {
  is_complete: boolean;
  missing_fields: string[];
  suggested_questions: string[];
}
export interface IntakeResponse {
  profile: ClientProfile;
  intake: Intake;
  warnings?: string[];
  metrics?: Record<string, number>;
}
export interface Recommendation {
  community_id: string;
  rank: number;
  final_score: number;
  explanation: string;
  explanation_source: string;
  community: {
    name: string;
    monthly_fee: number;
    zip_code: string;
    care_levels: string[];
    wait_months: number | null;
    business_tier: number;
  };
  score_breakdown: Record<
    string,
    { score: number; reason: string; evidence: Record<string, unknown> }
  >;
  active_weights: Record<string, number>;
  reasons: string[];
  unscored_dimensions: string[];
}
export interface RecommendationResponse {
  recommendations: Recommendation[];
  intake: Intake;
  exclusions: { community_id: string; reasons: string[] }[];
  metrics: Record<string, number>;
  warnings: string[];
  eligible_count: number;
  total_communities: number;
  consultation_id: string;
  receipt: string | null;
}
export type InputMode = "live" | "audio" | "text" | "manual" | "demo";
