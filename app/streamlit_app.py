"""College Debt Explorer — Major Explorer and Trends Over Time (Streamlit)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from major_explorer import (
    CREDENTIAL_LABELS,
    aggregate_by_program,
    family_labels,
    load_and_prepare,
)
from trends_data import (
    aggregate_by_program_cohort,
    family_ratio_delta,
    load_panels_long,
)

st.set_page_config(
    page_title="College Debt Explorer",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner="Loading College Scorecard data…")
def _load_data():
    return load_and_prepare()


@st.cache_data(show_spinner="Loading panel data (8 cohorts)…")
def _load_panels_long():
    return load_panels_long()


def _format_cipcode(x) -> str:
    try:
        v = float(x)
        return str(int(v)) if v == int(v) else str(x)
    except (TypeError, ValueError):
        return str(x)


def _major_explorer_tab(
    df: pd.DataFrame,
    family_options: list,
    fam_label_map: dict,
    broad: str,
    cred_pick: list[int],
):
    if not cred_pick:
        st.warning("Select at least one credential level.")
        return

    agg = aggregate_by_program(df, cip_families=[broad], cred_levels=cred_pick)
    if agg.empty:
        st.info("No rows for this combination of filters.")
        return

    plot_df = agg.dropna(subset=["debt_mdn", "earn_2yr"]).copy()
    plot_df = plot_df[plot_df["earn_2yr"] > 0]

    st.subheader("Debt vs. 2-year earnings")
    if plot_df.empty:
        st.info("Not enough numeric debt and earnings data to plot for this filter.")
    else:
        fig = go.Figure()
        for cred in sorted(plot_df["cred_short"].dropna().unique()):
            sub = plot_df[plot_df["cred_short"] == cred]
            fig.add_trace(
                go.Scatter(
                    x=sub["debt_mdn"],
                    y=sub["earn_2yr"],
                    mode="markers",
                    name=cred,
                    text=sub.apply(
                        lambda r: f"{r['CIPDESC']} ({_format_cipcode(r['CIPCODE'])})",
                        axis=1,
                    ),
                    hovertemplate=(
                        "%{text}<br>Median debt: $%{x:,.0f}<br>"
                        "Median 2yr earnings: $%{y:,.0f}<br>"
                        "n inst: %{customdata}"
                        "<extra></extra>"
                    ),
                    customdata=sub["n_inst"],
                )
            )
        hi = max(
            plot_df["debt_mdn"].max(),
            plot_df["earn_2yr"].max(),
        )
        if hi and hi > 0:
            fig.add_trace(
                go.Scatter(
                    x=[0, hi],
                    y=[0, hi],
                    mode="lines",
                    line=dict(dash="dash", color="gray"),
                    name="Break-even (earnings = debt)",
                    hoverinfo="skip",
                )
            )
        fig.update_layout(
            xaxis_title="Median debt (all undergrad borrowers, STGP)",
            yaxis_title="Median earnings 2 years after completion",
            legend_title="Credential",
            height=520,
            margin=dict(l=40, r=40, t=40, b=40),
        )
        st.plotly_chart(fig, use_container_width=True, key="scatter_debt_vs_earn_2yr")

    st.divider()
    agg["_label"] = agg.apply(
        lambda r: f"{r['CIPDESC']} [{_format_cipcode(r['CIPCODE'])}] — {r['cred_short']}",
        axis=1,
    )
    sel_label = st.selectbox(
        "Selected major (for summary)",
        options=agg["_label"].tolist(),
        key="major_select",
    )
    row = agg.loc[agg["_label"] == sel_label].iloc[0]

    st.subheader("Summary")
    debt = row["debt_mdn"]
    e1 = row["earn_1yr"]
    e2 = row["earn_2yr"]
    yrs = (
        float(debt) / float(e2)
        if pd.notna(debt) and pd.notna(e2) and float(e2) > 0
        else None
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Median debt", _money(debt))
    c2.metric("Median earnings (1 yr)", _money(e1))
    c3.metric("Median earnings (2 yr)", _money(e2))
    c4.metric(
        "Years to repay (debt ÷ 2yr earnings)",
        f"{yrs:.2f}" if yrs is not None else "—",
    )
    st.caption(
        f"Institutions in aggregate for this program: {int(row['n_inst'])}."
    )

    st.subheader("Debt-to-earnings ratio (median debt ÷ median 2yr earnings)")
    ratio_df = agg.dropna(subset=["debt_mdn", "earn_2yr"]).copy()
    ratio_df = ratio_df[ratio_df["earn_2yr"] > 0]
    ratio_df["ratio"] = ratio_df["debt_mdn"] / ratio_df["earn_2yr"]
    if ratio_df.empty:
        st.info("No ratio data for this filter.")
    else:
        best = ratio_df.nsmallest(15, "ratio").iloc[::-1]
        worst = ratio_df.nlargest(15, "ratio")
        bcol, wcol = st.columns(2)
        with bcol:
            st.markdown("**Best 15 (lowest debt relative to earnings)**")
            fig_b = _ratio_bars(best, "Lowest ratios")
            st.plotly_chart(fig_b, use_container_width=True, key="ratio_bar_best15")
        with wcol:
            st.markdown("**Worst 15 (highest debt relative to earnings)**")
            fig_w = _ratio_bars(worst, "Highest ratios")
            st.plotly_chart(fig_w, use_container_width=True, key="ratio_bar_worst15")


def _trends_tab(panel_df: pd.DataFrame):
    st.subheader("Trends over award-year cohorts")
    st.caption(
        "Panel files pool institutions; each point is the median of institution-level medians "
        "for that program and cohort. **Lower** debt-to-earnings ratio means better ROI."
    )

    if panel_df.empty:
        st.error("No panel data found. Check that FieldOfStudyData*_PP_slim.csv files exist.")
        return

    cred_keys = sorted(CREDENTIAL_LABELS.keys())
    cred_trend = st.radio(
        "Credential level (one level for fair comparison)",
        options=cred_keys,
        format_func=lambda k: CREDENTIAL_LABELS[k],
        horizontal=True,
        key="trends_cred",
    )

    latest_sort = panel_df["cohort_sort"].max()
    latest = panel_df[panel_df["cohort_sort"] == latest_sort]
    latest = latest[latest["CREDLEV"] == cred_trend]
    prog = (
        latest.drop_duplicates(["CIPCODE", "CIPDESC"])
        .sort_values("CIPDESC", kind="stable")
        .reset_index(drop=True)
    )

    q = st.text_input(
        "Filter majors (matches title or CIP code)",
        "",
        key="trends_search",
    ).strip().lower()

    def _match(row) -> bool:
        if not q:
            return True
        desc = str(row["CIPDESC"]).lower()
        code = _format_cipcode(row["CIPCODE"])
        return q in desc or q in code

    prog_f = prog[prog.apply(_match, axis=1)]
    tuples = [(float(r.CIPCODE), str(r.CIPDESC)) for r in prog_f.itertuples(index=False)]

    selected = st.multiselect(
        "Select 1–3 majors to compare",
        options=tuples,
        format_func=lambda t: f"{t[1]} [{_format_cipcode(t[0])}]",
        max_selections=3,
        key="trends_majors",
    )

    if not selected:
        st.info("Choose at least one major from the list (use search to narrow).")
        return

    cip_list = [t[0] for t in selected]
    trend = aggregate_by_program_cohort(
        panel_df,
        cipcodes=cip_list,
        cred_levels=[cred_trend],
    )

    cat_order = (
        trend[["cohort_sort", "cohort_label"]]
        .drop_duplicates()
        .sort_values("cohort_sort")["cohort_label"]
        .tolist()
    )

    # Dual-axis: debt vs earnings by cohort
    fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
    colors = ("#636EFA", "#EF553B", "#00CC96")
    for i, (cip, cdesc) in enumerate(selected):
        color = colors[i % len(colors)]
        sub = trend[pd.to_numeric(trend["CIPCODE"], errors="coerce") == float(cip)].sort_values(
            "cohort_sort"
        )
        name_base = f"{cdesc[:30]}…" if len(cdesc) > 30 else cdesc
        fig_dual.add_trace(
            go.Scatter(
                x=sub["cohort_label"],
                y=sub["debt_mdn"],
                mode="lines+markers",
                name=f"{name_base} — debt",
                legendgroup=f"g{i}",
                line=dict(color=color),
                marker=dict(symbol="circle"),
            ),
            secondary_y=False,
        )
        fig_dual.add_trace(
            go.Scatter(
                x=sub["cohort_label"],
                y=sub["earn_2yr"],
                mode="lines+markers",
                name=f"{name_base} — 2yr earnings",
                legendgroup=f"g{i}",
                line=dict(color=color, dash="dash"),
                marker=dict(symbol="square"),
            ),
            secondary_y=True,
        )
    fig_dual.update_layout(
        height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=60, t=40, b=80),
        xaxis=dict(categoryorder="array", categoryarray=cat_order),
    )
    fig_dual.update_yaxes(title_text="Median debt ($)", secondary_y=False)
    fig_dual.update_yaxes(title_text="Median 2yr earnings ($)", secondary_y=True)
    st.plotly_chart(fig_dual, use_container_width=True, key="trends_dual_axis")

    # Ratio trend
    fig_ratio = go.Figure()
    for i, (cip, cdesc) in enumerate(selected):
        sub = trend[pd.to_numeric(trend["CIPCODE"], errors="coerce") == float(cip)].sort_values(
            "cohort_sort"
        )
        sub = sub.dropna(subset=["debt_mdn", "earn_2yr"])
        sub = sub[sub["earn_2yr"] > 0]
        if sub.empty:
            continue
        sub = sub.copy()
        sub["ratio"] = sub["debt_mdn"] / sub["earn_2yr"]
        name_base = f"{cdesc[:40]}…" if len(cdesc) > 40 else cdesc
        fig_ratio.add_trace(
            go.Scatter(
                x=sub["cohort_label"],
                y=sub["ratio"],
                mode="lines+markers",
                name=f"{name_base} [{_format_cipcode(cip)}]",
            )
        )
    fig_ratio.update_layout(
        title="Debt-to-earnings ratio over time (median debt ÷ median 2yr earnings)",
        xaxis=dict(categoryorder="array", categoryarray=cat_order),
        yaxis_title="Ratio (lower is better)",
        height=400,
        margin=dict(l=40, r=40, t=60, b=80),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_ratio, use_container_width=True, key="trends_ratio_lines")

    st.subheader("Broad fields: change in median debt-to-earnings ratio")
    st.caption(
        "For each 2-digit CIP family: median of program-level ratios within the family, "
        "then **latest cohort minus earliest cohort**. Negative = improvement (lower ratio)."
    )
    delta_df = family_ratio_delta(panel_df, cred_trend)
    if delta_df.empty:
        st.info("Not enough data to compute family-level changes for this credential.")
        return

    delta_df = delta_df.sort_values("delta_ratio", ascending=True)
    bar_colors = [
        "#2ca02c" if v < 0 else "#d62728" if v > 0 else "#7f7f7f"
        for v in delta_df["delta_ratio"]
    ]
    fig_div = go.Figure(
        go.Bar(
            x=delta_df["delta_ratio"],
            y=delta_df["family_title"],
            orientation="h",
            marker_color=bar_colors,
            hovertemplate="Δ ratio: %{x:.4f}<extra></extra>",
        )
    )
    fig_div.add_vline(x=0, line_width=1, line_dash="solid", line_color="gray")
    fig_div.update_layout(
        xaxis_title="Change in median debt-to-earnings ratio (latest − earliest cohort)",
        yaxis=dict(title="", automargin=True),
        height=max(420, min(28 * len(delta_df), 1200)),
        margin=dict(l=20, r=40, t=40, b=40),
        showlegend=False,
    )
    st.plotly_chart(fig_div, use_container_width=True, key="trends_diverging_families")


def _money(x) -> str:
    if x is None:
        return "—"
    try:
        if pd.isna(x):
            return "—"
    except TypeError:
        return "—"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    return f"${v:,.0f}"


def _ratio_bars(frame, _title: str) -> go.Figure:
    labels = frame.apply(
        lambda r: f"{r['CIPDESC'][:42]}… [{_format_cipcode(r['CIPCODE'])}] · {r['cred_short']}"
        if len(str(r["CIPDESC"])) > 42
        else f"{r['CIPDESC']} [{_format_cipcode(r['CIPCODE'])}] · {r['cred_short']}",
        axis=1,
    )
    fig = go.Figure(
        go.Bar(
            x=frame["ratio"],
            y=labels,
            orientation="h",
            text=frame["ratio"].round(3),
            textposition="outside",
            hovertemplate="Ratio %{x:.3f}<extra></extra>",
        )
    )
    fig.update_layout(
        yaxis=dict(autorange="reversed", title=""),
        xaxis_title="Debt ÷ 2yr earnings",
        height=max(360, 24 * len(frame)),
        margin=dict(l=20, r=80, t=20, b=40),
        showlegend=False,
    )
    return fig


def main():
    df = _load_data()
    fam_df = family_labels(df)
    family_options = sorted(fam_df["cip_family"].unique().tolist())
    fam_label_map = dict(zip(fam_df["cip_family"], fam_df["family_label"]))

    panel_df = _load_panels_long()

    st.title("College Debt Explorer")
    st.caption(
        "Debt and earnings from the U.S. College Scorecard field-of-study data "
        "(median debt and earnings aggregated across institutions per program)."
    )

    with st.sidebar:
        st.header("Major Explorer")
        st.caption("Filters below apply to the **Major Explorer** tab.")
        broad = st.selectbox(
            "Broad field of study (2-digit CIP)",
            options=family_options,
            format_func=lambda c: fam_label_map.get(c, c),
            key="me_broad_cip",
        )
        cred_default = sorted(CREDENTIAL_LABELS.keys())
        cred_pick = st.multiselect(
            "Credential level",
            options=cred_default,
            default=cred_default,
            format_func=lambda k: CREDENTIAL_LABELS[k],
            key="me_cred",
        )

    tab1, tab2 = st.tabs(["Major Explorer", "Trends Over Time"])

    with tab1:
        _major_explorer_tab(df, family_options, fam_label_map, broad, cred_pick)

    with tab2:
        _trends_tab(panel_df)


if __name__ == "__main__":
    main()
