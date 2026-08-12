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


def get_preset(name):
    tilts = {c: 0.0 for c in CURRENCIES}

    if name == "USD +5pp / EUR -5pp":
        tilts["USD"] = 0.05
        tilts["EUR"] = -0.05

    elif name == "USD +3pp / AUD -3pp":
        tilts["USD"] = 0.03
        tilts["AUD"] = -0.03

    return tilts


# ------------------------------------------------------------
# TITLE
# ------------------------------------------------------------

st.title("FX Allocation Tool")
st.caption(
    "Fixed Equity / IG / HY currency exposures + adjustable government-bond allocation "
    "= total portfolio FX allocation."
)

# ------------------------------------------------------------
# SIDEBAR — PORTFOLIO ASSUMPTIONS
# ------------------------------------------------------------

st.sidebar.header("Portfolio assumptions")

equity_weight = st.sidebar.slider(
    "Equity weight",
    min_value=0.25,
    max_value=0.30,
    value=0.25,
    step=0.005,
    format="%.1f%%",
)

# Streamlit's slider format works on raw values, so show exact percentage below.
st.sidebar.caption(f"Selected Equity weight: **{pct(equity_weight)}**")

ig_weight = 0.09
hy_weight = 0.01
gov_weight = 1.0 - equity_weight - ig_weight - hy_weight

st.sidebar.metric("IG", pct(ig_weight))
st.sidebar.metric("HY", pct(hy_weight))
st.sidebar.metric("Government bonds", pct(gov_weight))

st.sidebar.divider()

preset = st.sidebar.selectbox(
    "Government-bond preset",
    [
        "COFER",
        "USD +5pp / EUR -5pp",
        "USD +3pp / AUD -3pp",
        "Custom",
    ],
)

balancing_currency = st.sidebar.selectbox(
    "Balancing currency",
    CURRENCIES,
    index=CURRENCIES.index("EUR"),
    help=(
        "The tilt of this currency is calculated automatically so that "
        "all government-bond tilts sum to zero."
    ),
)

# ------------------------------------------------------------
# GOVERNMENT-BOND TILTS
# ------------------------------------------------------------

st.subheader("Government-bond allocation")

col_info, col_controls = st.columns([1.15, 1.85], gap="large")

with col_info:
    st.markdown(
        """
        **Base allocation:** COFER government-bond distribution.

        Enter tilts in percentage points. The selected **balancing currency**
        adjusts automatically so that the total tilt is always zero.

        Example: if USD is +5pp and EUR is the balancing currency,
        EUR becomes -5pp automatically.
        """
    )

base_tilts = get_preset(preset)
tilts = {}

with col_controls:
    control_cols = st.columns(3)

    for i, currency in enumerate(CURRENCIES):
        if currency == balancing_currency:
            continue

        default_value = base_tilts.get(currency, 0.0) * 100

        with control_cols[i % 3]:
            tilts[currency] = (
                st.number_input(
                    f"{currency} tilt (pp)",
                    min_value=-30.0,
                    max_value=30.0,
                    value=float(default_value),
                    step=0.5,
                    key=f"tilt_{currency}_{preset}_{balancing_currency}",
                )
                / 100.0
            )

# Balance residual automatically.
tilts[balancing_currency] = -sum(
    v for c, v in tilts.items()
    if c != balancing_currency
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

invalid_negative = adjusted_gov.min() < -1e-10
invalid_sum = not np.isclose(adjusted_gov.sum(), 1.0, atol=1e-9)

if invalid_negative:
    st.error(
        "At least one adjusted government-bond weight is negative. "
        "Reduce the tilt or choose a different balancing currency."
    )

if invalid_sum:
    st.error(
        "Adjusted government-bond weights do not sum to 100%."
    )

st.info(
    f"Balancing currency **{balancing_currency}** tilt: "
    f"**{tilts[balancing_currency] * 100:+.1f} pp**"
)

# ------------------------------------------------------------
# CALCULATE
# ------------------------------------------------------------

result, gov_weight = calculate_portfolio(
    equity_weight,
    ig_weight,
    hy_weight,
    adjusted_gov.reindex(CURRENCIES).values,
)

# ------------------------------------------------------------
# TOP METRICS
# ------------------------------------------------------------

m1, m2, m3, m4 = st.columns(4)

m1.metric("Equity", pct(equity_weight))
m2.metric("IG + HY", pct(ig_weight + hy_weight))
m3.metric("Government bonds", pct(gov_weight))
m4.metric(
    "FX allocation total",
    pct(result["Total_FX_Allocation"].sum()),
)

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

gov_table["Tilt_pp"] = gov_table.apply(
    lambda r: (
        r["Gov_Dist_Adjusted"]
        - r["COFER_Gov_Dist"]
    ) * 100,
    axis=1,
)

gov_display = gov_table.rename(
    columns={
        "COFER_Gov_Dist": "COFER Gov.",
        "Gov_Dist_Adjusted": "Adjusted Gov.",
        "Tilt_pp": "Tilt (pp)",
    }
)

gov_display["COFER Gov."] = gov_display["COFER Gov."].map(pct)
gov_display["Adjusted Gov."] = gov_display["Adjusted Gov."].map(pct)
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
    "Fixed Components",
    "Government Bonds",
    "New Portfolio",
    "Difference",
]

for col in [
    "Current Benchmark",
    "Fixed Components",
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
