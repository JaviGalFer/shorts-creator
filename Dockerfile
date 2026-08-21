# syntax=docker/dockerfile:1
FROM node:20-alpine AS frontend-builder

WORKDIR /app

# Install build dependencies
COPY web/frontend/package.json web/frontend/package-lock.json ./
RUN npm ci

# Copy only frontend source needed for build
COPY web/frontend/src ./src
COPY web/frontend/angular.json ./
COPY web/frontend/tsconfig.app.json ./
COPY web/frontend/tsconfig.json ./
COPY web/frontend/public ./public

# Angular production build
RUN npm run build

# --- Stage 2: Python runtime ---
FROM python:3.12-slim AS runtime

# Install runtime Python dependencies from canonical project file
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install ffmpeg/ffprobe for local rendering (required by pipeline)
# Used by rendering/validation when running natively (not via Docker-run)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy application code (src/ layout)
WORKDIR /app
COPY src/shorts_creator ./shorts_creator

# Copy Angular build output from builder stage
# The Angular CLI outputs to dist/<project>/browser/
COPY --from=frontend-builder /app/dist ./dist

# Copy pipeline scripts and bin entries
COPY bin ./bin

# Ensure bin scripts are executable
RUN chmod +x bin/*.py

# Production frontend build root. The Angular application builder emits to
# <project>/dist/frontend/browser; app.py resolves it via SHORTS_FRONTEND_DIST
# (else falls back to the source layout default).
ENV SHORTS_FRONTEND_DIST=/app/dist/frontend/browser

# Expose the application port
EXPOSE 8000

# Run with one Uvicorn worker (MVP concurrency model)
# LocalJobExecutor and its bounded queue live in-process.
# Multiple workers would create multiple independent executors/queues.
# ffmpeg/ffprobe are available locally (see RUN apt-get above);
# the renderer prefers local binaries but can fall back to Docker.
CMD ["uvicorn", "shorts_creator.web.app:app", "--host", "0.0.0.0", "--port", "8000"]