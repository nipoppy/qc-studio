from pathlib import Path


def bare_bids_id(val: str, prefix: str) -> str:
	val = str(val)
	if val.startswith(prefix):
		val = val[len(prefix) :]
	return val.lstrip("0") or "0"


def normalize_participant_id_bids(pid: str) -> str:
	p = str(pid).strip()
	return p if p.startswith("sub-") else f"sub-{p}"


def normalize_session_id_bids(sid: str) -> str:
	s = str(sid).strip()
	if not s:
		raise ValueError("session id cannot be empty")
	if s.startswith("ses-"):
		return s
	if s.isdigit():
		return f"ses-{int(s):02d}"
	return f"ses-{s}"


def parse_session_list(raw: str | None) -> list[str] | None:
	"""Return ordered unique BIDS session ids from CLI ``--session_list``.

	Returns None for single-session datasets (no session label).
	"""
	if raw is None or str(raw).strip() == "":
		return None
	parts = [p.strip() for p in str(raw).strip().split(",") if p.strip()]
	if not parts:
		return None
	seen: list[str] = []
	for p in parts:
		norm = normalize_session_id_bids(p)
		if norm not in seen:
			seen.append(norm)
	return seen or None


def extract_bids_entities_from_path(path: str | Path | None) -> dict[str, str]:
	"""Return BIDS entities parsed from a path-like filename.

	The path does not need to exist; this helper only inspects the filename.
	For example, ``sub-01_ses-01_task-rest_run-02_desc-sdc_bold.svg`` returns
	``{"sub": "01", "ses": "01", "task": "rest", "run": "02", "desc": "sdc"}``.
	"""
	if not path:
		return {}

	path = Path(path)
	stem = path.name
	for suffix in path.suffixes:
		stem = stem.removesuffix(suffix)

	entities: dict[str, str] = {}
	for part in stem.split("_"):
		if "-" not in part:
			continue
		key, value = part.split("-", 1)
		if key and value:
			entities[key] = value

	return entities


def format_bids_entity(key: str, value: str | None) -> str | None:
	if not value:
		return None
	value = str(value)
	return value if value.startswith(f"{key}-") else f"{key}-{value}"


def extract_unique_task_run_from_paths(paths) -> tuple[str | None, str | None]:
	"""Return task_id/run_id when paths have one unambiguous task/run pair."""
	if not paths:
		return None, None

	if isinstance(paths, (str, Path)):
		paths = [paths]

	pairs = set()
	for path in paths:
		entities = extract_bids_entities_from_path(path)
		task = entities.get("task")
		run = entities.get("run")
		if task or run:
			pairs.add((task, run))

	if len(pairs) != 1:
		return None, None

	task, run = pairs.pop()
	return format_bids_entity("task", task), format_bids_entity("run", run)
