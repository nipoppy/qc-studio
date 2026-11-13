"""Raters tab: add, edit or remove rater entries in the users config (with preview and backup)."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from admin import icons
from admin.core import AdminContext, log_admin_action, require_editor
from utils.users_config_writer import (
    ENTRY_KEYS,
    ConfigWriteError,
    apply_change,
    prepare_add_rater,
    prepare_remove_rater,
    prepare_update_rater,
)

ACTIONS = {f"{icons.ADD} Add rater": "Add rater", f"{icons.EDIT} Edit rater": "Edit rater", f"{icons.REMOVE} Remove rater": "Remove rater"}

_PENDING = "admin_pending_config_change"

_HELP = {
    "rater_id": "Used in file names. Defaults to the part of the email before the @.",
    "rater_dir": "Folder relative to rater_root (absolute paths allowed). Defaults to the rater_id.",
    "participant_list": "TSV inside rater_dir. Create it in the Assignments tab after saving.",
    "session_list": "Overrides the launcher's --session_list for this rater, e.g. ses-BL.",
    "output_dir": "Where ratings are saved, relative to rater_dir. Defaults to <rater_dir>/qc-output.",
}


def _raw_entry(ctx: AdminContext, email: str) -> dict:
    try:
        users = json.loads(ctx.users_config.read_text(encoding="utf-8")).get("users", {})
    except (OSError, json.JSONDecodeError):
        return {}
    return next((v for k, v in users.items() if str(k).strip().lower() == email), {}) or {}


def _entry_form(key: str, defaults: dict, email_editable: bool, email: str = "") -> tuple[bool, str, dict]:
    with st.form(key):
        email_in = st.text_input("Email (as authenticated by Cloudflare Access)", value=email, disabled=not email_editable)
        values = {}
        cols = st.columns(2)
        for i, k in enumerate(ENTRY_KEYS):
            label = k + (" *" if k == "participant_list" else "")
            values[k] = cols[i % 2].text_input(label, value=str(defaults.get(k) or ""), help=_HELP[k])
        submitted = st.form_submit_button("Preview change")
    return submitted, (email_in if email_editable else email), values


def _show_pending(ctx: AdminContext) -> None:
    change = st.session_state.get(_PENDING)
    if change is None:
        return
    st.markdown(f"#### Pending: {change.summary}")
    diff = change.diff()
    st.code(diff or "(no changes)", language="diff")
    st.caption("The file is re-formatted with 4-space indentation on save. A backup of the current file is kept in config_backups/.")
    c1, c2 = st.columns(2)
    if c1.button("💾 Save to users config", type="primary", disabled=not diff):
        require_editor(ctx)
        try:
            backup = apply_change(change)
        except ConfigWriteError as exc:
            st.error(f"Not saved: {exc}")
            return
        log_admin_action(ctx.email, f"{change.summary} in {change.path} (backup {backup})")
        st.session_state.pop(_PENDING, None)
        st.session_state["admin_flash"] = f"Saved: {change.summary}. Backup: `{backup}`"
        st.rerun()
    if c2.button("Discard"):
        st.session_state.pop(_PENDING, None)
        st.rerun()


def _prepare(fn, *args) -> None:
    try:
        st.session_state[_PENDING] = fn(*args)
    except ConfigWriteError as exc:
        st.session_state.pop(_PENDING, None)
        st.error(f"Refused: {exc}")


def render(ctx: AdminContext) -> None:
    cfg = ctx.cfg
    flash = st.session_state.pop("admin_flash", None)
    if flash:
        st.success(flash)

    rows = [
        {
            "email": email,
            "rater_id": u["rater_id"],
            "rater_dir": u["rater_dir"],
            "participant_list": u["participant_list"],
            "session_list": u.get("session_list") or "",
            "out_dir": u["out_dir"],
        }
        for email, u in sorted(cfg.users.items(), key=lambda kv: kv[1]["rater_id"])
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if cfg.rejected:
        st.warning("Invalid entries (refused at sign-in):\n" + "\n".join(f"- `{e}`: {'; '.join(r)}" for e, r in cfg.rejected.items()))
    if not ctx.can_edit:
        st.caption("View-only access: ask an admin to add, edit or remove raters.")
        return
    st.caption(
        "Admins, viewers and rater_root can only be changed by editing the users config file. "
        "Saved changes apply to the rater app on the raters' next page load."
    )

    action = ACTIONS[st.radio("Action", list(ACTIONS), horizontal=True, key="admin_rater_action")]
    all_emails = sorted(set(cfg.users) | set(cfg.rejected))

    if action == "Add rater":
        submitted, email, values = _entry_form("admin_add_rater", {}, email_editable=True)
        if submitted:
            _prepare(prepare_add_rater, ctx.users_config, email, values)
    elif not all_emails:
        st.info("No raters in the users config yet.")
    elif action == "Edit rater":
        email = st.selectbox(f"{icons.RATER} Rater", all_emails, key="admin_edit_email")
        submitted, _, values = _entry_form(f"admin_edit_rater_{email}", _raw_entry(ctx, email), email_editable=False, email=email)
        if submitted:
            _prepare(prepare_update_rater, ctx.users_config, email, values)
    else:
        email = st.selectbox(f"{icons.RATER} Rater", all_emails, key="admin_remove_email")
        st.caption("Only the config entry is removed: the rater's participant list and rating files stay on disk.")
        if st.button("Preview removal"):
            _prepare(prepare_remove_rater, ctx.users_config, email)

    _show_pending(ctx)
