# LLaVA-OneVision 0.5B Local Experiment

This experiment tests the Hugging Face checkpoint:

`llava-hf/llava-onevision-qwen2-0.5b-ov-hf`

The script:

1. Reads an MRI QC `PACKAGE.md`.
2. Converts its IQM table into compact, explicit text fields.
3. Optionally loads a NIfTI volume with Nilearn.
4. Renders sagittal, coronal, and axial middle slices into one PNG.
5. Sends the compact IQM evidence and rendered image to LLaVA-OneVision.

## Usage

Activate an environment containing PyTorch, Transformers 4.53.0, Nilearn,
Nibabel, NumPy, and Matplotlib.

```bash
python chat_image.py /path/to/PACKAGE.md /path/to/scan.nii.gz
```

The generated compact IQM text and middle-slice PNG are saved in the current
working directory.

To run without an image:

```bash
python chat_image.py /path/to/PACKAGE.md
```

Set the execution device explicitly when needed:

```bash
LLAVA_DEVICE=cpu python chat_image.py /path/to/PACKAGE.md /path/to/scan.nii.gz
```

## Current Finding

The 0.5B checkpoint is useful for validating the local multimodal pipeline,
but it was not reliable for MRI QC reasoning. It copied schemas, confused
metric values with percentiles, hallucinated unsupported findings, and
occasionally produced unrelated text. Larger 4B or 8B checkpoints should be
tested separately.
