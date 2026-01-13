import streamlit as st
import pandas as pd

from market_explorer.notes import load_notes, reset_notes

# -----------------------
# Theme (Neat)
# -----------------------
C_FONCE = "#41072A"
C_ROSE = "#FF85C8"
C_WHITE = "#FFFFFF"
C_BG2 = "#F7F2F6"  # soft background


st.set_page_config(page_title="Market Explorer — Home", layout="wide")

PROFILES = ["Robin", "Jordan", "Arthus", "Anaïs","Eléonore"]  # UI labels
PROFILE_SLUG = {p: p.lower() for p in PROFILES}  # robin, jordan, team
PROFILE_LABEL = {slug: label for label, slug in PROFILE_SLUG.items()}


# -----------------------
# Global CSS
# -----------------------
st.markdown(
    f"""
    <style>
      .stApp {{ background: {C_WHITE}; }}
      h1, h2, h3 {{ color: {C_FONCE}; }}
      .muted {{ color: rgba(0,0,0,0.55); font-size: 0.95rem; }}
      .card {{
        background: white;
        border: 1px solid rgba(65,7,42,0.10);
        border-radius: 18px;
        padding: 18px 18px 14px 18px;
        box-shadow: 0 8px 22px rgba(0,0,0,0.04);
      }}
      .pill {{
        display:inline-block;
        padding: 6px 10px;
        border-radius: 999px;
        background: rgba(255,133,200,0.18);
        color: {C_FONCE};
        font-weight: 700;
        font-size: 0.85rem;
        margin-bottom: 10px;
      }}
      .tiny {{
        color: rgba(0,0,0,0.5);
        font-size: 0.85rem;
        line-height: 1.35;
      }}
      .footer {{
        margin-top: 22px;
        padding-top: 14px;
        border-top: 1px solid rgba(0,0,0,0.08);
        color: rgba(0,0,0,0.50);
        font-size: 0.85rem;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)


def _notes_to_dataframe(notes: dict) -> pd.DataFrame:
    """
    Normalize notes to a table.

    Supports both legacy format:
        { "company__country": "some note" }
    and new format:
        { "company__country": {"tag": "...", "note": "...", "updated_at": "...", "url": "..."} }
    """
    rows = []
    for ck, v in (notes or {}).items():
        if isinstance(v, dict):
            rows.append(
                {
                    "Company": v.get("display_name") or ck,
                    "Country": v.get("country", ""),
                    "Tag": v.get("tag", ""),
                    "Note": v.get("note", ""),
                    "Updated": v.get("updated_at", ""),
                    "LinkedIn": v.get("linkedin_url") or v.get("url", ""),
                }
            )
        else:
            rows.append(
                {
                    "Company": ck,
                    "Country": "",
                    "Tag": "",
                    "Note": str(v),
                    "Updated": "",
                    "LinkedIn": "",
                }
            )

    df = pd.DataFrame(rows)

    # Sort by Updated desc if possible
    if not df.empty and "Updated" in df.columns:
        try:
            df["_dt"] = pd.to_datetime(df["Updated"], errors="coerce")
            df = df.sort_values("_dt", ascending=False).drop(columns=["_dt"])
        except Exception:
            pass

    return df


def show_login():
    st.title("🔐 Connection")
    st.write("Select your profile to continue.")

    p_ui = st.selectbox("Profile", PROFILES, index=0)
    if st.button("✅ Continue", use_container_width=True):
        st.session_state["profile"] = PROFILE_SLUG[p_ui]
        st.rerun()


def show_user_space(profile: str):
    profile_label = PROFILE_LABEL.get(profile, profile)
    st.title(f"👤 {profile_label}")
    st.caption(f"Connected as **{profile_label}**")


    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("🧭 Go to Market Explorer", use_container_width=True):
            st.switch_page("pages/1_Market_Explorer.py")

    with col2:
        if st.button("🧼 Clean my notes", use_container_width=True):
            reset_notes(profile)
            st.success("Notes cleared.")
            st.rerun()

    with col3:
        if st.button("🔁 Change profile", use_container_width=True):
            st.session_state.pop("profile", None)
            st.rerun()

    # Notes overview
    notes = load_notes(profile)
    if not notes:
        st.info("No notes yet. Go to Market Explorer and add your first notes.")
        return

    df = _notes_to_dataframe(notes)

    st.subheader("📝 My notes")
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "LinkedIn": st.column_config.LinkColumn(
                "LinkedIn",
                display_text="View profile",
            )
        },
    )

    st.download_button(
        "⬇️ Export my notes (CSV)",
        df.to_csv(index=False).encode("utf-8"),
        file_name=f"notes_{profile}.csv",
        mime="text/csv",
        use_container_width=True,
    )


# -----------------------
# Header
# -----------------------
st.markdown("# Market Explorer")
st.markdown(
    '<div class="muted">Internal market intelligence tool — explore markets, shortlist accounts, export target lists, and (soon) generate company business plans.</div>',
    unsafe_allow_html=True,
)
st.write("")


# -----------------------
# Router (login / user space)
# -----------------------
profile = st.session_state.get("profile")
if not profile:
    show_login()
else:
    show_user_space(profile)

st.write("")
st.write("")


# -----------------------
# Action cards
# -----------------------
c1, c2 = st.columns(2, gap="large")

with c1:
    st.markdown(
        """
        <div class="card">
          <div class="pill">Explore</div>
          <h3 style="margin-top:0;">Market Explorer</h3>
          <div class="muted">KPIs, concentration, top countries, top companies, and exports.</div>
          <div style="height:10px;"></div>
          <div class="tiny">Best for: Sales targeting, market overview, account prioritization.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    if st.button("Open Market Explorer →", use_container_width=True):
        st.switch_page("pages/1_Market_Explorer.py")

with c2:
    st.markdown(
        """
        <div class="card">
          <div class="pill">Build</div>
          <h3 style="margin-top:0;">Company Business Plan</h3>
          <div class="muted">Select a company, set assumptions, generate projections and exports.</div>
          <div style="height:10px;"></div>
          <div class="tiny">Status: placeholder (model to be defined).</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    if st.button("Open Company Business Plan →", use_container_width=True):
        st.switch_page("pages/2_Company_Business_Plan.py")

st.markdown(
    """
    <div class="footer">
      Tip: you can later add “Recent datasets”, “Last exports”, or “Top markets this week” here.
    </div>
    """,
    unsafe_allow_html=True,
)
