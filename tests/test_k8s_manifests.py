"""Run the offline Kubernetes manifest checks (skipped when PyYAML is missing)."""

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "validate_k8s.py"


def _load():
    spec = importlib.util.spec_from_file_location("validate_k8s", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(mod, k8s_dir, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["validate_k8s.py", "--k8s-dir", str(k8s_dir)])
    return mod.main()


def test_k8s_manifests_are_consistent(monkeypatch, capsys):
    assert _run(_load(), ROOT / "k8s", monkeypatch) == 0, capsys.readouterr().out


def test_validator_detects_broken_service_selector(tmp_path, monkeypatch):
    k8s = tmp_path / "k8s"
    shutil.copytree(ROOT / "k8s", k8s)
    backend = k8s / "base" / "backend.yaml"
    text = backend.read_text(encoding="utf-8")
    # Break only the Service selector (first occurrence after "kind: Service").
    head, sep, tail = text.partition("kind: Service")
    tail = tail.replace("app.kubernetes.io/name: backend\n    app.kubernetes.io/part-of",
                        "app.kubernetes.io/name: backendd\n    app.kubernetes.io/part-of", 1)
    backend.write_text(head + sep + tail, encoding="utf-8")
    assert _run(_load(), k8s, monkeypatch) == 1


def test_validator_detects_missing_configmap_ref(tmp_path, monkeypatch):
    k8s = tmp_path / "k8s"
    shutil.copytree(ROOT / "k8s", k8s)
    f = k8s / "base" / "frontend.yaml"
    f.write_text(f.read_text(encoding="utf-8").replace("motorsport-config", "nope"), encoding="utf-8")
    assert _run(_load(), k8s, monkeypatch) == 1
