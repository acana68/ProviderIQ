# syntax=docker/dockerfile:1
# Frontend image: build the Vite app with Node, serve dist/ with unprivileged nginx on 8080.
#   docker build frontend

# --- Build stage -------------------------------------------------------------------------
# The major version must match .nvmrc (CI checks it). It's written out rather than passed
# as a build arg so Dependabot can see and update it. Pinned by digest (what's actually
# pulled), with the tag kept for Dependabot, which updates both. Node 24.21.0.
FROM node:24-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS build

WORKDIR /app

# Dependencies first, so this layer is cached until the lockfile changes.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# --- Final stage -------------------------------------------------------------------------
# Runs as a non-root user and listens on 8080 (not 80), so it needs no privileges.
# nginx 1.31.6 (mainline), pinned by digest. A versioned tag rather than plain "alpine",
# so Dependabot can tell when a newer release is out.
FROM nginxinc/nginx-unprivileged:1.31-alpine@sha256:26b0bf6fbf07297983cb341998d79c831508787de26627dd2a112321b9c3a4af

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

# busybox wget ships with the alpine image.
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -q --spider http://127.0.0.1:8080/ || exit 1
