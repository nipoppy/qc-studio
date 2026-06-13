import streamlit as st

@st.fragment
def radio_buttons_with_shortcuts(
	label,
	options,
	key,
	default=None,
	shortcuts=False,
	horizontal=False,
):
	# --- Initialize state safely ---
	if key not in st.session_state:
		st.session_state[key] = default if default in options else options[0]

	# Ensure value is valid if options change dynamically
	if st.session_state[key] not in options:
		st.session_state[key] = options[0]

	current = st.session_state[key]

	# --- Label ---
	if label:
		st.markdown(f"**{label}**")

	# --- Layout ---
	if horizontal:
		cols = st.columns(len(options), gap="small")
	else:
		cols = [st.container() for _ in options]

	# --- Render buttons ---
	for i, (col, opt) in enumerate(zip(cols, options)):
		is_selected = opt == current

		display_label = f"{i+1}. {opt}" if shortcuts else opt

		# Use primary for selected (highlight effect)
		button_type = "primary" if is_selected else "secondary"

		with col:
			# Full-width button inside the column
			clicked = st.button(
				display_label,
				key=f"{key}_{i}",
				use_container_width=True,
				type=button_type,
				shortcut=f"Shift+{i+1}"
			)

		if clicked and opt != st.session_state[key]:
			st.session_state[key] = opt
			st.rerun()  # forces immediate UI update (optional but improves responsiveness)

	return st.session_state[key]
