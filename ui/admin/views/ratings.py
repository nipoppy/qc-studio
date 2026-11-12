"""Ratings tab: every rater's current QC ratings collated into dataset-level reports."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from admin.core import AdminContext, cached_collation, clear_collation_cache, log_admin_action, to_tsv_bytes
from utils.assignments import read_participant_ids
from utils.ratings_report import (
    QC_ORDER,
    VALUE_ORDER,
    agreement_summary,
    assigned_ids,
    consensus,
    dataset_coverage,
    facet_rating_counts,
    final_qc_counts,
    off_list_ratings,
    participant_level,
    rater_progress,
    raters_per_participant,
    split_expected,
    task_status,
)

# Status colours (good / warning / serious / critical) and a neutral grey for missing.
QC_COLORS = {"All-Pass": "#0ca30c", "Mixed": "#fab219", "All-Uncertain": "#ec835a", "All-Fail": "#d03b3b", "All-Missing": "#898781"}
VALUE_COLORS = {"PASS": "#0ca30c", "UNCERTAIN": "#ec835a", "FAIL": "#d03b3b", "MISSING": "#898781"}
COVERAGE_COLORS = {"0": "#e1e0d9", "1": "#9ec5f4", "2": "#3987e5", "3+": "#184f95"}


def _download(label: str, df: pd.DataFrame, name: str, index: bool = False) -> None:
    st.download_button(f"⬇️ {label}", to_tsv_bytes(df, index=index), file_name=f"{name}.tsv", mime="text/tab-separated-values", key=f"dl_{name}")


def _stacked_share(long: pd.DataFrame, y: str, color: str, order: list[str], colors: dict, facet_col: str | None = None, height=400):
    fig = px.bar(
        long,
        x="n",
        y=y,
        color=color,
        orientation="h",
        facet_col=facet_col,
        category_orders={color: order},
        color_discrete_map=colors,
        labels={"n": "% of ratings", y: ""},
    )
    fig.update_traces(marker_line_color="white", marker_line_width=1)
    fig.update_layout(barnorm="percent", height=height, margin=dict(t=30, b=10), legend_title_text="", legend=dict(orientation="h", y=-0.15))
    fig.update_yaxes(categoryorder="category descending")
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    return fig


def render(ctx: AdminContext) -> None:
    c1, c2 = st.columns([3, 1])
    prefer_transformed = c1.toggle(
        "Use *_transformed checkpoint copies when available",
        value=True,
        help="Old checkpoints may have a *_transformed.tsv copy using the current facet names; it replaces the original of the same stamp.",
    )
    if c2.button("🔄 Reload ratings"):
        clear_collation_cache()

    try:
        pool_ids = read_participant_ids(ctx.participant_list)
    except (OSError, ValueError) as exc:
        st.error(f"Dataset participant list cannot be read: {exc}")
        return
    col = cached_collation(ctx, prefer_transformed)
    if col.ratings.empty:
        st.info("No ratings saved yet.")
        return
    qc_all = participant_level(col.ratings)
    qc, qc_other = split_expected(qc_all, ctx.qc_pipeline, ctx.expected_tasks)
    qc = qc.assign(pipeline=ctx.qc_pipeline)  # normalise case so expected tasks line up
    ratings_exp = col.ratings[col.ratings["pipeline"].str.lower().eq(ctx.qc_pipeline.lower()) & col.ratings["qc_task"].isin(ctx.expected_tasks)]
    assigned = assigned_ids(ctx.cfg)
    tasks = list(ctx.expected_tasks)  # the qc.json prescription, including tasks nobody has started
    started = [t for t in tasks if t in set(qc["qc_task"])]
    not_started = [t for t in tasks if t not in started]

    m = st.columns(4)
    m[0].metric("Raters with ratings", f"{col.sources['rater_id'].nunique()} / {len(ctx.cfg.users)}")
    m[1].metric("Participant-level ratings", len(qc))
    m[2].metric("Facet ratings", len(col.ratings))
    m[3].metric("Dataset participants", len(set(pool_ids)))
    if col.raters_without_files:
        st.caption("No status/checkpoint files yet: " + ", ".join(col.raters_without_files))
    if col.warnings:
        with st.expander(f"⚠️ {len(col.warnings)} file warning(s)"):
            st.markdown("\n".join(f"- {w}" for w in col.warnings))
    if not_started:
        st.warning(f"Not started by any rater: {', '.join(not_started)}")
    if not qc_other.empty:
        other = qc_other.groupby(["pipeline", "qc_task"]).size()
        st.warning(
            "Ratings for task(s) not in qc.json are left out of the reports below (still in the facet/participant exports): "
            + ", ".join(f"{p}/{t} ({n})" for (p, t), n in other.items())
        )
    if qc.empty:
        st.info("No ratings for the expected tasks yet.")
        return

    # --- Sources -------------------------------------------------------------
    st.subheader("Rating file used per rater and task")
    st.caption("The rater's qc_status.tsv when present, otherwise their newest checkpoint.")
    st.dataframe(col.sources, hide_index=True, width="stretch")
    flagged = col.sources[col.sources["in_latest_ckpt_not_in_status"] > 0]
    if not flagged.empty:
        st.warning("The newest checkpoint has participants that are missing from the status file for: " + ", ".join(flagged["source_file"]))

    st.subheader("final_qc per task")
    counts = final_qc_counts(qc).reindex(pd.MultiIndex.from_product([[ctx.qc_pipeline], tasks], names=["pipeline", "qc_task"]), fill_value=0)
    st.dataframe(counts, width="stretch")

    # --- Progress ------------------------------------------------------------
    st.subheader("Rater progress")
    progress = rater_progress(qc, assigned, pool_ids)
    all_raters = sorted(u["rater_id"] for u in ctx.cfg.users.values())
    pct = progress.pivot(index="rater_id", columns="qc_task", values="pct_complete").reindex(index=all_raters, columns=tasks)
    cnt = progress.pivot(index="rater_id", columns="qc_task", values="rated_assigned").reindex(index=all_raters, columns=tasks)
    text = pct.round(0).astype("Int64").astype(str).where(pct.notna(), "–") + "% (" + cnt.astype("Int64").astype(str).where(cnt.notna(), "0") + ")"
    text = text.where(pct.notna(), "–")
    fig = px.imshow(pct, color_continuous_scale="Blues", zmin=0, zmax=100, aspect="auto", labels=dict(color="% of own list"))
    fig.update_traces(text=text.values, texttemplate="%{text}", hovertemplate="%{y} · %{x}<br>%{text}<extra></extra>")
    fig.update_layout(height=max(300, 26 * len(pct) + 100), margin=dict(t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    st.caption("% of each rater's own participant list rated (number rated). – = task not started.")
    st.dataframe(progress, hide_index=True, width="stretch")
    off = off_list_ratings(qc, assigned, pool_ids)
    if not off.empty:
        st.warning(f"{len(off)} rating(s) of participants outside the rater's own list or outside the dataset list.")
        with st.expander("Show them"):
            st.dataframe(off, hide_index=True, width="stretch")

    # --- Coverage ------------------------------------------------------------
    st.subheader("Dataset coverage")
    coverage = dataset_coverage(qc, pool_ids, assigned, tasks=tasks, pipeline=ctx.qc_pipeline)
    st.dataframe(coverage, hide_index=True, width="stretch")
    dist = []
    for task in tasks:
        n_r = raters_per_participant(qc, pool_ids, task).clip(upper=3).astype(str).replace("3", "3+")
        for b, n in n_r.value_counts().items():
            dist.append({"qc_task": task, "raters": b, "n": int(n)})
    fig = px.bar(
        pd.DataFrame(dist),
        x="n",
        y="qc_task",
        color="raters",
        orientation="h",
        category_orders={"raters": list(COVERAGE_COLORS)},
        color_discrete_map=COVERAGE_COLORS,
        labels={"n": f"Participants in dataset list (n={len(set(pool_ids))})", "qc_task": "", "raters": "Raters"},
    )
    fig.update_traces(marker_line_color="white", marker_line_width=1)
    fig.update_layout(height=120 + 50 * len(tasks), margin=dict(t=10, b=10), legend=dict(orientation="h", y=-0.4))
    st.plotly_chart(fig, width="stretch")

    # --- Distributions -------------------------------------------------------
    st.subheader("final_qc by rater")
    long = qc.groupby(["qc_task", "rater_id", "final_qc"]).size().rename("n").reset_index()
    order = QC_ORDER + sorted(set(long["final_qc"]) - set(QC_ORDER))
    fig = _stacked_share(long, "rater_id", "final_qc", order, QC_COLORS, facet_col="qc_task", height=120 + 24 * long["rater_id"].nunique())
    st.plotly_chart(fig, width="stretch")
    if not_started:
        st.caption(f"No ratings yet for: {', '.join(not_started)}")

    st.subheader("Facet ratings")
    task = st.selectbox("QC task", started, key="admin_facet_task")
    facets = facet_rating_counts(ratings_exp, task)
    long = facets.reset_index().melt(id_vars="facet", var_name="rating_value", value_name="n")
    order = VALUE_ORDER + sorted(set(long["rating_value"]) - set(VALUE_ORDER))
    fig = _stacked_share(long, "facet", "rating_value", order, VALUE_COLORS, height=120 + 22 * len(facets))
    fig.update_yaxes(categoryorder="array", categoryarray=list(facets.index[::-1]))
    st.plotly_chart(fig, width="stretch")
    st.caption("Least-passing facets on top.")

    # --- Agreement -----------------------------------------------------------
    st.subheader("Participants rated by more than one rater")
    cons = consensus(qc)
    summary = agreement_summary(cons)
    if summary.empty:
        st.info("No participant has been rated by more than one rater yet.")
    else:
        st.dataframe(summary, width="stretch")
        disagree = cons[(cons["n_raters"] > 1) & ~cons["unanimous"]]
        st.markdown(f"**Disagreements** ({len(disagree)}); `majority_qc` is the final_qc given by more than half of the raters.")
        st.dataframe(disagree, hide_index=True, width="stretch")

    # --- Export --------------------------------------------------------------
    st.subheader("Export")
    reports = {
        "qc_ratings_facets": col.ratings,
        "qc_ratings_participants": qc_all,
        "qc_consensus": cons,
        "qc_rater_progress": progress,
        "qc_dataset_coverage": coverage,
        "qc_task_status": task_status(qc_all, ctx.qc_pipeline, tasks),
        "qc_source_files": col.sources,
    }
    cols = st.columns(3)
    for i, (name, df) in enumerate(reports.items()):
        with cols[i % 3]:
            _download(name, df, name)
    if ctx.output_dir is None:
        st.caption("Start the admin app with --output_dir to also save these reports on the server.")
    elif st.button(f"💾 Save reports to {ctx.output_dir}"):
        ctx.output_dir.mkdir(parents=True, exist_ok=True)
        for name, df in reports.items():
            df.to_csv(ctx.output_dir / f"{name}.tsv", sep="\t", index=False)
        log_admin_action(ctx.admin_email, f"saved {len(reports)} reports to {ctx.output_dir}")
        st.success(f"Saved {len(reports)} reports to `{ctx.output_dir}`")
