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
    /* Force the Streamlit sidebar controls to LTR. */
    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] > div,
    section[data-testid="stSidebar"] [data-testid="stSlider"],
    section[data-testid="stSidebar"] [data-testid="stSlider"] *,
    section[data-testid="stSidebar"] [data-baseweb="slider"],
    section[data-testid="stSidebar"] [data-baseweb="slider"] * {
        direction: ltr !important;
        unicode-bidi: isolate !important;
    }

    section[data-testid="stSidebar"] [data-testid="stSlider"] {
        text-align: left !important;
    }

    section[data-testid="stSidebar"] [data-baseweb="slider"],
    section[data-testid="stSidebar"] [data-baseweb="slider"] > div {
        flex-direction: row !important;
        transform: none !important;
    }

    section[data-testid="stSidebar"] [role="slider"],
    section[data-testid="stSidebar"] [role="slider"] * {
        direction: ltr !important;
        unicode-bidi: isolate !important;
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


# ------------------------------------------------------------
# CURRENCY ORDER
# ------------------------------------------------------------

# Required order throughout the application:
# USD, EUR, JPY, GBP, AUD, CAD

CURRENCY_ORDER = [
    "USD",
    "EUR",
    "JPY",
    "GBP",
    "AUD",
    "CAD",
]

# Validate that the required currencies exist.
missing_currencies = [
    c for c in CURRENCY_ORDER
    if c not in data["Currency"].values
]

if missing_currencies:
    st.error(
        "Missing currencies in inputs.csv: "
        + ", ".join(missing_currencies)
    )
    st.stop()

# Keep only currencies used by the tool and force the desired order.
data = data[
    data["Currency"].isin(CURRENCY_ORDER)
].copy()

data["Currency"] = pd.Categorical(
    data["Currency"],
    categories=CURRENCY_ORDER,
    ordered=True,
)

data = (
    data
    .sort_values("Currency")
    .reset_index(drop=True)
)

CURRENCIES = CURRENCY_ORDER.copy()


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def pct(x):
    return f"{x * 100:.1f}%"


def calculate_portfolio(
    equity_weight,
    ig_weight,
    hy_weight,
    gov_dist,
):
    # Government bonds are ALWAYS the residual asset class.
    gov_weight = (
        1.0
        - equity_weight
        - ig_weight
        - hy_weight
    )

    result = data.copy()

    result["Equity_Contribution"] = (
        equity_weight
        * result["Equity_Dist"]
    )

    result["IG_Contribution"] = (
        ig_weight
        * result["IG_Dist"]
    )

    result["HY_Contribution"] = (
        hy_weight
        * result["HY_Dist"]
    )

    result["Fixed_Contribution"] = (
        result["Equity_Contribution"]
        + result["IG_Contribution"]
        + result["HY_Contribution"]
    )

    result["Gov_Dist_Adjusted"] = gov_dist

    result["Gov_Contribution"] = (
        gov_weight
        * result["Gov_Dist_Adjusted"]
    )

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
# GOVERNMENT-BOND TILTS — TOP OF PAGE
# ------------------------------------------------------------

st.subheader("Government-bond currency allocation")

st.markdown(
    """
    **Base allocation:** COFER government-bond distribution.

    Enter a tilt for **each currency** in percentage points.
    There is no balancing currency: the tilts must sum to **0.0 pp**.

    Example: USD +5pp and EUR -5pp gives a total tilt of 0pp.
    """
)


# Default recommended starting scenario.
# Sum = 0.0 pp.
default_tilts_pp = {
    "USD": 1.1,
    "EUR": -1.9,
    "JPY": -0.9,
    "GBP": -0.8,
    "AUD": 1.7,
    "CAD": 0.8,
}


tilts = {}


# ------------------------------------------------------------
# TILT CONTROLS
#
# Row 1: USD | EUR | JPY
# Row 2: GBP | AUD | CAD
# ------------------------------------------------------------

row1_cols = st.columns(3)

for col, currency in zip(
    row1_cols,
    ["USD", "EUR", "JPY"],
):
    with col:
        tilts[currency] = (
            st.number_input(
                f"{currency} tilt (pp)",
                min_value=-30.0,
                max_value=30.0,
                value=float(
                    default_tilts_pp[currency]
                ),
                step=0.1,
                key=f"tilt_{currency}",
            )
            / 100.0
        )


row2_cols = st.columns(3)

for col, currency in zip(
    row2_cols,
    ["GBP", "AUD", "CAD"],
):
    with col:
        tilts[currency] = (
            st.number_input(
                f"{currency} tilt (pp)",
                min_value=-30.0,
                max_value=30.0,
                value=float(
                    default_tilts_pp[currency]
                ),
                step=0.1,
                key=f"tilt_{currency}",
            )
            / 100.0
        )


# ------------------------------------------------------------
# ADJUSTED GOVERNMENT-BOND MIX
# ------------------------------------------------------------

cofer = (
    data
    .set_index("Currency")[
        "COFER_Gov_Dist"
    ]
)

adjusted_gov = pd.Series(
    {
        c: (
            cofer.loc[c]
            + tilts[c]
        )
        for c in CURRENCIES
    }
)


# ------------------------------------------------------------
# VALIDATION
# ------------------------------------------------------------

tilt_sum = float(
    sum(tilts.values())
)

invalid_tilt_sum = not np.isclose(
    tilt_sum,
    0.0,
    atol=1e-9,
)

invalid_negative = (
    adjusted_gov.min()
    < -1e-10
)

invalid_sum = not np.isclose(
    adjusted_gov.sum(),
    1.0,
    atol=1e-9,
)


if invalid_tilt_sum:
    st.warning(
        f"Currency tilts must sum to 0.0 pp. "
        f"Current sum: {tilt_sum * 100:+.1f} pp."
    )
else:
    st.success(
        "Currency tilts sum to 0.0 pp."
    )


if invalid_negative:
    negative_currencies = (
        adjusted_gov[
            adjusted_gov < -1e-10
        ]
        .index
        .tolist()
    )

    st.error(
        "At least one adjusted government-bond weight is negative: "
        + ", ".join(negative_currencies)
        + ". Reduce the relevant tilt."
    )


if invalid_sum:
    st.error(
        f"Adjusted government-bond weights must sum to 100%. "
        f"Current sum: "
        f"{adjusted_gov.sum() * 100:.1f}%."
    )


if (
    invalid_tilt_sum
    or invalid_negative
    or invalid_sum
):
    st.stop()


st.divider()


# ------------------------------------------------------------
# SIDEBAR — PORTFOLIO ASSUMPTIONS
# ------------------------------------------------------------

st.sidebar.header(
    "Portfolio assumptions"
)

equity_pct = st.sidebar.number_input(
    "Equity weight (%)",
    min_value=25,
    max_value=30,
    value=25,
    step=1,
)

ig_pct = st.sidebar.number_input(
    "IG weight (%)",
    min_value=9,
    max_value=15,
    value=9,
    step=1,
)

hy_pct = st.sidebar.number_input(
    "HY weight (%)",
    min_value=1,
    max_value=5,
    value=1,
    step=1,
)


equity_weight = (
    equity_pct / 100.0
)

ig_weight = (
    ig_pct / 100.0
)

hy_weight = (
    hy_pct / 100.0
)


# Government bonds are always the residual.
gov_weight = (
    1.0
    - equity_weight
    - ig_weight
    - hy_weight
)


st.sidebar.metric(
    "Equity",
    pct(equity_weight)
)

st.sidebar.metric(
    "IG",
    pct(ig_weight)
)

st.sidebar.metric(
    "HY",
    pct(hy_weight)
)

st.sidebar.metric(
    "Government bonds (residual)",
    pct(gov_weight)
)

st.sidebar.divider()

st.sidebar.caption(
    "Government-bond base allocation: COFER"
)


# ------------------------------------------------------------
# PORTFOLIO STRUCTURE
# ------------------------------------------------------------

st.subheader(
    "Portfolio structure"
)

c1, c2, c3, c4, c5 = st.columns(
    [
        1.15,
        0.22,
        1.0,
        0.22,
        1.55,
    ]
)


with c1:
    st.metric(
        "Equity",
        pct(equity_weight)
    )


with c2:
    st.markdown("## +")


with c3:
    st.metric(
        "IG + HY",
        pct(
            ig_weight
            + hy_weight
        )
    )


with c4:
    st.markdown("## +")


with c5:
    st.metric(
        "Government bonds = residual",
        pct(gov_weight)
    )


st.markdown(
    f"""
    **{pct(equity_weight)} Equity
    + {pct(ig_weight)} IG
    + {pct(hy_weight)} HY
    + {pct(gov_weight)} Government Bonds
    = 100.0%**
    """
)


st.info(
    "Equity, IG and HY can be changed within the selected ranges. "
    "Government Bonds automatically equal the residual needed to reach 100%."
)


# ------------------------------------------------------------
# ALLOCATION ASSUMPTIONS
# ------------------------------------------------------------

with st.expander(
    "Show allocation assumptions"
):

    assumptions = data[
        [
            "Currency",
            "Equity_Dist",
            "IG_Dist",
            "HY_Dist",
            "COFER_Gov_Dist",
        ]
    ].copy()

    assumptions.columns = [
        "Currency",
        "Equity",
        "IG",
        "HY",
        "COFER Gov.",
    ]

    for col in [
        "Equity",
        "IG",
        "HY",
        "COFER Gov.",
    ]:
        assumptions[col] = (
            assumptions[col]
            .map(pct)
        )

    st.dataframe(
        assumptions,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "The currency distributions within Equity, IG and HY are fixed assumptions. "
        "Total Equity can vary from 25% to 30%, IG from 9% to 15%, "
        "and HY from 1% to 5%. "
        "Government Bonds are always the residual required to bring "
        "the total portfolio to 100%. "
        "The Government Bond currency distribution starts from COFER "
        "and can be changed using the tilts above."
    )


# ------------------------------------------------------------
# CALCULATE
# ------------------------------------------------------------

result, gov_weight_check = calculate_portfolio(
    equity_weight,
    ig_weight,
    hy_weight,
    adjusted_gov
    .reindex(CURRENCIES)
    .values,
)


if not np.isclose(
    gov_weight,
    gov_weight_check,
):
    st.error(
        "Internal weight calculation mismatch."
    )


# ------------------------------------------------------------
# GOVERNMENT-BOND TABLE
# ------------------------------------------------------------

BASE_EQUITY_WEIGHT = 0.25
BASE_IG_WEIGHT = 0.09
BASE_HY_WEIGHT = 0.01

BASE_GOV_WEIGHT = (
    1.0
    - BASE_EQUITY_WEIGHT
    - BASE_IG_WEIGHT
    - BASE_HY_WEIGHT
)


current_fixed_contribution = (
    BASE_EQUITY_WEIGHT
    * data["Equity_Dist"]

    + BASE_IG_WEIGHT
    * data["IG_Dist"]

    + BASE_HY_WEIGHT
    * data["HY_Dist"]
)


current_gov_contribution = (
    data["Current_FX_Benchmark"]
    - current_fixed_contribution
)


current_gov_dist_implied = (
    current_gov_contribution
    / BASE_GOV_WEIGHT
)


gov_table = result[
    [
        "Currency",
        "COFER_Gov_Dist",
        "Gov_Dist_Adjusted",
    ]
].copy()


gov_table[
    "Current_Gov_Dist_Implied"
] = current_gov_dist_implied.values


gov_table[
    "Tilt_pp"
] = (
    gov_table["Gov_Dist_Adjusted"]
    - gov_table["COFER_Gov_Dist"]
) * 100


gov_table[
    "Gov_Portfolio_Contribution"
] = (
    gov_weight
    * gov_table["Gov_Dist_Adjusted"]
)


gov_display = gov_table[
    [
        "Currency",
        "Current_Gov_Dist_Implied",
        "COFER_Gov_Dist",
        "Gov_Dist_Adjusted",
        "Tilt_pp",
        "Gov_Portfolio_Contribution",
    ]
].rename(
    columns={
        "Current_Gov_Dist_Implied":
            "Current Gov. Mix (implied)",

        "COFER_Gov_Dist":
            "COFER Gov.",

        "Gov_Dist_Adjusted":
            "Adjusted Gov.",

        "Tilt_pp":
            "Tilt (pp)",

        "Gov_Portfolio_Contribution":
            "Contribution to Portfolio",
    }
)


for col in [
    "Current Gov. Mix (implied)",
    "COFER Gov.",
    "Adjusted Gov.",
    "Contribution to Portfolio",
]:
    gov_display[col] = (
        gov_display[col]
        .map(pct)
    )


gov_display[
    "Tilt (pp)"
] = (
    gov_display[
        "Tilt (pp)"
    ]
    .map(
        lambda x:
            f"{x:+.1f}"
    )
)


st.subheader(
    "Government-bond currency mix"
)

st.dataframe(
    gov_display,
    use_container_width=True,
    hide_index=True,
)


st.caption(
    "Current Gov. Mix (implied) is derived from the current currency benchmark "
    "after subtracting the fixed currency contribution of 25% Equity, 9% IG and "
    "1% HY, and normalizing the remaining 65% Government Bonds sleeve to 100%."
)


# ------------------------------------------------------------
# DETAIL TABLE
# ------------------------------------------------------------

st.subheader(
    "Portfolio detail"
)


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
    detail[col] = (
        detail[col]
        .map(pct)
    )


detail["Difference"] = (
    result["Vs_Benchmark"]
    * 100
).map(
    lambda x:
        f"{x:+.1f} pp"
)


st.dataframe(
    detail,
    use_container_width=True,
    hide_index=True,
)


# ------------------------------------------------------------
# CURRENCY MIX COMPARISON TABLE
# ------------------------------------------------------------

st.subheader(
    "Currency mix comparison"
)


risk_sleeve_total = (
    equity_weight
    + ig_weight
    + hy_weight
)


mix_comparison = result[
    [
        "Currency",
        "Current_FX_Benchmark",
        "Fixed_Contribution",
        "Gov_Dist_Adjusted",
        "Total_FX_Allocation",
    ]
].copy()


mix_comparison[
    "Recommended Equity + Corporate Bonds"
] = (
    mix_comparison["Fixed_Contribution"]
    / risk_sleeve_total
)


mix_comparison = (
    mix_comparison
    .rename(
        columns={
            "Current_FX_Benchmark":
                "Current Currency Benchmark",

            "Gov_Dist_Adjusted":
                "Recommended Government Bond Mix",

            "Total_FX_Allocation":
                "Recommended Currency Benchmark",
        }
    )
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
    mix_comparison[col] = (
        mix_comparison[col]
        .map(pct)
    )


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
# MAIN FX CHART
# ------------------------------------------------------------

st.subheader(
    "Total portfolio FX allocation"
)


fig = go.Figure()


fig.add_bar(
    x=result["Currency"].astype(str),
    y=(
        result[
            "Current_FX_Benchmark"
        ]
        * 100
    ),
    name="Current benchmark",
)


fig.add_bar(
    x=result["Currency"].astype(str),
    y=(
        result[
            "Total_FX_Allocation"
        ]
        * 100
    ),
    name="New portfolio",
)


fig.update_layout(
    barmode="group",
    yaxis_title="Portfolio FX allocation (%)",
    xaxis_title="Currency",
    legend_title="",
    height=430,
    margin=dict(
        l=30,
        r=20,
        t=20,
        b=30,
    ),
)


fig.update_xaxes(
    categoryorder="array",
    categoryarray=CURRENCY_ORDER,
)


st.plotly_chart(
    fig,
    use_container_width=True,
)


# ------------------------------------------------------------
# CHANGE DECOMPOSITION VS BENCHMARK
# ------------------------------------------------------------

st.subheader(
    "Change vs current FX benchmark — decomposition"
)


current_total = (
    data[
        "Current_FX_Benchmark"
    ]
    .astype(float)
)


# Stage 1:
# Fixed strategic mix, government bonds moved to COFER.

base_fixed_contribution = (
    BASE_EQUITY_WEIGHT
    * data["Equity_Dist"]

    + BASE_IG_WEIGHT
    * data["IG_Dist"]

    + BASE_HY_WEIGHT
    * data["HY_Dist"]
)


cofer_stage = (
    base_fixed_contribution
    + BASE_GOV_WEIGHT
    * data["COFER_Gov_Dist"]
)


# Stage 2:
# Apply selected tilts.

tilt_stage = (
    base_fixed_contribution
    + BASE_GOV_WEIGHT
    * result["Gov_Dist_Adjusted"]
)


# Stage 3:
# Apply selected Equity / IG / HY weights.

final_stage = (
    result[
        "Total_FX_Allocation"
    ]
    .astype(float)
)


decomp = pd.DataFrame(
    {
        "Currency":
            result["Currency"],

        "COFER effect":
            (
                cofer_stage
                - current_total
            ) * 100.0,

        "Tilt effect":
            (
                tilt_stage
                - cofer_stage
            ) * 100.0,

        "Asset-mix effect":
            (
                final_stage
                - tilt_stage
            ) * 100.0,

        "Total change":
            (
                final_stage
                - current_total
            ) * 100.0,
    }
)


decomp[
    "Reconstructed change"
] = (
    decomp["COFER effect"]
    + decomp["Tilt effect"]
    + decomp["Asset-mix effect"]
)


if not np.allclose(
    decomp["Reconstructed change"],
    decomp["Total change"],
    atol=1e-9,
):
    st.error(
        "Internal decomposition mismatch."
    )


decomp_fig = go.Figure()


for component in [
    "COFER effect",
    "Tilt effect",
    "Asset-mix effect",
]:

    decomp_fig.add_bar(
        x=decomp["Currency"].astype(str),
        y=decomp[component],
        name=component,
        customdata=(
            decomp[
                ["Total change"]
            ]
            .to_numpy()
        ),
        hovertemplate=(
            "%{x}"
            f"<br>{component}: "
            "%{y:+.2f} pp"
            "<br>Total change: "
            "%{customdata[0]:+.2f} pp"
            "<extra></extra>"
        ),
    )


decomp_fig.add_trace(
    go.Scatter(
        x=decomp["Currency"].astype(str),
        y=decomp["Total change"],
        mode="markers",
        name="Total change",
        marker=dict(
            symbol="diamond",
            size=10,
            color="black",
        ),
        hovertemplate=(
            "%{x}"
            "<br>Total change: "
            "%{y:+.2f} pp"
            "<extra></extra>"
        ),
    )
)


decomp_fig.add_hline(
    y=0,
    line_width=1,
)


decomp_fig.update_layout(
    barmode="relative",
    yaxis_title=(
        "Contribution to change "
        "(percentage points)"
    ),
    xaxis_title="Currency",
    legend_title="",
    height=430,
    margin=dict(
        l=30,
        r=20,
        t=20,
        b=30,
    ),
)


decomp_fig.update_xaxes(
    categoryorder="array",
    categoryarray=CURRENCY_ORDER,
)


st.plotly_chart(
    decomp_fig,
    use_container_width=True,
)


st.caption(
    "COFER effect: move from the current implied government-bond mix to COFER "
    "using the fixed 25% Equity / 9% IG / 1% HY benchmark mix. "
    "Tilt effect: additional impact of the selected government-bond currency tilts. "
    "Asset-mix effect: additional impact of changing Equity / IG / HY weights "
    "from 25% / 9% / 1%. "
    "At the default 25% / 9% / 1%, the Asset-mix effect is zero."
)


# ------------------------------------------------------------
# DECOMPOSITION TABLE
# ------------------------------------------------------------

decomp_display = decomp[
    [
        "Currency",
        "COFER effect",
        "Tilt effect",
        "Asset-mix effect",
        "Total change",
    ]
].copy()


for col in [
    "COFER effect",
    "Tilt effect",
    "Asset-mix effect",
    "Total change",
]:

    decomp_display[col] = (
        decomp_display[col]
        .map(
            lambda x:
                f"{x:+.2f} pp"
        )
    )


st.dataframe(
    decomp_display,
    use_container_width=True,
    hide_index=True,
)


# ------------------------------------------------------------
# DOWNLOAD CURRENT SCENARIO
# ------------------------------------------------------------

csv = (
    result
    .to_csv(
        index=False
    )
    .encode("utf-8")
)


st.download_button(
    "Download current scenario as CSV",
    data=csv,
    file_name="fx_allocation_scenario.csv",
    mime="text/csv",
)


st.caption(
    "Current FX benchmark: "
    "USD 63.0%, EUR 20.0%, JPY 5.0%, GBP 5.0%, "
    "AUD 3.5%, CAD 3.5%."
)
