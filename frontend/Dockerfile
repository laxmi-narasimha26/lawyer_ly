# Multi-stage build for production-optimized frontend container
FROM node:18-alpine as builder

# Set build arguments
ARG BUILD_DATE
ARG VERSION
ARG VCS_REF
ARG VITE_API_BASE_URL
ARG VITE_APP_NAME="Indian Legal AI Assistant"

# Add metadata labels
LABEL maintainer="Indian Legal AI Team" \
      org.opencontainers.image.title="Indian Legal AI Assistant Frontend" \
      org.opencontainers.image.description="Production frontend for Indian Legal AI Assistant" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/your-org/indian-legal-ai"

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install all dependencies (including devDependencies needed for build)
RUN npm ci --silent

# Copy source code
COPY . .

# Set build environment variables
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_APP_NAME=${VITE_APP_NAME}
ENV NODE_ENV=production

# Build the application
RUN npm run build

# Production stage with nginx
FROM nginx:1.25-alpine as production

# Install curl for health checks
RUN apk add --no-cache curl

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built application from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Create nginx pid directory
RUN mkdir -p /var/run/nginx && chown -R nginx:nginx /var/run/nginx

# Note: nginx:alpine image already has nginx user/group configured
# nginx.conf will handle user switching to nginx user
# Set proper permissions
RUN chown -R nginx:nginx /usr/share/nginx/html

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]