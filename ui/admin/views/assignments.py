"""Assignments tab: rater workloads, overlaps, and participant lists for new raters."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from admin.core import AdminContext, log_admin_action, to_tsv_bytes
from utils.assignments import (
    POLICIES,
    add_units,
    create_rater_list,
    load_assignments,
    overlap_matrices,
    overlapping_pairs,
    participant_list_path,
    rater_count_distribution,
    rater_summary,
    read_participant_ids,
    read_participant_list,
    restrict_to_pool,
    write_participant_list,
)

_PREVIEW = "admin_new_list_preview"
SOURCES = {"dataset": "Dataset participant list", "custom": "Custom list (upload a TSV)"}


def _workloads(ctx: AdminContext) -> pd.DataFrame | None:
    notes: list[str] = []
    assign = load_assignments(ctx.cfg, warn=notes.append)
    for n in notes:
        st.caption(f"ℹ️ {n}")
    if assign.empty:
        st.info("No participant lists found yet.")
        return None
    assign, key = add_units(assign)
    st.caption(f"Overlap unit: {' + '.join(key)} · {len(assign)} assigned rows across {assign['rater_id'].nunique()} raters")

    st.subheader("Per-rater workload")
    st.dataframe(rater_summary(assign), width="stretch")

    st.subheader("Raters per participant")
    dist = rater_count_distribution(assign).reset_index()
    c1, c2 = st.columns([1, 2])
    c1.dataframe(dist, hide_index=True, width="stretch")
    fig = px.bar(dist, x="n_raters", y="n_units", labels={"n_raters": "Raters assigned", "n_units": "Participants"})
    fig.update_traces(marker_color="#2a78d6")
    fig.update_layout(height=280, margin=dict(t=10, b=10), xaxis=dict(dtick=1))
    c2.plotly_chart(fig, width="stretch")

    st.subheader("Pairwise overlap")
    overlap, jaccard = overlap_matrices(assign)
    fig = px.imshow(
        jaccard,
        color_continuous_scale="Blues",
        zmin=0,
        zmax=1,
        labels=dict(color="Jaccard"),
        aspect="auto",
    )
    fig.update_traces(text=overlap.values, texttemplate="%{text}", hovertemplate="%{y} × %{x}<br>shared: %{text}<br>Jaccard: %{z:.2f}<extra></extra>")
    fig.update_layout(height=max(300, 28 * len(overlap) + 120), margin=dict(t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    st.caption("Cell text = shared participants; colour = Jaccard index. The diagonal is each rater's list size.")
    pairs = overlapping_pairs(assign)
    if pairs["identical"].any():
        st.warning(
            "Some raters have identical lists: " + ", ".join(f"{a} = {b}" for a, b in pairs.loc[pairs["identical"], ["rater_a", "rater_b"]].values)
        )
    with st.expander(f"{len(pairs)} rater pairs share participants"):
        st.dataframe(pairs, hide_index=True, width="stretch")
    return assign


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


def _new_list(ctx: AdminContext) -> None:
    st.subheader("Create a participant list for a rater")
    st.markdown(
        "Draws participants from the dataset list, or from a custom list restricted to participants in the dataset list, "
        "with the chosen policy. The rater's own current list is ignored, so re-running with the same seed gives the same "
        "list. The file is written to the `participant_list` path the users config gives that rater; add the rater in the "
        "**Raters** tab first."
    )
    try:
        pool_ids = read_participant_ids(ctx.participant_list)
    except (OSError, ValueError) as exc:
        st.error(f"Dataset participant list cannot be read: {exc}")
        return
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
        rater_id = c[0].selectbox("Rater", rater_ids, index=None, placeholder="Choose a rater")
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
        assignments = load_assignments(ctx.cfg, warn=notes.append)
        try:
            chosen = create_rater_list(
                rater_id,
                int(n),
                source_ids,
                assignments,
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
    overwrite = st.checkbox("Replace the existing list", value=False, key=f"admin_overwrite_{rid}") if exists else False
    if st.button("💾 Write list", type="primary", disabled=exists and not overwrite):
        out, status = write_participant_list(chosen["participant_id"], ctx.cfg, rid, overwrite=overwrite)
        if status == "written":
            log_admin_action(ctx.admin_email, f"wrote {len(chosen)} participants to {out} ({how}, overwrite={overwrite})")
            st.session_state.pop(_PREVIEW, None)
            st.success(f"Wrote {len(chosen)} participants to `{out}`")
        else:
            st.warning(f"`{out}`: {status}")


def render(ctx: AdminContext) -> None:
    _workloads(ctx)
    st.divider()
    _new_list(ctx)
