FROM node:22-alpine AS deps
WORKDIR /srv
COPY package.json ./
RUN npm install --legacy-peer-deps

FROM node:22-alpine AS build
WORKDIR /srv
COPY --from=deps /srv/node_modules ./node_modules
COPY . .
ENV NODE_OPTIONS="--max-old-space-size=512"
RUN npm run build

FROM node:22-alpine
WORKDIR /srv
ENV NODE_ENV=production
COPY --from=build /srv/.next/standalone ./
COPY --from=build /srv/.next/static ./.next/static
COPY --from=build /srv/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
