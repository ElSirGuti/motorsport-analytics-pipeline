#!/usr/bin/env python3
"""Offline consistency checks for the Kustomize manifests in k8s/.

No cluster, kubectl or kustomize needed (only PyYAML). It does NOT render overlays or talk to an
API server: it verifies that the YAML parses and that the objects reference each other
correctly (selectors/labels, Service ports, ConfigMap/Secret/PVC references, probes, volumes,
HPA/PDB/NetworkPolicy targets, overlay patch targets) plus a few security/hygiene rules.

Usage:  python scripts/validate_k8s.py [--k8s-dir k8s]      (exit code 1 on errors)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("PyYAML is required: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

POD_KINDS = {"Deployment", "StatefulSet"}
# Secrets that overlays are expected to receive from outside the repo (never committed).
EXTERNAL_SECRETS = {"prod": {"motorsport-db"}}


def load_docs(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [d for d in yaml.safe_load_all(fh) if d]


def index_by_kind(objs: list[dict]) -> dict[tuple[str, str], dict]:
    return {(o["kind"], o["metadata"]["name"]): o for o in objs}


def pod_spec(obj: dict) -> dict:
    return obj["spec"]["template"]["spec"]


def pod_labels(obj: dict) -> dict:
    return obj["spec"]["template"]["metadata"].get("labels", {})


def selector_matches(selector: dict | None, labels: dict) -> bool:
    if selector is None:
        return False
    ml = selector.get("matchLabels", {})
    return all(labels.get(k) == v for k, v in ml.items())  # {} selects everything


def containers_of(obj: dict):
    spec = pod_spec(obj)
    for c in spec.get("initContainers", []) or []:
        yield c, True
    for c in spec.get("containers", []) or []:
        yield c, False


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, ctx: str, msg: str) -> None:
        self.errors.append(f"[{ctx}] {msg}")

    def warn(self, ctx: str, msg: str) -> None:
        self.warnings.append(f"[{ctx}] {msg}")


def check_base(objs: list[dict], extra_secrets: dict[str, set[str] | None], rep: Report, ctx: str) -> None:
    idx = index_by_kind(objs)
    seen: set[tuple[str, str]] = set()
    for o in objs:
        key = (o["kind"], o["metadata"]["name"])
        if key in seen:
            rep.err(ctx, f"duplicate object {key}")
        seen.add(key)

    configmaps = {n: set((o.get("data") or {}).keys()) for (k, n), o in idx.items() if k == "ConfigMap"}
    secrets: dict[str, set[str] | None] = dict(extra_secrets)  # None = keys unknown (external)
    for (k, n), o in idx.items():
        if k == "Secret":
            secrets[n] = set((o.get("stringData") or {}).keys()) | set((o.get("data") or {}).keys())
    pvcs = {n for (k, n) in idx if k == "PersistentVolumeClaim"}
    sas = {n for (k, n) in idx if k == "ServiceAccount"}
    services = {n: o for (k, n), o in idx.items() if k == "Service"}
    workloads = [o for o in objs if o["kind"] in POD_KINDS]

    for w in workloads:
        name = w["metadata"]["name"]
        wctx = f"{ctx}:{w['kind']}/{name}"
        sel = w["spec"].get("selector", {})
        lbls = pod_labels(w)
        if not selector_matches(sel, lbls) or not sel.get("matchLabels"):
            rep.err(wctx, "spec.selector does not match template labels")
        spec = pod_spec(w)
        sa = spec.get("serviceAccountName")
        if sa and sa not in sas:
            rep.err(wctx, f"serviceAccountName '{sa}' not defined")
        sc = spec.get("securityContext", {})
        if not sc.get("runAsNonRoot"):
            rep.err(wctx, "pod securityContext.runAsNonRoot must be true")
        volumes = {v["name"]: v for v in spec.get("volumes", []) or []}
        for vct in w["spec"].get("volumeClaimTemplates", []) or []:
            volumes[vct["metadata"]["name"]] = vct
        for v in (spec.get("volumes", []) or []):
            claim = (v.get("persistentVolumeClaim") or {}).get("claimName")
            if claim and claim not in pvcs:
                rep.err(wctx, f"volume '{v['name']}' references missing PVC '{claim}'")
        if w["kind"] == "StatefulSet":
            svc = services.get(w["spec"].get("serviceName", ""))
            if not svc:
                rep.err(wctx, "serviceName does not match an existing Service")
            elif svc["spec"].get("clusterIP") != "None":
                rep.err(wctx, f"Service '{svc['metadata']['name']}' should be headless (clusterIP: None)")

        for c, is_init in containers_of(w):
            cctx = f"{wctx}/{c['name']}"
            image = c.get("image", "")
            if image.endswith(":latest"):
                rep.err(cctx, "image uses the :latest tag")
            if not c.get("resources", {}).get("requests") or not c.get("resources", {}).get("limits"):
                rep.err(cctx, "resources.requests and resources.limits are required")
            csc = c.get("securityContext", {})
            if csc.get("allowPrivilegeEscalation") is not False:
                rep.err(cctx, "allowPrivilegeEscalation must be false")
            if csc.get("readOnlyRootFilesystem") is not True:
                rep.err(cctx, "readOnlyRootFilesystem must be true")
            if "ALL" not in (csc.get("capabilities", {}) or {}).get("drop", []):
                rep.err(cctx, "capabilities.drop must include ALL")
            for vm in c.get("volumeMounts", []) or []:
                if vm["name"] not in volumes:
                    rep.err(cctx, f"volumeMount '{vm['name']}' has no matching volume")
            port_names = {p.get("name") for p in c.get("ports", []) or []}
            if not is_init:
                for probe in ("startupProbe", "readinessProbe", "livenessProbe"):
                    pr = c.get(probe)
                    if not pr:
                        if probe == "readinessProbe":
                            rep.err(cctx, "readinessProbe missing")
                        continue
                    port = (pr.get("httpGet") or pr.get("tcpSocket") or {}).get("port")
                    if isinstance(port, str) and port not in port_names:
                        rep.err(cctx, f"{probe} port '{port}' is not a named containerPort")
            for ef in c.get("envFrom", []) or []:
                ref = ef.get("configMapRef")
                if ref and ref["name"] not in configmaps:
                    rep.err(cctx, f"envFrom ConfigMap '{ref['name']}' missing")
                sref = ef.get("secretRef")
                if sref and sref["name"] not in secrets:
                    rep.err(cctx, f"envFrom Secret '{sref['name']}' missing")
            defined: set[str] = set()
            for e in c.get("env", []) or []:
                vf = e.get("valueFrom") or {}
                cm = vf.get("configMapKeyRef")
                if cm:
                    if cm["name"] not in configmaps:
                        rep.err(cctx, f"env {e['name']}: ConfigMap '{cm['name']}' missing")
                    elif cm["key"] not in configmaps[cm["name"]]:
                        rep.err(cctx, f"env {e['name']}: key '{cm['key']}' not in ConfigMap '{cm['name']}'")
                sk = vf.get("secretKeyRef")
                if sk:
                    if sk["name"] not in secrets:
                        rep.err(cctx, f"env {e['name']}: Secret '{sk['name']}' missing")
                    elif secrets[sk["name"]] is not None and sk["key"] not in secrets[sk["name"]]:
                        rep.err(cctx, f"env {e['name']}: key '{sk['key']}' not in Secret '{sk['name']}'")
                for ref in re.findall(r"\$\(([A-Za-z_][A-Za-z0-9_]*)\)", str(e.get("value", ""))):
                    if ref not in defined:
                        rep.err(cctx, f"env {e['name']} uses $({ref}) before it is defined")
                defined.add(e["name"])

    # Services -> workloads
    for name, svc in services.items():
        sel = svc["spec"].get("selector") or {}
        if svc["spec"].get("clusterIP") == "None" and not sel:
            continue
        targets = [w for w in workloads if all(pod_labels(w).get(k) == v for k, v in sel.items())]
        if not targets:
            rep.err(f"{ctx}:Service/{name}", "selector matches no workload")
            continue
        for p in svc["spec"].get("ports", []):
            tp = p.get("targetPort", p["port"])
            ok = False
            for w in targets:
                for c, is_init in containers_of(w):
                    if is_init:
                        continue
                    for cp in c.get("ports", []) or []:
                        if cp.get("name") == tp or cp.get("containerPort") == tp:
                            ok = True
            if not ok:
                rep.err(f"{ctx}:Service/{name}", f"targetPort '{tp}' is not a containerPort of its pods")

    # Ingress -> Service
    for (k, n), o in idx.items():
        if k != "Ingress":
            continue
        for rule in o["spec"].get("rules", []):
            for p in rule["http"]["paths"]:
                b = p["backend"]["service"]
                svc = services.get(b["name"])
                if not svc:
                    rep.err(f"{ctx}:Ingress/{n}", f"backend Service '{b['name']}' missing")
                    continue
                port = b["port"]
                names = {sp.get("name") for sp in svc["spec"]["ports"]}
                nums = {sp["port"] for sp in svc["spec"]["ports"]}
                if port.get("name") not in names and port.get("number") not in nums:
                    rep.err(f"{ctx}:Ingress/{n}", f"port {port} not exposed by Service '{b['name']}'")

    # HPA / PDB / NetworkPolicy
    for (k, n), o in idx.items():
        if k == "HorizontalPodAutoscaler":
            t = o["spec"]["scaleTargetRef"]
            if (t["kind"], t["name"]) not in idx:
                rep.err(f"{ctx}:HPA/{n}", f"scaleTargetRef {t['kind']}/{t['name']} missing")
            if o["spec"]["minReplicas"] > o["spec"]["maxReplicas"]:
                rep.err(f"{ctx}:HPA/{n}", "minReplicas > maxReplicas")
        elif k == "PodDisruptionBudget":
            if not any(selector_matches(o["spec"]["selector"], pod_labels(w)) for w in workloads):
                rep.err(f"{ctx}:PDB/{n}", "selector matches no workload")
        elif k == "NetworkPolicy":
            ps = o["spec"]["podSelector"]
            if ps.get("matchLabels") and not any(selector_matches(ps, pod_labels(w)) for w in workloads):
                rep.err(f"{ctx}:NetworkPolicy/{n}", "podSelector matches no workload")
            rules = []
            for r in (o["spec"].get("ingress") or []):
                rules += r.get("from", [])
            for r in (o["spec"].get("egress") or []):
                rules += r.get("to", [])
            for peer in rules:
                p = peer.get("podSelector")
                if p and p.get("matchLabels") and not any(selector_matches(p, pod_labels(w)) for w in workloads):
                    rep.err(f"{ctx}:NetworkPolicy/{n}", f"peer podSelector {p['matchLabels']} matches no workload")

    # Secrets must never carry real-looking values in committed manifests
    for (k, n), o in idx.items():
        if k == "Secret":
            rep.err(ctx, f"Secret/{n} committed in resources: use generators or external secrets")


def parse_kustomization(path: Path) -> dict:
    docs = load_docs(path)
    return docs[0] if docs else {}


def check_overlay(base_objs: list[dict], kdir: Path, name: str, rep: Report) -> None:
    ctx = f"overlay/{name}"
    kz = parse_kustomization(kdir / "kustomization.yaml")
    base_idx = index_by_kind(base_objs)
    base_images = {c["image"].rsplit(":", 1)[0] for o in base_objs if o["kind"] in POD_KINDS
                   for c, _ in containers_of(o)}
    for r in kz.get("resources", []):
        if not (kdir / r).exists():
            rep.err(ctx, f"resource '{r}' not found")
    for img in kz.get("images", []):
        if img["name"] not in base_images:
            rep.err(ctx, f"images: '{img['name']}' is not used by any base workload")
        if str(img.get("newTag", "")) == "latest":
            rep.err(ctx, "images: do not use the latest tag")
    for rp in kz.get("replicas", []):
        if not any(k in POD_KINDS and n == rp["name"] for (k, n) in base_idx):
            rep.err(ctx, f"replicas: workload '{rp['name']}' not in base")
    gen_secrets: dict[str, set[str] | None] = {}
    for g in kz.get("secretGenerator", []):
        keys = {lit.split("=", 1)[0] for lit in g.get("literals", [])}
        gen_secrets[g["name"]] = keys
    for ext in EXTERNAL_SECRETS.get(name, set()):
        gen_secrets.setdefault(ext, None)
        rep.warn(ctx, f"Secret '{ext}' must exist in the cluster before applying (not generated here)")
    for p in kz.get("patches", []):
        if "path" in p:
            f = kdir / p["path"]
            if not f.exists():
                rep.err(ctx, f"patch file '{p['path']}' not found")
                continue
            for d in load_docs(f):
                key = (d["kind"], d["metadata"]["name"])
                if key not in base_idx:
                    rep.err(ctx, f"patch '{p['path']}' targets {key} which is not in base")
        else:
            t = p["target"]
            key = (t["kind"], t["name"])
            if key not in base_idx:
                rep.err(ctx, f"inline patch target {key} not in base")
                continue
            for op in yaml.safe_load(p["patch"]):
                m = re.match(r"^/data/([^/]+)$", op["path"])
                if m and key[0] == "ConfigMap" and m.group(1) not in (base_idx[key].get("data") or {}):
                    rep.err(ctx, f"patch touches unknown ConfigMap key '{m.group(1)}'")
                if op["op"] == "replace" and op["path"].startswith("/spec/rules/0/host") and key[0] != "Ingress":
                    rep.err(ctx, "host patch on a non-Ingress")
    # Re-run reference checks with the overlay's generated secrets available.
    # Deleted objects (patch $patch: delete) are removed first, to mimic the rendered set.
    deleted = set()
    for p in kz.get("patches", []):
        if "path" in p:
            for d in load_docs(kdir / p["path"]):
                if d.get("$patch") == "delete":
                    deleted.add((d["kind"], d["metadata"]["name"]))
    kept = [o for o in base_objs if (o["kind"], o["metadata"]["name"]) not in deleted]
    sub = Report()
    check_base(kept, gen_secrets, sub, ctx)
    rep.errors += sub.errors
    rep.warnings += sub.warnings
    if name == "local" and "motorsport-db" not in gen_secrets:
        rep.err(ctx, "local overlay must generate the Secret 'motorsport-db'")
    # sample files must not leak anything real
    for f in kdir.glob("*.example.yaml"):
        if f.name in {p.get("path") for p in kz.get("patches", [])} or f.name in kz.get("resources", []):
            rep.err(ctx, f"{f.name} is an example but is wired into the kustomization")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k8s-dir", default=str(Path(__file__).resolve().parent.parent / "k8s"))
    args = ap.parse_args()
    root = Path(args.k8s_dir)
    rep = Report()

    base_dir = root / "base"
    kz = parse_kustomization(base_dir / "kustomization.yaml")
    base_objs: list[dict] = []
    for r in kz.get("resources", []):
        f = base_dir / r
        if not f.exists():
            rep.err("base", f"resource '{r}' not found")
            continue
        base_objs += load_docs(f)
    listed = set(kz.get("resources", []))
    for f in base_dir.glob("*.yaml"):
        if f.name != "kustomization.yaml" and f.name not in listed:
            rep.warn("base", f"{f.name} is not listed in kustomization.yaml")
    ns = kz.get("namespace")
    if not ns or not any(o["kind"] == "Namespace" and o["metadata"]["name"] == ns for o in base_objs):
        rep.err("base", "kustomization namespace must match a Namespace resource")

    # In base the Secret is supplied externally (overlays); allow its keys, check them elsewhere.
    base_secret = {"motorsport-db": {"POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"}}
    check_base(base_objs, base_secret, rep, "base")

    overlays = root / "overlays"
    for d in sorted(p for p in overlays.iterdir() if p.is_dir()):
        check_overlay(base_objs, d, d.name, rep)

    for w in rep.warnings:
        print(f"WARN  {w}")
    for e in rep.errors:
        print(f"ERROR {e}")
    print(f"\nvalidate_k8s: {len(base_objs)} base objects, {len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
