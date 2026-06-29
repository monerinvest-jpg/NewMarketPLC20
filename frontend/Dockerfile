# ── Build stage ─────────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY . .

# Empty by default → the SPA calls the API at the RELATIVE path /api/v1, i.e.
# the same origin it is served from. The edge (Kong) routes /api/* to the
# backend and everything else to this container, so the frontend image embeds
# NO backend hostname and is fully decoupled from the backend. Local dev /
# docker-compose may override this arg with an absolute gateway URL.
ARG VITE_API_URL=
ENV VITE_API_URL=$VITE_API_URL

RUN npx vite build

# ── Production stage (nginx) ───────────────────────────────
FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
