"""Assignments tab: rater workloads, overlaps, and participant lists for new raters."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from admin import icons
from admin.charts import style_heatmap
from admin.core import AdminContext, log_admin_action, require_editor, to_tsv_bytes
from utils.cohort import parse_session_list
from utils.assignments import (
    POLICIES,
    create_rater_list,
    load_assignments,
    overlap_matrices,
    participant_list_path,
    rater_count_buckets,
    rater_workload,
    read_participant_list,
    restrict_to_pool,
    write_participant_list,
)

_PREVIEW = "admin_new_list_preview"
SOURCES = {"dataset": "Dataset participant list", "custom": "Custom list (upload a TSV)"}


def _workloads(ctx: AdminContext, assign: pd.DataFrame) -> None:
    if assign.empty:
        st.info("No participant lists found yet.")
        return
    st.subheader("Rater workload")
    sessions = {u["rater_id"]: parse_session_list(u.get("session_list") or ctx.session_list) for u in ctx.cfg.users.values()}
    workload = rater_workload(assign, len(ctx.expected_tasks), sessions)
    st.dataframe(
        workload,
        width="stretch",
        column_config={
            "qc_records": st.column_config.NumberColumn("qc_records", help="QC records to rate: unique participants × sessions × tasks"),
            "n_tasks": st.column_config.NumberColumn("n_tasks", help="QC tasks prescribed in qc.json"),
            "n_sessions": st.column_config.NumberColumn(
                "n_sessions", help="Sessions per participant: from the list's session_id column, else the rater's or the launch session_list"
            ),
        },
    )

    _raters_per_participant(ctx, assign)

    st.subheader("Pairwise overlap")
    overlap, jaccard = overlap_matrices(assign)
    shared = jaccard.where(overlap > 0)  # no shared participants -> grey cell, like other "none" cells
    fig = px.imshow(shared, zmin=0, zmax=1, labels=dict(color="Jaccard"), aspect="auto")
    fig.update_traces(
        text=overlap.values,
        customdata=jaccard.values,
        texttemplate="%{text}",
        hovertemplate="%{y} × %{x}<br>shared: %{text}<br>Jaccard: %{customdata:.2f}<extra></extra>",
    )
    style_heatmap(fig, z=shared, height=max(300, 28 * len(overlap) + 120))
    st.plotly_chart(fig, width="stretch")
    same = [f"{a} = {b}" for i, a in enumerate(jaccard.index) for b in jaccard.columns[i + 1 :] if jaccard.loc[a, b] == 1]
    if same:
        st.warning("Some raters have identical lists: " + ", ".join(same))


def _raters_per_participant(ctx: AdminContext, assign: pd.DataFrame) -> None:
    """One tile per number of assigned raters (0, 1, 2, 3+), as a share of the dataset participant list."""
    st.subheader(f"{icons.USERS} Raters per participant")
    pool_ids = ctx.pool_ids
    buckets = rater_count_buckets(assign, pool_ids)
    for col, row in zip(st.columns(len(buckets)), buckets.itertuples()):
        label = f"{row.bucket} rater" + ("" if row.bucket == "1" else "s")
        col.metric(
            label,
            f"{row.n_participants:,}",
            delta=f"{row.pct:.1f}%",
            delta_color="off",
            delta_arrow="off",
            help=f"{row.pct_at_least:.1f}% of the dataset participants have {row.n_raters} or more raters",
            border=True,
            height="stretch",
        )
    outside = set(assign["participant_id"]) - set(pool_ids)
    if outside:
        st.caption(f"{len(outside)} assigned participant(s) are not in the dataset list and are not counted here.")


def _source_pool(pool_ids: list[str]) -> tuple[list[str] | None, str]:
    """The participants to draw from (``None`` if unusable) and a label for the preview and audit log."""
    source = st.radio("Draw participants from", list(SOURCES), format_func=SOURCES.get, horizontal=True, key="admin_list_source")
    if source == "dataset":
        return pool_ids, f"dataset list ({len(pool_ids)})"
    upload = st.file_uploader(
        "Custom participant list (TSV with a participant_id column)",
        type=["tsv", "txt"],
        key="admin_custom_list",
        help="Only participants that are also in the dataset participant list are used.",
    )
    if upload is None:
        st.info("Upload a custom list to continue.")
        return None, ""
    try:
        custom_ids = read_participant_list(upload)["participant_id"].tolist()
    except Exception as exc:  # pandas raises many types for malformed files
        st.error(f"{upload.name} cannot be read: {exc}")
        return None, ""
    kept, dropped = restrict_to_pool(custom_ids, pool_ids)
    st.caption(f"{len(kept)} of {len(kept) + len(dropped)} participants in {upload.name} are in the dataset participant list.")
    if dropped:
        with st.expander(f"⚠️ {len(dropped)} not in the dataset list (left out)"):
            st.write(", ".join(dropped[:50]) + (" …" if len(dropped) > 50 else ""))
    if not kept:
        st.error("None of the uploaded participants are in the dataset participant list.")
        return None, ""
    return kept, f"custom list {upload.name} ({len(kept)} in dataset)"


def _new_list(ctx: AdminContext, assign: pd.DataFrame) -> None:
    st.subheader(f"{icons.NEW_LIST} Create a participant list for a rater")
    st.markdown(
        "Draws participants from the dataset list, or from a custom list restricted to participants in the dataset list, "
        "with the chosen policy. The file is written to the `participant_list` path the users config gives that rater. "
        "For a new rater, add them in the **Raters** tab first so they appear in the list below."
    )
    pool_ids = ctx.pool_ids
    rater_ids = sorted(u["rater_id"] for u in ctx.cfg.users.values())
    if not rater_ids:
        st.info("No valid raters in the users config.")
        return
    source_ids, source_label = _source_pool(pool_ids)
    if source_ids is None:
        return
    policy = st.radio("Policy", list(POLICIES), format_func=lambda k: POLICIES[k], key="admin_list_policy")
    with st.form("admin_new_list"):
        c = st.columns(3)
        rater_id = c[0].selectbox(f"{icons.RATER} Rater", rater_ids, index=None, placeholder="Choose a rater")
        if policy == "all":
            n, seed = len(source_ids), 0
            c[1].markdown(f"**All {len(source_ids)}** participants of the source")
        else:
            n = c[1].number_input("Participants", min_value=1, max_value=len(source_ids), value=min(100, len(source_ids)), step=10)
            seed = c[2].number_input("Seed", min_value=0, value=42, step=1)
        submitted = st.form_submit_button("Preview list")
    if submitted:
        if rater_id is None:
            st.warning("Choose a rater first.")
            return
        notes: list[str] = []
        try:
            chosen = create_rater_list(
                rater_id,
                int(n),
                source_ids,
                assign,
                seed=int(seed),
                policy=policy,
                warn=notes.append,
                warn_outside_pool=source_ids is pool_ids,  # a custom subset leaves most assignments outside it
            )
        except ValueError as exc:
            st.error(str(exc))
            return
        st.session_state[_PREVIEW] = {
            "rater_id": rater_id,
            "list": chosen,
            "notes": notes,
            "seed": int(seed),
            "policy": policy,
            "source": source_label,
        }

    preview = st.session_state.get(_PREVIEW)
    if not preview or preview["rater_id"] not in rater_ids:
        return
    rid, chosen = preview["rater_id"], preview["list"]
    for n_ in preview["notes"]:
        st.caption(f"ℹ️ {n_}")
    how = f"policy {preview['policy']}" + ("" if preview["policy"] == "all" else f", seed {preview['seed']}") + f", from {preview['source']}"
    st.markdown(f"**{rid}**: {len(chosen)} participants ({how}). Raters they already had:")
    c1, c2 = st.columns([1, 2])
    c1.dataframe(chosen["n_raters"].value_counts().sort_index().rename_axis("prior_n_raters").rename("participants").to_frame(), width="stretch")
    c2.dataframe(chosen, hide_index=True, width="stretch", height=240)

    target = participant_list_path(ctx.cfg, rid)
    st.download_button("⬇️ Download list (TSV)", to_tsv_bytes(chosen[["participant_id"]]), file_name=target.name, mime="text/tab-separated-values")
    exists = target.exists()
    st.markdown(f"Target: `{target}`" + (" — **already exists**" if exists else ""))
    if not ctx.can_edit:
        st.caption("View-only access: download the list, or ask an admin to write it.")
        return
    overwrite = st.checkbox("Replace the existing list", value=False, key=f"admin_overwrite_{rid}") if exists else False
    if st.button("💾 Write list", type="primary", disabled=exists and not overwrite):
        require_editor(ctx)
        out, status = write_participant_list(chosen["participant_id"], ctx.cfg, rid, overwrite=overwrite)
        if status == "written":
            log_admin_action(ctx.email, f"wrote {len(chosen)} participants to {out} ({how}, overwrite={overwrite})")
            st.session_state.pop(_PREVIEW, None)
            st.success(f"Wrote {len(chosen)} participants to `{out}`")
        else:
            st.warning(f"`{out}`: {status}")


def render(ctx: AdminContext) -> None:
    notes: list[str] = []
    assign = load_assignments(ctx.cfg, warn=notes.append)  # read once for both sections
    for n in notes:
        st.caption(f"ℹ️ {n}")
    _workloads(ctx, assign)
    st.divider()
    _new_list(ctx, assign)
