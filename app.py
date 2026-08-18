import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(
    page_title="FX Allocation Tool",
    page_icon="💱",
    layout="wide",
)


# ------------------------------------------------------------
# DISPLAY DIRECTION
# ------------------------------------------------------------

st.markdown(
    """
    <style>
    /* Force sliders to run left-to-right even when the page/browser is RTL:
       minimum and starting point on the LEFT, maximum on the RIGHT. */
    div[data-testid="stSlider"],
    div[data-testid="stSlider"] > div,
    div[data-testid="stSlider"] [data-baseweb="slider"],
    div[data-testid="stSlider"] [role="slider"] {
        direction: ltr !important;
        text-align: left !important;
    }

    /* BaseWeb sometimes mirrors the slider using CSS in RTL contexts. */
    div[data-testid="stSlider"] [data-baseweb="slider"] {
        transform: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# DATA
# ------------------------------------------------------------

@st.cache_data
def load_inputs():
    return pd.read_csv("inputs.csv")

data = load_inputs()

CURRENCIES = data["Currency"].tolist()

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def pct(x):
    return f"{x * 100:.1f}%"

def calculate_portfolio(equity_weight, ig_weight, hy_weight, gov_dist):
    # Government bonds are ALWAYS the residual asset class.
    gov_weight = 1.0 - equity_weight - ig_weight - hy_weight

    result = data.copy()

    result["Equity_Contribution"] = equity_weight * result["Equity_Dist"]
    result["IG_Contribution"] = ig_weight * result["IG_Dist"]
    result["HY_Contribution"] = hy_weight * result["HY_Dist"]

    result["Fixed_Contribution"] = (
        result["Equity_Contribution"]
        + result["IG_Contribution"]
        + result["HY_Contribution"]
    )

    result["Gov_Dist_Adjusted"] = gov_dist
    result["Gov_Contribution"] = gov_weight * result["Gov_Dist_Adjusted"]

    result["Total_FX_Allocation"] = (
        result["Fixed_Contribution"]
        + result["Gov_Contribution"]
    )

    result["Vs_Benchmark"] = (
        result["Total_FX_Allocation"]
        - result["Current_FX_Benchmark"]
    )

    return result, gov_weight



# ------------------------------------------------------------
# TITLE
# ------------------------------------------------------------

st.title("FX Allocation Tool")
st.caption(
    "Change the equity weight and government-bond currency mix, "
    "and see the resulting total portfolio FX allocation."
)

# ------------------------------------------------------------
# SIDEBAR — PORTFOLIO ASSUMPTIONS
# ------------------------------------------------------------

st.sidebar.header("Portfolio assumptions")

# Asset-class weights are selectable; Government Bonds are always the residual.
equity_pct = st.sidebar.slider(
    "Equity weight (%)",
    min_value=25,
    max_value=30,
    value=25,
    step=1,
)

ig_pct = st.sidebar.slider(
    "IG weight (%)",
    min_value=9,
    max_value=15,
    value=9,
    step=1,
)

hy_pct = st.sidebar.slider(
    "HY weight (%)",
    min_value=1,
    max_value=5,
    value=1,
    step=1,
)

equity_weight = equity_pct / 100.0
ig_weight = ig_pct / 100.0
hy_weight = hy_pct / 100.0

# IMPORTANT: Government bonds are always the residual.
gov_weight = 1.0 - equity_weight - ig_weight - hy_weight

st.sidebar.metric("Equity", pct(equity_weight))
st.sidebar.metric("IG", pct(ig_weight))
st.sidebar.metric("HY", pct(hy_weight))
st.sidebar.metric("Government bonds (residual)", pct(gov_weight))

st.sidebar.divider()
st.sidebar.caption("Government-bond base allocation: COFER")

# ------------------------------------------------------------
# PORTFOLIO STRUCTURE — CLEAR TOP-LINE IDENTITY
# ------------------------------------------------------------

st.subheader("Portfolio structure")

c1, c2, c3, c4, c5 = st.columns([1.15, 0.22, 1.0, 0.22, 1.55])

with c1:
    st.metric("Equity", pct(equity_weight))
with c2:
    st.markdown("## +")
with c3:
    st.metric("IG + HY", pct(ig_weight + hy_weight))
with c4:
    st.markdown("## +")
with c5:
    st.metric("Government bonds = residual", pct(gov_weight))

st.markdown(
    f"""
    **{pct(equity_weight)} Equity + {pct(ig_weight)} IG + {pct(hy_weight)} HY
    + {pct(gov_weight)} Government Bonds = 100.0%**
    """
)

st.info(
    "Equity, IG and HY can be changed within the selected ranges. "
    "Government Bonds automatically equal the residual needed to reach 100%."
)

# ------------------------------------------------------------
# ALLOCATION ASSUMPTIONS
# ------------------------------------------------------------

with st.expander("Show allocation assumptions"):
    assumptions = data[
        ["Currency", "Equity_Dist", "IG_Dist", "HY_Dist", "COFER_Gov_Dist"]
    ].copy()

    assumptions.columns = [
        "Currency",
        "Equity",
        "IG",
        "HY",
        "COFER Gov.",
    ]

    for col in ["Equity", "IG", "HY", "COFER Gov."]:
        assumptions[col] = assumptions[col].map(pct)

    st.dataframe(
        assumptions,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "The currency distributions within Equity, IG and HY are fixed assumptions. "
        "Total Equity can vary from 25% to 30%, IG from 9% to 15%, and HY from 1% to 5%. "
        "Government Bonds are always the residual required to bring the total portfolio to 100%. "
        "The Government Bond currency distribution starts from COFER and can be changed using the tilts below."
    )

# ------------------------------------------------------------
# GOVERNMENT-BOND TILTS
# ------------------------------------------------------------

st.subheader("Government-bond currency allocation")

col_info, col_controls = st.columns([1.15, 1.85], gap="large")

with col_info:
    st.markdown(
        """
        **Base allocation:** COFER government-bond distribution.

        Enter a tilt for **each currency** in percentage points.
        There is no balancing currency: the tilts must sum to **0.0 pp**.

        Example: USD +5pp and EUR -5pp gives a total tilt of 0pp.
        """
    )

tilts = {}

with col_controls:
    control_cols = st.columns(3)

    # All government-bond currencies are editable, including EUR.
    for i, currency in enumerate(CURRENCIES):
        with control_cols[i % 3]:
            tilts[currency] = (
                st.number_input(
                    f"{currency} tilt (pp)",
                    min_value=-30.0,
                    max_value=30.0,
                    value=0.0,
                    step=0.5,
                    key=f"tilt_{currency}",
                )
                / 100.0
            )

cofer = data.set_index("Currency")["COFER_Gov_Dist"]

adjusted_gov = pd.Series(
    {
        c: cofer.loc[c] + tilts[c]
        for c in CURRENCIES
    }
)

# ------------------------------------------------------------
# VALIDATION
# ------------------------------------------------------------

tilt_sum = float(sum(tilts.values()))
invalid_tilt_sum = not np.isclose(tilt_sum, 0.0, atol=1e-9)
invalid_negative = adjusted_gov.min() < -1e-10
invalid_sum = not np.isclose(adjusted_gov.sum(), 1.0, atol=1e-9)

if invalid_tilt_sum:
    st.warning(
        f"Currency tilts must sum to 0.0 pp. "
        f"Current sum: {tilt_sum * 100:+.1f} pp."
    )
else:
    st.success("Currency tilts sum to 0.0 pp.")

if invalid_negative:
    negative_currencies = adjusted_gov[adjusted_gov < -1e-10].index.tolist()
    st.error(
        "At least one adjusted government-bond weight is negative: "
        + ", ".join(negative_currencies)
        + ". Reduce the relevant tilt."
    )

if invalid_sum:
    st.error(
        f"Adjusted government-bond weights must sum to 100%. "
        f"Current sum: {adjusted_gov.sum() * 100:.1f}%."
    )

# Do not calculate or display downstream portfolio results until the
# government-bond currency allocation is valid.
if invalid_tilt_sum or invalid_negative or invalid_sum:
    st.stop()

# ------------------------------------------------------------
# CALCULATE
# ------------------------------------------------------------

result, gov_weight_check = calculate_portfolio(
    equity_weight,
    ig_weight,
    hy_weight,
    adjusted_gov.reindex(CURRENCIES).values,
)

# Internal consistency check.
if not np.isclose(gov_weight, gov_weight_check):
    st.error("Internal weight calculation mismatch.")

# ------------------------------------------------------------
# GOVERNMENT-BOND TABLE
# ------------------------------------------------------------

gov_table = result[
    [
        "Currency",
        "COFER_Gov_Dist",
        "Gov_Dist_Adjusted",
    ]
].copy()

gov_table["Tilt_pp"] = (
    gov_table["Gov_Dist_Adjusted"]
    - gov_table["COFER_Gov_Dist"]
) * 100

gov_table["Gov_Portfolio_Contribution"] = (
    gov_weight * gov_table["Gov_Dist_Adjusted"]
)

gov_display = gov_table.rename(
    columns={
        "COFER_Gov_Dist": "COFER Gov.",
        "Gov_Dist_Adjusted": "Adjusted Gov.",
        "Tilt_pp": "Tilt (pp)",
        "Gov_Portfolio_Contribution": "Contribution to Portfolio",
    }
)

gov_display["COFER Gov."] = gov_display["COFER Gov."].map(pct)
gov_display["Adjusted Gov."] = gov_display["Adjusted Gov."].map(pct)
gov_display["Contribution to Portfolio"] = gov_display[
    "Contribution to Portfolio"
].map(pct)
gov_display["Tilt (pp)"] = gov_display["Tilt (pp)"].map(
    lambda x: f"{x:+.1f}"
)

st.dataframe(
    gov_display,
    use_container_width=True,
    hide_index=True,
)

# ------------------------------------------------------------
# MAIN FX CHART
# ------------------------------------------------------------

st.subheader("Total portfolio FX allocation")

fig = go.Figure()

fig.add_bar(
    x=result["Currency"],
    y=result["Current_FX_Benchmark"] * 100,
    name="Current benchmark",
)

fig.add_bar(
    x=result["Currency"],
    y=result["Total_FX_Allocation"] * 100,
    name="New portfolio",
)

fig.update_layout(
    barmode="group",
    yaxis_title="Portfolio FX allocation (%)",
    xaxis_title="Currency",
    legend_title="",
    height=430,
    margin=dict(l=30, r=20, t=20, b=30),
)

st.plotly_chart(
    fig,
    use_container_width=True,
)

# ------------------------------------------------------------
# CHANGE VS BENCHMARK
# ------------------------------------------------------------

st.subheader("Change vs current FX benchmark")

delta_fig = go.Figure()

delta_fig.add_bar(
    x=result["Currency"],
    y=result["Vs_Benchmark"] * 100,
    name="Change",
)

delta_fig.add_hline(
    y=0,
    line_width=1,
)

delta_fig.update_layout(
    yaxis_title="Difference (percentage points)",
    xaxis_title="Currency",
    showlegend=False,
    height=350,
    margin=dict(l=30, r=20, t=20, b=30),
)

st.plotly_chart(
    delta_fig,
    use_container_width=True,
)

# ------------------------------------------------------------
# DETAIL TABLE
# ------------------------------------------------------------

st.subheader("Portfolio detail")

detail = result[
    [
        "Currency",
        "Current_FX_Benchmark",
        "Fixed_Contribution",
        "Gov_Contribution",
        "Total_FX_Allocation",
        "Vs_Benchmark",
    ]
].copy()

detail.columns = [
    "Currency",
    "Current Benchmark",
    "Equity + IG + HY",
    "Government Bonds",
    "New Portfolio",
    "Difference",
]

for col in [
    "Current Benchmark",
    "Equity + IG + HY",
    "Government Bonds",
    "New Portfolio",
]:
    detail[col] = detail[col].map(pct)

detail["Difference"] = (
    result["Vs_Benchmark"] * 100
).map(lambda x: f"{x:+.1f} pp")

st.dataframe(
    detail,
    use_container_width=True,
    hide_index=True,
)


# ------------------------------------------------------------
# CURRENCY MIX COMPARISON TABLE
# ------------------------------------------------------------

st.subheader("Currency mix comparison")

# Current benchmark = current total FX benchmark.
# Recommended Equity + Corporate Bonds = Equity + IG + HY, normalized to 100%.
# Recommended Government Bonds = adjusted government-bond currency mix, normalized to 100%.
# Recommended Total = resulting total portfolio FX allocation.

risk_sleeve_total = equity_weight + ig_weight + hy_weight

mix_comparison = result[
    [
        "Currency",
        "Current_FX_Benchmark",
        "Fixed_Contribution",
        "Gov_Dist_Adjusted",
        "Total_FX_Allocation",
    ]
].copy()

mix_comparison["Recommended Equity + Corporate Bonds"] = (
    mix_comparison["Fixed_Contribution"] / risk_sleeve_total
)

mix_comparison = mix_comparison.rename(
    columns={
        "Currency": "Currency",
        "Current_FX_Benchmark": "Current Currency Benchmark",
        "Gov_Dist_Adjusted": "Recommended Government Bond Mix",
        "Total_FX_Allocation": "Recommended Currency Benchmark",
    }
)

mix_comparison = mix_comparison[
    [
        "Currency",
        "Current Currency Benchmark",
        "Recommended Equity + Corporate Bonds",
        "Recommended Government Bond Mix",
        "Recommended Currency Benchmark",
    ]
]

for col in [
    "Current Currency Benchmark",
    "Recommended Equity + Corporate Bonds",
    "Recommended Government Bond Mix",
    "Recommended Currency Benchmark",
]:
    mix_comparison[col] = mix_comparison[col].map(pct)

st.dataframe(
    mix_comparison,
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "The Equity + Corporate Bonds and Government Bonds columns each show "
    "the currency composition within that sleeve, normalized to 100%. "
    "The final column shows the resulting total portfolio currency allocation."
)

# ------------------------------------------------------------
# DOWNLOAD CURRENT SCENARIO
# ------------------------------------------------------------

csv = result.to_csv(index=False).encode("utf-8")

st.download_button(
    "Download current scenario as CSV",
    data=csv,
    file_name="fx_allocation_scenario.csv",
    mime="text/csv",
)

st.caption(
    "Current FX benchmark: USD 63.0%, EUR 20.0%, GBP 5.0%, "
    "JPY 5.0%, AUD 3.5%, CAD 3.5%."
)
