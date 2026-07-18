# Frontend BANK Digital (S10) — build Vite tĩnh → nginx serve. Port 80 trong container.
# 2-stage: node build → nginx alpine (image nhỏ, chỉ static + SPA fallback).

# ── stage 1: build ──
FROM node:20-slim AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci 2>/dev/null || npm install
COPY frontend/ ./
# FIX F: prod bundle PHẢI dùng REAL client (không mock). api/index.ts: USE_MOCK_API =
# VITE_USE_MOCK_API !== 'false' → set 'false' TRƯỚC build → bundle tất định dùng REST thật (hết
# banner "● MOCK API"). Vite inline env vào bundle lúc build (không đọc runtime).
ENV VITE_USE_MOCK_API=false
# VITE_API_BASE build-time (FE gọi API qua path tương đối /api mặc định — reverse-proxy compose lo).
RUN npm run build

# ── stage 2: nginx serve tĩnh ──
FROM nginx:1.27-alpine
# SPA fallback: mọi route không-file → index.html (React Router). /api → proxy backend (compose network).
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
