FROM node:20-slim
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
# VITE_API_URL must be baked in at build time (Vite inlines env vars).
# Railway passes the service variable of the same name as a build arg.
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build
RUN npm install -g serve
EXPOSE 3000
# Bind to Railway's $PORT in prod; fall back to 3000 locally.
CMD ["sh", "-c", "serve -s dist -l ${PORT:-3000}"]