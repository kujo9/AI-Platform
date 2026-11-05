# model/: copy one model version to S3

vLLM loads the weights from S3, not from Hugging Face. This folder copies them there.

| File | What it is |
|---|---|
| `qwen3.8-27b.yaml` | the model spec: Hugging Face repo, the exact revision (a commit hash), license, file types |
| `loader/download.py` | downloads that revision, only the allowed file types, and refuses non-safetensors weights |
| `loader/scan.py` | checks the safetensors headers, runs modelscan, checks the license |
| `loader/upload.py` | uploads to `s3://astra-models-<account>/<name>/<revision>/`, `SHA256SUMS` last |
| `loader/register.py` | records the version in the MLflow App: a run with the evidence, and a version of the model `qwen3.8-27b` whose source is the S3 folder, alias `candidate` |
| `job.yaml` | the Kubernetes Job that runs the four scripts inside the cluster |
| `kustomization.yaml` | puts the scripts and the spec in a ConfigMap for the Job |

## Run it

Needs: the cluster. The Hugging Face token in `astra/hf-token` (`terraform output fill_hf_token`) is optional: a public model downloads without it; a gated or private model needs it.

```bash
kubectl apply -k model/
kubectl -n models logs -f job/model-loader
```

The last log line is `registered: qwen3.8-27b version <n> -> s3://astra-models-<account>/qwen3.8-27b/<revision>/ (alias candidate)`.

To see it: `bash scripts/mlflow-ui.sh`, then Models, then `qwen3.8-27b`. The weights stay in S3. MLflow keeps the record of each version (its S3 folder, revision, license, scan result, checksums) and two aliases: `candidate` (loaded, not serving yet) and `champion` (the version that serves; you move it).

## A new version

1. Change `revision` in `qwen3.8-27b.yaml`.
2. Run the Job again:

```bash
kubectl -n models delete job model-loader --ignore-not-found
kubectl apply -k model/
```

3. Serve it: change `model.revision` in `serving/values/` (or start a canary: `scripts/canary.sh`).

In a company, a pipeline runs these steps, plus an evaluation on a GPU and a human approval, before any version can serve. The guide explains that pipeline; this folder is its first four steps, run by hand.
