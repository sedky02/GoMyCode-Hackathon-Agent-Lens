FROM node:22-alpine

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# The browser calls the API directly, so this is the address as seen from the host.
ARG VITE_API_URL=http://localhost:8100
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build && chown -R node:node /app
USER node

EXPOSE 5173
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD wget -q -O /dev/null http://127.0.0.1:5173/ || exit 1
CMD ["npx", "vite", "preview", "--host", "0.0.0.0", "--port", "5173", "--strictPort"]
