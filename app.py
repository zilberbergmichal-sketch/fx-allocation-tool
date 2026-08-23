import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(
    page_title="FX Allocation Tool",
    page_icon="💱",
    layout="wide",
)

# ============================================================
# DISPLAY DIRECTION
# ============================================================

st.markdown(
    """
    <style>
    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] > div {
        direction: ltr !important;
        unicode-bidi: isolate !important;
    }

    section[data-testid="stSidebar"] {
        text-align: left !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# DATA
# ============================================================

@st.cache_data
def load_inputs():
    return pd.read_csv("inputs.csv")


data = load_inputs()


# ============================================================
# CURRENCY ORDER
# ============================================================

CURRENCY_ORDER = [
    "USD",
    "EUR",
    "JPY",
    "GBP",
    "AUD",
    "CAD",
]

CURRENCIES = CURRENCY_ORDER.copy()


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


# ============================================================
# EQUITY DISTRIBUTION SCENARIOS
#
# These are distributions WITHIN the equity sleeve.
# Each scenario sums to 100%.
# ============================================================

EQUITY_SCENARIOS = {

    "Scenario 1": {
        "USD": 0.736535819857901,
        "EUR": 0.121912162984008,
        "JPY": 0.0561833737475408,
        "GBP": 0.0349243475049016,
        "AUD": 0.0160198719615416,
        "CAD": 0.0344244239441068,
        "OTHER": 0.0,
    },

    "Scenario 2 - with Other": {
        "USD": 0.708934013437677,
        "EUR": 0.0867278105914609,
        "JPY": 0.0561833737475408,
        "GBP": 0.0349243475049016,
        "AUD": 0.0160198719615416,
        "CAD": 0.0344244239441068,
        "OTHER": 0.0627861588127708,
    },
}


# Validate equity scenarios

for scenario_name, scenario in EQUITY_SCENARIOS.items():

    scenario_sum = sum(scenario.values())

    if not np.isclose(
        scenario_sum,
        1.0,
        atol=1e-10,
    ):

        st.error(
            f"{scenario_name} equity distribution "
            f"does not sum to 100%. "
            f"Current total: {scenario_sum * 100:.6f}%"
        )

        st.stop()


# ============================================================
# HELPERS
# ============================================================

def pct(x):
    return f"{x * 100:.1f}%"


def calculate_portfolio(
    equity_weight,
    ig_weight,
    hy_weight,
    gov_dist,
    equity_dist,
):

    # Government bonds are the residual asset class

    gov_weight = (
        1.0
        - equity_weight
        - ig_weight
        - hy_weight
    )

    result = data.copy()


    # --------------------------------------------------------
    # EQUITY
    # --------------------------------------------------------

    result["Equity_Dist_Selected"] = (
        result["Currency"]
        .astype(str)
        .map(equity_dist)
        .fillna(0.0)
        .astype(float)
    )


    result["Equity_Contribution"] = (
        equity_weight
        * result["Equity_Dist_Selected"]
    )


    # --------------------------------------------------------
    # CORPORATE BONDS
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # GOVERNMENT BONDS
    # --------------------------------------------------------

    result["Gov_Dist_Adjusted"] = (
        np.asarray(
            gov_dist,
            dtype=float,
        )
    )


    result["Gov_Contribution"] = (
        gov_weight
        * result["Gov_Dist_Adjusted"]
    )


    # --------------------------------------------------------
    # TOTAL FX
    # --------------------------------------------------------

    result["Total_FX_Allocation"] = (
        result["Fixed_Contribution"]
        + result["Gov_Contribution"]
    )


    result["Vs_Benchmark"] = (
        result["Total_FX_Allocation"]
        - result["Current_FX_Benchmark"]
    )


    # --------------------------------------------------------
    # OTHER
    #
    # Exists only in Equity Scenario 2
    # --------------------------------------------------------

    other_equity_dist = float(
        equity_dist.get(
            "OTHER",
            0.0,
        )
    )


    if other_equity_dist > 0:

        other_contribution = (
            equity_weight
            * other_equity_dist
        )


        other_row = {

            "Currency":
                "OTHER",

            "Equity_Dist_Selected":
                other_equity_dist,

            "Equity_Contribution":
                other_contribution,

            "IG_Contribution":
                0.0,

            "HY_Contribution":
                0.0,

            "Fixed_Contribution":
                other_contribution,

            "Gov_Dist_Adjusted":
                0.0,

            "Gov_Contribution":
                0.0,

            "Total_FX_Allocation":
                other_contribution,

            "Current_FX_Benchmark":
                0.0,

            "Vs_Benchmark":
                other_contribution,
        }


        # Fill any additional input columns with NaN

        for col in result.columns:

            if col not in other_row:
                other_row[col] = np.nan


        result = pd.concat(
            [
                result,
                pd.DataFrame(
                    [other_row]
                )[result.columns],
            ],
            ignore_index=True,
        )


    return result, gov_weight


# ============================================================
# TITLE
# ============================================================

st.title(
    "FX Allocation Tool"
)


st.caption(
    "Choose the equity distribution scenario and enter "
    "the government-bond currency allocation directly. "
    "The dashboard calculates the resulting total "
    "portfolio FX allocation."
)


# ============================================================
# COFER
# ============================================================

cofer = (
    data
    .set_index("Currency")[
        "COFER_Gov_Dist"
    ]
    .astype(float)
    .reindex(CURRENCIES)
)


# ============================================================
# GOVERNMENT-BOND CURRENCY ALLOCATION
# ============================================================

st.subheader(
    "Government-bond currency allocation"
)


st.markdown(
    """
    **Starting allocation: COFER**

    Enter the desired currency allocation
    **within the government-bond sleeve**.

    The starting values are COFER, shown with one decimal
    place for convenient input.

    The selected weights must sum to **100%**.

    The implied tilt versus the exact COFER weights
    is calculated automatically.
    """
)


# ============================================================
# GOVERNMENT-BOND INPUTS
# ============================================================

selected_gov_pct = {}


# ------------------------------------------------------------
# ROW 1
# USD / EUR / JPY
# ------------------------------------------------------------

row1_cols = st.columns(3)


for col, currency in zip(
    row1_cols,
    ["USD", "EUR", "JPY"],
):

    with col:

        st.caption(
            f"Exact COFER: "
            f"{cofer.loc[currency] * 100:.2f}%"
        )


        selected_gov_pct[currency] = (
            st.number_input(
                f"{currency} Government Bond Weight (%)",

                min_value=0.0,
                max_value=100.0,

                value=round(
                    float(
                        cofer.loc[currency]
                        * 100
                    ),
                    1,
                ),

                step=0.1,

                format="%.1f",

                key=f"gov_weight_{currency}",
            )
        )


# ------------------------------------------------------------
# ROW 2
# GBP / AUD / CAD
# ------------------------------------------------------------

row2_cols = st.columns(3)


for col, currency in zip(
    row2_cols,
    ["GBP", "AUD", "CAD"],
):

    with col:

        st.caption(
            f"Exact COFER: "
            f"{cofer.loc[currency] * 100:.2f}%"
        )


        selected_gov_pct[currency] = (
            st.number_input(
                f"{currency} Government Bond Weight (%)",

                min_value=0.0,
                max_value=100.0,

                value=round(
                    float(
                        cofer.loc[currency]
                        * 100
                    ),
                    1,
                ),

                step=0.1,

                format="%.1f",

                key=f"gov_weight_{currency}",
            )
        )


# Convert percentage inputs to decimals

selected_gov = pd.Series(

    {
        currency:
            selected_gov_pct[currency]
            / 100.0

        for currency
        in CURRENCIES
    },

    dtype=float,
)


# ============================================================
# IMPLIED TILTS
# ============================================================

tilts = (
    selected_gov
    - cofer
)


# ============================================================
# CHECK THAT GOVERNMENT BONDS SUM TO 100%
# ============================================================

gov_mix_sum = float(
    selected_gov.sum()
)


gov_mix_sum_pct = (
    gov_mix_sum
    * 100.0
)


gov_mix_difference_pp = (
    gov_mix_sum_pct
    - 100.0
)


valid_gov_sum = np.isclose(
    gov_mix_sum_pct,
    100.0,
    atol=1e-8,
)


summary_col1, summary_col2 = (
    st.columns(2)
)


with summary_col1:

    st.metric(
        "Selected Gov. Allocation",
        f"{gov_mix_sum_pct:.1f}%",
    )


with summary_col2:

    st.metric(
        "Difference from 100%",
        f"{gov_mix_difference_pp:+.1f} pp",
    )


if valid_gov_sum:

    st.success(
        "Government-bond currency allocation "
        "sums to 100.0%."
    )

else:

    st.warning(
        "Government-bond currency allocation "
        "must sum to 100.0%. "
        f"Current total: "
        f"{gov_mix_sum_pct:.1f}% "
        f"({gov_mix_difference_pp:+.1f} pp)."
    )


# ============================================================
# COFER VS SELECTED TABLE
# ============================================================

gov_input_table = pd.DataFrame(

    {
        "Currency":
            CURRENCIES,

        "COFER (%)":
            [
                cofer.loc[c]
                * 100
                for c in CURRENCIES
            ],

        "Selected (%)":
            [
                selected_gov.loc[c]
                * 100
                for c in CURRENCIES
            ],

        "Tilt vs COFER (pp)":
            [
                tilts.loc[c]
                * 100
                for c in CURRENCIES
            ],
    }
)


gov_input_display = (
    gov_input_table.copy()
)


gov_input_display[
    "COFER (%)"
] = (
    gov_input_display[
        "COFER (%)"
    ]
    .map(
        lambda x:
            f"{x:.2f}%"
    )
)


gov_input_display[
    "Selected (%)"
] = (
    gov_input_display[
        "Selected (%)"
    ]
    .map(
        lambda x:
            f"{x:.1f}%"
    )
)


gov_input_display[
    "Tilt vs COFER (pp)"
] = (
    gov_input_display[
        "Tilt vs COFER (pp)"
    ]
    .map(
        lambda x:
            f"{x:+.2f} pp"
    )
)


st.dataframe(
    gov_input_display,
    use_container_width=True,
    hide_index=True,
)


# Stop calculation if government mix != 100%

if not valid_gov_sum:

    st.info(
        "Adjust the government-bond currency "
        "weights above until the total equals 100.0%."
    )

    st.stop()


adjusted_gov = (
    selected_gov.copy()
)


st.divider()


# ============================================================
# SIDEBAR
# PORTFOLIO ASSUMPTIONS
# ============================================================

st.sidebar.header(
    "Portfolio assumptions"
)


# ============================================================
# EQUITY SCENARIO
# ============================================================

st.sidebar.subheader(
    "Equity allocation"
)


equity_scenario_name = (
    st.sidebar.selectbox(

        "Equity distribution scenario",

        options=list(
            EQUITY_SCENARIOS.keys()
        ),

        index=0,
    )
)


equity_dist_selected = pd.Series(
    EQUITY_SCENARIOS[
        equity_scenario_name
    ],
    dtype=float,
)


# ------------------------------------------------------------
# SHOW EQUITY DISTRIBUTION
# ------------------------------------------------------------

with st.sidebar.expander(
    "Show equity distribution"
):

    equity_scenario_display = (
        pd.DataFrame(
            {
                "Market": [
                    "US",
                    "Euro",
                    "Japan",
                    "UK",
                    "Australia",
                    "Canada",
                    "Other",
                ],

                "Weight": [
                    equity_dist_selected[
                        "USD"
                    ],

                    equity_dist_selected[
                        "EUR"
                    ],

                    equity_dist_selected[
                        "JPY"
                    ],

                    equity_dist_selected[
                        "GBP"
                    ],

                    equity_dist_selected[
                        "AUD"
                    ],

                    equity_dist_selected[
                        "CAD"
                    ],

                    equity_dist_selected[
                        "OTHER"
                    ],
                ],
            }
        )
    )


    equity_scenario_display[
        "Weight"
    ] = (
        equity_scenario_display[
            "Weight"
        ]
        .map(
            lambda x:
                f"{x * 100:.1f}%"
        )
    )


    st.dataframe(
        equity_scenario_display,
        hide_index=True,
        use_container_width=True,
    )


# ============================================================
# ASSET CLASS WEIGHTS
# ============================================================

equity_pct = (
    st.sidebar.number_input(
        "Equity weight (%)",
        min_value=25,
        max_value=30,
        value=25,
        step=1,
    )
)


ig_pct = (
    st.sidebar.number_input(
        "IG weight (%)",
        min_value=9,
        max_value=15,
        value=9,
        step=1,
    )
)


hy_pct = (
    st.sidebar.number_input(
        "HY weight (%)",
        min_value=1,
        max_value=5,
        value=1,
        step=1,
    )
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


# Government bonds = residual

gov_weight = (
    1.0
    - equity_weight
    - ig_weight
    - hy_weight
)


if gov_weight < 0:

    st.sidebar.error(
        "Equity + IG + HY exceed 100%."
    )

    st.stop()


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
    "Government-bond reference allocation: COFER"
)


# ============================================================
# PORTFOLIO STRUCTURE
# ============================================================

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

    st.markdown(
        "## +"
    )


with c3:

    st.metric(
        "IG + HY",
        pct(
            ig_weight
            + hy_weight
        )
    )


with c4:

    st.markdown(
        "## +"
    )


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
    f"Selected equity distribution: "
    f"**{equity_scenario_name}**. "
    "Equity, IG and HY can be changed "
    "within the selected ranges. "
    "Government Bonds automatically equal "
    "the residual needed to reach 100%."
)


# ============================================================
# ALLOCATION ASSUMPTIONS
# ============================================================

with st.expander(
    "Show allocation assumptions"
):

    assumptions = data[
        [
            "Currency",
            "IG_Dist",
            "HY_Dist",
            "COFER_Gov_Dist",
        ]
    ].copy()


    assumptions["Equity"] = (
        assumptions["Currency"]
        .astype(str)
        .map(
            equity_dist_selected
        )
        .fillna(0.0)
    )


    assumptions = assumptions[
        [
            "Currency",
            "Equity",
            "IG_Dist",
            "HY_Dist",
            "COFER_Gov_Dist",
        ]
    ]


    assumptions.columns = [
        "Currency",
        "Equity",
        "IG",
        "HY",
        "COFER Gov.",
    ]


    # Add OTHER if Scenario 2 is selected

    if (
        equity_dist_selected[
            "OTHER"
        ]
        > 0
    ):

        other_assumption = (
            pd.DataFrame(
                {
                    "Currency":
                        ["OTHER"],

                    "Equity":
                        [
                            equity_dist_selected[
                                "OTHER"
                            ]
                        ],

                    "IG":
                        [0.0],

                    "HY":
                        [0.0],

                    "COFER Gov.":
                        [0.0],
                }
            )
        )


        assumptions = pd.concat(
            [
                assumptions,
                other_assumption,
            ],
            ignore_index=True,
        )


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
        "Equity uses the selected scenario. "
        "IG and HY use the fixed input distributions. "
        "Government Bonds use COFER as the reference, "
        "while the actual government-bond distribution "
        "is entered directly above."
    )


# ============================================================
# CALCULATE PORTFOLIO
# ============================================================

result, gov_weight_check = (
    calculate_portfolio(

        equity_weight,

        ig_weight,

        hy_weight,

        adjusted_gov
        .reindex(CURRENCIES)
        .values,

        equity_dist_selected,
    )
)


if not np.isclose(
    gov_weight,
    gov_weight_check,
):

    st.error(
        "Internal weight calculation mismatch."
    )

    st.stop()


# ============================================================
# BASE PORTFOLIO
# Used for benchmark decomposition
# ============================================================

BASE_EQUITY_WEIGHT = 0.25

BASE_IG_WEIGHT = 0.09

BASE_HY_WEIGHT = 0.01


BASE_GOV_WEIGHT = (
    1.0
    - BASE_EQUITY_WEIGHT
    - BASE_IG_WEIGHT
    - BASE_HY_WEIGHT
)


# ============================================================
# CURRENT IMPLIED GOVERNMENT BOND MIX
#
# Keep the original Equity_Dist from inputs.csv here,
# because Current_FX_Benchmark represents the existing benchmark.
# ============================================================

current_fixed_contribution = (

    BASE_EQUITY_WEIGHT
    * data["Equity_Dist"]

    + BASE_IG_WEIGHT
    * data["IG_Dist"]

    + BASE_HY_WEIGHT
    * data["HY_Dist"]
)


current_gov_contribution = (

    data[
        "Current_FX_Benchmark"
    ]

    - current_fixed_contribution
)


current_gov_dist_implied = (

    current_gov_contribution
    / BASE_GOV_WEIGHT
)


# ============================================================
# CORE SIX CURRENCIES
# ============================================================

result_core = result[
    result[
        "Currency"
    ]
    .astype(str)
    .isin(CURRENCIES)
].copy()


# ============================================================
# GOVERNMENT BOND TABLE
# ============================================================

gov_table = result_core[
    [
        "Currency",
        "COFER_Gov_Dist",
        "Gov_Dist_Adjusted",
    ]
].copy()


gov_table[
    "Current_Gov_Dist_Implied"
] = (
    current_gov_dist_implied
    .values
)


gov_table[
    "Tilt_pp"
] = (

    gov_table[
        "Gov_Dist_Adjusted"
    ]

    - gov_table[
        "COFER_Gov_Dist"
    ]

) * 100


gov_table[
    "Gov_Portfolio_Contribution"
] = (

    gov_weight
    * gov_table[
        "Gov_Dist_Adjusted"
    ]
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
            "Selected Gov.",

        "Tilt_pp":
            "Tilt vs COFER (pp)",

        "Gov_Portfolio_Contribution":
            "Contribution to Portfolio",
    }
)


for col in [

    "Current Gov. Mix (implied)",

    "COFER Gov.",

    "Selected Gov.",

    "Contribution to Portfolio",

]:

    gov_display[col] = (
        gov_display[col]
        .map(pct)
    )


gov_display[
    "Tilt vs COFER (pp)"
] = (
    gov_display[
        "Tilt vs COFER (pp)"
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
    "Selected Gov. is the currency allocation entered above. "
    "Tilt vs COFER is calculated automatically as "
    "Selected Gov. minus COFER."
)


# ============================================================
# PORTFOLIO DETAIL
# ============================================================

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


detail[
    "Difference"
] = (
    result[
        "Vs_Benchmark"
    ]
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


# ============================================================
# CURRENCY MIX COMPARISON
# ============================================================

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

    mix_comparison[
        "Fixed_Contribution"
    ]

    / risk_sleeve_total
)


mix_comparison = (
    mix_comparison
    .rename(
        columns={

            "Current_FX_Benchmark":
                "Current Currency Benchmark",

            "Gov_Dist_Adjusted":
                "Selected Government Bond Mix",

            "Total_FX_Allocation":
                "Recommended Currency Benchmark",
        }
    )
)


mix_comparison = (
    mix_comparison[
        [
            "Currency",

            "Current Currency Benchmark",

            "Recommended Equity + Corporate Bonds",

            "Selected Government Bond Mix",

            "Recommended Currency Benchmark",
        ]
    ]
)


for col in [

    "Current Currency Benchmark",

    "Recommended Equity + Corporate Bonds",

    "Selected Government Bond Mix",

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
    "The Equity + Corporate Bonds and Government Bonds "
    "columns show the currency composition within each sleeve. "
    "The final column shows the resulting total portfolio "
    "currency allocation."
)


# ============================================================
# MAIN FX CHART
# ============================================================

st.subheader(
    "Total portfolio FX allocation"
)


chart_order = (
    CURRENCY_ORDER.copy()
)


if (
    "OTHER"
    in result[
        "Currency"
    ]
    .astype(str)
    .values
):

    chart_order.append(
        "OTHER"
    )


fig = go.Figure()


fig.add_bar(

    x=result[
        "Currency"
    ].astype(str),

    y=(
        result[
            "Current_FX_Benchmark"
        ]
        .fillna(0.0)
        * 100
    ),

    name="Current benchmark",
)


fig.add_bar(

    x=result[
        "Currency"
    ].astype(str),

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

    yaxis_title=(
        "Portfolio FX allocation (%)"
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


fig.update_xaxes(

    categoryorder="array",

    categoryarray=chart_order,
)


st.plotly_chart(
    fig,
    use_container_width=True,
)


# ============================================================
# CHANGE DECOMPOSITION
# ============================================================

st.subheader(
    "Change vs current FX benchmark — decomposition"
)


current_total = (
    data[
        "Current_FX_Benchmark"
    ]
    .astype(float)
)


# ------------------------------------------------------------
# STAGE 1
# Current benchmark -> COFER
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# STAGE 2
# COFER -> selected government-bond allocation
# ------------------------------------------------------------

selected_gov_stage = (

    base_fixed_contribution

    + BASE_GOV_WEIGHT
    * adjusted_gov
      .reindex(CURRENCIES)
      .values
)


# ------------------------------------------------------------
# STAGE 3
# Selected equity scenario + selected asset-class weights
# ------------------------------------------------------------

final_core = (

    result_core
    .assign(
        Currency_String=
            result_core[
                "Currency"
            ].astype(str)
    )
    .set_index(
        "Currency_String"
    )[
        "Total_FX_Allocation"
    ]
    .reindex(
        CURRENCIES
    )
    .astype(float)
    .values
)


# ============================================================
# DECOMPOSITION DATAFRAME
# ============================================================

decomp = pd.DataFrame(

    {
        "Currency":
            CURRENCIES,

        "COFER effect":
            (
                cofer_stage.values
                - current_total.values
            )
            * 100.0,

        "Gov. allocation effect":
            (
                selected_gov_stage.values
                - cofer_stage.values
            )
            * 100.0,

        "Equity / asset-mix effect":
            (
                final_core
                - selected_gov_stage.values
            )
            * 100.0,

        "Total change":
            (
                final_core
                - current_total.values
            )
            * 100.0,
    }
)


# ------------------------------------------------------------
# Add OTHER for Scenario 2
# ------------------------------------------------------------

if (
    equity_dist_selected[
        "OTHER"
    ]
    > 0
):

    other_total = (

        equity_weight
        * equity_dist_selected[
            "OTHER"
        ]
    )


    other_decomp = pd.DataFrame(

        {
            "Currency":
                ["OTHER"],

            "COFER effect":
                [0.0],

            "Gov. allocation effect":
                [0.0],

            "Equity / asset-mix effect":
                [
                    other_total
                    * 100.0
                ],

            "Total change":
                [
                    other_total
                    * 100.0
                ],
        }
    )


    decomp = pd.concat(
        [
            decomp,
            other_decomp,
        ],
        ignore_index=True,
    )


# ============================================================
# DECOMPOSITION CHECK
# ============================================================

decomp[
    "Reconstructed change"
] = (

    decomp[
        "COFER effect"
    ]

    + decomp[
        "Gov. allocation effect"
    ]

    + decomp[
        "Equity / asset-mix effect"
    ]
)


if not np.allclose(

    decomp[
        "Reconstructed change"
    ],

    decomp[
        "Total change"
    ],

    atol=1e-9,
):

    st.error(
        "Internal decomposition mismatch."
    )


# ============================================================
# DECOMPOSITION CHART
# ============================================================

decomp_fig = go.Figure()


for component in [

    "COFER effect",

    "Gov. allocation effect",

    "Equity / asset-mix effect",

]:

    decomp_fig.add_bar(

        x=decomp[
            "Currency"
        ].astype(str),

        y=decomp[
            component
        ],

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

        x=decomp[
            "Currency"
        ].astype(str),

        y=decomp[
            "Total change"
        ],

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

    categoryarray=chart_order,
)


st.plotly_chart(
    decomp_fig,
    use_container_width=True,
)


st.caption(
    "COFER effect: move from the current implied "
    "government-bond mix to COFER. "
    "Gov. allocation effect: move from COFER to the "
    "selected government-bond mix. "
    "Equity / asset-mix effect: the remaining impact "
    "from the selected equity scenario and changes "
    "in Equity / IG / HY weights."
)


# ============================================================
# DECOMPOSITION TABLE
# ============================================================

decomp_display = decomp[
    [
        "Currency",

        "COFER effect",

        "Gov. allocation effect",

        "Equity / asset-mix effect",

        "Total change",
    ]
].copy()


for col in [

    "COFER effect",

    "Gov. allocation effect",

    "Equity / asset-mix effect",

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


# ============================================================
# VALIDATION CHECKS
# ============================================================

with st.expander(
    "Validation checks"
):

    selected_equity_sum = float(
        equity_dist_selected.sum()
    )


    selected_gov_sum = float(
        adjusted_gov.sum()
    )


    final_portfolio_sum = float(
        result[
            "Total_FX_Allocation"
        ]
        .sum()
    )


    checks = pd.DataFrame(

        {
            "Check": [

                "Selected equity distribution",

                "Selected government-bond distribution",

                "Final portfolio FX allocation",
            ],

            "Total": [

                selected_equity_sum,

                selected_gov_sum,

                final_portfolio_sum,
            ],
        }
    )


    checks[
        "Total"
    ] = (
        checks[
            "Total"
        ]
        .map(pct)
    )


    st.dataframe(
        checks,
        hide_index=True,
        use_container_width=True,
    )


# ============================================================
# DOWNLOAD CURRENT SCENARIO
# ============================================================

csv = (
    result
    .to_csv(
        index=False
    )
    .encode(
        "utf-8"
    )
)


st.download_button(

    "Download current scenario as CSV",

    data=csv,

    file_name=(
        "fx_allocation_scenario.csv"
    ),

    mime="text/csv",
)


st.caption(
    "Current FX benchmark: "
    "USD 63.0%, EUR 20.0%, JPY 5.0%, "
    "GBP 5.0%, AUD 3.5%, CAD 3.5%."
)
