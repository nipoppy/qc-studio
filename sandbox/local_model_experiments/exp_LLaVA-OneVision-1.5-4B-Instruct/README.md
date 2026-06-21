# LLaVA-OneVision 1.5 4B CPU Experiment

This experiment tests:

`lmms-lab/LLaVA-OneVision-1.5-4B-Instruct`

Apple MPS previously failed for this checkpoint with an
`MPSNDArray > 2**32` allocation error, so the script defaults to CPU on Macs.

First test whether the model can fit into memory without running generation:

```bash
LLAVA_DEVICE=cpu LLAVA_LOAD_ONLY=1 python chat_image.py /path/to/PACKAGE.md
```

To reduce weight memory, float16 can be attempted explicitly:

```bash
LLAVA_DEVICE=cpu LLAVA_DTYPE=float16 LLAVA_LOAD_ONLY=1 \
  python chat_image.py /path/to/PACKAGE.md
```

If load-only succeeds, run multimodal inference:

```bash
LLAVA_DEVICE=cpu python chat_image.py /path/to/PACKAGE.md /path/to/scan.nii.gz
```

Generation defaults to 500 new tokens so the model has enough room to finish
the required JSON. Override it when needed:

```bash
LLAVA_MAX_NEW_TOKENS=700 LLAVA_DEVICE=cpu \
  python chat_image.py /path/to/PACKAGE.md /path/to/scan.nii.gz
```

The script saves:

- `<package>_compact_iqm.txt`: compact metric evidence
- `<package>_llava_4b_raw.txt`: unmodified model output
- `<package>_llava_4b_validation.json`: schema validation status
- `<package>_llava_4b_result.json`: formatted output, only when validation passes

The result must contain exactly these keys:

```text
decision
confidence
summary
flagged_metrics
reasons
recommended_followup
```

Set a custom result path with:

```bash
LLAVA_OUTPUT_JSON=/path/to/result.json LLAVA_DEVICE=cpu \
  python chat_image.py /path/to/PACKAGE.md /path/to/scan.nii.gz
```

CPU generation may be slow. This checkpoint requires Transformers 4.53.0,
`qwen-vl-utils`, PyTorch, Nilearn, Nibabel, NumPy, and Matplotlib.
