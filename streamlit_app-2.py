# =============================================================================
# Commercial & Product KPI Dashboard — Streamlit in Snowflake
# Answers:
#   Q1  How many customers do we have today?
#   Q2  What is our Average Contract Value (ACV)?
#   Q3  What is the retention of our users?
#   Q4  How does our sales funnel convert?
#   Q5  How fast do new organisations reach first value (TTFV)?
# =============================================================================
import os

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

try:  # Plotly gives the nicest funnel; add "plotly" in Packages / requirements
    import plotly.graph_objects as go

    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

st.set_page_config(page_title="Commercial & Product KPIs", page_icon="📊", layout="wide")

# ── Config: point these at where your dbt models live ────────────────────────
DATABASE = "FLINN_DB"
MART_SCHEMA = "DBT_REBECCAAKOTO"   # schema with the MART_* views
INT_SCHEMA = "DBT_REBECCAAKOTO"    # schema with INT_DEAL_LIFECYCLE


def fq(schema: str, table: str) -> str:
    return f"{DATABASE}.{schema}.{table}"


T_DEALS = fq(INT_SCHEMA, "INT_DEAL_LIFECYCLE")
T_PORTFOLIO = fq(MART_SCHEMA, "MART_CUSTOMER_PORTFOLIO")
T_REVENUE = fq(MART_SCHEMA, "MART_REVENUE_PERFORMANCE")
T_TTFV = fq(MART_SCHEMA, "MART_TIME_TO_FIRST_VALUE")
T_RETENTION = fq(MART_SCHEMA, "MART_USER_RETENTION")

STAGES = [
    ("Pre-pitch", "ENTERED_PRE_PITCH_AT"),
    ("Pitching", "ENTERED_PITCHING_AT"),
    ("Product testing", "ENTERED_PRODUCT_TESTING_AT"),
    ("Price offering", "ENTERED_PRICE_OFFERING_AT"),
    ("Contract negotiation", "ENTERED_CONTRACT_NEGOTIATION_AT"),
    ("Closed won", "ENTERED_CLOSED_WON_AT"),
]
STAGE_NAMES = [s for s, _ in STAGES]
STAGE_COLS = [c for _, c in STAGES]

# ── Styling ──────────────────────────────────────────────────────────────────
ACCENTS = {
    "customers": "#1F6F78",
    "acv": "#3B5BA9",
    "retention": "#7A4FA3",
    "funnel": "#C0762B",
    "ttfv": "#2E8B57",
}

st.markdown(
    """
<style>
.kpi {
    border: 1px solid rgba(128,128,128,.22);
    border-left: 5px solid var(--accent);
    border-radius: 10px;
    padding: 14px 18px 12px 18px;
    background: rgba(128,128,128,.05);
    height: 100%;
}
.kpi-q     { font-size: .78rem; opacity: .65; margin-bottom: 2px; }
.kpi-label { font-size: .95rem; font-weight: 600; }
.kpi-value { font-size: 2.1rem; font-weight: 700; line-height: 1.15; margin-top: 6px;
             font-variant-numeric: tabular-nums; }
.kpi-sub   { font-size: .8rem; opacity: .7; margin-top: 4px; }

/* Print / Save as PDF */
@media print {
    @page { size: A4 landscape; margin: 12mm; }
    [data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"],
    [data-testid="stDecoration"], [data-testid="stStatusWidget"], header, footer { display: none !important; }
    .block-container, [data-testid="stMainBlockContainer"] { max-width: 100% !important; padding: 0 !important; }
    .page-break { break-before: page; page-break-before: always; }
    .kpi, [data-testid="stVegaLiteChart"], [data-testid="stHorizontalBlock"] { break-inside: avoid; page-break-inside: avoid; }
    * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
}
</style>
""",
    unsafe_allow_html=True,
)


def tiles(items):
    """items: list of dicts with label, value, sub, accent, q (optional)."""
    cols = st.columns(len(items))
    for col, it in zip(cols, items):
        col.markdown(
            f"""<div class="kpi" style="--accent:{it.get('accent', '#888')}">
                  <div class="kpi-q">{it.get('q', '&nbsp;')}</div>
                  <div class="kpi-label">{it['label']}</div>
                  <div class="kpi-value">{it['value']}</div>
                  <div class="kpi-sub">{it.get('sub') or '&nbsp;'}</div>
                </div>""",
            unsafe_allow_html=True,
        )


def how_to_read(text: str):
    st.caption(f"**How to read:** {text}")


FUNNEL_HELP = (
    "Each bar is a pipeline stage, from the first stage at the top to Closed won at the bottom. "
    "The bar width and the number inside show how many deals reached that stage and what share of the "
    "top stage that is. The percentage next to each bar is the conversion from the stage above; the "
    "biggest drop shows where deals get stuck."
)
CURVE_HELP = (
    "The line shows the share of users still active each month after their first active month, averaged "
    "across cohorts and weighted by cohort size. Month 0 is the first active month, so it is always 100%. A steep early drop that then flattens is "
    "normal; the level where the line flattens is the share of users you keep long term."
)


# ── Formatting helpers ───────────────────────────────────────────────────────
def is_missing(x) -> bool:
    return x is None or (isinstance(x, float) and np.isnan(x))


def fmt_int(x):
    return "–" if is_missing(x) else f"{x:,.0f}"


def fmt_pct(x, d=1):
    return "–" if is_missing(x) else f"{x * 100:.{d}f}%"


def fmt_money_exact(x, cur):
    if is_missing(x):
        return "–"
    sym = {"EUR": "€", "USD": "$", "GBP": "£"}.get(cur, "")
    return f"{sym}{x:,.2f}" if sym else f"{x:,.2f} {cur}"


def fmt_money(x, cur):
    if is_missing(x):
        return "–"
    sym = {"EUR": "€", "USD": "$", "GBP": "£"}.get(cur, "")
    if abs(x) >= 1e6:
        s = f"{x / 1e6:,.2f}M"
    elif abs(x) >= 1e4:
        s = f"{x / 1e3:,.1f}k"
    else:
        s = f"{x:,.0f}"
    return f"{sym}{s}" if sym else f"{s} {cur}"


def fmt_hours(h):
    if is_missing(h):
        return "–"
    return f"{h:.1f} h" if h < 48 else f"{h / 24:.1f} days"


def to_bool(s: pd.Series) -> pd.Series:
    return s.fillna(False).astype(bool)


# ── Data ─────────────────────────────────────────────────────────────────────
conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()


@st.cache_data(ttl=600, show_spinner="Loading data from Snowflake…")
def run(sql: str) -> pd.DataFrame:
    return session.sql(sql).to_pandas()


portfolio = run(f"select * from {T_PORTFOLIO}")
revenue = run(f"select * from {T_REVENUE}")
deals = run(f"select * from {T_DEALS}")
retention = run(f"select * from {T_RETENTION}")
ttfv = run(f"select * from {T_TTFV}")

# Snowflake returns upper-case column names, unless a model quoted them in lower case
for _df in (portfolio, revenue, deals, retention, ttfv):
    _df.columns = [c.upper() for c in _df.columns]

# Type clean-up
portfolio["CUSTOMER_STATUS"] = portfolio["CUSTOMER_STATUS"].fillna("Unknown")
deals["CREATED_AT"] = pd.to_datetime(deals["CREATED_AT"])
deals["CLOSED_AT"] = pd.to_datetime(deals["CLOSED_AT"])
for c in ["IS_WON", "IS_LOST", "IS_OPEN"]:
    deals[c] = deals[c].fillna(0).astype(int)
retention["COHORT_MONTH"] = pd.to_datetime(retention["COHORT_MONTH"])
retention["ACTIVITY_MONTH"] = pd.to_datetime(retention["ACTIVITY_MONTH"])
ttfv["CREATED_AT"] = pd.to_datetime(ttfv["CREATED_AT"])
ttfv["FIRST_SEARCH_AT"] = pd.to_datetime(ttfv["FIRST_SEARCH_AT"])
ttfv["DATA_END_DATE"] = pd.to_datetime(ttfv["DATA_END_DATE"])
if "TTFV_HOURS" not in ttfv.columns:
    ttfv["TTFV_HOURS"] = (ttfv["FIRST_SEARCH_AT"] - ttfv["CREATED_AT"]).dt.total_seconds() / 3600

# Use the flags from the mart when they exist; otherwise derive them from the timestamps,
# with the same rules the mart uses.
_age_days = (ttfv["DATA_END_DATE"] - ttfv["CREATED_AT"]).dt.total_seconds() / 86400
_derived = {
    "IS_ACTIVATED": ttfv["FIRST_SEARCH_AT"].notna(),
    "ELIGIBLE_FOR_7_DAY_MEASUREMENT": _age_days >= 7,
    "ELIGIBLE_FOR_30_DAY_MEASUREMENT": _age_days >= 30,
    "ACTIVATED_WITHIN_7_DAYS": ttfv["TTFV_HOURS"].le(7 * 24),
    "ACTIVATED_WITHIN_30_DAYS": ttfv["TTFV_HOURS"].le(30 * 24),
}
for c, fallback in _derived.items():
    ttfv[c] = to_bool(ttfv[c]) if c in ttfv.columns else fallback.fillna(False).astype(bool)

# ── Sidebar: global settings ─────────────────────────────────────────────────
st.sidebar.header("Settings")

currencies = (
    revenue.groupby("CURRENCY")["TOTAL_WON_VALUE"].sum().sort_values(ascending=False).index.tolist()
)
currency = st.sidebar.selectbox(
    "Currency",
    currencies or ["EUR"],
    help="Amounts are never summed across currencies.",
)

all_statuses = portfolio["CUSTOMER_STATUS"].value_counts().index.tolist()


def looks_like_customer(status: str) -> bool:
    s = status.lower()
    excluded = ("former", "churn", "lost", "prospect", "inactive", "ex-", "lead")
    return ("customer" in s or "active" in s) and not any(x in s for x in excluded)


customer_statuses = st.sidebar.multiselect(
    "Statuses counted as a customer",
    all_statuses,
    default=[s for s in all_statuses if looks_like_customer(s)] or all_statuses[:1],
    help="Defines Q1. Check the defaults against the CUSTOMER_STATUS logic in the mart.",
)

print_layout = st.sidebar.toggle(
    "Print layout",
    value=False,
    help="Shows every section on one page, each starting on a new PDF page, so you can save the whole "
         "dashboard with your browser's Print → Save as PDF.",
)

if st.sidebar.button("Refresh data"):
    st.cache_data.clear()
    st.rerun()


# ── KPI calculations ─────────────────────────────────────────────────────────
# Q1 — customers today
customers = portfolio[portfolio["CUSTOMER_STATUS"].isin(customer_statuses)]
n_customers = customers["HUBSPOT_COMPANY_ID"].nunique()
n_companies = portfolio["HUBSPOT_COMPANY_ID"].nunique()

# Q2 — ACV (won value / won deals, one currency at a time)
rev_c = revenue[revenue["CURRENCY"] == currency]
won_deals_n = rev_c["WON_DEALS"].sum()
won_value = rev_c["TOTAL_WON_VALUE"].sum()
acv = won_value / won_deals_n if won_deals_n else None  # overall average won deal value


def _norm_type(t):
    return "".join(ch for ch in str(t).lower() if ch.isalnum())


_nb = rev_c[rev_c["DEAL_TYPE"].map(_norm_type) == "newbusiness"]
_eb = rev_c[rev_c["DEAL_TYPE"].map(_norm_type) == "existingbusiness"]
nb_avg = _nb["TOTAL_WON_VALUE"].sum() / _nb["WON_DEALS"].sum() if _nb["WON_DEALS"].sum() else None
eb_avg = _eb["TOTAL_WON_VALUE"].sum() / _eb["WON_DEALS"].sum() if _eb["WON_DEALS"].sum() else None
est_acv = nb_avg  # estimated ACV: new-business deals, assuming they are annual licences

# Q3 — retention, weighted by cohort size, only over cohorts old enough
max_activity = retention["ACTIVITY_MONTH"].max()
cohort_sizes = retention.groupby("COHORT_MONTH")["COHORT_SIZE"].max()


def weighted_retention(k: int, cohorts=None):
    sizes = cohort_sizes if cohorts is None else cohort_sizes[cohort_sizes.index.isin(cohorts)]
    eligible = sizes[[(c + pd.DateOffset(months=k)) <= max_activity for c in sizes.index]]
    if eligible.empty or eligible.sum() == 0:
        return None, 0
    active = retention[
        (retention["MONTHS_SINCE_COHORT"] == k) & retention["COHORT_MONTH"].isin(eligible.index)
    ]["ACTIVE_USERS"].sum()
    return active / eligible.sum(), len(eligible)


def retention_curve(cohorts=None) -> pd.DataFrame:
    rows = []
    max_k = int(retention["MONTHS_SINCE_COHORT"].max()) if not retention.empty else 0
    for k in range(0, max_k + 1):
        rate, n = weighted_retention(k, cohorts)
        if rate is not None:
            rows.append({"MONTHS_SINCE_COHORT": k, "RETENTION": rate, "COHORTS": n})
    return pd.DataFrame(rows)


m1, m1_n = weighted_retention(1)
m3, m3_n = weighted_retention(3)
m6, m6_n = weighted_retention(6)


# Q4 — funnel
def funnel_counts(df: pd.DataFrame) -> pd.DataFrame:
    def back_fill(r):
        # A deal that reached a later stage also passed the earlier ones (stages can be skipped in HubSpot)
        return r.iloc[:, ::-1].cummax(axis=1).iloc[:, ::-1]

    reached = back_fill(df[STAGE_COLS].notna().astype(int))
    # Closed won = deals that are won today, so the funnel matches the won-deal count used for ACV
    # and win rate. Deals that entered Closed won and were later moved out still count for the
    # earlier stages they passed.
    reached["ENTERED_CLOSED_WON_AT"] = (df["IS_WON"] == 1).astype(int).values
    reached = back_fill(reached)
    counts = reached.sum().values
    out = pd.DataFrame({"STAGE": STAGE_NAMES, "DEALS": counts})
    top = out["DEALS"].iloc[0]
    out["PCT_OF_TOP"] = out["DEALS"] / top if top else np.nan
    out["STEP_CONVERSION"] = out["DEALS"] / out["DEALS"].shift(1)
    return out


def win_rate(df: pd.DataFrame):
    closed = df["IS_WON"].sum() + df["IS_LOST"].sum()
    return df["IS_WON"].sum() / closed if closed else None


funnel_all = funnel_counts(deals)
win_rate_all = win_rate(deals)
median_cycle_all = deals.loc[deals["IS_WON"] == 1, "SALES_CYCLE_DAYS"].median()

# Q5 — TTFV
activation_rate = ttfv["IS_ACTIVATED"].mean() if len(ttfv) else None
median_ttfv_h = ttfv.loc[ttfv["IS_ACTIVATED"], "TTFV_HOURS"].median()
e7 = ttfv[ttfv["ELIGIBLE_FOR_7_DAY_MEASUREMENT"]]
e30 = ttfv[ttfv["ELIGIBLE_FOR_30_DAY_MEASUREMENT"]]
rate7 = e7["ACTIVATED_WITHIN_7_DAYS"].mean() if len(e7) else None
rate30 = e30["ACTIVATED_WITHIN_30_DAYS"].mean() if len(e30) else None
data_end = pd.to_datetime(ttfv["DATA_END_DATE"]).max() if len(ttfv) else None


# ── Chart builders ───────────────────────────────────────────────────────────
def funnel_chart(fdf: pd.DataFrame, key: str, order=None, color=None, height=380):
    """Centered funnel built in Altair, so no extra package is needed.
    fdf needs STAGE, DEALS, PCT_OF_TOP and STEP_CONVERSION columns."""
    order = order or STAGE_NAMES
    color = color or ACCENTS["funnel"]
    if HAS_PLOTLY:
        fig = go.Figure(
            go.Funnel(
                y=fdf["STAGE"],
                x=fdf["DEALS"],
                textinfo="value+percent initial+percent previous",
                marker={"color": color},
                connector={"line": {"color": "rgba(128,128,128,.4)", "width": 1}},
            )
        )
        fig.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            height=height,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True, key=key)
        return

    df = fdf.copy()
    df["LEFT"] = -df["DEALS"] / 2
    df["RIGHT"] = df["DEALS"] / 2
    df["LABEL"] = df.apply(
        lambda r: f"{int(r.DEALS):,}  ·  {r.PCT_OF_TOP:.0%} of top"
        if pd.notna(r.PCT_OF_TOP) else f"{int(r.DEALS):,}",
        axis=1,
    )
    # Step conversion shown between bars, on the stage it converts into
    df["STEP_LABEL"] = df["STEP_CONVERSION"].map(lambda v: f"↓ {v:.0%}" if pd.notna(v) else "")

    top = max(df["DEALS"].max(), 1)
    y = alt.Y("STAGE:N", sort=order, title=None,
              axis=alt.Axis(labelLimit=200, ticks=False, domain=False, labelPadding=8))
    tooltip = [
        "STAGE",
        "DEALS",
        alt.Tooltip("PCT_OF_TOP:Q", format=".1%", title="% of top"),
        alt.Tooltip("STEP_CONVERSION:Q", format=".1%", title="From previous stage"),
    ]

    bars = (
        alt.Chart(df)
        .mark_bar(color=color, cornerRadius=3)
        .encode(
            y=y,
            x=alt.X("LEFT:Q", axis=None, scale=alt.Scale(domain=[-top * 0.62, top * 0.62])),
            x2="RIGHT:Q",
            tooltip=tooltip,
        )
    )
    # Labels in the center of each bar
    labels = (
        alt.Chart(df)
        .mark_text(color="white", fontWeight="bold", fontSize=12)
        .encode(y=y, x=alt.X("MID:Q", scale=alt.Scale(domain=[-top * 0.62, top * 0.62]), axis=None), text="LABEL:N", tooltip=tooltip)
        .transform_calculate(MID="0")
    )
    steps = (
        alt.Chart(df)
        .mark_text(align="left", dx=6, fontSize=11, opacity=0.75)
        .encode(y=y, x=alt.X("RIGHT:Q", scale=alt.Scale(domain=[-top * 0.62, top * 0.62]), axis=None), text="STEP_LABEL:N")
    )
    chart = (bars + labels + steps).properties(height=height).configure_view(strokeWidth=0)
    st.altair_chart(chart, use_container_width=True)


def retention_curve_chart(curve: pd.DataFrame):
    if curve.empty:
        st.info("No retention data yet.")
        return
    chart = (
        alt.Chart(curve)
        .mark_line(point=True, color=ACCENTS["retention"])
        .encode(
            x=alt.X("MONTHS_SINCE_COHORT:O", title="Months since first active month"),
            y=alt.Y("RETENTION:Q", title="Users still active", axis=alt.Axis(format="%"),
                    scale=alt.Scale(domain=[0, 1])),
            tooltip=[
                alt.Tooltip("MONTHS_SINCE_COHORT:O", title="Month"),
                alt.Tooltip("RETENTION:Q", format=".1%", title="Retention"),
                alt.Tooltip("COHORTS:Q", title="Cohorts included"),
            ],
        )
        .properties(height=380)
    )
    st.altair_chart(chart, use_container_width=True)


# ── Header ───────────────────────────────────────────────────────────────────
st.title("Commercial & Product KPIs")
st.markdown(
    "This dashboard answers five questions about the business: how many customers we have, "
    "what an average contract is worth, how well we keep users, how deals move through the sales "
    "pipeline, and how quickly new organisations get value from the product. "
    "Commercial figures come from HubSpot deals and companies; product figures come from backend "
    "usage events. Use the sidebar to pick the currency and decide which company statuses count as a customer."
)
st.caption(
    f"Source: dbt models in {DATABASE}. "
    + (f"Product data through {data_end:%d %b %Y}." if data_end is not None else "")
)

st.info(
    f"**Settings in this view:** amounts in {currency}; customers are companies with status "
    f"{', '.join(customer_statuses) if customer_statuses else '(none selected)'}."
)

SECTION_NAMES = ["Overview", "Customers", "Contract value", "Retention", "Sales funnel", "Time to first value"]
if print_layout:
    # One long page instead of tabs; each section starts on a new PDF page
    _sections = []
    for i, name in enumerate(SECTION_NAMES):
        box = st.container()
        if i > 0:
            box.markdown('<div class="page-break"></div>', unsafe_allow_html=True)
        box.header(name)
        _sections.append(box)
    tab_overview, tab_cust, tab_acv, tab_ret, tab_funnel, tab_ttfv = _sections
else:
    tab_overview, tab_cust, tab_acv, tab_ret, tab_funnel, tab_ttfv = st.tabs(SECTION_NAMES)

# ── Overview ─────────────────────────────────────────────────────────────────
with tab_overview:
    st.markdown("The headline answer to each question. Open the other tabs for the breakdown behind each number.")
    tiles(
        [
            dict(q="Q1", label="Customers today", value=fmt_int(n_customers),
                 sub=f"of {fmt_int(n_companies)} companies in HubSpot", accent=ACCENTS["customers"]),
            dict(q="Q2", label="Estimated ACV (new business)", value=fmt_money(est_acv, currency),
                 sub=f"Assumes annual licences. Average won deal overall: {fmt_money_exact(acv, currency)}",
                 accent=ACCENTS["acv"]),
            dict(q="Q3", label="Month-1 retention", value=fmt_pct(m1),
                 sub=f"Month 3: {fmt_pct(m3)} · Month 6: {fmt_pct(m6)}", accent=ACCENTS["retention"]),
            dict(q="Q4", label="Win rate", value=fmt_pct(win_rate_all),
                 sub=f"Won ÷ closed deals · median cycle {fmt_int(median_cycle_all)} days",
                 accent=ACCENTS["funnel"]),
            dict(q="Q5", label="Median time to first value", value=fmt_hours(median_ttfv_h),
                 sub=f"{fmt_pct(rate7)} activate within 7 days", accent=ACCENTS["ttfv"]),
        ]
    )
    st.write("")
    left, right = st.columns(2)
    with left:
        st.subheader("Sales funnel")
        funnel_chart(funnel_all, key="overview_funnel")
        how_to_read(FUNNEL_HELP)
    with right:
        st.subheader("User retention curve")
        retention_curve_chart(retention_curve())
        how_to_read(CURVE_HELP)

# ── Q1 Customers ─────────────────────────────────────────────────────────────
with tab_cust:
    st.markdown(
        "**How many customers do we have today?** Counts HubSpot companies whose customer status is selected "
        "in the sidebar, and shows where they sit by industry and country and which have open expansion deals."
    )
    churned = portfolio[portfolio["WON_THEN_LOST_DEALS"].fillna(0) > 0]["HUBSPOT_COMPANY_ID"].nunique()
    expanding = customers[customers["OPEN_EXPANSION_DEALS"].fillna(0) > 0]["HUBSPOT_COMPANY_ID"].nunique()
    open_nb = portfolio[portfolio["OPEN_NEW_BUSINESS_DEALS"].fillna(0) > 0]["HUBSPOT_COMPANY_ID"].nunique()
    tiles(
        [
            dict(label="Customers today", value=fmt_int(n_customers), accent=ACCENTS["customers"],
                 sub=", ".join(customer_statuses) or "No status selected"),
            dict(label="Customers with an open expansion deal", value=fmt_int(expanding),
                 accent=ACCENTS["customers"], sub=fmt_pct(expanding / n_customers) + " of customers" if n_customers else None),
            dict(label="Companies with open new-business deals", value=fmt_int(open_nb),
                 accent=ACCENTS["customers"], sub="Potential new customers"),
            dict(label="Companies with a won-then-lost deal", value=fmt_int(churned),
                 accent=ACCENTS["customers"], sub="Churn signal"),
        ]
    )
    st.write("")
    c1, c2 = st.columns(2)
    st.subheader("Companies by status")
    status_counts = (portfolio.groupby("CUSTOMER_STATUS")["HUBSPOT_COMPANY_ID"].nunique()
                     .sort_values(ascending=False))
    status_tiles = [
        dict(
            label=status,
            value=fmt_int(n),
            sub=("Counted as customer" if status in customer_statuses else "Not counted as customer")
                + f", {fmt_pct(n / n_companies)} of companies",
            accent=ACCENTS["customers"] if status in customer_statuses else "#B8BEC4",
        )
        for status, n in status_counts.items()
    ]
    for i in range(0, len(status_tiles), 4):
        tiles(status_tiles[i:i + 4])
        st.write("")
    how_to_read(
        "One tile per HubSpot customer status, showing how many companies have that status. "
        "Coloured tiles are the statuses counted as customers today; grey tiles are not counted."
    )

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("From company to customer")
        cust_stages = ["Companies in HubSpot", "Had at least one deal", "Won at least one deal", "Customer today"]
        cust_counts = [
            n_companies,
            portfolio.loc[portfolio["TOTAL_DEALS"].fillna(0) > 0, "HUBSPOT_COMPANY_ID"].nunique(),
            portfolio.loc[portfolio["DEALS_EVER_WON"].fillna(0) > 0, "HUBSPOT_COMPANY_ID"].nunique(),
            n_customers,
        ]
        cust_funnel = pd.DataFrame({"STAGE": cust_stages, "DEALS": cust_counts})
        cust_funnel["PCT_OF_TOP"] = cust_funnel["DEALS"] / n_companies if n_companies else np.nan
        cust_funnel["STEP_CONVERSION"] = cust_funnel["DEALS"] / cust_funnel["DEALS"].shift(1)
        funnel_chart(cust_funnel, key="customer_funnel", order=cust_stages,
                     color=ACCENTS["customers"], height=300)
        how_to_read(
            "Each bar is a step from being a company in HubSpot to being a customer today. The number inside "
            "shows how many companies reached that step and their share of all companies; the percentage next "
            "to each bar is the share of the step above that made it. A drop between won and customer today "
            "means companies that bought once but are no longer customers."
        )
    with c2:
        dim = st.radio("Break customers down by", ["INDUSTRY", "COUNTRY"], horizontal=True,
                       format_func=str.title)
        by_dim = (customers.assign(**{dim: customers[dim].fillna("Unknown")})
                  .groupby(dim)["HUBSPOT_COMPANY_ID"].nunique().reset_index(name="CUSTOMERS")
                  .sort_values("CUSTOMERS", ascending=False).head(15))
        st.altair_chart(
            alt.Chart(by_dim).mark_bar(color=ACCENTS["customers"]).encode(
                y=alt.Y(f"{dim}:N", sort="-x", title=None),
                x=alt.X("CUSTOMERS:Q", title="Customers"),
                tooltip=[dim, "CUSTOMERS"],
            ),
            use_container_width=True,
        )
        how_to_read("Bars rank the top 15 industries or countries by number of customers; a longer bar means more customers. Use the toggle above to switch between industry and country.")
    st.subheader("Customer list")
    st.dataframe(
        customers[["COMPANY_NAME", "DOMAIN", "INDUSTRY", "COUNTRY", "CUSTOMER_STATUS",
                   "WON_DEALS", "OPEN_DEALS", "OPEN_EXPANSION_DEALS", "CREATE_DATE"]]
        .sort_values("WON_DEALS", ascending=False),
        use_container_width=True, hide_index=True,
    )

# ── Q2 ACV ───────────────────────────────────────────────────────────────────
with tab_acv:
    st.markdown(
        "**What is our Average Contract Value (ACV)?** ACV means *annual* contract value, which is not "
        "automatically the same as the average deal value. The data has no contract-duration field, so the "
        "estimated ACV uses new-business deals and assumes each is an annual licence."
    )
    max_deal = rev_c["MAX_DEAL_VALUE"].max() if len(rev_c) else None
    min_deal = rev_c["MIN_DEAL_VALUE"].min() if len(rev_c) else None
    tiles(
        [
            dict(label="Estimated new-business ACV", value=fmt_money_exact(est_acv, currency),
                 accent=ACCENTS["acv"], sub="If new-business deals are annual licences"),
            dict(label="Average won deal value, all deals", value=fmt_money_exact(acv, currency),
                 accent=ACCENTS["acv"], sub=f"{fmt_money(won_value, currency)} ÷ {fmt_int(won_deals_n)} won deals"),
            dict(label="Average won deal value, new business", value=fmt_money_exact(nb_avg, currency),
                 accent=ACCENTS["acv"], sub=f"{fmt_int(_nb['WON_DEALS'].sum())} deals"),
            dict(label="Average won deal value, existing business", value=fmt_money_exact(eb_avg, currency),
                 accent=ACCENTS["acv"], sub=f"{fmt_int(_eb['WON_DEALS'].sum())} deals"),
        ]
    )
    st.write("")
    tiles(
        [
            dict(label="Total won value", value=fmt_money(won_value, currency), accent=ACCENTS["acv"]),
            dict(label="Won deals", value=fmt_int(won_deals_n), accent=ACCENTS["acv"]),
            dict(label="Deal size range", value=f"{fmt_money(min_deal, currency)} – {fmt_money(max_deal, currency)}",
                 accent=ACCENTS["acv"]),
        ]
    )
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("ACV by deal type")
        st.altair_chart(
            alt.Chart(rev_c).mark_bar(color=ACCENTS["acv"]).encode(
                y=alt.Y("DEAL_TYPE:N", sort="-x", title=None),
                x=alt.X("AVERAGE_DEAL_VALUE:Q", title=f"Average contract value ({currency})"),
                tooltip=["DEAL_TYPE", "WON_DEALS",
                         alt.Tooltip("AVERAGE_DEAL_VALUE:Q", format=",.0f"),
                         alt.Tooltip("TOTAL_WON_VALUE:Q", format=",.0f")],
            ),
            use_container_width=True,
        )
        how_to_read("Each bar is the average value of a won deal of that type. Compare bar lengths to see which kind of deal brings in larger contracts. Hover to see how many deals sit behind each average; an average built on only a few deals can swing a lot.")
    with c2:
        st.subheader("ACV trend by close quarter")
        won = deals[(deals["IS_WON"] == 1) & (deals["CURRENCY"] == currency) & deals["CLOSED_AT"].notna()].copy()
        if won.empty:
            st.info("No won deals in this currency yet.")
        else:
            won["CLOSE_QUARTER"] = won["CLOSED_AT"].dt.to_period("Q").astype(str)
            trend = won.groupby("CLOSE_QUARTER").agg(ACV=("AMOUNT", "mean"), WON_DEALS=("DEAL_ID", "count")).reset_index()
            st.altair_chart(
                alt.Chart(trend).mark_line(point=True, color=ACCENTS["acv"]).encode(
                    x=alt.X("CLOSE_QUARTER:O", title=None),
                    y=alt.Y("ACV:Q", title=f"ACV ({currency})"),
                    tooltip=["CLOSE_QUARTER", alt.Tooltip("ACV:Q", format=",.0f"), "WON_DEALS"],
                ),
                use_container_width=True,
            )
            how_to_read("Each point is the average value of deals won in that quarter. A rising line means newer contracts are larger. Hover to see how many deals closed in the quarter; quarters with only a few deals are noisy.")
    st.dataframe(rev_c, use_container_width=True, hide_index=True)
    with st.expander("How ACV is calculated"):
        st.markdown(
            "ACV = total value of closed-won deals ÷ number of closed-won deals, per currency. "
            "This assumes the HubSpot deal **amount is an annual value**. If deals carry multi-year "
            "totals, divide by contract length in years before averaging."
        )

# ── Q3 Retention ─────────────────────────────────────────────────────────────
with tab_ret:
    st.markdown(
        "**What is the retention of our users?** Users are grouped by the month of their first product use. "
        "The curve shows the share of users still active in each following month, averaged across those cohorts."
    )
    tiles(
        [
            dict(label="Month-1 retention", value=fmt_pct(m1), sub=f"{m1_n} cohorts", accent=ACCENTS["retention"]),
            dict(label="Month-3 retention", value=fmt_pct(m3), sub=f"{m3_n} cohorts", accent=ACCENTS["retention"]),
            dict(label="Month-6 retention", value=fmt_pct(m6), sub=f"{m6_n} cohorts", accent=ACCENTS["retention"]),
            dict(label="Users in tracked cohorts", value=fmt_int(cohort_sizes.sum()),
                 sub=f"{len(cohort_sizes)} monthly cohorts", accent=ACCENTS["retention"]),
        ]
    )
    st.write("")
    all_cohorts = sorted(cohort_sizes.index)
    n_show = st.slider("Cohorts to show", 3, max(3, len(all_cohorts)), min(12, max(3, len(all_cohorts))))
    shown = all_cohorts[-n_show:]

    st.subheader("Average retention curve")
    retention_curve_chart(retention_curve(shown))
    how_to_read(CURVE_HELP)
    with st.expander("How retention is calculated"):
        st.markdown(
            "Retention in month *k* = active users in month *k* ÷ cohort size. Headline figures are "
            "weighted by cohort size and only include cohorts old enough to have reached month *k*, "
            "so young cohorts don't drag the average down. The latest activity month may be partial."
        )

# ── Q4 Sales funnel ──────────────────────────────────────────────────────────
with tab_funnel:
    st.markdown(
        "**How does our sales funnel convert?** How many deals reach each pipeline stage, the conversion from one "
        "stage to the next, and the stage where lost deals dropped out. Filter by pipeline, deal type and creation date."
    )
    f1, f2, f3 = st.columns(3)
    pipelines = sorted(deals["PIPELINE"].dropna().unique())
    deal_types = sorted(deals["DEAL_TYPE"].dropna().unique())
    sel_pipe = f1.multiselect("Pipeline", pipelines, default=pipelines)
    sel_type = f2.multiselect("Deal type", deal_types, default=deal_types)
    min_d, max_d = deals["CREATED_AT"].min(), deals["CREATED_AT"].max()
    date_range = f3.date_input("Deal created between", value=(min_d.date(), max_d.date()))

    fd = deals[deals["PIPELINE"].isin(sel_pipe) & deals["DEAL_TYPE"].isin(sel_type)]
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]) + pd.Timedelta(days=1)
        fd = fd[(fd["CREATED_AT"] >= start) & (fd["CREATED_AT"] < end)]

    fdf = funnel_counts(fd)
    open_value = fd.loc[(fd["IS_OPEN"] == 1) & (fd["CURRENCY"] == currency), "AMOUNT"].sum()
    tiles(
        [
            dict(label="Deals in view", value=fmt_int(len(fd)), accent=ACCENTS["funnel"],
                 sub=f"{fmt_int(fd['IS_OPEN'].sum())} still open"),
            dict(label="Win rate", value=fmt_pct(win_rate(fd)), accent=ACCENTS["funnel"],
                 sub="Won ÷ (won + lost)"),
            dict(label="Median sales cycle", value=f"{fmt_int(fd.loc[fd['IS_WON'] == 1, 'SALES_CYCLE_DAYS'].median())} days",
                 accent=ACCENTS["funnel"], sub="Won deals, created → closed"),
            dict(label="Open pipeline", value=fmt_money(open_value, currency), accent=ACCENTS["funnel"],
                 sub=f"Open deals in {currency}"),
        ]
    )
    st.write("")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("Stage funnel")
        funnel_chart(fdf, key="tab_funnel")
        how_to_read(FUNNEL_HELP)
    with c2:
        st.subheader("Where lost deals dropped out")
        lost = fd[fd["IS_LOST"] == 1]
        if lost.empty:
            st.info("No lost deals in this selection.")
        else:
            pre_won = STAGE_COLS[:-1]
            reached = lost[pre_won].notna().to_numpy()
            furthest = len(pre_won) - 1 - reached[:, ::-1].argmax(axis=1)
            labels = np.where(reached.any(axis=1), np.array(STAGE_NAMES[:-1])[furthest], "No stage recorded")
            drop = pd.Series(labels).value_counts().reset_index()
            drop.columns = ["FURTHEST_STAGE", "LOST_DEALS"]
            st.altair_chart(
                alt.Chart(drop).mark_bar(color="#B05A4A").encode(
                    y=alt.Y("FURTHEST_STAGE:N", sort=STAGE_NAMES[:-1] + ["No stage recorded"], title=None),
                    x=alt.X("LOST_DEALS:Q", title="Lost deals"),
                    tooltip=["FURTHEST_STAGE", "LOST_DEALS"],
                ),
                use_container_width=True,
            )
            how_to_read("Each bar counts lost deals by the furthest stage they reached before they were lost. A long bar at a late stage means deals fall through after a lot of sales effort; a long bar at an early stage points to weak qualification or poor fit.")
    st.dataframe(
        fdf.style.format({"PCT_OF_TOP": "{:.1%}", "STEP_CONVERSION": "{:.1%}"}, na_rep="–"),
        use_container_width=True, hide_index=True,
    )
    with st.expander("How the funnel is calculated"):
        st.markdown(
            "A deal counts as having reached a stage if it has that stage's entry timestamp **or any later one** — "
            "HubSpot lets reps skip stages, so this keeps the funnel monotonic. Lost deals count up to the furthest "
            "stage they reached. Closed won counts deals that are won today, so it matches the won-deal count "
            "used for ACV and win rate; deals moved out of Closed won after reaching it are not counted there. "
            "Win rate ignores open deals."
        )

# ── Q5 TTFV ──────────────────────────────────────────────────────────────────
with tab_ttfv:
    st.markdown(
        "**How fast do new organisations reach first value?** Time to first value (TTFV) is the time from an "
        "organisation's signup to its first search. Shows how long activation takes and whether it is getting faster."
    )
    tiles(
        [
            dict(label="Median time to first value", value=fmt_hours(median_ttfv_h), accent=ACCENTS["ttfv"],
                 sub="Signup → first search, activated orgs"),
            dict(label="Activated within 7 days", value=fmt_pct(rate7), accent=ACCENTS["ttfv"],
                 sub=f"{fmt_int(len(e7))} eligible orgs"),
            dict(label="Activated within 30 days", value=fmt_pct(rate30), accent=ACCENTS["ttfv"],
                 sub=f"{fmt_int(len(e30))} eligible orgs"),
            dict(label="Activated overall", value=fmt_pct(activation_rate), accent=ACCENTS["ttfv"],
                 sub=f"{fmt_int(ttfv['IS_ACTIVATED'].sum())} of {fmt_int(len(ttfv))} orgs"),
        ]
    )
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("How long activation takes")
        act = ttfv[ttfv["IS_ACTIVATED"]].copy()
        buckets = ["< 1 h", "1–24 h", "1–3 days", "3–7 days", "7–14 days", "14–30 days", "30+ days"]
        act["BUCKET"] = pd.cut(act["TTFV_HOURS"], bins=[0, 1, 24, 72, 168, 336, 720, np.inf],
                               labels=buckets, right=False, include_lowest=True)
        dist = act["BUCKET"].value_counts().reindex(buckets, fill_value=0).reset_index()
        dist.columns = ["BUCKET", "ORGS"]
        st.altair_chart(
            alt.Chart(dist).mark_bar(color=ACCENTS["ttfv"]).encode(
                x=alt.X("BUCKET:N", sort=buckets, title="Time from signup to first search"),
                y=alt.Y("ORGS:Q", title="Organisations"),
                tooltip=["BUCKET", "ORGS"],
            ),
            use_container_width=True,
        )
        how_to_read("Each bar counts activated organisations by how long they took from signup to their first search. Bars on the left mean fast activation; a long tail on the right points to onboarding friction. Organisations that never ran a search are not included here.")
    with c2:
        st.subheader("7-day activation by signup month")
        if e7.empty:
            st.info("No organisations are old enough for the 7-day measurement yet.")
        else:
            trend = (e7.assign(SIGNUP_MONTH=e7["CREATED_AT"].dt.to_period("M").dt.to_timestamp())
                     .groupby("SIGNUP_MONTH")
                     .agg(RATE=("ACTIVATED_WITHIN_7_DAYS", "mean"), ORGS=("ORGANIZATION_ID", "count"))
                     .reset_index())
            st.altair_chart(
                alt.Chart(trend).mark_line(point=True, color=ACCENTS["ttfv"]).encode(
                    x=alt.X("SIGNUP_MONTH:T", title=None, axis=alt.Axis(format="%b %Y")),
                    y=alt.Y("RATE:Q", title="Activated within 7 days", axis=alt.Axis(format="%"),
                            scale=alt.Scale(domain=[0, 1])),
                    tooltip=[alt.Tooltip("SIGNUP_MONTH:T", format="%b %Y"),
                             alt.Tooltip("RATE:Q", format=".1%"), "ORGS"],
                ),
                use_container_width=True,
            )
            how_to_read("Each point is the share of organisations that signed up in that month and ran their first search within 7 days. A rising line means onboarding is getting faster. Hover to see how many organisations sit behind each point.")
    with st.expander("How TTFV is calculated"):
        st.markdown(
            "Time to first value = hours from organisation creation to its first search. The 7- and 30-day rates "
            "only include organisations created at least 7 / 30 days before the data end date, so recent signups "
            "don't look artificially unactivated."
        )
