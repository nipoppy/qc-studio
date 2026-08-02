import os
import re
import sys
from pathlib import Path

import matplotlib
import numpy as np
import torch
from nilearn import image as nilearn_image
from transformers import AutoProcessor, LlavaOnevisionForConditionalGeneration

matplotlib.use("Agg")
import matplotlib.pyplot as plt


MODEL_ID = "llava-hf/llava-onevision-qwen2-0.5b-ov-hf"
EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PACKAGE = (
    REPO_ROOT
    / "sandbox/cloud_model_experiments/IQMs_only_exp/package/sub-000103_acq-standard_T1w/PACKAGE.md"
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
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


device = pick_device()
dtype = torch.float16 if device in {"mps", "cuda"} else torch.float32

package_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PACKAGE
image_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

package_text = build_compact_package(package_path.read_text(encoding="utf-8"))
compact_package_path = EXPERIMENT_DIR / f"{package_path.parent.name}_compact_iqm.txt"
compact_package_path.write_text(package_text, encoding="utf-8")

if image_path is not None and is_nifti_path(image_path):
    rendered_path = EXPERIMENT_DIR / f"{nifti_stem(image_path)}_middle_slices.png"
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

processor = AutoProcessor.from_pretrained(MODEL_ID)
model = LlavaOnevisionForConditionalGeneration.from_pretrained(
    MODEL_ID,
    torch_dtype=dtype,
    low_cpu_mem_usage=True,
).to(device).eval()

content = []
if image_path is not None:
    content.append({"type": "image", "url": str(image_path.resolve())})

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

inputs = processor.apply_chat_template(
    messages,
    add_generation_prompt=True,
    tokenize=True,
    return_dict=True,
    return_tensors="pt",
).to(device, dtype)

with torch.no_grad():
    outputs = model.generate(**inputs, max_new_tokens=400, do_sample=False)

input_length = inputs["input_ids"].shape[-1]
answer = processor.decode(outputs[0][input_length:], skip_special_tokens=True)
print(answer.strip())
