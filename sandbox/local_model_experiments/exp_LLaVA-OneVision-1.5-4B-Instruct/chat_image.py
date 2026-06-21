import json
import os
import re
import sys
from pathlib import Path

import matplotlib
import numpy as np
import torch
from nilearn import image as nilearn_image
from qwen_vl_utils import process_vision_info
from transformers import AutoConfig, AutoModelForCausalLM, AutoProcessor

matplotlib.use("Agg")
import matplotlib.pyplot as plt


MODEL_ID = "lmms-lab/LLaVA-OneVision-1.5-4B-Instruct"
DEFAULT_PACKAGE = (
    Path(__file__).parents[2]
    / "data/package/sub-000103_acq-standard_T1w/PACKAGE.md"
)
DEFAULT_PROMPT = """You are completing an MRI QC decision task.

Important:
- Do not extract, reformat, or summarize the package.
- Your job is to decide whether this scan should pass QC, fail QC, or remain uncertain.
- Return one raw JSON object only. No markdown. No prose before or after the JSON.
- Use exactly these JSON keys: decision, confidence, summary, flagged_metrics, reasons, recommended_followup.
- `decision` must be exactly one of: pass, fail, uncertain.
- `confidence` must be exactly one of: low, medium, high.
- `summary` must be one sentence.
- `flagged_metrics`, `reasons`, and `recommended_followup` must be arrays of strings.
- Each reason must cite a real metric_name, value, and percentile from the evidence package.
- Do not output nested participant/session/acquisition objects.
- In each metric line, `value` and `percentile` are different fields. Never use the metric value as the percentile.
- Do not invent target ranges or expected ranges. Use only the listed value, percentile, z_score, direction_of_concern, evidence_strength, interpretation, and caveats.
- If IMAGE_STATUS says no image was provided, do not mention image evidence.
- If IMAGE_STATUS says an image was provided, use visible image content as supporting QC evidence.
- Base the decision only on the package text and provided image. Do not invent findings.
- Most scans pass QC. Return fail only if the evidence clearly supports a named artifact or severe degradation. Return uncertain only when evidence is genuinely conflicting.
"""
EXPECTED_RESULT_KEYS = {
    "decision",
    "confidence",
    "summary",
    "flagged_metrics",
    "reasons",
    "recommended_followup",
}


def remove_fenced_code_blocks(text):
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def parse_markdown_row(line):
    return [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]


def build_compact_package(text):
    text = remove_fenced_code_blocks(text)
    lines = text.splitlines()
    compact = []

    for line in lines:
        if line.startswith("**Participant:**"):
            compact.append(line.replace("**", ""))
        elif line.startswith("**Session:**"):
            compact.append(line.replace("**", ""))
        elif line.startswith("**Modality:**"):
            compact.append(line.replace("**", ""))
        elif line.startswith("**Acquisition:**"):
            compact.append(line.replace("**", ""))

    compact.append("")
    compact.append("Provenance warnings:")
    in_warnings = False
    for line in lines:
        if line.startswith("## Provenance Warnings"):
            in_warnings = True
            continue
        if in_warnings and line.startswith("## "):
            in_warnings = False
        if in_warnings and line.startswith("- "):
            compact.append(line)

    compact.append("")
    compact.append("Highlighted IQMs. Column meanings are explicit: metric_name, value, percentile, z_score, direction_of_concern, evidence_strength, interpretation.")

    in_iqm_table = False
    for line in lines:
        if line.startswith("| Metric | Value | Percentile | Z-Score |"):
            in_iqm_table = True
            continue
        if in_iqm_table and line.startswith("---"):
            break
        if not in_iqm_table or not line.startswith("| `"):
            continue

        cells = parse_markdown_row(line)
        if len(cells) < 8:
            continue

        metric, value, percentile, z_score, direction, interpretation, caveats, strength = cells[:8]
        compact.append(
            f"- metric_name={metric}; value={value}; percentile={percentile}; "
            f"z_score={z_score}; direction_of_concern={direction}; "
            f"evidence_strength={strength}; interpretation={interpretation}; caveats={caveats}"
        )

    compact.append("")
    compact.append("Decision rules:")
    capture_rules = False
    for line in lines:
        if line.startswith("Rules:"):
            capture_rules = True
            continue
        if capture_rules and line.startswith("- "):
            compact.append(line)

    return "\n".join(compact)


def extract_json_object(text):
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    decoder = json.JSONDecoder()

    for index, character in enumerate(cleaned):
        if character != "{":
            continue
        try:
            result, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(result, dict):
            return result

    raise ValueError("The model response did not contain a complete JSON object.")


def validate_result(result):
    errors = []
    keys = set(result)

    missing = sorted(EXPECTED_RESULT_KEYS - keys)
    extra = sorted(keys - EXPECTED_RESULT_KEYS)
    if missing:
        errors.append(f"missing keys: {', '.join(missing)}")
    if extra:
        errors.append(f"unexpected keys: {', '.join(extra)}")

    if result.get("decision") not in {"pass", "fail", "uncertain"}:
        errors.append("decision must be pass, fail, or uncertain")
    if result.get("confidence") not in {"low", "medium", "high"}:
        errors.append("confidence must be low, medium, or high")
    if not isinstance(result.get("summary"), str) or not result.get("summary", "").strip():
        errors.append("summary must be a non-empty string")

    for key in ("flagged_metrics", "reasons", "recommended_followup"):
        value = result.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            errors.append(f"{key} must be an array of strings")

    reasons = result.get("reasons")
    if isinstance(reasons, list) and not 4 <= len(reasons) <= 7:
        errors.append("reasons must contain 4 to 7 items")

    return errors


def is_nifti_path(path):
    name = path.name.lower()
    return name.endswith(".nii") or name.endswith(".nii.gz")


def nifti_stem(path):
    name = path.name
    if name.endswith(".nii.gz"):
        return name[:-7]
    if name.endswith(".nii"):
        return name[:-4]
    return path.stem


def normalize_slice(slice_data):
    finite = slice_data[np.isfinite(slice_data)]
    if finite.size == 0:
        return np.zeros_like(slice_data, dtype=np.float32)

    low, high = np.percentile(finite, [1, 99])
    if high <= low:
        return np.zeros_like(slice_data, dtype=np.float32)

    return np.clip((slice_data - low) / (high - low), 0, 1)


def render_middle_slices(nifti_path, output_path):
    img = nilearn_image.load_img(str(nifti_path))
    data = np.asarray(img.get_fdata(dtype=np.float32))

    if data.ndim > 3:
        data = data[..., 0]
    if data.ndim != 3:
        raise ValueError(f"Expected a 3D or 4D NIfTI image, got shape {data.shape}")

    x_mid, y_mid, z_mid = [dim // 2 for dim in data.shape]
    panels = [
        ("Sagittal middle", data[x_mid, :, :]),
        ("Coronal middle", data[:, y_mid, :]),
        ("Axial middle", data[:, :, z_mid]),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(10, 3.6), dpi=180)
    for ax, (title, panel) in zip(axes, panels):
        shown = np.rot90(normalize_slice(panel))
        ax.imshow(shown, cmap="gray", interpolation="nearest")
        ax.set_title(title, fontsize=9)
        ax.axis("off")

    fig.suptitle(f"Middle slices: {nifti_path.name}", fontsize=10)
    fig.tight_layout(pad=0.6)
    fig.savefig(output_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def pick_device():
    force_device = os.getenv("LLAVA_DEVICE")
    if force_device:
        return force_device
    if torch.backends.mps.is_available():
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def pick_dtype(device):
    requested = os.getenv("LLAVA_DTYPE")
    if requested == "float16":
        return torch.float16
    if requested == "bfloat16":
        return torch.bfloat16
    if requested == "float32":
        return torch.float32
    return torch.float16 if device == "cuda" else torch.float32


device = pick_device()
dtype = pick_dtype(device)

package_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PACKAGE
image_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

package_text = build_compact_package(package_path.read_text(encoding="utf-8"))
compact_package_path = Path.cwd() / f"{package_path.parent.name}_compact_iqm.txt"
compact_package_path.write_text(package_text, encoding="utf-8")
raw_response_path = Path.cwd() / f"{package_path.parent.name}_llava_4b_raw.txt"
result_path = Path(
    os.getenv(
        "LLAVA_OUTPUT_JSON",
        str(Path.cwd() / f"{package_path.parent.name}_llava_4b_result.json"),
    )
)
validation_path = Path.cwd() / f"{package_path.parent.name}_llava_4b_validation.json"

if image_path is not None and is_nifti_path(image_path):
    rendered_path = Path.cwd() / f"{nifti_stem(image_path)}_middle_slices.png"
    image_path = render_middle_slices(image_path, rendered_path)
    print(f"Rendered middle slices: {image_path}")

image_status = (
    f"IMAGE_STATUS: image provided at {image_path.resolve()}"
    if image_path is not None
    else "IMAGE_STATUS: no image was provided"
)
print(f"Package input: {package_path.resolve()}")
print(f"Compact IQM package: {compact_package_path.resolve()}")
print(image_status)

processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
config = AutoConfig.from_pretrained(MODEL_ID, trust_remote_code=True)

pad_token_id = processor.tokenizer.pad_token_id
if pad_token_id is None:
    pad_token_id = processor.tokenizer.eos_token_id

config.pad_token_id = pad_token_id
config.text_config.pad_token_id = pad_token_id

print(f"Loading {MODEL_ID} on {device} with {dtype}...")
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    config=config,
    torch_dtype=dtype,
    trust_remote_code=True,
    low_cpu_mem_usage=True,
).to(device).eval()
print("Model loaded successfully.")

if os.getenv("LLAVA_LOAD_ONLY") == "1":
    raise SystemExit(0)

content = []
if image_path is not None:
    content.append({"type": "image", "image": str(image_path.resolve())})

content.append(
    {
        "type": "text",
        "text": f"{DEFAULT_PROMPT}\n\n{image_status}\n\nMRI QC evidence package:\n\n{package_text}",
    }
)

messages = [
    {
        "role": "user",
        "content": content,
    }
]

text = processor.apply_chat_template(
    messages,
    add_generation_prompt=True,
    tokenize=False,
)
image_inputs, video_inputs = process_vision_info(messages)
inputs = processor(
    text=[text],
    images=image_inputs,
    videos=video_inputs,
    padding=True,
    return_tensors="pt",
)
inputs = inputs.to(device)

with torch.no_grad():
    max_new_tokens = int(os.getenv("LLAVA_MAX_NEW_TOKENS", "500"))
    outputs = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=False,
    )

input_length = inputs["input_ids"].shape[-1]
answer = processor.batch_decode(
    outputs[:, input_length:],
    skip_special_tokens=True,
    clean_up_tokenization_spaces=False,
)[0].strip()
raw_response_path.write_text(answer, encoding="utf-8")

try:
    result = extract_json_object(answer)
    validation_errors = validate_result(result)
except ValueError as error:
    validation_errors = [str(error)]
    result = None

validation_report = {
    "valid": not validation_errors,
    "errors": validation_errors,
    "raw_response": raw_response_path.name,
}
validation_path.write_text(
    json.dumps(validation_report, indent=2) + "\n",
    encoding="utf-8",
)

if validation_errors:
    print(f"Raw model response: {raw_response_path.resolve()}")
    print(f"Validation report: {validation_path.resolve()}")
    raise SystemExit("Invalid model JSON: " + "; ".join(validation_errors))

result_path.parent.mkdir(parents=True, exist_ok=True)
result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(f"Validated JSON result: {result_path.resolve()}")
print(json.dumps(result, indent=2))
