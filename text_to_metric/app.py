"""
RevenueGrain console — Streamlit front-end for the SaaS revenue warehouse.

    streamlit run text_to_metric/app.py

The console serves the project's governed metrics — MRR and its movements
(new / expansion / contraction / churn / retained, per
``int_mrr_movements``), net & gross revenue retention (per
``fct_revenue_retention``), the composite account health score (per
``fct_account_health``: usage 0-50 + support 0-30 + revenue 0-20) and
feature adoption — over a deterministic demo dataset built with the same
plan prices (``seeds/seed_plan_tiers.csv``), segments, industries and
feature catalog as ``scripts/generate_data.py``. Global sidebar filters
live-update every view. The original text-to-metric layer lives on the
"Ask a Metric" tab: ask a question in plain English, get SQL generated
against the semantic layer.

CLI (no Streamlit):

    python -m text_to_metric "What was NRR by month in 2025?"
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from text_to_metric.query_builder import QueryBuilder, load_semantic_layer

st.set_page_config(page_title="RevenueGrain — SaaS Revenue Console", page_icon="📊", layout="wide")

# ----------------------------------------------------------------------------
# Custom CSS — dark glass / gradient console styling
# ----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .stApp {
        background: radial-gradient(1200px 600px at 15% -10%, #0f3d2e 0%, transparent 55%),
                    radial-gradient(1000px 500px at 90% 0%, #3b2a08 0%, transparent 50%),
                    #0e1117;
    }
    .rg-hero {
        padding: 1.1rem 1.4rem; border-radius: 16px; margin-bottom: 0.6rem;
        background: linear-gradient(120deg, rgba(16,120,80,.55), rgba(190,140,20,.40));
        border: 1px solid rgba(120,255,190,.35);
        box-shadow: 0 8px 32px rgba(0,0,0,.45);
    }
    .rg-hero h1 {
        margin: 0; font-size: 2.1rem; letter-spacing: .5px;
        background: linear-gradient(90deg,#9fffc8,#ffe9a3,#9fd0ff);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .rg-hero p { margin: .25rem 0 0 0; color: #cfd8e3; font-size: .95rem; }
    div[data-testid="stMetric"] {
        background: rgba(22,27,34,.85); border: 1px solid rgba(110,254,180,.35);
        border-radius: 12px; padding: .6rem .8rem;
        box-shadow: 0 4px 18px rgba(0,0,0,.35);
    }
    div[data-testid="stMetric"]:hover { border-color: rgba(255,233,163,.7); }
    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"] {
        background: rgba(22,27,34,.8); border-radius: 10px 10px 0 0; padding: 6px 14px;
    }
    section[data-testid="stSidebar"] { background: rgba(14,17,23,.92); }
    </style>
    <div class="rg-hero">
      <h1>📊 RevenueGrain — SaaS Revenue Console</h1>
      <p>MRR movements, revenue retention, account health and feature adoption —
         at the right grain. Drag the 3D revenue space, press play on the animated
         movements, slice everything from the sidebar.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Demo dataset — deterministic, built from the project's own domain & logic
# ----------------------------------------------------------------------------
PLAN_PRICES = {1: 49.0, 2: 199.0, 3: 499.0, 4: 1499.0, 5: 2999.0}  # seeds/seed_plan_tiers.csv, $/mo
PLAN_NAMES = {1: "Starter", 2: "Growth", 3: "Scale", 4: "Enterprise", 5: "Enterprise Plus"}
SEGMENT_PLANS = {"smb": [1, 2], "mid-market": [2, 3], "enterprise": [4, 5]}
SEGMENTS = ["smb", "mid-market", "enterprise"]
INDUSTRIES = ["software", "retail", "healthcare", "finance", "manufacturing", "education"]
COUNTRIES = ["US", "CA", "GB", "DE", "IN", "AU"]
FEATURES = ["dashboards", "api_access", "sso", "alerts", "exports", "audit_log", "workflows"]
FEATURE_LABEL = {
    "dashboards": "Dashboards", "api_access": "API Access", "sso": "Single Sign-On",
    "alerts": "Alerts", "exports": "Data Exports", "audit_log": "Audit Log",
    "workflows": "Workflows",
}
MONTHS = pd.period_range("2024-01", "2025-12", freq="M")


@st.cache_data
def build_demo() -> dict:
    rng = np.random.default_rng(42)
    n_accounts = 170
    acct_rows, mrr_rows, feat_rows = [], [], []
    for i in range(n_accounts):
        segment = rng.choice(SEGMENTS, p=[0.5, 0.35, 0.15])
        industry = rng.choice(INDUSTRIES)
        country = rng.choice(COUNTRIES)
        plan = int(rng.choice(SEGMENT_PLANS[segment]))
        acct = f"ACC-{i + 1:03d}"
        acct_rows.append(
            {"account_id": acct, "segment": segment, "industry": industry,
             "country": country, "plan_id": plan, "plan_name": PLAN_NAMES[plan]}
        )
        start = int(rng.integers(0, 16))
        churned = rng.random() < 0.30
        last = int(rng.integers(start + 3, 24)) if churned else 23
        last = min(last, 23)
        price = PLAN_PRICES[plan]
        engagement = rng.uniform(0.5, 1.6)  # per-account usage intensity
        for mi in range(start, last + 1):
            # step changes: expansion / contraction, as plan moves in the generator
            r = rng.random()
            if mi > start and r < 0.07 and plan < 5:
                plan += 1
                price = PLAN_PRICES[plan]
            elif mi > start and r > 0.96 and plan > SEGMENT_PLANS[segment][0]:
                plan -= 1
                price = PLAN_PRICES[plan]
            monthly_events = int(max(0, rng.normal(260 * engagement * (0.6 + 0.25 * plan), 70)))
            tickets = int(rng.poisson(1.1))
            high_pri = int(rng.binomial(tickets, 0.25)) if tickets else 0
            # fct_account_health scoring, verbatim formula
            usage_score = min(50.0, monthly_events / 10.0)
            support_score = max(0.0, 30.0 - high_pri * 10)
            revenue_score = 20.0 if price > 0 else 0.0
            health = round(usage_score + support_score + revenue_score, 1)
            mrr_rows.append(
                {"account_id": acct, "segment": segment, "industry": industry,
                 "country": country, "plan_id": plan, "plan_name": PLAN_NAMES[plan],
                 "month_start": MONTHS[mi].to_timestamp(), "mrr": float(price),
                 "monthly_events": monthly_events, "ticket_count": tickets,
                 "high_priority_tickets": high_pri, "health_score": health}
            )
            for f in FEATURES:
                base = {"dashboards": 90, "api_access": 55, "sso": 22, "alerts": 48,
                        "exports": 35, "audit_log": 16, "workflows": 30}[f]
                if rng.random() < 0.82:
                    feat_rows.append(
                        {"account_id": acct, "segment": segment, "industry": industry,
                         "month_start": MONTHS[mi].to_timestamp(), "feature_key": f,
                         "feature_name": FEATURE_LABEL[f],
                         "event_count": int(max(0, rng.normal(base * engagement, base * 0.35)))}
                    )
        if churned and last + 1 < 24:  # synthetic churn row, per int_mrr_movements
            mrr_rows.append(
                {"account_id": acct, "segment": segment, "industry": industry,
                 "country": country, "plan_id": plan, "plan_name": PLAN_NAMES[plan],
                 "month_start": MONTHS[last + 1].to_timestamp(), "mrr": 0.0,
                 "monthly_events": 0, "ticket_count": 0, "high_priority_tickets": 0,
                 "health_score": 0.0}
            )
    mrr = pd.DataFrame(mrr_rows).sort_values(["account_id", "month_start"])
    # int_mrr_movements classification, verbatim
    mrr["prior_mrr"] = mrr.groupby("account_id")["mrr"].shift(1).fillna(0.0)
    mrr["mrr_delta"] = mrr["mrr"] - mrr["prior_mrr"]
    mrr["movement_type"] = np.select(
        [(mrr.prior_mrr == 0) & (mrr.mrr > 0), (mrr.prior_mrr > 0) & (mrr.mrr == 0),
         mrr.mrr > mrr.prior_mrr, mrr.mrr < mrr.prior_mrr],
        ["new", "churn", "expansion", "contraction"], default="retained",
    )
    # fct_revenue_retention: pair each month with the prior month
    paired = mrr[mrr.mrr > 0].copy()
    paired["month_start"] = paired["month_start"] + pd.offsets.MonthBegin(1)
    cur = mrr[["account_id", "month_start", "mrr"]].rename(columns={"mrr": "current_mrr"})
    paired = paired.merge(cur, on=["account_id", "month_start"], how="left")
    paired["current_mrr"] = paired["current_mrr"].fillna(0.0)
    retention = paired.groupby("month_start").apply(
        lambda d: pd.Series({
            "starting_mrr": d["mrr"].sum(),
            "net_revenue_retention": d["current_mrr"].sum() / d["mrr"].sum() if d["mrr"].sum() else np.nan,
            "gross_revenue_retention": np.minimum(d["current_mrr"], d["mrr"]).sum() / d["mrr"].sum() if d["mrr"].sum() else np.nan,
        }), include_groups=False,
    ).reset_index()
    return {"accounts": pd.DataFrame(acct_rows), "mrr": mrr,
            "features": pd.DataFrame(feat_rows), "retention": retention}


DATA = build_demo()
mrr_all, feat_all, ret_all = DATA["mrr"], DATA["features"], DATA["retention"]


def _money(x: float) -> str:
    ax = abs(x)
    if ax >= 1e6:
        return f"${x / 1e6:,.2f}M"
    if ax >= 1e3:
        return f"${x / 1e3:,.1f}K"
    return f"${x:,.0f}"


# ----------------------------------------------------------------------------
# Sidebar — global dynamic filters (every view below reads the filtered data)
# ----------------------------------------------------------------------------
st.sidebar.header("🎛️ Live filters")
dmin, dmax = mrr_all["month_start"].min(), mrr_all["month_start"].max()
picked = st.sidebar.date_input(
    "Month range", value=(dmin.date(), dmax.date()),
    min_value=dmin.date(), max_value=dmax.date(),
)
if isinstance(picked, (list, tuple)) and len(picked) == 2:
    start, end = pd.Timestamp(picked[0]), pd.Timestamp(picked[1]) + pd.offsets.MonthEnd(0)
else:
    start, end = dmin, dmax + pd.offsets.MonthEnd(0)
sel_segments = st.sidebar.multiselect("Segments", SEGMENTS, default=SEGMENTS)
sel_industries = st.sidebar.multiselect("Industries", INDUSTRIES, default=INDUSTRIES)
sel_plans = st.sidebar.multiselect(
    "Plan tiers", [PLAN_NAMES[p] for p in sorted(PLAN_NAMES)],
    default=[PLAN_NAMES[p] for p in sorted(PLAN_NAMES)],
)
min_health = st.sidebar.slider("Min health score (account-months)", 0, 100, 0)


def _apply(df: pd.DataFrame) -> pd.DataFrame:
    out = df[(df["month_start"] >= start) & (df["month_start"] <= end)]
    if sel_segments:
        out = out[out["segment"].isin(sel_segments)]
    if "industry" in out.columns and sel_industries:
        out = out[out["industry"].isin(sel_industries)]
    if "plan_name" in out.columns and sel_plans:
        out = out[out["plan_name"].isin(sel_plans)]
    return out


f_mrr = _apply(mrr_all)
f_feat = _apply(feat_all)
f_active = f_mrr[f_mrr["mrr"] > 0]
if min_health > 0:
    f_active = f_active[f_active["health_score"] >= min_health]
# retention follows the segment/industry slice via its months present in f_mrr
f_ret = ret_all[(ret_all["month_start"] >= start) & (ret_all["month_start"] <= end)]

# ----------------------------------------------------------------------------
# KPI row — latest month in the filter, with deltas vs the prior month
# ----------------------------------------------------------------------------
if not f_active.empty:
    latest_month = f_active["month_start"].max()
    cur = f_active[f_active["month_start"] == latest_month]
    prev_month = latest_month - pd.offsets.MonthBegin(1)
    prev = f_active[f_active["month_start"] == prev_month]
    cur_mrr, prev_mrr = float(cur["mrr"].sum()), float(prev["mrr"].sum())
    cur_health = float(cur["health_score"].mean())
    prev_health = float(prev["health_score"].mean()) if not prev.empty else cur_health
    ret_row = f_ret[f_ret["month_start"] == latest_month]
    nrr = float(ret_row["net_revenue_retention"].iloc[0]) if not ret_row.empty else float("nan")
    ret_prev = f_ret[f_ret["month_start"] == prev_month]
    nrr_prev = float(ret_prev["net_revenue_retention"].iloc[0]) if not ret_prev.empty else nrr
    churned = f_mrr[(f_mrr["movement_type"] == "churn") & (f_mrr["month_start"] == latest_month)]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("MRR (latest month)", _money(cur_mrr),
              delta=f"{_money(cur_mrr - prev_mrr)} vs prior month" if not prev.empty else None)
    c2.metric("Active accounts", f"{cur['account_id'].nunique()}",
              delta=f"{cur['account_id'].nunique() - prev['account_id'].nunique():+d} vs prior month" if not prev.empty else None)
    c3.metric("Net revenue retention", f"{nrr:.1%}" if pd.notna(nrr) else "—",
              delta=f"{(nrr - nrr_prev):+.1%} vs prior month" if pd.notna(nrr) else None)
    c4.metric("Avg health score", f"{cur_health:.1f}",
              delta=f"{cur_health - prev_health:+.1f} vs prior month" if not prev.empty else None)
    c5.metric("Churned this month", f"{len(churned)}",
              delta=f"-{_money(float(churned['prior_mrr'].sum()))} MRR" if len(churned) else "no churn")
else:
    st.warning("No active account-months in the current filter — widen the sidebar filters.")

tab_mrr, tab_anim, tab_3d, tab_health, tab_feat, tab_ask = st.tabs(
    ["💰 MRR & movements", "🎬 Animated movements", "🧊 3D revenue space",
     "❤️ Account health", "🧩 Feature adoption", "💬 Ask a Metric"]
)

with tab_mrr:
    st.subheader("MRR trend by segment")
    if f_active.empty:
        st.info("No MRR rows in the current filter.")
    else:
        trend = f_active.groupby(["month_start", "segment"], as_index=False)["mrr"].sum()
        fig = px.area(trend, x="month_start", y="mrr", color="segment",
                      labels={"mrr": "MRR ($)", "month_start": "Month"},
                      template="plotly_dark")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")

        st.subheader("MRR movement bridge — latest month")
        moves = (f_mrr[f_mrr["month_start"] == latest_month]
                 .groupby("movement_type")["mrr_delta"].sum())
        order = ["new", "expansion", "contraction", "churn"]
        vals = [float(moves.get(k, 0.0)) for k in order]
        fig_w = go.Figure(go.Waterfall(
            orientation="v", measure=["relative"] * 4 + ["total"],
            x=order + ["net change"], y=vals + [sum(vals)],
            connector={"line": {"color": "rgba(160,200,255,.5)"}},
            increasing={"marker": {"color": "#2ecc71"}},
            decreasing={"marker": {"color": "#e74c3c"}},
            totals={"marker": {"color": "#6ea8fe"}},
        ))
        fig_w.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)", yaxis_title="MRR delta ($)")
        st.plotly_chart(fig_w, width="stretch")

        st.subheader("Retention — NRR & GRR by month")
        if not f_ret.empty:
            fig_r = px.line(f_ret, x="month_start",
                            y=["net_revenue_retention", "gross_revenue_retention"],
                            labels={"value": "Retention", "month_start": "Month", "variable": ""},
                            template="plotly_dark")
            fig_r.add_hline(y=1.0, line_dash="dot", line_color="rgba(255,255,255,.4)")
            fig_r.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_r, width="stretch")

with tab_anim:
    st.subheader("Press play — MRR movements evolving month by month")
    if f_mrr.empty:
        st.info("No movement rows in the current filter.")
    else:
        moves_m = (f_mrr.groupby(["month_start", "movement_type"], as_index=False)["mrr_delta"].sum())
        _grid = pd.MultiIndex.from_product(
            [sorted(f_mrr["month_start"].unique()),
             ["new", "expansion", "contraction", "churn", "retained"]],
            names=["month_start", "movement_type"],
        )
        moves_m = (moves_m.set_index(["month_start", "movement_type"])
                   .reindex(_grid, fill_value=0.0).reset_index())
        moves_m["frame"] = moves_m["month_start"].dt.strftime("%Y-%m")
        moves_m["abs_delta"] = moves_m["mrr_delta"].abs()
        lim = float(moves_m["mrr_delta"].abs().max()) or 1.0
        fig_a = px.bar(moves_m.sort_values(["month_start", "movement_type"]),
                       x="movement_type", y="mrr_delta", color="movement_type",
                       animation_frame="frame", range_y=[-lim * 1.15, lim * 1.15],
                       labels={"mrr_delta": "MRR delta ($)", "movement_type": "Movement"},
                       template="plotly_dark", title="Monthly MRR delta by movement type — animated")
        fig_a.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        if fig_a.layout.updatemenus:
            fig_a.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 450
        st.plotly_chart(fig_a, width="stretch")

        st.subheader("Cumulative MRR race by segment")
        seg_m = f_active.groupby(["month_start", "segment"], as_index=False)["mrr"].sum()
        seg_m["cum_mrr"] = seg_m.groupby("segment")["mrr"].cumsum()
        seg_m["frame"] = seg_m["month_start"].dt.strftime("%Y-%m")
        fig_c = px.line(seg_m.sort_values(["month_start", "segment"]),
                        x="month_start", y="cum_mrr", color="segment",
                        animation_frame="frame",
                        labels={"cum_mrr": "Cumulative MRR ($)", "month_start": "Month"},
                        template="plotly_dark", title="Cumulative MRR by segment — animated")
        fig_c.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        if fig_c.layout.updatemenus:
            fig_c.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 450
        st.plotly_chart(fig_c, width="stretch")
    st.caption("Animations are native Plotly `animation_frame` charts — hit ▶ Play on each chart.")

with tab_3d:
    st.subheader("🧊 3D revenue space — drag to rotate, scroll to zoom")
    if f_active.empty:
        st.info("No active account-months in the current filter.")
    else:
        d3 = f_active.copy()
        d3["size"] = np.clip(d3["monthly_events"] / 40.0, 2, 18)
        fig3 = px.scatter_3d(
            d3.sort_values("month_start"), x="month_start", y="health_score", z="mrr",
            color="segment", size="size", size_max=18, opacity=0.85,
            hover_data=["account_id", "plan_name", "industry"],
            labels={"health_score": "Health score", "mrr": "MRR ($)", "month_start": "Month"},
            template="plotly_dark",
            title="Every account-month in month × health × MRR space",
        )
        fig3.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            scene=dict(xaxis=dict(backgroundcolor="rgba(20,24,32,.9)"),
                       yaxis=dict(backgroundcolor="rgba(20,24,32,.9)"),
                       zaxis=dict(backgroundcolor="rgba(20,24,32,.9)")),
            margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig3, width="stretch")

        st.subheader("MRR surface — plan tier × month terrain")
        surf = (f_active.pivot_table(index="plan_name", columns="month_start",
                                     values="mrr", aggfunc="sum").fillna(0.0))
        surf = surf.reindex([PLAN_NAMES[p] for p in sorted(PLAN_NAMES) if PLAN_NAMES[p] in surf.index])
        if surf.shape[0] > 1 and surf.shape[1] > 2:
            fig_s = go.Figure(data=[go.Surface(
                z=surf.to_numpy(), x=[d.strftime("%Y-%m") for d in surf.columns],
                y=list(surf.index), colorscale="Viridis",
                colorbar=dict(title="MRR ($)"))])
            fig_s.update_layout(
                template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                scene=dict(xaxis_title="Month", yaxis_title="Plan tier", zaxis_title="MRR ($)",
                           camera=dict(eye=dict(x=1.5, y=-1.4, z=0.9))),
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig_s, width="stretch")
        else:
            st.info("Not enough plan/month coverage in the current filter for a surface.")

with tab_health:
    st.subheader("Health vs. revenue — where the at-risk money sits")
    if f_active.empty:
        st.info("No active account-months in the current filter.")
    else:
        latest = f_active[f_active["month_start"] == latest_month]
        fig = px.scatter(latest, x="health_score", y="mrr", color="segment",
                         size=np.clip(latest["monthly_events"] / 40.0, 2, 18), size_max=18,
                         hover_data=["account_id", "plan_name", "ticket_count"],
                         labels={"health_score": "Health score", "mrr": "MRR ($)"},
                         template="plotly_dark")
        fig.add_vline(x=50, line_dash="dot", line_color="rgba(255,120,120,.6)")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")

        st.subheader("Health distribution by segment")
        fig_h = px.histogram(f_active, x="health_score", color="segment", nbins=25,
                             labels={"health_score": "Health score"},
                             template="plotly_dark")
        fig_h.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_h, width="stretch")

        st.subheader("At-risk accounts (health < 50, latest month)")
        risk = (latest[latest["health_score"] < 50]
                .sort_values("mrr", ascending=False)
                [["account_id", "segment", "industry", "plan_name", "mrr",
                  "health_score", "monthly_events", "high_priority_tickets"]])
        if risk.empty:
            st.success("No at-risk accounts in the current filter. 🎉")
        else:
            st.dataframe(risk, width="stretch", hide_index=True)

with tab_feat:
    st.subheader("Feature adoption — events by feature and month")
    if f_feat.empty:
        st.info("No feature events in the current filter.")
    else:
        heat = (f_feat.pivot_table(index="feature_name", columns="month_start",
                                   values="event_count", aggfunc="sum").fillna(0.0))
        fig = px.imshow(heat, aspect="auto", color_continuous_scale="Viridis",
                        labels={"color": "Events", "x": "Month", "y": "Feature"},
                        template="plotly_dark")
        fig.update_xaxes(tickformat="%b %y")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")

        tot = (f_feat.groupby("feature_name", as_index=False)["event_count"].sum()
               .sort_values("event_count", ascending=True))
        fig_b = px.bar(tot, x="event_count", y="feature_name", orientation="h",
                       color="event_count", color_continuous_scale="Viridis",
                       labels={"event_count": "Events", "feature_name": "Feature"},
                       template="plotly_dark")
        fig_b.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_b, width="stretch")

with tab_ask:
    st.subheader("Ask a Metric — text-to-metric against the governed semantic layer")
    st.caption("Natural-language questions, answered against governed, tested metrics.")
    semantic = load_semantic_layer()
    with st.expander("Available metrics"):
        for m in semantic["metrics"]:
            st.markdown(f"- **{m['label']}** (`{m['name']}`) — {m['description']}")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.warning("No ANTHROPIC_API_KEY set — generating SQL from the semantic layer locally.")
    question = st.text_input(
        "Ask a question",
        placeholder="What was net revenue retention by month in 2025?",
    )
    if st.button("Generate SQL") and question:
        with st.spinner("Generating SQL..."):
            try:
                builder = QueryBuilder(semantic=semantic)
                sql = builder.build(question)
            except Exception as exc:
                st.error(str(exc))
            else:
                st.code(sql, language="sql")
                if builder.used_llm:
                    st.info("Generated with Claude against the governed semantic layer.")
                else:
                    st.info("Compiled locally from semantic_layer.yml. Review before running.")
