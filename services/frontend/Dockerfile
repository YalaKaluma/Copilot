# Production Dockerfile for Frontend
FROM node:18-alpine AS builder

# Build arguments for environment variables (ENVIRONMENT = prod | staging | branch name from CI)
ARG NODE_ENV=production
ARG ENVIRONMENT=prod
ARG VITE_BACKEND_URL
ARG VITE_PUBLIC_URL
ARG VITE_CLERK_PUBLISHABLE_KEY

# Set working directory
WORKDIR /app

# Install pnpm
RUN npm install -g pnpm

# Copy package files
COPY services/frontend/app/package.json services/frontend/app/pnpm-lock.yaml ./

# Install dependencies
# Use --no-frozen-lockfile to handle pnpm version differences between local and CI
RUN pnpm install --no-frozen-lockfile

# Copy application code
COPY services/frontend/app/ ./

# Build the application (VITE_ENVIRONMENT = ENVIRONMENT so frontend can read it)
ENV NODE_ENV=$NODE_ENV
ENV VITE_ENVIRONMENT=$ENVIRONMENT
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL
ENV VITE_PUBLIC_URL=$VITE_PUBLIC_URL
ENV VITE_CLERK_PUBLISHABLE_KEY=$VITE_CLERK_PUBLISHABLE_KEY
RUN pnpm build

# Production stage
FROM nginx:alpine

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration template. The nginx image renders templates with
# environment variables on startup, including Railway's PORT.
COPY services/frontend/nginx.conf.template /etc/nginx/templates/default.conf.template

# Default for local Docker runs. Railway overrides this at runtime.
ENV PORT=80

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
