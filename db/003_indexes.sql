-- Indexes. Safe to re-run.
USE RunNow;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'SIX_TrafficSignal_Location')
    CREATE SPATIAL INDEX SIX_TrafficSignal_Location ON dbo.TrafficSignal(Location);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'SIX_GraphNode_Location')
    CREATE SPATIAL INDEX SIX_GraphNode_Location ON dbo.GraphNode(Location);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'SIX_GraphEdge_Geometry')
    CREATE SPATIAL INDEX SIX_GraphEdge_Geometry ON dbo.GraphEdge(Geometry);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_GraphEdge_FromNode')
    CREATE INDEX IX_GraphEdge_FromNode ON dbo.GraphEdge(FromNodeId) INCLUDE (ToNodeId, LengthM);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_GraphNode_SignalId')
    CREATE INDEX IX_GraphNode_SignalId ON dbo.GraphNode(SignalId) WHERE SignalId IS NOT NULL;
GO
