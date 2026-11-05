"""Step 4: record this model version in MLflow, the model registry.

The weights stay in S3. MLflow keeps the reference:
  - one run in the experiment `astra-model-loader`: what was loaded and the scan report;
  - one version of the registered model `qwen3.8-27b`, linked to that run. Its source is the
    S3 folder, and its tags say what it is: repo, revision, license, scan result, checksums.
  - the alias `candidate` on that version: scanned and in S3, not serving yet.
    You move the alias `champion` to the version that serves (05-model-pipeline, 09-operate).

Running it again for the same revision changes nothing: it finds the version by its revision tag.
"""

import argparse
import hashlib
import json
import os
import pathlib
import sys
import tempfile

import boto3
import mlflow
from mlflow import MlflowClient

import spec as specs

EXPERIMENT = "astra-model-loader"


def tracking_uri():
    """The MLflow App's ARN. The sagemaker-mlflow plugin signs each call with the pod's role."""
    if os.environ.get("MLFLOW_TRACKING_URI"):
        return os.environ["MLFLOW_TRACKING_URI"]
    name = os.environ.get("MLFLOW_APP_NAME") or "astra"
    sm = boto3.client("sagemaker")
    for page in sm.get_paginator("list_mlflow_apps").paginate():
        for app in page["Summaries"]:
            if app["Name"] == name:
                return app["Arn"]
    sys.exit(f"no MLflow App named '{name}' in this account and region")


def read_from_s3(s3, bucket, key):
    try:
        return s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    except s3.exceptions.NoSuchKey:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    args = ap.parse_args()

    s = specs.load(args.spec)
    bucket, prefix = specs.models_bucket(), specs.model_prefix(s)
    source = f"s3://{bucket}/{prefix}"
    s3 = boto3.client("s3")

    # Only a complete upload is registered: SHA256SUMS is written last (upload.py).
    sums = read_from_s3(s3, bucket, prefix + "SHA256SUMS")
    if sums is None:
        sys.exit(f"not complete in S3 (no SHA256SUMS): {source}")
    report = read_from_s3(s3, bucket, prefix + "modelscan-report.json")

    mlflow.set_tracking_uri(tracking_uri())
    client = MlflowClient()
    name = s["name"]

    if not client.search_registered_models(filter_string=f"name = '{name}'"):
        client.create_registered_model(name, description=f"{s['hf_repo']}, copied to S3 by the model loader Job.")
        print(f"created registered model {name}")

    for v in client.search_model_versions(filter_string=f"name = '{name}'"):
        if v.tags.get("revision") == s["revision"]:
            print(f"already registered: {name} version {v.version} -> {v.source}")
            return

    lines = sums.decode().splitlines()
    tags = {
        "hf_repo": s["hf_repo"],
        "revision": s["revision"],
        "license": s["license"],
        "scan": "passed" if report is not None else "no report",
        "files": str(len(lines)),
        "sha256sums": hashlib.sha256(sums).hexdigest(),   # one hash for the whole file list
        "s3_uri": source,
    }

    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=f"{name}@{s['revision'][:8]}") as run:
        mlflow.set_tags(tags)
        mlflow.log_params({"hf_repo": s["hf_repo"], "revision": s["revision"], "license": s["license"]})
        mlflow.log_metric("files", len(lines))
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "SHA256SUMS").write_bytes(sums)
            if report is not None:
                (pathlib.Path(tmp) / "modelscan-report.json").write_bytes(report)
            mlflow.log_artifacts(tmp, artifact_path="evidence")
            # The spec, as loaded, so the run shows exactly what was asked for.
            mlflow.log_text(json.dumps(s, indent=2), "evidence/model-spec.json")

    v = client.create_model_version(
        name, source=source, run_id=run.info.run_id, tags=tags,
        description=f"{s['hf_repo']} at {s['revision']}",
    )
    client.set_registered_model_alias(name, "candidate", v.version)
    print(f"registered: {name} version {v.version} -> {source} (alias candidate)")


if __name__ == "__main__":
    main()
