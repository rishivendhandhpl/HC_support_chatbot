# syntax=docker/dockerfile:1
# Build the IIFE bundle, then serve dist/ statically. In production the widget
# is normally hosted on a CDN; this image is for local/preview convenience.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
