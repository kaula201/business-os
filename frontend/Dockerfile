# Frontend image.
# Default (last) stage is the production static build served by nginx.
# Local Compose uses `target: dev` so Vite HMR stays available only in development.

FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Same-origin /api when the SPA is served behind the edge proxy.
ENV VITE_API_URL=
RUN npm run build

FROM node:20-alpine AS dev
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]

FROM nginx:1.27-alpine AS production
COPY nginx.frontend.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
