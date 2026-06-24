from io import StringIO
import pandas as pd

DEMO_TRANSCRIPT = (
    "Hi, this is Sarah Johnson calling on behalf of my mother, Margaret Johnson. "
    "She's 78 years old and was recently diagnosed with mild cognitive impairment "
    "following a minor stroke. She's been in a rehab facility for the past three "
    "weeks and her care team recommends she transition to an assisted living "
    "community with enhanced care services.\n\n"
    "Margaret is mentally pretty sharp day-to-day — she just needs help with "
    "medication management, bathing, and mobility. She has a small dog named "
    "Biscuit, so pet-friendly would be great, but it's not a dealbreaker.\n\n"
    "We're looking at communities in the Rochester or Brighton area, ideally "
    "within 10 to 15 miles so the family can visit easily. Her monthly budget is "
    "around $4,000, though we could stretch to $4,500 if the place is a really "
    "good fit.\n\n"
    "She'll be discharged in about three to four weeks, so we're looking at a "
    "fairly immediate move-in — within the next month or two. Margaret is "
    "available for tours on weekday afternoons. You can reach me at 585-555-0142 "
    "or sarah.johnson@email.com. Thank you so much."
)

DEMO_PREFERENCES = {
    "name_of_patient": "Margaret Johnson",
    "age_of_patient": "78",
    "injury_or_reason": "Mild cognitive impairment following minor stroke; needs help with medication management, bathing, and mobility",
    "primary_contact_information": {
        "name": "Sarah Johnson",
        "phone_number": "585-555-0142",
        "email": "sarah.johnson@email.com",
    },
    "mentally": "Sharp day-to-day, mild cognitive impairment",
    "care_level": "Assisted Living",
    "preferred_location": ["Rochester, NY", "Brighton, NY"],
    "enhanced": "yes",
    "enriched": "no",
    "move_in_window": "Immediate (0-1 months)",
    "max_budget": 4500,
    "pet_friendly": "preferred",
    "tour_availability": ["Weekday afternoons"],
    "other_keywords": {"pet": "small dog named Biscuit"},
}

_DEMO_CSV = """\
CommunityID,Type of Service,Apartment Type,Enhanced,Enriched,Monthly Fee,Contract (w rate)?,Work with Placement?,ZIP,Est. Waitlist Length
ALL-001,Assisted Living,Studio,yes,no,3200,yes,yes,14618,1-2 months
ALL-002,Assisted Living,1-Bedroom,yes,yes,3800,yes,yes,14610,None
ALL-003,Assisted Living,Studio,no,no,2900,no,yes,14614,None
ALL-004,Memory Care,Studio,yes,yes,4500,yes,yes,14623,2-3 months
ALL-005,Assisted Living,Studio,yes,no,3400,yes,yes,14534,None
ALL-006,Independent Living,1-Bedroom,no,no,2400,no,yes,14580,None
ALL-007,Assisted Living,2-Bedroom,yes,yes,4200,yes,yes,14612,1 month
ALL-008,Memory Care,Studio,yes,yes,5000,no,yes,14620,None
ALL-009,Assisted Living,Studio,no,no,3100,no,no,14607,None
ALL-010,Assisted Living,Studio,yes,yes,4400,yes,yes,14526,3 months
ALL-011,Assisted Living,1-Bedroom,yes,no,3600,yes,yes,14617,None
ALL-012,Memory Care,Studio,yes,yes,5200,no,yes,14625,1 month
ALL-013,Assisted Living,Studio,no,no,2800,no,no,14619,None
ALL-014,Assisted Living,Studio,yes,yes,3900,yes,yes,14609,None
ALL-015,Independent Living,2-Bedroom,no,no,2600,no,yes,14642,None
"""


def load_demo_communities() -> pd.DataFrame:
    return pd.read_csv(StringIO(_DEMO_CSV))
