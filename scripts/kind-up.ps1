<#
 Create a kind cluster with ingress-nginx, build + load the images and apply k8s/overlays/local.
 Requires: docker, kind, kubectl. Result: http://localhost:8088
#>
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$Cluster = if ($env:CLUSTER) { $env:CLUSTER } else { "motorsport" }
$IngressVersion = if ($env:INGRESS_NGINX_VERSION) { $env:INGRESS_NGINX_VERSION } else { "controller-v1.11.2" }

foreach ($bin in "docker", "kind", "kubectl") {
    if (-not (Get-Command $bin -ErrorAction SilentlyContinue)) { throw "missing required tool: $bin" }
}
function Run { param([string]$Exe) & $Exe @args; if ($LASTEXITCODE -ne 0) { throw "$Exe $($args -join ' ') failed" } }

if (-not ((kind get clusters) -contains $Cluster)) {
    Run kind create cluster --name $Cluster --config scripts/kind-cluster.yaml
} else {
    Write-Host "kind cluster '$Cluster' already exists, reusing it"
}
Run kubectl config use-context "kind-$Cluster"

Write-Host "==> ingress-nginx ($IngressVersion)"
Run kubectl apply -f "https://raw.githubusercontent.com/kubernetes/ingress-nginx/$IngressVersion/deploy/static/provider/kind/deploy.yaml"
Run kubectl -n ingress-nginx rollout status deploy/ingress-nginx-controller --timeout=180s

Write-Host "==> building images"
Run docker build -t motorsport-backend:dev .
Run docker build -t motorsport-frontend:dev ./frontend

Write-Host "==> loading images into kind"
Run kind load docker-image motorsport-backend:dev motorsport-frontend:dev --name $Cluster

Write-Host "==> applying overlay local"
Run kubectl apply -k k8s/overlays/local
Run kubectl -n motorsport rollout status statefulset/postgres --timeout=180s
Run kubectl -n motorsport rollout status deploy/backend --timeout=300s
Run kubectl -n motorsport rollout status deploy/frontend --timeout=120s

Write-Host "Done. Open http://localhost:8088"
