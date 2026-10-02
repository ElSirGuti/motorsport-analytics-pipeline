#!/usr/bin/env bash
# Create a kind cluster with ingress-nginx, build + load the images and apply k8s/overlays/local.
# Requires: docker, kind, kubectl. Result: http://localhost:8088
set -euo pipefail
cd "$(dirname "$0")/.."

CLUSTER="${CLUSTER:-motorsport}"
INGRESS_NGINX_VERSION="${INGRESS_NGINX_VERSION:-controller-v1.11.2}"

for bin in docker kind kubectl; do
  command -v "$bin" >/dev/null || { echo "missing required tool: $bin" >&2; exit 1; }
done

if ! kind get clusters | grep -qx "$CLUSTER"; then
  kind create cluster --name "$CLUSTER" --config scripts/kind-cluster.yaml
else
  echo "kind cluster '$CLUSTER' already exists, reusing it"
fi
kubectl config use-context "kind-$CLUSTER"

echo "==> ingress-nginx ($INGRESS_NGINX_VERSION)"
kubectl apply -f "https://raw.githubusercontent.com/kubernetes/ingress-nginx/${INGRESS_NGINX_VERSION}/deploy/static/provider/kind/deploy.yaml"
kubectl -n ingress-nginx rollout status deploy/ingress-nginx-controller --timeout=180s

echo "==> building images"
docker build -t motorsport-backend:dev .
docker build -t motorsport-frontend:dev ./frontend

echo "==> loading images into kind"
kind load docker-image motorsport-backend:dev motorsport-frontend:dev --name "$CLUSTER"

echo "==> applying overlay local"
kubectl apply -k k8s/overlays/local
kubectl -n motorsport rollout status statefulset/postgres --timeout=180s
kubectl -n motorsport rollout status deploy/backend --timeout=300s
kubectl -n motorsport rollout status deploy/frontend --timeout=120s

echo "Done. Open http://localhost:8088"
