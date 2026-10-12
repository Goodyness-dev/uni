FROM node:22-bookworm-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXT_PUBLIC_API_VERSION=v1
ENV NEXT_PUBLIC_USE_MOCKS=false
ENV NEXT_PUBLIC_API_BASE=""
ENV API_BACKEND_URL=http://127.0.0.1:8001
RUN npm run build
USER node
EXPOSE 3000
CMD ["npm", "run", "start", "--", "--hostname", "127.0.0.1"]
