# syntax=docker/dockerfile:1
# Frontend image: build the Vite app with Node, serve dist/ with unprivileged nginx on 8080.
#   docker build frontend

# --- Build stage -------------------------------------------------------------------------
# The major version must match .nvmrc (CI checks it). It's written out rather than passed
# as a build arg so Dependabot can see and update it.
FROM node:24-alpine AS build

WORKDIR /app

# Dependencies first, so this layer is cached until the lockfile changes.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# --- Final stage -------------------------------------------------------------------------
# Runs as a non-root user and listens on 8080 (not 80), so it needs no privileges.
FROM nginxinc/nginx-unprivileged:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

# busybox wget ships with the alpine image.
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -q --spider http://127.0.0.1:8080/ || exit 1
