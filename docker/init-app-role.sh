#!/bin/bash
# Creates the least-privilege role the application runs as. Runs only on the first
# initialisation of an empty data directory (the official Postgres image's
# docker-entrypoint-initdb.d convention), so existing deployments are unaffected.
#
# Privileges are not granted here. Migration 0031 grants them, so that every upgrade
# can extend them to new tables. This script is only responsible for the role existing
# and having a password it can log in with.
# No `set -e`, no `exit`: the Postgres entrypoint *sources* this file rather than
# executing it whenever the mode bits say it is not executable (a fresh clone on
# Windows, a copy through a tool that drops the bit). Sourced, an `exit 0` here
# ends the entrypoint itself, and the container stops with code 0 right after
# initdb, before the server is ever started. Seen on a fresh volume: the app then
# fails with "dependency db failed to start".

APP_PASSWORD="${UTOPIA_APP_DB_PASSWORD:-}"
if [ -z "$APP_PASSWORD" ]; then
    echo "UTOPIA_APP_DB_PASSWORD is not set; skipping the least-privilege role. The application will run as the owner." >&2
else
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'utopia_app') THEN
        CREATE ROLE utopia_app LOGIN PASSWORD '${APP_PASSWORD}';
        RAISE NOTICE 'created least-privilege role utopia_app';
    END IF;
END
\$\$;
GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO utopia_app;
SQL
fi
