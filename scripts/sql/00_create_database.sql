/*
ACM Database Creation
- Collation: Latin1_General_CI_AI (Case-Insensitive, Accent-Insensitive)
- Files: single data/log for simplicity (adjust for your environment)
*/

IF NOT EXISTS (SELECT 1 FROM sys.databases WHERE name = N'ACM')
BEGIN
    DECLARE @sql nvarchar(max) = N'CREATE DATABASE [ACM]
    COLLATE Latin1_General_CI_AI';
    EXEC (@sql);
END
GO

-- Ensure database options (safe defaults)
ALTER DATABASE [ACM] SET RECOVERY SIMPLE WITH NO_WAIT;
ALTER DATABASE [ACM] SET ANSI_NULL_DEFAULT OFF;
ALTER DATABASE [ACM] SET ANSI_NULLS OFF;
ALTER DATABASE [ACM] SET QUOTED_IDENTIFIER ON;
GO

USE [ACM];
GO

-- Schema owner
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'dbo')
BEGIN
    EXEC('CREATE SCHEMA dbo');
END
GO
