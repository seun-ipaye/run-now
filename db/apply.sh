#!/usr/bin/env bash
# Applies every numbered .sql file in db/ in order, inside the runnow-sql container.
set -euo pipefail
cd "$(dirname "$0")"
source ../.env
for f in [0-9][0-9][0-9]_*.sql; do
  echo "Applying $f"
  docker exec -i runnow-sql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -C -b -I < "$f"
done
