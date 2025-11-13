USE [XStudio_Historian]
GO

/****** Object:  StoredProcedure [dbo].[XHS_Retrieve_Tag_Full_Value_Usp]    Script Date: 28-10-2025 12:52:08 ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

-- =============================================
-- Author:		<Author,,Name>
-- Create date: <Create Date,,>
-- Description:	<Description,,>
-- =============================================
CREATE OR ALTER   PROCEDURE [dbo].[XHS_Retrieve_Tag_Full_Value_Usp]
	@StartTime	VARCHAR(25)		= '2025-Jul-12 00:00:00',
	@EndTime	VARCHAR(25)		= '2025-Jul-16 11:00:00',
	@TagName		VARCHAR(MAX)	= 'MT00001,MT00002,MT00003,MT00004,MT00005,MT00006,MT00007,MT00008,MT00015,MT00009,MT00010',
	@Format		VARCHAR(100)	= 'Wide', -- 'Narrow', 'Wide' 
	@HeaderFormat VARCHAR(200)	= 'Name' -- Name, Unit, Description, TagNo, TagType, TagID, StorageType, AliasName, Agg
AS
BEGIN
	SET NOCOUNT ON;

    ---------- Prepare datatable list ----------
	BEGIN
		---------- Load data table list between start-date and end-date for full retrieval ----------
		DECLARE @DATATABLE AS TABLE ([DatabaseName] VARCHAR(100) NULL, [Name] VARCHAR(100) NULL, [StartDate] DATETIME NULL, [EndDate] DATETIME NULL, [TableType] VARCHAR(100) NULL, [TableTagValueDataType] VARCHAR(100) NULL, [IsProcessed] BIT NULL);

		---------- Insert data table list in to variable table ----------
		INSERT INTO @DATATABLE
		SELECT [DatabaseName], [Name], [StartDate], [EndDate], [TableType], [TableTagValueDataType], [IsProcessed] FROM XHS_Datatable_Mst_Tbl WITH (NOLOCK) 
		WHERE [IsSystem] = 0 AND [IsDeleted] = 0 AND [EndDate] >= '' + @StartTime + '' AND  [StartDate] <= '' + @EndTime + ''
		AND ([TableType] = 'BUFFER' OR ([TableType] = 'QUARTERLY' AND [IsProcessed] = 1))
		AND [TableTagValueDataType] != 'ALARM'
		ORDER BY [StartDate]
	END

	BEGIN

	DECLARE @TableAnalogTags NVARCHAR(MAX), @TableStringTags NVARCHAR(MAX), @TableDiscreteTags NVARCHAR(MAX);
	DECLARE @STRANALOGQUERY NVARCHAR(MAX), @STRSTRINGQUERY NVARCHAR(MAX), @STRDISCRETEQUERY NVARCHAR(MAX);
	DECLARE @STRFINALQUERY NVARCHAR(MAX);

	DECLARE @TAGTABLE TABLE(Name VARCHAR(100), TagNo VARCHAR(100),TagType VARCHAR(100), TagID VARCHAR(100), StorageType VARCHAR(100), Unit VARCHAR(100), Description VARCHAR(MAX), DataSource VARCHAR(100), AliasName VARCHAR(100), SR INT);
	INSERT INTO @TAGTABLE SELECT  TAG.Name, TagNo, TagType, TagID, StorageType, U.Name as Unit, TAG.Description, DataSource, AliasName, ROW_NUMBER()OVER(ORDER BY GETDATE()) as SR FROM STRING_SPLIT(@TagName, ',') AS T
	JOIN XHS_Tag_Mst_Tbl AS TAG ON TAG.Name = T.value
	JOIN XHS_Unit_Mst_Tbl U ON TAG.UnitID = U.ID;

	IF EXISTS (select 1 from @TAGTABLE)
	BEGIN
	DECLARE @ANALOGTAGTABLE TABLE(Name VARCHAR(100), TagNo VARCHAR(100), TagType VARCHAR(100));
	INSERT INTO @ANALOGTAGTABLE SELECT Name, TagNo, TagType FROM XHS_Tag_Mst_Tbl WHERE TagType = 'Analog' AND Name IN (select value from  string_split(@TagName, ','));

	DECLARE @STRINGTAGTABLE TABLE(Name VARCHAR(100), TagNo VARCHAR(100), TagType VARCHAR(100));
	INSERT INTO @STRINGTAGTABLE SELECT Name, TagNo, TagType FROM XHS_Tag_Mst_Tbl WHERE TagType = 'String' AND Name IN (select value from  string_split(@TagName, ','));

	DECLARE @DISCRETETAGTABLE TABLE(Name VARCHAR(100), TagNo VARCHAR(100), TagType VARCHAR(100));
	INSERT INTO @DISCRETETAGTABLE SELECT Name, TagNo, TagType FROM XHS_Tag_Mst_Tbl WHERE TagType = 'Discrete' AND Name IN (select value from  string_split(@TagName, ','));
	
	SET @TableAnalogTags = STUFF((SELECT ', ' + t.TagNo + '' FROM @ANALOGTAGTABLE as t FOR XML PATH ('')), 1, 2, '');
	SET @TableStringTags = STUFF((SELECT ', ' + t.TagNo + '' FROM @STRINGTAGTABLE as t FOR XML PATH ('')), 1, 2, '');
	SET @TableDiscreteTags = STUFF((SELECT ', ' + t.TagNo + '' FROM @DISCRETETAGTABLE as t FOR XML PATH ('')), 1, 2, '');

	SELECT @STRANALOGQUERY = STUFF(( SELECT ' UNION ALL '+ 'SELECT AP.[TagID], [CreatedDate], [Quality], CAST([Val] AS VARCHAR(MAX)) AS [Val] FROM [' + DatabaseName + '].[dbo].[' + Name + '] AS AP WITH(NOLOCK) WHERE AP.TagID IN ('+@TableAnalogTags+') AND [Val] IS NOT NULL AND [CreatedDate] BETWEEN CONVERT(DATETIME,'''+@StartTime+''') AND CONVERT(DATETIME,'''+@EndTime+''')' FROM @DATATABLE WHERE TableTagValueDataType = 'ANALOG' ORDER BY Name FOR XML PATH ('')), 1, 10, '');

	SELECT @STRSTRINGQUERY = STUFF(( SELECT ' UNION ALL '+ 'SELECT SP.[TagID], [CreatedDate], [Quality], CAST([Val] AS VARCHAR(MAX)) AS [Val] FROM [' + DatabaseName + '].[dbo].[' + Name + '] AS SP WITH(NOLOCK) WHERE SP.TagID IN ('+@TableStringTags+') AND [Val] IS NOT NULL AND [CreatedDate] BETWEEN CONVERT(DATETIME,'''+@StartTime+''') AND CONVERT(DATETIME,'''+@EndTime+''')' FROM @DATATABLE WHERE TableTagValueDataType = 'STRING' ORDER BY Name FOR XML PATH ('')), 1, 10, '');
		
	SELECT @STRDISCRETEQUERY = STUFF(( SELECT ' UNION ALL '+ 'SELECT DP.[TagID], [CreatedDate], [Quality], CAST([Val] AS VARCHAR(MAX)) AS [Val] FROM [' + DatabaseName + '].[dbo].[' + Name + '] AS DP WITH(NOLOCK) WHERE DP.TagID IN ('+@TableDiscreteTags+') AND [Val] IS NOT NULL AND [CreatedDate] BETWEEN CONVERT(DATETIME,'''+@StartTime+''') AND CONVERT(DATETIME,'''+@EndTime+''')' FROM @DATATABLE WHERE TableTagValueDataType = 'DISCRETE' ORDER BY Name FOR XML PATH ('')), 1, 10, '');

	IF(@Format = 'Narrow')
	BEGIN

		SELECT @STRFINALQUERY= 'SELECT Tag.Name AS [Name], [CreatedDate], [Quality], [Val] FROM ( '+
		CASE WHEN (ISNULL((SELECT COUNT(*) FROM @ANALOGTAGTABLE),0)) <> 0 THEN @STRANALOGQUERY ELSE '' END +
		CASE WHEN (ISNULL((SELECT COUNT(*) FROM @STRINGTAGTABLE),0)) <> 0 THEN 
			CASE WHEN LEN(ISNULL(@STRANALOGQUERY,'')) <> 0 THEN ' UNION ALL ' ELSE '' END + @STRSTRINGQUERY ELSE '' END +
		CASE WHEN (ISNULL((SELECT COUNT(*) FROM @DISCRETETAGTABLE),0))<>0 THEN 
			CASE WHEN LEN(ISNULL(@STRANALOGQUERY,'')) <> 0 THEN ' UNION ALL '
				WHEN LEN(ISNULL(@STRSTRINGQUERY,'')) <> 0 THEN ' UNION ALL ' ELSE '' END + @STRDISCRETEQUERY ELSE '' END +
				' ) AS T 
				LEFT JOIN XHS_Tag_Mst_Tbl AS Tag WITH(NOLOCK) ON Tag.TagNo = T.TagID ORDER BY Name, CreatedDate';
	END
	ELSE
	BEGIN

		DECLARE @TableTags NVARCHAR(MAX), @InTags NVARCHAR(MAX);
		SET @TableTags = STUFF((SELECT ', MAX([' + t.TagNo + ']) AS ['+ (REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(@HeaderFormat, 'AliasName', ISNULL(AliasName,'')), 'Unit', ISNULL(Unit,'')), 
		'Description', ISNULL(Description,'')), 'TagNo', ISNULL(TagNo,'')), 'TagType', ISNULL(TagType,'')), 'TagID', ISNULL(TagID,'')), 'StorageType', ISNULL(StorageType,'')), 'Name', ISNULL(Name,''))) +']' FROM @TAGTABLE as t ORDER BY Sr FOR XML PATH ('')),1,2,'');

		SET @InTags = STUFF((SELECT ',[' + t.TagNo + ']' FROM @TAGTABLE as t FOR XML PATH ('')),1,1,'');
		
		SELECT @STRFINALQUERY= 'SELECT [CreatedDate], ' + @TableTags + ' FROM ( '+
		CASE WHEN (ISNULL((SELECT COUNT(*) FROM @ANALOGTAGTABLE),0)) <> 0 THEN @STRANALOGQUERY ELSE '' END +
		CASE WHEN (ISNULL((SELECT COUNT(*) FROM @STRINGTAGTABLE),0)) <> 0 THEN 
			CASE WHEN LEN(ISNULL(@STRANALOGQUERY,'')) <> 0 THEN ' UNION ALL ' ELSE '' END + @STRSTRINGQUERY ELSE '' END +
		CASE WHEN (ISNULL((SELECT COUNT(*) FROM @DISCRETETAGTABLE),0))<>0 THEN 
			CASE WHEN LEN(ISNULL(@STRANALOGQUERY,'')) <> 0 THEN ' UNION ALL '
				WHEN LEN(ISNULL(@STRSTRINGQUERY,'')) <> 0 THEN ' UNION ALL ' ELSE '' END + @STRDISCRETEQUERY ELSE '' END +
				' )AS T 
				
				PIVOT(
					MAX(Val) FOR TagID IN(' + @InTags + ')
				) AS PVT 
				GROUP BY CreatedDate
				ORDER BY CreatedDate';

	END
		print(@STRFINALQUERY)
		EXEC (@STRFINALQUERY);
	END
	END
END
GO


