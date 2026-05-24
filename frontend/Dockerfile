# ⚠ DELIBERATE BROWNFIELD DEBT — Item 11
FROM node:latest AS build
WORKDIR /workspace

COPY package.json ./
RUN npm install --no-audit --no-fund

COPY . .
RUN npm run build

# ⚠ Item 11 — nginx:latest also
FROM nginx:latest
COPY --from=build /workspace/dist/grants-portal-modern-frontend/browser /usr/share/nginx/html
EXPOSE 80
