#!/bin/bash
set -e

echo "Starting Backend..."

APP_USER="${APP_USER:-appuser}"
PRIVS_DROPPED_FLAG="${BACKEND_PRIVS_DROPPED:-0}"

if [ "$(id -u)" -eq 0 ] && [ "$PRIVS_DROPPED_FLAG" != "1" ]; then
    echo "Preparing runtime directories..."
    mkdir -p /sandbox/data /sandbox/jobs
    chown -R "$APP_USER:$APP_USER" /sandbox /app

    quoted_entrypoint="$(printf '%q ' /usr/local/bin/docker-entrypoint.sh "$@")"
    echo "Dropping privileges to $APP_USER"
    exec su -s /bin/bash "$APP_USER" -c "export BACKEND_PRIVS_DROPPED=1; exec ${quoted_entrypoint}"
fi

# Centralized migrations in packages/db
ALEMBIC_CONFIG="/packages/db/alembic.ini"
MIGRATION_MAX_RETRIES="${MIGRATION_MAX_RETRIES:-10}"
MIGRATION_RETRY_DELAY_SECONDS="${MIGRATION_RETRY_DELAY_SECONDS:-3}"
RUN_DB_MIGRATIONS_ON_STARTUP="${RUN_DB_MIGRATIONS_ON_STARTUP:-true}"

if [ "$RUN_DB_MIGRATIONS_ON_STARTUP" != "true" ]; then
    echo "RUN_DB_MIGRATIONS_ON_STARTUP=$RUN_DB_MIGRATIONS_ON_STARTUP - skipping startup migrations"
elif [ -n "$DATABASE_URL" ]; then
    echo "Database configured, running migrations..."

    migration_ok=0
    for attempt in $(seq 1 "$MIGRATION_MAX_RETRIES"); do
        echo "Migration attempt $attempt/$MIGRATION_MAX_RETRIES"
        if [ -n "$UV_NO_SYNC" ]; then
            if .venv/bin/alembic -c "$ALEMBIC_CONFIG" upgrade head; then
                migration_ok=1
                break
            fi
        else
            if uv run -- alembic -c "$ALEMBIC_CONFIG" upgrade head; then
                migration_ok=1
                break
            fi
        fi

        if [ "$attempt" -lt "$MIGRATION_MAX_RETRIES" ]; then
            echo "Migration attempt failed, retrying in ${MIGRATION_RETRY_DELAY_SECONDS}s..."
            sleep "$MIGRATION_RETRY_DELAY_SECONDS"
        fi
    done

    if [ "$migration_ok" -ne 1 ]; then
        echo "Migrations failed after $MIGRATION_MAX_RETRIES attempts. Exiting."
        exit 1
    fi

    echo "Migrations completed"
else
    echo "No DATABASE_URL configured - skipping migrations"
fi

echo "Starting application..."
exec "$@"
