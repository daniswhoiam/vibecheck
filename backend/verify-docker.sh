#!/bin/bash
# Docker Compose verification script
# Run this script when Docker is available to verify the stack

set -e

echo "Verifying Docker Compose configuration..."

# Validate YAML syntax
docker compose config

echo "✓ Docker Compose YAML is valid"

# Clean up any existing containers
docker compose down -v

echo "Starting PostgreSQL service..."
docker compose up -d postgres

# Wait for PostgreSQL to become healthy
echo "Waiting for PostgreSQL healthcheck..."
timeout=30
elapsed=0
while [ $elapsed -lt $timeout ]; do
    if docker compose ps postgres | grep -q "healthy"; then
        echo "✓ PostgreSQL is healthy"
        break
    fi
    sleep 1
    elapsed=$((elapsed + 1))
done

if [ $elapsed -eq $timeout ]; then
    echo "✗ PostgreSQL failed to become healthy"
    docker compose logs postgres
    exit 1
fi

# Check PostgreSQL status
docker compose ps

echo "Stopping services..."
docker compose down

echo "✓ All verifications passed"
