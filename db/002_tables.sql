-- Core tables. Safe to re-run: each table is created only if missing.
USE RunNow;
GO

-- Toronto traffic signals (City of Toronto open data).
IF OBJECT_ID(N'dbo.TrafficSignal', N'U') IS NULL
CREATE TABLE dbo.TrafficSignal (
    SignalId        INT IDENTITY(1,1) PRIMARY KEY,
    SourceId        NVARCHAR(50)  NOT NULL,           -- id from the city dataset
    SignalType      NVARCHAR(50)  NULL,               -- e.g. full signal, pedestrian crossover
    MainStreet      NVARCHAR(200) NULL,
    CrossStreet     NVARCHAR(200) NULL,
    Location        GEOGRAPHY     NOT NULL,           -- point, SRID 4326
    LoadedAt        DATETIME2(0)  NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_TrafficSignal_SourceId UNIQUE (SourceId)
);
GO

-- Street network intersections and dead ends (OpenStreetMap via OSMnx).
IF OBJECT_ID(N'dbo.GraphNode', N'U') IS NULL
CREATE TABLE dbo.GraphNode (
    NodeId          BIGINT        PRIMARY KEY,        -- OSM node id
    Location        GEOGRAPHY     NOT NULL,
    StreetCount     TINYINT       NULL,               -- streets meeting at this node
    SignalId        INT           NULL REFERENCES dbo.TrafficSignal(SignalId), -- set when a signal is matched here
    LoadedAt        DATETIME2(0)  NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

-- Runnable street segments between two nodes. One row per direction.
IF OBJECT_ID(N'dbo.GraphEdge', N'U') IS NULL
CREATE TABLE dbo.GraphEdge (
    EdgeId          BIGINT IDENTITY(1,1) PRIMARY KEY,
    FromNodeId      BIGINT        NOT NULL REFERENCES dbo.GraphNode(NodeId),
    ToNodeId        BIGINT        NOT NULL REFERENCES dbo.GraphNode(NodeId),
    OsmWayId        BIGINT        NULL,
    StreetName      NVARCHAR(200) NULL,
    HighwayType     NVARCHAR(50)  NULL,               -- OSM highway tag, e.g. residential, footway
    LengthM         FLOAT         NOT NULL CHECK (LengthM >= 0),
    Geometry        GEOGRAPHY     NOT NULL,           -- linestring
    LoadedAt        DATETIME2(0)  NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
