# Multi-stage build: compile the Vite/React app, then serve the static
# output with a lightweight nginx image. Build-time VITE_* args let
# docker-compose / Cloud Build point the built bundle at the right API,
# since Vite inlines import.meta.env values at build time, not runtime.
FROM node:22-slim AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_WS_BASE_URL=ws://localhost:8000
ARG VITE_API_KEY=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_WS_BASE_URL=$VITE_WS_BASE_URL
ENV VITE_API_KEY=$VITE_API_KEY

RUN npm run build

FROM nginx:1.27-alpine AS serve

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
