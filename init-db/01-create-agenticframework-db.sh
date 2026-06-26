#!/bin/sh
# Runs once, only on a fresh/empty Postgres volume (the postgres image's own
# docker-entrypoint-initdb.d convention — see docker-compose.yml's `db`
# service). Creates the second logical database the Ops Portal and
# runtime/llm_gateway.py use, kept separate from Phoenix's own
# alembic-migrated schema (which lives in ${POSTGRES_DB:-phoenix}).
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
    SELECT 'CREATE DATABASE agenticframework' WHERE NOT EXISTS (
        SELECT FROM pg_database WHERE datname = 'agenticframework'
    )\gexec
SQL
