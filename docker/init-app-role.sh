#!/bin/bash
# Creates the least-privilege role the application runs as. Runs only on the first
# initialisation of an empty data directory (the official Postgres image's
# docker-entrypoint-initdb.d convention), so existing deployments are unaffected.
#
# Privileges are not granted here. Migration 0031 grants them, so that every upgrade
# can extend them to new tables. This script is only responsible for the role existing
# and having a password it can log in with.
set -euo pipefail

APP_PASSWORD="${UTOPIA_APP_DB_PASSWORD:-}"
if [ -z "$APP_PASSWORD" ]; then
    echo "未设置 UTOPIA_APP_DB_PASSWORD，跳过受限角色创建；应用将以 owner 身份运行。" >&2
    exit 0
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'utopia_app') THEN
        CREATE ROLE utopia_app LOGIN PASSWORD '${APP_PASSWORD}';
        RAISE NOTICE '已创建受限角色 utopia_app';
    END IF;
END
\$\$;
GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO utopia_app;
SQL
