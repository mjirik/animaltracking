# Model files

This directory contains the versioned model metadata and class map. The trained
checkpoint is intentionally excluded from Git because binary model weights make
repository history large and cannot be reviewed meaningfully.

Inference downloads `pigtracking_rfdetr_best.pth` from the pinned
[`mjirik/antra`](https://huggingface.co/mjirik/antra) Hugging Face release when
the local file is absent. Place a checkpoint in this directory only to override
the cached default. Each model release publishes these three assets together:

- `pigtracking_rfdetr_best.pth`
- `pigtracking_rfdetr_best.classes.json`
- `pigtracking_rfdetr_best.metadata.json`
- `SHA256SUMS`

The checkpoint used for release `v0.0.1` has SHA-256:

```text
6e836d9db8da992b0ca7f1383ec348848eb51bf51f9523414e6476d910992e0e  pigtracking_rfdetr_best.pth
```
