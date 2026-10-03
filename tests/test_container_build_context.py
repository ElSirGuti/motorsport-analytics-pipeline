"""Static guards for the container build context (no Docker needed).

They protect against regressions that were only discoverable by running the image:
- .dockerignore excluding files the backend needs at runtime,
- the nginx template using a variable the entrypoint does not provide,
- alembic.ini not putting the project root on sys.path (``alembic upgrade head`` failed
  with "No module named 'src'" when run through the console script in the container).
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _dockerignore_patterns() -> list[str]:
    lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def _excluded(rel: str, patterns: list[str]) -> bool:
    """Minimal .dockerignore semantics: patterns are anchored at the context root,
    ``*`` does not cross ``/``, ``**`` does, a matching parent directory excludes the file,
    and a later ``!`` pattern re-includes."""
    parts = rel.split("/")
    excluded = False
    for pat in patterns:
        neg = pat.startswith("!")
        body = (pat[1:] if neg else pat).strip("/")
        rx = (re.escape(body).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*")
              .replace(r"\*", "[^/]*").replace(r"\?", "[^/]"))
        if any(re.fullmatch(rx, "/".join(parts[: i + 1])) for i in range(len(parts))):
            excluded = not neg
    return excluded


RUNTIME_FILES = [
    "main.py",
    "requirements.txt",
    "alembic.ini",
    "alembic/env.py",
    "alembic/script.py.mako",
    "docker/entrypoint.sh",
    "src/data/circuits.json",
    "src/locales/en.json",
    "src/locales/es.json",
]


@pytest.mark.parametrize("rel", RUNTIME_FILES)
def test_runtime_file_exists_and_is_not_dockerignored(rel):
    assert (ROOT / rel).is_file(), rel
    assert not _excluded(rel, _dockerignore_patterns()), f"{rel} is excluded by .dockerignore"


def test_runtime_directories_are_not_dockerignored():
    pats = _dockerignore_patterns()
    for pattern in ("alembic/versions/*.py", "src/locales/extra/*.json", "src/**/*.py"):
        files = [p.relative_to(ROOT).as_posix() for p in ROOT.glob(pattern)
                 if "__pycache__" not in p.parts]
        assert files, pattern
        bad = [f for f in files if _excluded(f, pats)]
        assert not bad, f"excluded by .dockerignore: {bad[:3]}"


def test_dev_only_material_is_dockerignored():
    pats = _dockerignore_patterns()
    for rel in ("tests/test_upload_limit.py", "docs/DEPLOYMENT.md", "k8s/base/backend.yaml",
                "frontend/package.json", "data/motorsport.db", ".git/config", "src/io/__pycache__/x.pyc"):
        assert _excluded(rel, pats), f"{rel} should not be in the image"


def test_alembic_can_import_project_in_container():
    ini = (ROOT / "alembic.ini").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    has_prepend = re.search(r"^\s*prepend_sys_path\s*=\s*\.\s*$", ini, re.M) is not None
    has_pythonpath = re.search(r"PYTHONPATH=/app", dockerfile) is not None
    assert has_prepend or has_pythonpath


def test_nginx_template_variables_are_provided_by_the_entrypoint():
    tpl = (ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    used = set(re.findall(r"\$\{(\w+)\}", tpl))
    dockerfile = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    envsh = (ROOT / "frontend" / "docker" / "15-upload-limit.envsh").read_text(encoding="utf-8")
    provided = set(re.findall(r"^(?:ENV\s+|\s+)(\w+)=", dockerfile, re.M))
    provided |= set(re.findall(r"^export (\w+)", envsh, re.M))
    assert used == {"BACKEND_URL", "NGINX_MAX_BODY", "PROXY_TIMEOUT"}
    assert used <= provided, used - provided


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh")
@pytest.mark.parametrize("mb,expected", [("2048", "4097m"), ("100", "201m"), ("1", "3m")])
def test_upload_limit_envsh(mb, expected):
    script = ROOT / "frontend" / "docker" / "15-upload-limit.envsh"
    out = subprocess.run(["sh", "-c", f'. "{script.as_posix()}" >/dev/null; printf %s "$NGINX_MAX_BODY"'],
                         env={"MAX_UPLOAD_MB": mb, "PATH": __import__("os").environ.get("PATH", "")},
                         capture_output=True, text=True, timeout=20)
    assert out.stdout == expected, out.stderr
