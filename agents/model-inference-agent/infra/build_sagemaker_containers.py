"""
Build and push custom SageMaker containers for AutoGluon and TabPFN
using AWS CodeBuild (no local Docker needed).

Usage: python infra/build_sagemaker_containers.py
"""

import os
import json
import time
import boto3
import zipfile
import tempfile

REGION = "us-east-1"
ACCOUNT_ID = "014097726564"
BUCKET = f"healthcare-agent-v2-{ACCOUNT_ID}"
CB_SOURCE_BUCKET = f"bedrock-agentcore-codebuild-sources-{ACCOUNT_ID}-{REGION}"

ecr = boto3.client("ecr", region_name=REGION)
cb = boto3.client("codebuild", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)

CONTAINERS = {
    "healthcare-autogluon-serving": "sagemaker/autogluon",
    "healthcare-tabpfn-serving": "sagemaker/tabpfn",
}


def ensure_ecr_repo(name):
    try:
        ecr.create_repository(repositoryName=name)
        print(f"  Created ECR repo: {name}")
    except ecr.exceptions.RepositoryAlreadyExistsException:
        print(f"  ECR repo exists: {name}")
    return f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/{name}"


def upload_source(repo_name, source_dir, ecr_uri):
    """Zip the source dir with buildspec and upload to S3."""
    key = f"codebuild/{repo_name}/source.zip"

    # Generate buildspec.yml
    buildspec = f"""version: 0.2
phases:
  pre_build:
    commands:
      - aws ecr get-login-password --region {REGION} | docker login --username AWS --password-stdin {ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com
  build:
    commands:
      - docker build -t {ecr_uri}:latest .
  post_build:
    commands:
      - docker push {ecr_uri}:latest
"""

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add buildspec
            zf.writestr("buildspec.yml", buildspec)
            # Add source files
            for root, dirs, files in os.walk(source_dir):
                for f in files:
                    full = os.path.join(root, f)
                    arc = os.path.relpath(full, source_dir)
                    zf.write(full, arc)
        tmp_path = tmp.name

    s3.upload_file(tmp_path, CB_SOURCE_BUCKET, key)
    os.unlink(tmp_path)
    print(f"  Uploaded source to s3://{CB_SOURCE_BUCKET}/{key}")
    return key


def create_or_update_project(repo_name, ecr_uri):
    """Create a CodeBuild project for building the container."""
    project_name = f"build-{repo_name}"
    role_arn = f"arn:aws:iam::{ACCOUNT_ID}:role/AmazonBedrockAgentCoreSDKCodeBuild-{REGION}-28aaa8f5de"

    env_config = {
        "type": "LINUX_CONTAINER",
        "computeType": "BUILD_GENERAL1_MEDIUM",
        "image": "aws/codebuild/amazonlinux2-x86_64-standard:5.0",
        "privilegedMode": True,
    }
    source_config = {
        "type": "S3",
        "location": f"{CB_SOURCE_BUCKET}/codebuild/{repo_name}/source.zip",
    }

    try:
        cb.create_project(
            name=project_name,
            source=source_config,
            artifacts={"type": "NO_ARTIFACTS"},
            environment=env_config,
            serviceRole=role_arn,
        )
        print(f"  Created CodeBuild project: {project_name}")
    except cb.exceptions.ResourceAlreadyExistsException:
        cb.update_project(
            name=project_name,
            source=source_config,
            environment=env_config,
        )
        print(f"  Updated CodeBuild project: {project_name}")

    return project_name


def start_and_wait(project_name, max_wait=600):
    """Start build and wait for completion."""
    resp = cb.start_build(projectName=project_name)
    build_id = resp["build"]["id"]
    print(f"  Build started: {build_id}")

    start = time.time()
    while time.time() - start < max_wait:
        builds = cb.batch_get_builds(ids=[build_id])["builds"]
        status = builds[0]["buildStatus"]
        phase = builds[0].get("currentPhase", "?")
        elapsed = int(time.time() - start)

        if status == "SUCCEEDED":
            print(f"  ✓ Build succeeded in {elapsed}s")
            return True
        elif status in ("FAILED", "FAULT", "STOPPED", "TIMED_OUT"):
            print(f"  ✗ Build {status} after {elapsed}s")
            # Print failure details
            for p in builds[0].get("phases", []):
                if p.get("phaseStatus") == "FAILED":
                    ctx = p.get("contexts", [{}])
                    msg = ctx[0].get("message", "") if ctx else ""
                    print(f"    Failed phase: {p['phaseType']} — {msg[:200]}")
            return False

        print(f"    {phase} ({elapsed}s)...")
        time.sleep(15)

    print(f"  ✗ Timeout after {max_wait}s")
    return False


def main():
    print("=" * 60)
    print("  Building Custom SageMaker Containers via CodeBuild")
    print("=" * 60)

    results = {}
    for repo_name, source_dir in CONTAINERS.items():
        print(f"\n[{repo_name}]")
        ecr_uri = ensure_ecr_repo(repo_name)
        upload_source(repo_name, source_dir, ecr_uri)
        project = create_or_update_project(repo_name, ecr_uri)
        ok = start_and_wait(project)
        results[repo_name] = {"ecr_uri": ecr_uri, "success": ok}

    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    for name, r in results.items():
        status = "✓" if r["success"] else "✗"
        print(f"  {status} {name}: {r['ecr_uri']}:latest")


if __name__ == "__main__":
    main()
