# syntax=docker/dockerfile:1
# ── Frontend image: Vite build -> unprivileged nginx (listens on 8080) ───────

FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# VITE_API_URL is empty on purpose: production builds call the relative path /api,
# which nginx proxies to the backend (same origin, no CORS).
RUN npm run build


FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

# Rendered by the stock entrypoint (envsubst) into /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --chmod=0755 docker/15-upload-limit.envsh /docker-entrypoint.d/15-upload-limit.envsh
COPY --from=builder /app/dist /usr/share/nginx/html

ENV BACKEND_URL=http://backend:8000 \
    MAX_UPLOAD_MB=2048 \
    PROXY_TIMEOUT=900s

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
