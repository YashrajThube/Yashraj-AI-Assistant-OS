### Build stage
FROM node:20-slim AS builder
WORKDIR /app

# Copy sources and install
COPY ./frontend/package.json ./frontend/package-lock.json* ./
COPY ./frontend /app
RUN npm install --silent --legacy-peer-deps
RUN npm run build

### Production stage
FROM nginx:stable-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY ./frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
