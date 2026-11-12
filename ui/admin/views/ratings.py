"""Ratings tab: every rater's current QC ratings collated into dataset-level reports."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from admin.charts import COVERAGE_COLORS, QC_COLORS, VALUE_COLORS, style_bars, style_heatmap
from admin.core import AdminContext, cached_ratings, log_admin_action, require_editor, to_tsv_bytes
from utils.ratings_report import (
    QC_ORDER,
    VALUE_ORDER,
    agreement_summary,
    assigned_ids,
    consensus,
    coverage_buckets,
    dataset_coverage,
    expected_records,
    facet_rating_counts,
    final_qc_counts,
    off_list_ratings,
    rater_progress,
    records_rated,
    split_expected,
    task_status,
)


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
    style_bars(fig, height)
    fig.update_layout(barnorm="percent")
    fig.update_yaxes(categoryorder="category descending")
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    return fig


def render(ctx: AdminContext) -> None:
    alerts = st.container()  # every warning/error banner of this tab is collected here, above the content
    prefer_transformed = st.toggle(
        "Use *_transformed checkpoint copies when available",
        value=True,
        help="Old checkpoints may have a *_transformed.tsv copy using the current facet names; it replaces the original of the same stamp.",
    )
    pool_ids = ctx.pool_ids
    col, qc_all = cached_ratings(ctx, prefer_transformed)
    if col.ratings.empty:
        st.info("No ratings saved yet.")
        return
    tasks = ctx.expected_tasks  # the qc.json prescription, including tasks nobody has started
    qc, qc_other = split_expected(qc_all, ctx.qc_pipeline, tasks)
    ratings_exp, _ = split_expected(col.ratings, ctx.qc_pipeline, tasks)
    assigned = assigned_ids(ctx.cfg)
    started = [t for t in tasks if t in set(qc["qc_task"])]
    not_started = [t for t in tasks if t not in started]

    # Counts use participant-level ratings (one final_qc per rater × participant × session × task); facet ratings are never counted.
    records = expected_records(ctx.pool, tasks, ctx.session_list)
    n_rated = records_rated(qc, records)
    pct_rated = 100 * n_rated / len(records) if len(records) else 0.0
    per_task = qc.groupby("qc_task").agg(
        ratings=("participant_id", "size"), participants=("participant_id", "nunique"), raters=("rater_id", "nunique")
    )
    per_task = per_task.reindex(tasks, fill_value=0)
    n_participants_rated = len(set(qc["participant_id"]) & set(pool_ids))
    pct_participants = 100 * n_participants_rated / len(pool_ids) if pool_ids else 0.0
    m = st.columns(3 + len(tasks))  # one row of bordered tiles
    m[0].metric("Raters with ratings", f"{col.sources['rater_id'].nunique()} / {len(ctx.cfg.users)}", border=True, height="stretch")
    m[1].metric(
        "Participant-level ratings",
        f"{n_participants_rated:,} / {len(pool_ids):,}",
        delta=f"{pct_participants:.1f}% of dataset participants",
        delta_color="off",
        delta_arrow="off",
        help="Dataset participants with at least one rating (any session or task) / all dataset participants. "
        "Each participant counts once however many raters rated them.",
        border=True,
        height="stretch",
    )
    m[2].metric(
        "Record-level ratings",
        f"{n_rated:,} / {len(records):,}",
        delta=f"{pct_rated:.1f}% of QC records",
        delta_color="off",
        delta_arrow="off",
        help=f"QC records with at least one rating / total QC records (dataset participants × sessions × {len(tasks)} task(s) in qc.json). "
        "Each record counts once however many raters rated it.",
        border=True,
        height="stretch",
    )
    for c, (task, row) in zip(m[3:], per_task.iterrows()):
        c.metric(
            task,
            f"{int(row['ratings']):,}",
            delta="not started" if row["ratings"] == 0 else None,
            delta_color="off",
            delta_arrow="off",
            help=f"Participant-level ratings for this task: {int(row['participants'])} distinct participants rated by {int(row['raters'])} rater(s)",
            border=True,
            height="stretch",
        )
    if col.raters_without_files:
        st.caption("No status/checkpoint files yet: " + ", ".join(col.raters_without_files))
    if col.warnings:
        with st.expander(f"⚠️ {len(col.warnings)} file warning(s)"):
            st.markdown("\n".join(f"- {w}" for w in col.warnings))
    if not_started:
        alerts.warning(f"Not started by any rater: {', '.join(not_started)}")
    if not qc_other.empty:
        other = qc_other.groupby(["pipeline", "qc_task"]).size()
        alerts.warning(
            "Ratings for task(s) not in qc.json are left out of the reports below (still in the facet/participant exports): "
            + ", ".join(f"{p}/{t} ({n})" for (p, t), n in other.items())
        )
    if qc.empty:
        st.info("No ratings for the expected tasks yet.")
        return

    # --- Coverage ------------------------------------------------------------
    st.subheader("Dataset coverage")
    coverage = dataset_coverage(qc, pool_ids, assigned, tasks=tasks, pipeline=ctx.qc_pipeline)
    st.dataframe(coverage, hide_index=True, width="stretch")
    dist = coverage_buckets(qc, pool_ids, tasks).reset_index().melt(id_vars="qc_task", var_name="raters", value_name="n")
    fig = px.bar(
        dist,
        x="n",
        y="qc_task",
        color="raters",
        orientation="h",
        category_orders={"raters": list(COVERAGE_COLORS)},
        color_discrete_map=COVERAGE_COLORS,
        labels={"n": f"Dataset participants (n={len(pool_ids):,})", "qc_task": ""},
    )
    style_bars(fig, height=140 + 50 * len(tasks))
    fig.update_layout(legend_title_text="Raters")
    st.plotly_chart(fig, width="stretch")

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
    fig = px.imshow(pct, zmin=0, zmax=100, aspect="auto", labels=dict(color="% of own list"))
    fig.update_traces(text=text.values, texttemplate="%{text}", hovertemplate="%{y} · %{x}<br>%{text}<extra></extra>")
    style_heatmap(fig, z=pct, height=max(300, 26 * len(pct) + 100))
    st.plotly_chart(fig, width="stretch")
    st.caption("% of each rater's own participant list rated (number rated). – = task not started.")
    st.dataframe(progress, hide_index=True, width="stretch")
    off = off_list_ratings(qc, assigned, pool_ids)
    if not off.empty:
        alerts.warning(
            f"{len(off)} rating(s) of participants outside the rater's own list or outside the dataset list (listed under Rater progress)."
        )
        with st.expander(f"{len(off)} rating(s) outside the rater's own list or the dataset list"):
            st.dataframe(off, hide_index=True, width="stretch")

    # --- Sources -------------------------------------------------------------
    with st.expander("Rating file used per rater and task"):
        st.caption("The rater's qc_status.tsv when present, otherwise their newest checkpoint.")
        st.dataframe(col.sources, hide_index=True, width="stretch")
    flagged = col.sources[col.sources["in_latest_ckpt_not_in_status"] > 0]
    if not flagged.empty:
        alerts.warning("The newest checkpoint has participants that are missing from the status file for: " + ", ".join(flagged["source_file"]))

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
    elif not ctx.can_edit:
        st.caption(f"View-only access: download the reports above (only admins save them to `{ctx.output_dir}`).")
    elif st.button(f"💾 Save reports to {ctx.output_dir}"):
        require_editor(ctx)
        ctx.output_dir.mkdir(parents=True, exist_ok=True)
        for name, df in reports.items():
            df.to_csv(ctx.output_dir / f"{name}.tsv", sep="\t", index=False)
        log_admin_action(ctx.email, f"saved {len(reports)} reports to {ctx.output_dir}")
        st.success(f"Saved {len(reports)} reports to `{ctx.output_dir}`")
