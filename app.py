import pandas as pd
import streamlit as st

from src.data_loader import DEMO_TRANSCRIPT, DEMO_PREFERENCES, load_demo_communities
from src.geo import add_geodata
from src.ranking import filter_and_rank
from src.ai_pipeline import transcribe_audio, extract_preferences, batch_generate_explanations

try:
    import gspread
    from google.oauth2.service_account import Credentials
    _GSHEETS_AVAILABLE = True
except ImportError:
    _GSHEETS_AVAILABLE = False


# ── Google Sheets loader (cached at Streamlit level for secrets access) ───────

@st.cache_data(ttl=300, show_spinner=False)
def load_google_sheet(sheet_name: str, worksheet_name: str | None = None) -> pd.DataFrame:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
    )
    gc = gspread.authorize(creds)
    ws = gc.open(sheet_name)
    worksheet = ws.worksheet(worksheet_name) if worksheet_name else ws.sheet1
    return pd.DataFrame(worksheet.get_all_records())


# ── Page config & session state ───────────────────────────────────────────────

st.set_page_config(page_title="Senior Living Placement Assistant", layout="wide")

_DEFAULTS = {
    "step": "upload",
    "audio_files": None,
    "transcription": None,
    "preferences": None,
    "results": None,
    "explanations": None,
}
for k, v in _DEFAULTS.items():
    st.session_state.setdefault(k, v)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ Configuration")

    demo_mode = st.toggle(
        "🎮 Demo Mode",
        value=False,
        help="Try the full app with sample data — no audio file or Google Sheets credentials needed",
    )
    if demo_mode:
        st.info("Using 15 sample Rochester NY communities and a pre-loaded consultation transcript.")

    st.divider()

    api_key = st.text_input(
        "OpenAI API Key", type="password",
        help="Required for transcription and AI explanations. Not needed in Demo Mode.",
    )
    if api_key:
        if api_key.startswith("sk-"):
            st.success("✅ API Key loaded")
        else:
            st.warning("⚠️ Key should start with 'sk-'")

    st.divider()
    st.subheader("📊 Progress")
    _STEP_LABELS = {
        "upload":      "1️⃣ Upload Audio",
        "transcribe":  "2️⃣ Transcribe",
        "preferences": "3️⃣ Extract Preferences",
        "rank":        "4️⃣ Rank Communities",
        "results":     "5️⃣ View Results",
    }
    _step_keys = list(_STEP_LABELS.keys())
    for key, label in _STEP_LABELS.items():
        if key == st.session_state.step:
            st.markdown(f"**➡️ {label}**")
        elif _step_keys.index(key) < _step_keys.index(st.session_state.step):
            st.markdown(f"✅ {label}")
        else:
            st.markdown(f"⚪ {label}")

    st.divider()
    if st.button("🔄 Start Over", use_container_width=True):
        for k, v in _DEFAULTS.items():
            st.session_state[k] = v
        st.rerun()


st.title("Senior Living Placement Assistant")


# ── STEP 1 — Upload / Demo launch ─────────────────────────────────────────────

if st.session_state.step == "upload":
    if demo_mode:
        st.header("🎮 Demo Mode")
        st.markdown(
            "This demo uses a **sample consultation transcript** and a **synthetic community database** "
            "for Rochester, NY — no credentials required."
        )
        with st.expander("📝 Preview Demo Transcript"):
            st.text(DEMO_TRANSCRIPT)
        if st.button("🚀 Launch Demo", type="primary", use_container_width=True):
            st.session_state.transcription = DEMO_TRANSCRIPT
            st.session_state.preferences = DEMO_PREFERENCES
            st.session_state.step = "rank"
            st.rerun()
    else:
        st.header("Step 1: Upload Audio File")
        st.markdown("📤 Upload a recording of the client consultation call.")
        audio = st.file_uploader("Choose an audio file", type=["m4a", "mp3", "wav", "mp4"])
        if audio:
            st.success(f"✅ **{audio.name}** ({len(audio.getbuffer()) / (1024 * 1024):.2f} MB)")
            st.session_state.audio_files = audio
            if st.button("▶️ Continue to Transcription", type="primary"):
                st.session_state.step = "transcribe"
                st.rerun()


# ── STEP 2 — Transcribe ───────────────────────────────────────────────────────

elif st.session_state.step == "transcribe":
    st.header("Step 2: Transcribe Audio")

    if st.session_state.audio_files:
        st.info(f"📁 Processing: **{st.session_state.audio_files.name}**")

    if not api_key:
        st.warning("⚠️ Please enter your OpenAI API Key in the sidebar.")
        st.stop()

    if st.session_state.transcription:
        st.success("✅ Transcription complete!")
        with st.expander("📝 View Transcription", expanded=True):
            st.text_area("Transcribed Text:", st.session_state.transcription, height=200)
        if st.button("▶️ Continue to Preference Extraction", type="primary"):
            st.session_state.step = "preferences"
            st.rerun()
    else:
        if st.button("🎧 Start Transcription", type="primary"):
            bar = st.progress(0)
            status = st.empty()
            try:
                status.text("🔄 Initializing OpenAI client...")
                bar.progress(20)
                from openai import OpenAI
                client = OpenAI(api_key=api_key)

                audio_file = st.session_state.audio_files
                ext = audio_file.name.rsplit(".", 1)[-1]

                status.text("🎤 Sending to Whisper API (this may take a minute)...")
                bar.progress(50)
                text = transcribe_audio(client, audio_file.getbuffer(), ext)
                st.session_state.transcription = text

                bar.progress(100)
                status.empty()
                bar.empty()
                st.success("✅ Transcription complete!")
                st.rerun()
            except Exception as e:
                status.empty()
                bar.empty()
                st.error(f"❌ Transcription failed: {e}")
                st.info("💡 Check that your API key is valid and has sufficient credits.")


# ── STEP 3 — Extract Preferences ──────────────────────────────────────────────

elif st.session_state.step == "preferences":
    st.header("Step 3: Extract Client Preferences")

    with st.expander("📝 View Transcription"):
        st.text_area("Transcribed Text:", st.session_state.transcription, height=150)

    if st.session_state.preferences:
        st.success("✅ Preferences extracted successfully!")
        with st.expander("🎯 Extracted Preferences", expanded=True):
            st.json(st.session_state.preferences)

        st.markdown("---")
        st.subheader("🔧 Review & Adjust (Optional)")
        col1, col2 = st.columns(2)

        with col1:
            current_budget = st.session_state.preferences.get("max_budget")
            if not current_budget or current_budget in ("", "NULL"):
                st.warning("⚠️ Budget not detected — enter manually if needed.")
                current_budget = None
            new_budget = st.number_input(
                "Monthly Budget ($)", min_value=0, max_value=50000,
                value=int(current_budget) if current_budget else 0, step=100,
            )
            if new_budget > 0 and new_budget != current_budget:
                if st.button("💾 Update Budget"):
                    st.session_state.preferences["max_budget"] = new_budget
                    st.success(f"✅ Budget updated to ${new_budget:,}/month")
                    st.rerun()

        with col2:
            care_options = [
                "Independent Living", "Assisted Living",
                "Enhanced Assisted Living", "Memory Care",
            ]
            current_care = st.session_state.preferences.get("care_level", "")
            default_idx = care_options.index(current_care) if current_care in care_options else 1
            new_care = st.selectbox("Care Level", options=care_options, index=default_idx)
            if new_care != current_care:
                if st.button("💾 Update Care Level"):
                    st.session_state.preferences["care_level"] = new_care
                    st.success(f"✅ Care level updated to {new_care}")
                    st.rerun()

        st.markdown("---")
        if st.button("▶️ Continue to Community Ranking", type="primary"):
            st.session_state.step = "rank"
            st.rerun()

    else:
        if not api_key:
            st.warning("⚠️ Please enter your OpenAI API Key in the sidebar.")
            st.stop()

        if st.button("🔍 Extract Preferences", type="primary"):
            bar = st.progress(0)
            status = st.empty()
            try:
                status.text("🤖 Initializing AI model...")
                bar.progress(20)
                from openai import OpenAI
                client = OpenAI(api_key=api_key)

                status.text("🧠 Analyzing transcript with GPT-4o...")
                bar.progress(55)
                prefs = extract_preferences(client, st.session_state.transcription)

                if prefs.get("max_budget"):
                    st.info(f"💡 Detected budget: ${int(prefs['max_budget']):,}/month")

                st.session_state.preferences = prefs
                bar.progress(100)
                status.empty()
                bar.empty()
                st.success("✅ Preferences extracted!")
                st.rerun()
            except Exception as e:
                status.empty()
                bar.empty()
                st.error(f"❌ Extraction failed: {e}")


# ── STEP 4 — Filter & Rank ────────────────────────────────────────────────────

elif st.session_state.step == "rank":
    st.header("Step 4: Filter & Rank Communities")

    col1, col2 = st.columns(2)
    with col1:
        with st.expander("📝 View Transcription"):
            st.text_area("", st.session_state.transcription, height=100)
    with col2:
        with st.expander("🎯 View Preferences"):
            st.json(st.session_state.preferences)

    if st.session_state.results is not None:
        df = st.session_state.results
        st.success(f"✅ Found {len(df)} matching communities!")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Matches", len(df))
        c2.metric("Priority 1 (Contracted)", len(df[df["Priority_Level"] == 1]))
        if df["Distance_miles"].notna().any():
            c3.metric("Avg Distance", f"{df['Distance_miles'].mean():.1f} mi")
        if df["Monthly Fee"].notna().any():
            c4.metric("Avg Monthly Fee", f"${int(df['Monthly Fee'].mean()):,}")
        if st.button("▶️ View Top Recommendations", type="primary"):
            st.session_state.step = "results"
            st.rerun()

    else:
        if st.button("🎯 Start Ranking", type="primary"):
            bar = st.progress(0)
            status = st.empty()
            try:
                prefs = st.session_state.preferences

                status.text("📥 Loading community database...")
                bar.progress(10)
                if demo_mode:
                    df = load_demo_communities()
                    st.info("🎮 Demo: using 15 sample Rochester NY communities.")
                else:
                    df = load_google_sheet("Living_Locators_Data", "Rochester")
                    st.info(f"📊 Loaded {len(df)} communities from Google Sheets.")

                status.text("🏥 Filtering by care level, budget, and care needs...")
                bar.progress(40)
                df = filter_and_rank(df, prefs)
                st.info(f"✓ {len(df)} communities match the client's criteria.")

                status.text("📍 Calculating distances via pgeocode...")
                bar.progress(70)
                locs = prefs.get("preferred_location", ["Rochester, NY"])
                if isinstance(locs, str):
                    locs = [locs]
                df = add_geodata(df, locs)

                status.text("📊 Sorting by priority tier and distance...")
                bar.progress(95)
                st.session_state.results = df

                bar.progress(100)
                status.empty()
                bar.empty()
                st.success(f"✅ Ranking complete! Found {len(df)} matching communities.")
                st.rerun()

            except Exception as e:
                status.empty()
                bar.empty()
                st.error(f"❌ Ranking failed: {e}")
                import traceback
                with st.expander("🔍 Full Error Trace"):
                    st.code(traceback.format_exc())


# ── STEP 5 — Results ──────────────────────────────────────────────────────────

elif st.session_state.step == "results":
    st.header("🏆 Step 5: Top Recommendations")

    df = st.session_state.results
    prefs = st.session_state.preferences

    col1, col2, col3 = st.columns(3)
    with col1:
        with st.expander("📝 View Transcription"):
            st.text_area("", st.session_state.transcription, height=100, key="r_transcript")
    with col2:
        with st.expander("🎯 View Preferences"):
            st.json(prefs)
    with col3:
        with st.expander("📊 All Matching Communities"):
            display_cols = [c for c in ["Type of Service", "Town", "Monthly Fee", "Distance_miles", "Priority_Level"] if c in df.columns]
            st.dataframe(df[display_cols].head(15), use_container_width=True, hide_index=True)

    st.markdown("---")

    # Pre-generate all explanations in one batched API call, then cache in session
    if st.session_state.explanations is None:
        if api_key and api_key.startswith("sk-"):
            with st.spinner("🤖 Generating AI match explanations..."):
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=api_key)
                    st.session_state.explanations = batch_generate_explanations(
                        client, df.head(15).to_dict("records"), prefs
                    )
                except Exception as e:
                    st.warning(f"⚠️ Could not generate AI explanations: {e}")
                    st.session_state.explanations = []
        else:
            st.session_state.explanations = []

    explanations = st.session_state.explanations or []

    # Client summary
    with st.expander("👤 Client Summary", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Patient Name", prefs.get("name_of_patient", "N/A"))
            st.metric("Age", prefs.get("age_of_patient", "N/A"))
        with c2:
            st.metric("Care Level", prefs.get("care_level", "N/A"))
            budget_val = prefs.get("max_budget")
            st.metric("Max Budget", f"${budget_val:,.0f}/mo" if isinstance(budget_val, (int, float)) else "N/A")
        with c3:
            locs = prefs.get("preferred_location", [])
            if isinstance(locs, list) and locs:
                st.metric("Preferred Areas", len(locs))
                st.caption(", ".join(locs))
            else:
                st.metric("Preferred Area", locs or "N/A")

    st.success(f"🎉 Found **{len(df)}** matching communities across **{df['Priority_Level'].nunique()}** priority tiers.")

    # Results grouped by priority tier
    _TIER_LABELS = {
        1: "🥇 Priority 1 — Contracted Rates",
        2: "🥈 Priority 2 — Placement Partners",
        3: "🥉 Priority 3 — Other Communities",
    }
    _explanation_idx = 0

    for priority in [1, 2, 3]:
        tier_df = df[df["Priority_Level"] == priority]
        if tier_df.empty:
            continue

        st.markdown("---")
        st.markdown(f"### {_TIER_LABELS[priority]}")
        st.caption(f"{len(tier_df)} communities in this tier")

        for idx, (_, row) in enumerate(tier_df.head(5).iterrows(), 1):
            dist_text = f"{round(row['Distance_miles'], 1)} mi" if pd.notna(row.get("Distance_miles")) else "N/A"
            label = f"P{priority}-{idx}. {row.get('Type of Service','N/A')} | {dist_text} | {row.get('Town','N/A')}"

            with st.expander(label, expanded=(priority == 1 and idx <= 2)):
                c1, c2 = st.columns([2, 1])
                town_val = row.get("Town", "N/A")
                state_val = row.get("State", "N/A")

                with c1:
                    st.markdown("#### 📍 Location & Details")
                    st.write(f"**Town:** {town_val}, {state_val}")
                    if pd.notna(row.get("Distance_miles")):
                        st.write(f"**Distance:** {round(row['Distance_miles'], 1)} miles from preferred area")
                    st.write(f"**Service Type:** {row.get('Type of Service','N/A')}")
                    st.write(f"**Apartment Type:** {row.get('Apartment Type','N/A')}")

                with c2:
                    st.markdown("#### 💰 Pricing")
                    if pd.notna(row.get("Monthly Fee")):
                        st.metric("Monthly Fee", f"${int(row['Monthly Fee']):,}")
                    else:
                        st.metric("Monthly Fee", "Contact for pricing")
                    st.metric("Priority Tier", f"Level {int(row.get('Priority_Level', 0))}")
                    st.metric("Rank in Tier", f"#{int(row.get('Rank_Within_Priority', 0))}")

                if _explanation_idx < len(explanations):
                    st.info(f"**🎯 Why this matches:** {explanations[_explanation_idx]}")
                elif not api_key:
                    st.info("💡 Add your OpenAI API key in the sidebar to see AI-powered match explanations.")

                st.markdown("---")
                st.markdown("#### 📋 Additional Details")
                d1, d2 = st.columns(2)
                with d1:
                    st.write(f"**Enhanced:** {row.get('Enhanced','N/A')}")
                    st.write(f"**Enriched:** {row.get('Enriched','N/A')}")
                    st.write(f"**Contract Status:** {row.get('Contract (w rate)?','N/A')}")
                with d2:
                    st.write(f"**Works with Placement:** {row.get('Work with Placement?','N/A')}")
                    st.write(f"**Est. Waitlist:** {row.get('Est. Waitlist Length','N/A')}")
                    st.write(f"**Community ID:** {row.get('CommunityID','N/A')}")

            _explanation_idx += 1

        if len(tier_df) > 5:
            with st.expander(f"📋 View all {len(tier_df)} Priority {priority} communities"):
                cols = [c for c in ["Type of Service", "Town", "State", "Monthly Fee", "Distance_miles", "Rank_Within_Priority"] if c in tier_df.columns]
                st.dataframe(tier_df[cols], use_container_width=True, hide_index=True)

    # Downloads
    st.markdown("---")
    st.subheader("📥 Download Results")
    patient_name = prefs.get("name_of_patient", "client").replace(" ", "_")
    _dl_cols = [c for c in ["Type of Service", "Town", "State", "Monthly Fee", "Distance_miles",
                             "Priority_Level", "Rank_Within_Priority", "Apartment Type",
                             "Enhanced", "Enriched", "CommunityID"] if c in df.columns]

    c1, c2, c3 = st.columns(3)
    with c1:
        p1 = df[df["Priority_Level"] == 1]
        if not p1.empty:
            st.download_button("🥇 Priority 1 Communities", p1[_dl_cols].to_csv(index=False),
                               f"priority1_{patient_name}.csv", "text/csv", use_container_width=True)
        else:
            st.info("No Priority 1 matches")
    with c2:
        p2 = df[df["Priority_Level"] == 2]
        if not p2.empty:
            st.download_button("🥈 Priority 2 Communities", p2[_dl_cols].to_csv(index=False),
                               f"priority2_{patient_name}.csv", "text/csv", use_container_width=True)
        else:
            st.info("No Priority 2 matches")
    with c3:
        st.download_button(f"📊 All {len(df)} Matches", df[_dl_cols].to_csv(index=False),
                           f"all_matches_{patient_name}.csv", "text/csv", use_container_width=True)

    # Statistics by priority tier
    st.markdown("---")
    st.subheader("📈 Statistics by Priority Tier")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Matches", len(df))
    c2.metric("Priority 1 (Contracted)", len(df[df["Priority_Level"] == 1]))
    c3.metric("Priority 2 (Partners)", len(df[df["Priority_Level"] == 2]))
    c4.metric("Priority 3 (Other)", len(df[df["Priority_Level"] == 3]))

    stats_rows = []
    for p in [1, 2, 3]:
        sub = df[df["Priority_Level"] == p]
        if sub.empty:
            continue
        avg_dist = sub["Distance_miles"].mean() if "Distance_miles" in sub.columns else None
        avg_fee = sub["Monthly Fee"].mean() if "Monthly Fee" in sub.columns else None
        min_dist = sub["Distance_miles"].min() if "Distance_miles" in sub.columns else None
        stats_rows.append({
            "Priority Tier": f"Level {p}",
            "Count": len(sub),
            "Avg Distance (mi)": f"{avg_dist:.1f}" if pd.notna(avg_dist) else "N/A",
            "Avg Monthly Fee": f"${int(avg_fee):,}" if pd.notna(avg_fee) else "N/A",
            "Closest (mi)": f"{min_dist:.1f}" if pd.notna(min_dist) else "N/A",
        })
    if stats_rows:
        st.table(pd.DataFrame(stats_rows))
