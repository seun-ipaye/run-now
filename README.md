# RunNow

Running loops in Toronto with the fewest red lights.

Pick a start point and a distance, and RunNow returns a loop that avoids signalized intersections.

## Stack

SQL Server 2022 (T-SQL views, spatial stored procedures) · Python ETL (Pandas, GeoPandas, OSMnx, SQLAlchemy) · NetworkX routing · FastAPI · Angular + Leaflet (planned)

## Layout

```
db/    T-SQL schema, indexes, views, stored procedures (numbered, applied in order)
etl/   one loader per dataset, plus shared helpers
api/   FastAPI service and routing
web/   Angular front end (planned)
```

## Local setup

Requires Docker Desktop. On Apple Silicon, turn on **Settings → General → Use Rosetta for x86_64/amd64 emulation**, because SQL Server has no ARM image.

```bash
cp .env.example .env    # then set a strong MSSQL_SA_PASSWORD
docker compose up -d
docker compose ps       # wait for "healthy"
```

Check that it's running:

```bash
docker exec runnow-sql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -C -Q "SELECT @@VERSION"
```

The container runs SQL Server **Developer Edition**, which is licensed for development and testing only. A public deployment needs a production-licensed database, such as Azure SQL Database.

## Data limits

_To be written as the datasets are loaded._
