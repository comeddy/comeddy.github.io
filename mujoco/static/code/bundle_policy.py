#!/usr/bin/env python3
"""Create or verify an offline workshop bundle. Never publish, deploy, or authorize a robot."""

import argparse
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys

from check_policy import (MAX_POLICY_BYTES, SCOPE, PolicyError, json_bytes,
                          read_regular, sha256, strict_json, validate_bytes)

MANIFEST = "workshop-manifest.json"
CHECKSUMS = "checksums.sha256"
EVALUATION = "evidence/evaluation.json"
SMOKE = "smoke-report.json"
MAX_JSON_BYTES = 1024 * 1024
MAX_REPORT_BYTES = 16 * 1024 * 1024
MAX_BUNDLE_BYTES = 512 * 1024 * 1024
SAFETY = {"physical_trial_authorized": False, "hardware_validated": False,
          "deployment_authorized": False, "deployed": False,
          "normalizer_verified": False}


def require(condition, message):
    if not condition:
        raise PolicyError(message)


def keys(value, expected, label):
    require(isinstance(value, dict) and set(value) == set(expected),
            f"Invalid {label} fields; expected {', '.join(expected)}")


def digest(value, label="SHA256"):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value),
            f"{label} must be a lowercase 64-character SHA256")
    return value


def safe_relative(name):
    require(isinstance(name, str) and 0 < len(name) <= 240, "Invalid relative file path")
    require(all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", part)
                for part in name.split("/")), f"Unsafe relative path: {name!r}")
    return PurePosixPath(name)


def read_member(root, name, limit=MAX_POLICY_BYTES):
    """Resolve every component using no-follow directory descriptors (POSIX)."""
    parts = safe_relative(name).parts
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(root, flags)
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return read_regular(parts[-1], limit, dir_fd=fd)
    finally:
        os.close(fd)


def check_provenance(value):
    keys(value, ["source_refs", "task_id", "checkpoint_sha256", "exporter",
                 "official_exporter_used", "checkpoint_validated_by_user"], "provenance")
    refs = value["source_refs"]
    require(isinstance(refs, dict) and 1 <= len(refs) <= 16, "Provide pinned source refs")
    for repo, commit in refs.items():
        require(isinstance(repo, str) and re.fullmatch(
            r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo),
            "Source refs must name a public GitHub repository URL (no branch or credentials)")
        require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit),
                "Each source ref must be a full lowercase 40-character Git commit")
    require(isinstance(value["task_id"], str) and re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}", value["task_id"]), "Invalid task_id")
    digest(value["checkpoint_sha256"], "checkpoint_sha256")
    require(value["exporter"] == "mjlab_microduck.export", "Unrecognized exporter declaration")
    for key in ["official_exporter_used", "checkpoint_validated_by_user"]:
        require(type(value[key]) is bool, f"{key} must be an explicit boolean attestation")


def check_evaluation(value, provenance, policy_hash):
    keys(value, ["schema_version", "simulation", "notes"], "evaluation")
    require(type(value["schema_version"]) is int and value["schema_version"] == 1,
            "Unsupported evaluation schema_version")
    require(isinstance(value["notes"], str), "Evaluation notes must be a string")
    sim = value["simulation"]
    keys(sim, ["status", "task_id", "checkpoint_sha256", "policy_sha256", "reports"], "simulation")
    require(isinstance(sim["status"], str) and sim["status"] in {"passed", "failed", "not_run"},
            "simulation.status must explicitly be passed, failed, or not_run")
    require(sim["task_id"] == provenance["task_id"], "Evaluation task_id does not match provenance")
    require(sim["checkpoint_sha256"] == provenance["checkpoint_sha256"],
            "Evaluation checkpoint_sha256 does not match provenance")
    require(sim["policy_sha256"] == policy_hash, "Evaluation policy_sha256 does not match policy")
    reports = sim["reports"]
    require(isinstance(reports, list) and 1 <= len(reports) <= 32,
            "Evaluation must reference 1..32 local report sidecars")
    for name in reports:
        safe_relative(name)
        require(name != "evaluation.json", "evaluation.json is reserved; reference a separate report")
    require(len(set(reports)) == len(reports), "Duplicate evaluation report path")
    # Prevent a report file from also acting as another report's parent directory.
    for name in reports:
        require(not any(str(parent) in reports for parent in PurePosixPath(name).parents),
                "Conflicting report file/directory paths")
    return sim


def _check_smoke(value, policy_hash):
    require(isinstance(value, dict), "Invalid smoke report")
    for field, expected in [("schema_version", 1), ("scope", SCOPE), ("passed", True),
                            ("portable_single_file", True), ("finite_outputs", True),
                            ("constant_output", False), ("physical_trial_authorized", False),
                            ("normalizer_verified", False), ("policy_sha256", policy_hash)]:
        require(type(value.get(field)) is type(expected) and value.get(field) == expected,
                f"Invalid smoke report {field}")
    for key, shape in [("input", [1, 61]), ("output", [1, 14])]:
        require(isinstance(value.get(key), dict) and value[key].get("shape") == shape
                and value[key].get("dtype") == "float32", f"Invalid smoke report {key}")


def create_bundle(policy, output, evaluation, provenance, *, samples=32, seed=2026):
    """Package verified bytes and user evidence, without a simulation success gate."""
    output, evaluation = Path(output), Path(evaluation)
    require(not os.path.lexists(output), f"Output already exists; refusing overwrite: {output}")
    check_provenance(provenance)
    data = read_regular(policy)
    smoke = validate_bytes(data, samples=samples, seed=seed)
    evaluation_data = read_regular(evaluation, MAX_JSON_BYTES)
    sim = check_evaluation(strict_json(evaluation_data), provenance, sha256(data))
    payloads = {"policy.onnx": data, SMOKE: json_bytes(smoke), EVALUATION: evaluation_data}
    for name in sim["reports"]:
        report = read_member(evaluation.parent, name, MAX_REPORT_BYTES)
        require(bool(report), f"Empty evaluation report: {name}")
        if name.lower().endswith(".json"):
            strict_json(report)
        payloads[f"evidence/{name}"] = report
        require(sum(map(len, payloads.values())) <= MAX_BUNDLE_BYTES, "Bundle exceeds 512 MiB")
    manifest = {
        "schema_version": 1, "kind": "microduck-offline-workshop-bundle",
        "policy": {"path": "policy.onnx", "sha256": sha256(data)},
        "provenance": provenance,
        "evaluation": {"path": EVALUATION, "simulation_status": sim["status"],
                       "report_files": [f"evidence/{name}" for name in sim["reports"]]},
        "smoke_report": SMOKE, "safety": dict(SAFETY),
        "files": {name: sha256(value) for name, value in sorted(payloads.items())},
    }
    payloads[MANIFEST] = json_bytes(manifest)
    payloads[CHECKSUMS] = "".join(f"{sha256(value)}  {name}\n"
                                for name, value in sorted(payloads.items())).encode()
    # Exclusive mkdir is the final overwrite check, including a concurrent creator.
    output.mkdir()
    try:
        for name, value in payloads.items():
            dest = output.joinpath(*safe_relative(name).parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("xb") as stream:
                stream.write(value)
        return verify_bundle(output, expected_manifest_sha256=sha256(payloads[MANIFEST]))
    except Exception:
        shutil.rmtree(output)
        raise


def _inventory(root):
    require(stat.S_ISDIR(root.lstat().st_mode), "Bundle root must be a directory, not a symlink")
    members = set()
    def walk_error(exc):
        raise exc
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        for name in dirs + files:
            path = Path(directory) / name
            mode = path.lstat().st_mode
            relative = path.relative_to(root).as_posix()
            safe_relative(relative)
            require(stat.S_ISDIR(mode) or stat.S_ISREG(mode),
                    f"Only regular files/directories are allowed, no symlinks: {relative}")
            if stat.S_ISREG(mode):
                members.add(relative)
                require(len(members) <= 40, "Too many files in bundle")
    return members


def verify_bundle(root, *, expected_manifest_sha256=None):
    """Verify integrity and declared schema only. Does not execute the model."""
    root = Path(root)
    members = _inventory(root)
    checksums = read_member(root, CHECKSUMS, MAX_JSON_BYTES)
    hashes = {}
    try:
        for line in checksums.decode("ascii").splitlines():
            require(len(line) > 66 and line[64:66] == "  ", "Malformed checksums.sha256 line")
            value, name = digest(line[:64]), line[66:]
            safe_relative(name)
            require(name != CHECKSUMS and name not in hashes, "Duplicate or self checksum entry")
            hashes[name] = value
    except UnicodeError as exc:
        raise PolicyError("checksums.sha256 must be ASCII") from exc
    require(set(hashes) | {CHECKSUMS} == members, "Checksum inventory does not match exact bundle files")
    require(MANIFEST in hashes, "Missing workshop manifest checksum")
    payloads = {}
    for name, expected in hashes.items():
        limit = (MAX_POLICY_BYTES if name == "policy.onnx" else
                 MAX_JSON_BYTES if name in {MANIFEST, SMOKE, EVALUATION} else MAX_REPORT_BYTES)
        payloads[name] = read_member(root, name, limit)
        require(sha256(payloads[name]) == expected, f"SHA256 mismatch: {name}")
        require(sum(map(len, payloads.values())) <= MAX_BUNDLE_BYTES, "Bundle exceeds 512 MiB")
        if name.lower().endswith(".json"):
            strict_json(payloads[name])
    manifest_data = payloads[MANIFEST]
    if expected_manifest_sha256 is not None:
        require(sha256(manifest_data) == digest(expected_manifest_sha256),
                "Manifest differs from the independently retained SHA256")
    manifest = strict_json(manifest_data)
    keys(manifest, ["schema_version", "kind", "policy", "provenance", "evaluation",
                    "smoke_report", "safety", "files"], "workshop manifest")
    require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1,
            "Unsupported workshop manifest version")
    require(manifest["kind"] == "microduck-offline-workshop-bundle", "Invalid workshop bundle kind")
    keys(manifest["safety"], SAFETY, "safety")
    require(all(value is False for value in manifest["safety"].values()),
            "All hardware/deployment/normalizer flags must remain false")
    check_provenance(manifest["provenance"])
    keys(manifest["policy"], ["path", "sha256"], "policy")
    require(manifest["policy"]["path"] == "policy.onnx", "Invalid policy path")
    require(isinstance(manifest["files"], dict), "Invalid manifest files")
    for name, value in manifest["files"].items():
        safe_relative(name)
        digest(value)
    require(manifest["files"] == {n: h for n, h in hashes.items() if n != MANIFEST},
            "Manifest file hashes do not match checksums")
    require(manifest["smoke_report"] == SMOKE, "Invalid smoke_report path")
    require({"policy.onnx", SMOKE, EVALUATION} <= payloads.keys(), "Missing required bundle files")
    policy_hash = sha256(payloads["policy.onnx"])
    require(manifest["policy"]["sha256"] == policy_hash, "Policy provenance hash mismatch")
    _check_smoke(strict_json(payloads[SMOKE]), policy_hash)
    sim = check_evaluation(strict_json(payloads[EVALUATION]), manifest["provenance"], policy_hash)
    expected_eval = {"path": EVALUATION, "simulation_status": sim["status"],
                     "report_files": [f"evidence/{name}" for name in sim["reports"]]}
    require(manifest["evaluation"] == expected_eval, "Evaluation references/status do not match")
    require(set(manifest["files"]) == {"policy.onnx", SMOKE, EVALUATION,
                                      *expected_eval["report_files"]}, "Unexpected bundle payloads")
    require(all(payloads[name] for name in expected_eval["report_files"]), "Empty report sidecar")
    return {"verified": True, "scope": "bundle_integrity_and_schema_only",
            "manifest_sha256": sha256(manifest_data), "policy_sha256": policy_hash,
            "file_count": len(members), "simulation_status_user_reported": sim["status"],
            **SAFETY}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="Validate and copy into a NEW offline bundle directory")
    create.add_argument("policy", type=Path)
    create.add_argument("output", type=Path)
    create.add_argument("--evaluation", type=Path, required=True)
    create.add_argument("--task-id", required=True)
    create.add_argument("--checkpoint-sha256", required=True)
    create.add_argument("--source-ref", action="append", required=True, metavar="REPO_URL@COMMIT",
                        help="Repeat for pinned training/runtime sources; full 40-character commits")
    create.add_argument("--official-exporter-used", action="store_true",
                        help="USER ATTESTATION that mjlab_microduck.export was used; not detected")
    create.add_argument("--checkpoint-validated-by-user", action="store_true",
                        help="USER ATTESTATION that this checkpoint was independently validated")
    create.add_argument("--samples", type=int, default=32)
    create.add_argument("--seed", type=int, default=2026)
    verify = sub.add_parser("verify", help="Check exact bytes, safe paths and schema; no inference")
    verify.add_argument("bundle", type=Path)
    verify.add_argument("--expected-manifest-sha256", help="Digest retained separately from the bundle")
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            report = verify_bundle(args.bundle, expected_manifest_sha256=args.expected_manifest_sha256)
        else:
            refs = {}
            for source in args.source_ref:
                repo, sep, ref = source.rpartition("@")
                require(bool(sep) and repo not in refs, "Invalid or duplicate --source-ref")
                refs[repo] = ref
            provenance = {"source_refs": refs, "task_id": args.task_id,
                          "checkpoint_sha256": args.checkpoint_sha256,
                          "exporter": "mjlab_microduck.export",
                          "official_exporter_used": args.official_exporter_used,
                          "checkpoint_validated_by_user": args.checkpoint_validated_by_user}
            report = create_bundle(args.policy, args.output, args.evaluation, provenance,
                                   samples=args.samples, seed=args.seed)
        sys.stdout.buffer.write(json_bytes(report))
        return 0
    except (PolicyError, OSError) as exc:
        sys.stderr.buffer.write(json_bytes({"verified": False, "error": str(exc), **SAFETY}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
