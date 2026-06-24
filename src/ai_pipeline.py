import re
import json
import tempfile
import pandas as pd
from pathlib import Path
from openai import OpenAI

_EXTRACTION_SYSTEM = """
You are a JSON generator for senior living placement.
Output ONLY valid JSON — no markdown, no explanations, no code blocks.

RULES:
1. Extract the PATIENT's information (the person who needs care), not the caller.
2. "max_budget": numeric monthly max (e.g. 4000 for "$4,000/month"). null if absent.
3. "care_level": one of ["Independent Living","Assisted Living","Enhanced Assisted Living","Memory Care"].
4. "enhanced"/"enriched": "yes" only if explicitly stated as a requirement.
5. "preferred_location": list of "City, State" strings.
6. "move_in_window": one of ["Immediate (0-1 months)","Near-term (1-6 months)","Flexible (6+ months)"].

JSON STRUCTURE:
{
  "name_of_patient": "",
  "age_of_patient": "",
  "injury_or_reason": "",
  "primary_contact_information": {"name":"","phone_number":"","email":""},
  "mentally": "",
  "care_level": "",
  "preferred_location": [],
  "enhanced": "",
  "enriched": "",
  "move_in_window": "",
  "max_budget": null,
  "pet_friendly": "",
  "tour_availability": [],
  "other_keywords": {}
}
"""


def _regex_budget_fallback(transcript: str) -> int | None:
    """Extract a budget number from free text when GPT returns null."""
    for pattern in [
        r'\$\s*([\d,]+(?:\.\d{2})?)',
        r'([\d,]+)\s*(?:dollars?|per\s*month|/month)',
        r'(?:budget|maximum|max|up to)\s*(?:is|of)?\s*\$?\s*([\d,]+)',
    ]:
        matches = re.findall(pattern, transcript, re.IGNORECASE)
        if matches:
            try:
                return int(max(float(m.replace(",", "")) for m in matches))
            except (ValueError, TypeError):
                pass
    return None


def transcribe_audio(client: OpenAI, audio_bytes: bytes, ext: str) -> str:
    """Write audio to a temp file, send to Whisper, return transcript text."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
        tmp.write(audio_bytes)
        fp = tmp.name
    try:
        with open(fp, "rb") as f:
            result = client.audio.transcriptions.create(model="whisper-1", file=f)
        return result.text
    finally:
        Path(fp).unlink(missing_ok=True)


def extract_preferences(client: OpenAI, transcript: str) -> dict:
    """Use GPT-4o (JSON mode) to extract structured client preferences from a transcript."""
    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _EXTRACTION_SYSTEM},
            {"role": "user", "content": (
                "Extract structured information from this consultation transcript.\n\n"
                f"TRANSCRIPT:\n{transcript}\n\nReturn ONLY valid JSON."
            )},
        ],
    )
    prefs = json.loads(response.choices[0].message.content)
    if not prefs.get("max_budget"):
        prefs["max_budget"] = _regex_budget_fallback(transcript)
    return prefs


def batch_generate_explanations(client: OpenAI, communities: list, prefs: dict) -> list:
    """Generate match explanations for all communities in one GPT-4o-mini call."""
    entries = "\n".join(
        f"{i+1}. {c.get('Type of Service','N/A')} in {c.get('Town','N/A')}, "
        f"${c.get('Monthly Fee','N/A')}/mo, "
        f"{round(c['Distance_miles'], 1) if pd.notna(c.get('Distance_miles')) else 'N/A'} mi, "
        f"Priority {c.get('Priority_Level','N/A')}"
        for i, c in enumerate(communities)
    )
    prompt = (
        f"Client: care_level={prefs.get('care_level')}, budget=${prefs.get('max_budget')}, "
        f"locations={prefs.get('preferred_location')}, "
        f"enhanced={prefs.get('enhanced')}, enriched={prefs.get('enriched')}.\n\n"
        f"Communities:\n{entries}\n\n"
        "Write ONE concise sentence (max 25 words) per community explaining why it matches the client. "
        'Return JSON: {"explanations": ["sentence 1", "sentence 2", ...]}'
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=800,
    )
    result = json.loads(response.choices[0].message.content)
    if isinstance(result, list):
        return result
    return result.get("explanations", [])
