#!/bin/bash
set -e

# Docker container entrypoint script for VibeCheck backend
# This script waits for PostgreSQL to be ready, runs migrations,
# and then starts the FastAPI server.

echo "🚀 Starting VibeCheck backend..."

# Extract PostgreSQL connection details from DATABASE_URL
# Expected format: postgresql+asyncpg://user:password@host:port/database
DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_USER=$(echo $DATABASE_URL | sed -n 's/.*\/\/\([^:]*\):.*/\1/p')
DB_PASSWORD=$(echo $DATABASE_URL | sed -n 's/.*:\([^@]*\)@.*/\1/p')
DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')

# Set defaults if parsing failed
: "${DB_HOST:=postgres}"
: "${DB_USER:=vibecheck}"
: "${DB_PASSWORD:=password}"
: "${DB_NAME:=vibecheck}"

echo "Database config: host=$DB_HOST user=$DB_USER db=$DB_NAME"

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready at $DB_HOST..."
until PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c '\q' 2>/dev/null; do
  echo "  PostgreSQL is unavailable - sleeping"
  sleep 2
done

echo "✓ PostgreSQL is ready!"

# Run database migrations
echo "⏳ Running database migrations..."
cd /app && alembic upgrade head

echo "✓ Migrations complete!"

# Start the FastAPI server
echo "🎯 Starting FastAPI server..."
exec "$@"
