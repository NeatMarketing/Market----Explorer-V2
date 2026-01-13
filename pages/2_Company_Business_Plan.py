from __future__ import annotations

from pathlib import Path
import math
import pandas as pd
import streamlit as st
import plotly.express as px

from market_explorer.discovery import DatasetCatalog, list_datasets
from market_explorer.data_io import load_dataset
from market_explorer.labels import zone_label_ui, zones_in_scope_from_ui


# =============================================================================
# Auth guard (profile required)
# =============================================================================
profile = st.session_state.get("profile")
if not profile:
    st.warning("Please select a profile first.")
    st.switch_page("pages/0_Home.py")


# =============================================================================
# Page config
# =============================================================================
st.set_page_config(page_title="Company Business Plan", layout="wide")


# =============================================================================
# Theme (Neat)
# =============================================================================
C_FONCE = "#41072A"
C_ROSE = "#FF85C8"
C_WHITE = "#FFFFFF"
C_BG2 = "#F7F2F6"  # soft background

st.markdown(
    f"""
    <style>
      .stApp {{ background: {C_WHITE}; }}
      h1, h2, h3, h4 {{ color: {C_FONCE}; }}
      .muted {{ color: rgba(0,0,0,0.55); font-size: 0.95rem; }}
      .card {{
        background: white;
        border: 1px solid rgba(65,7,42,0.10);
        border-radius: 18px;
        padding: 16px 16px 14px 16px;
        box-shadow: 0 8px 22px rgba(0,0,0,0.04);
      }}
      .pill {{
        display:inline-block;
        padding: 6px 10px;
        border-radius: 999px;
        background: rgba(255,133,200,0.18);
        color: {C_FONCE};
        font-weight: 800;
        font-size: 0.85rem;
        margin-bottom: 8px;
      }}
      .kpi {{
        background: {C_BG2};
        border: 1px solid rgba(65,7,42,0.10);
        border-radius: 16px;
        padding: 12px 12px 10px 12px;
      }}
      .tiny {{
        color: rgba(0,0,0,0.50);
        font-size: 0.85rem;
        line-height: 1.35;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# Paths / catalog
# =============================================================================
DATA_DIR = Path(__file__).resolve().parents[1] / "Data_Clean"
catalog = DatasetCatalog.from_dir(DATA_DIR)

datasets_all = list_datasets(DATA_DIR)
if not datasets_all:
    st.error(f"Aucun CSV exploitable trouvé dans {DATA_DIR}")
    st.stop()


# =============================================================================
# Helpers
# =============================================================================
@st.cache_data(show_spinner=False)
def _load_panorama_for(market: str, vertical: str, zones: list[str]) -> pd.DataFrame:
    paths = catalog.paths_for(market=market, vertical=vertical, zones=zones)
    if not paths:
        return pd.DataFrame()
    dfs = [load_dataset(p) for p in paths]
    df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    # Normalize types
    if "Revenue_M" in df.columns:
        df["Revenue_M"] = pd.to_numeric(df["Revenue_M"], errors="coerce")
    for col in ["Name", "Country", "Sector", "Company Type"]:
        if col in df.columns:
            df[col] = df[col].astype(str)
    return df


def _fmt_money(x: float, currency: str = "€") -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    # French-ish grouping but without locale dependency
    return f"{currency}{x:,.0f}".replace(",", " ")


def _seasonality_weights(peak_month: int, amplitude: float) -> list[float]:
    """
    Cosine-based monthly weights.
    - peak_month: 1..12
    - amplitude: 0..0.6 (reasonable)
    Returns 12 positive weights summing to 1.
    """
    peak_idx = (peak_month - 1) % 12
    vals = []
    for m in range(12):
        # cosine peak at m = peak_idx
        angle = 2 * math.pi * (m - peak_idx) / 12
        v = 1.0 + amplitude * math.cos(angle)
        vals.append(max(0.05, v))  # avoid near-zero months
    s = sum(vals)
    return [v / s for v in vals]


# =============================================================================
# Header
# =============================================================================
st.title("🏨 Company Business Plan — Hotels")
st.markdown(
    '<div class="muted">From hotel revenue → estimate ADR → simulate insurance revenue, claims, and net income (with simple seasonality).</div>',
    unsafe_allow_html=True,
)
st.write("")


# =============================================================================
# Sidebar: scope + assumptions
# =============================================================================
with st.sidebar:
    st.markdown("## Scope")

    # We lock to hotels (travel / hotel)
    market = "travel"
    vertical = "hotel"

    # Zone UI options with the exact UX wording you asked for
    zone_ui_options = ["France", "Europe", "Europe + France"]
    default_zone_ui = st.session_state.get("bp_zone_ui", "France")
    if default_zone_ui not in zone_ui_options:
        default_zone_ui = "France"

    zone_ui = st.selectbox("Zone", zone_ui_options, index=zone_ui_options.index(default_zone_ui))
    st.session_state["bp_zone_ui"] = zone_ui
    zones = zones_in_scope_from_ui(zone_ui)  # -> ["europe","france"] etc.

    st.markdown("---")
    st.markdown("## Hotel inputs")

    rooms = st.number_input("Number of rooms", min_value=1, max_value=20000, value=120, step=10)
    occupancy = st.slider("Occupancy rate (assumption)", min_value=0.10, max_value=0.98, value=0.72, step=0.01)
    avg_stay = st.slider("Average stay (nights)", min_value=1.0, max_value=14.0, value=2.4, step=0.1)

    st.markdown("---")
    st.markdown("## Insurance assumptions")

    # By default: insurance priced per stay (simple & common)
    insurance_price = st.number_input("Insurance price per stay (€)", min_value=0.0, max_value=500.0, value=18.0, step=1.0)
    take_rate = st.slider("Take rate (% of stays)", min_value=0.0, max_value=0.60, value=0.18, step=0.01)

    claim_rate = st.slider("Claim frequency (% of policies)", min_value=0.0, max_value=0.30, value=0.06, step=0.005)
    avg_claim_cost = st.number_input("Average claim cost (€)", min_value=0.0, max_value=5000.0, value=220.0, step=10.0)

    st.markdown("---")
    st.markdown("## Time / seasonality")

    horizon_years = st.selectbox("Horizon", [1, 3, 5], index=0)
    growth = st.slider("Hotel revenue growth (YoY)", min_value=-0.20, max_value=0.40, value=0.05, step=0.01)

    seasonality_amp = st.slider("Seasonality amplitude", min_value=0.0, max_value=0.60, value=0.20, step=0.05)
    peak_month = st.selectbox(
        "Peak month",
        list(range(1, 13)),
        index=6,  # July
        format_func=lambda m: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m - 1],
    )

    st.markdown("---")
    st.caption("Assumptions are intentionally simple for V1 (hotels only).")


# =============================================================================
# Load hotel dataset (travel/hotel) and select company
# =============================================================================
df = _load_panorama_for(market=market, vertical=vertical, zones=zones)

if df.empty:
    st.error(
        f"No dataset found for **{market}/{vertical}** in **{zone_label_ui(zones)}**.\n\n"
        f"Expected CSV name format: `travel_hotel_<zone>_cleaned.csv` inside `{DATA_DIR}`."
    )
    st.stop()

# Clean & sort companies
df = df.copy()
df = df[df["Revenue_M"].notna()] if "Revenue_M" in df.columns else df
df = df.sort_values("Revenue_M", ascending=False)

companies = df["Name"].dropna().astype(str).unique().tolist()
if not companies:
    st.error("No companies available in the current scope.")
    st.stop()

default_company = st.session_state.get("bp_company")
if default_company not in companies:
    default_company = companies[0]

colA, colB = st.columns([2, 1])
with colA:
    company = st.selectbox("Hotel company", companies, index=companies.index(default_company))
    st.session_state["bp_company"] = company
with colB:
    st.markdown(
        f"""
        <div class="card">
          <div class="pill">Scope</div>
          <div class="tiny"><b>Market</b>: travel</div>
          <div class="tiny"><b>Vertical</b>: hotel</div>
          <div class="tiny"><b>Zone</b>: {zone_label_ui(zones)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

row = df[df["Name"].astype(str) == str(company)].head(1)
if row.empty:
    st.error("Selected company not found (unexpected).")
    st.stop()

country = row["Country"].iloc[0] if "Country" in row.columns else ""
rev_m = float(row["Revenue_M"].iloc[0]) if "Revenue_M" in row.columns else float("nan")

# Interpret Revenue_M as annual revenue in millions (dataset convention)
hotel_rev_year_eur = rev_m * 1_000_000.0


# =============================================================================
# Core model (simple V1)
# =============================================================================
# Nights sold implied by revenue and ADR.
# We estimate ADR from rooms, occupancy, and 365 days:
# room_nights_capacity = rooms * 365
# room_nights_sold = room_nights_capacity * occupancy
# ADR = hotel_revenue / room_nights_sold
room_nights_capacity = rooms * 365.0
room_nights_sold = room_nights_capacity * occupancy if occupancy > 0 else 0.0
adr = (hotel_rev_year_eur / room_nights_sold) if room_nights_sold > 0 else float("nan")

# Number of stays (bookings) = room_nights_sold / avg_stay
stays = (room_nights_sold / avg_stay) if avg_stay > 0 else 0.0

# Insurance business
policies = stays * take_rate
gross_ins_rev = policies * insurance_price
claims = policies * claim_rate * avg_claim_cost
net_ins_rev = gross_ins_rev - claims

loss_ratio = (claims / gross_ins_rev) if gross_ins_rev > 0 else float("nan")
attach_rate = take_rate


# =============================================================================
# KPIs header
# =============================================================================
k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Hotel revenue (annual)", _fmt_money(hotel_rev_year_eur))
k2.metric("Estimated ADR (€/night)", _fmt_money(adr, currency="€"))
k3.metric("Room-nights sold", f"{room_nights_sold:,.0f}".replace(",", " "))
k4.metric("Stays (annual)", f"{stays:,.0f}".replace(",", " "))
k5.metric("Policies sold (annual)", f"{policies:,.0f}".replace(",", " "))

st.write("")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Gross insurance revenue", _fmt_money(gross_ins_rev))
c2.metric("Expected claims", _fmt_money(claims))
c3.metric("Net insurance revenue", _fmt_money(net_ins_rev))
c4.metric("Loss ratio", f"{loss_ratio*100:,.1f}%" if loss_ratio == loss_ratio else "—")

st.caption(f"Company: **{company}** ({country}) — Using **Revenue_M** as annual revenue in EUR millions.")


# =============================================================================
# Build monthly + multi-year projection tables
# =============================================================================
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
weights = _seasonality_weights(peak_month=peak_month, amplitude=seasonality_amp)

# Monthly (Year 1)
df_month = pd.DataFrame(
    {
        "Month": months,
        "Weight": weights,
    }
)
df_month["HotelRevenue"] = hotel_rev_year_eur * df_month["Weight"]
df_month["RoomNightsSold"] = room_nights_sold * df_month["Weight"]
df_month["Stays"] = stays * df_month["Weight"]
df_month["Policies"] = policies * df_month["Weight"]
df_month["GrossInsuranceRevenue"] = gross_ins_rev * df_month["Weight"]
df_month["Claims"] = claims * df_month["Weight"]
df_month["NetInsuranceRevenue"] = net_ins_rev * df_month["Weight"]

# Multi-year annual projection (simple growth on hotel revenue only; ADR & volume follow proportionally)
years = list(range(1, horizon_years + 1))
df_year = pd.DataFrame({"Year": years})
df_year["HotelRevenue"] = [hotel_rev_year_eur * ((1 + growth) ** (y - 1)) for y in years]

# Assume occupancy/rooms/avg_stay constant; so room-nights sold and stays scale with revenue via ADR (ADR constant here).
# For V1: keep ADR fixed (from year1), scale volumes with revenue proportionally.
rev_scale = df_year["HotelRevenue"] / hotel_rev_year_eur if hotel_rev_year_eur > 0 else 0.0
df_year["RoomNightsSold"] = room_nights_sold * rev_scale
df_year["Stays"] = stays * rev_scale
df_year["Policies"] = df_year["Stays"] * attach_rate
df_year["GrossInsuranceRevenue"] = df_year["Policies"] * insurance_price
df_year["Claims"] = df_year["Policies"] * claim_rate * avg_claim_cost
df_year["NetInsuranceRevenue"] = df_year["GrossInsuranceRevenue"] - df_year["Claims"]


# =============================================================================
# Charts
# =============================================================================
left, right = st.columns([1.2, 0.8], gap="large")

with left:
    st.subheader("📈 Monthly insurance economics (Year 1)")
    plot_month = df_month.melt(
        id_vars=["Month"],
        value_vars=["GrossInsuranceRevenue", "Claims", "NetInsuranceRevenue"],
        var_name="Metric",
        value_name="EUR",
    )
    fig1 = px.line(plot_month, x="Month", y="EUR", color="Metric", markers=True)
    fig1.update_layout(height=420, legend_title_text="")
    st.plotly_chart(fig1, use_container_width=True)

with right:
    st.subheader("🧾 Key assumptions (V1)")
    st.markdown(
        f"""
        <div class="card">
          <div class="pill">Hotel</div>
          <div class="tiny"><b>Rooms</b>: {rooms}</div>
          <div class="tiny"><b>Occupancy</b>: {occupancy*100:.1f}%</div>
          <div class="tiny"><b>Avg stay</b>: {avg_stay:.1f} nights</div>
          <div style="height:10px;"></div>
          <div class="pill">Insurance</div>
          <div class="tiny"><b>Price / stay</b>: {_fmt_money(insurance_price, currency="€")}</div>
          <div class="tiny"><b>Take rate</b>: {take_rate*100:.1f}%</div>
          <div class="tiny"><b>Claim freq</b>: {claim_rate*100:.1f}%</div>
          <div class="tiny"><b>Avg claim</b>: {_fmt_money(avg_claim_cost, currency="€")}</div>
          <div style="height:10px;"></div>
          <div class="pill">Projection</div>
          <div class="tiny"><b>Horizon</b>: {horizon_years} year(s)</div>
          <div class="tiny"><b>YoY growth</b>: {growth*100:.1f}%</div>
          <div class="tiny"><b>Seasonality</b>: amp {seasonality_amp:.2f}, peak {months[peak_month-1]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")
st.subheader("📊 Annual projection")
plot_year = df_year.melt(
    id_vars=["Year"],
    value_vars=["HotelRevenue", "GrossInsuranceRevenue", "Claims", "NetInsuranceRevenue"],
    var_name="Metric",
    value_name="EUR",
)
fig2 = px.bar(plot_year, x="Year", y="EUR", color="Metric", barmode="group")
fig2.update_layout(height=420, legend_title_text="")
st.plotly_chart(fig2, use_container_width=True)

st.write("")
st.subheader("🔎 Tables")
t1, t2 = st.columns(2, gap="large")

with t1:
    st.markdown("**Monthly (Year 1)**")
    show_month = df_month.copy()
    for c in ["HotelRevenue", "GrossInsuranceRevenue", "Claims", "NetInsuranceRevenue"]:
        show_month[c] = show_month[c].round(0)
    st.dataframe(show_month[["Month", "HotelRevenue", "Stays", "Policies", "GrossInsuranceRevenue", "Claims", "NetInsuranceRevenue"]], use_container_width=True, hide_index=True)

with t2:
    st.markdown("**Annual projection**")
    show_year = df_year.copy()
    for c in ["HotelRevenue", "GrossInsuranceRevenue", "Claims", "NetInsuranceRevenue"]:
        show_year[c] = show_year[c].round(0)
    st.dataframe(show_year[["Year", "HotelRevenue", "Policies", "GrossInsuranceRevenue", "Claims", "NetInsuranceRevenue"]], use_container_width=True, hide_index=True)

st.caption("V1 model: insurance priced per stay; volumes scale with hotel revenue using constant ADR assumption (simple).")
