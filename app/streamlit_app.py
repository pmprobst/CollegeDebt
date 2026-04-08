"""College Debt — Major Explorer (Streamlit)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from major_explorer import (
    CREDENTIAL_LABELS,
    aggregate_by_program,
    family_labels,
    load_and_prepare,
)

st.set_page_config(
    page_title="Major Explorer",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner="Loading College Scorecard data…")
def _load_data():
    return load_and_prepare()


def _format_cipcode(x) -> str:
    try:
        v = float(x)
        return str(int(v)) if v == int(v) else str(x)
    except (TypeError, ValueError):
        return str(x)


def main():
    df = _load_data()
    fam_df = family_labels(df)
    family_options = sorted(fam_df["cip_family"].unique().tolist())
    fam_label_map = dict(zip(fam_df["cip_family"], fam_df["family_label"]))

    st.title("Major Explorer")
    st.caption(
        "Debt and earnings from the U.S. College Scorecard field-of-study data "
        "(median debt and earnings aggregated across institutions per program)."
    )

    with st.sidebar:
        st.header("Filters")
        broad = st.selectbox(
            "Broad field of study (2-digit CIP)",
            options=family_options,
            format_func=lambda c: fam_label_map.get(c, c),
        )
        cred_default = sorted(CREDENTIAL_LABELS.keys())
        cred_pick = st.multiselect(
            "Credential level",
            options=cred_default,
            default=cred_default,
            format_func=lambda k: CREDENTIAL_LABELS[k],
        )

    if not cred_pick:
        st.warning("Select at least one credential level.")
        return

    agg = aggregate_by_program(df, cip_families=[broad], cred_levels=cred_pick)
    if agg.empty:
        st.info("No rows for this combination of filters.")
        return

    plot_df = agg.dropna(subset=["debt_mdn", "earn_2yr"]).copy()
    plot_df = plot_df[plot_df["earn_2yr"] > 0]

    tab1, = st.tabs(["Major Explorer"])

    with tab1:
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


if __name__ == "__main__":
    main()
