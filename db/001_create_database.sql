-- Creates the RunNow database. Safe to re-run.
IF DB_ID(N'RunNow') IS NULL
    CREATE DATABASE RunNow;
GO
