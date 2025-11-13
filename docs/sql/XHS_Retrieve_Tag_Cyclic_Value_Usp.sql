USE [XStudio_Historian]
GO

/****** Object:  StoredProcedure [dbo].[XHS_Retrieve_Tag_Cyclic_Value_Usp]    Script Date: 28-10-2025 12:52:33 ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

-- =============================================
-- Author:		Divya Dakoria
-- Create date: 20-Dec-2022
-- Description:	Used to retrieve cyclic tag value
-- Intervals: 10 Second, 30 Second, 1 Minute, 5 Minute, 10 Minute, 15 Minute,30 Minute, 1 Hour, 1 Day, 1 Month, 1 Year
-- =============================================
CREATE OR ALTER   PROCEDURE [dbo].[XHS_Retrieve_Tag_Cyclic_Value_Usp] -- [XHS_Retrieve_Tag_Cyclic_Value_Usp] '','','','',,'',''
	@StartTime	VARCHAR(25)		= '2025-AUG-07 14:00:00',
	@EndTime	VARCHAR(25)		= '2025-Aug-07 14:01:00',
	@TagName	VARCHAR(MAX)	= 'MT00001,MT00002,MT00020,MT00019,MT00015,MT00008,MT00010,MT00012,MT00006,MT00004',
	@Frequency	VARCHAR(20)		=  'MILLISECOND', -- 'Second', 'Minute', 'Hour', 'Day', 'Month', 'Year',
	@Interval	INT				= 100,
	@Format		VARCHAR(100)	= 'Narrow', -- 'Narrow', 'Wide' 
	@HeaderFormat VARCHAR(200)	= 'Name' -- Name, Unit, Description, TagNo, TagType, TagID, StorageType, AliasName, Agg
AS
BEGIN
	SET NOCOUNT ON;

	DECLARE @TimeInterval AS VARCHAR(MAX) = 0,@Addwhere NVarchar(max)='';
	
	---------- Set date format and convert intreval to second ----------
	BEGIN
		IF @Frequency = 'MILLISECOND'
		BEGIN
			SET @StartTime = CAST(FORMAT(CAST(@StartTime AS datetime), 'yyyy-MMM-dd HH:mm:ss.fff') AS datetime);
			SET @TimeInterval = @Interval;
		END
		IF @Frequency = 'Second'
		BEGIN
			SET @StartTime = CAST(FORMAT(CAST(@StartTime AS datetime), 'yyyy-MMM-dd HH:mm:ss') AS datetime);
			SET @TimeInterval = @Interval;
		END
		ELSE IF @Frequency = 'Minute'
		BEGIN
			SET @StartTime = CAST(DATEADD(MINUTE, ROUND(DATEDIFF(MINUTE, 0,  CAST(''+@StartTime+'' as VARCHAR(25))) / CAST(@Interval AS VARCHAR), 0) * CAST(@Interval AS VARCHAR), 0) AS DATETIME)
			SET @TimeInterval = @Interval * 60;
		END
		ELSE IF @Frequency = 'Hour'
		BEGIN
			SET @StartTime = CAST(FORMAT(CAST(@StartTime As datetime), 'yyyy-MMM-dd HH:00:00') AS datetime);
			SET @TimeInterval = @Interval * 3600;
		END
		ELSE IF @Frequency = 'Day'
		BEGIN
			SET @StartTime = CAST(FORMAT(CAST(@StartTime As datetime), 'yyyy-MMM-dd') AS datetime);
			SET @TimeInterval = @Interval * 86400;
		END
		ELSE IF @Frequency = 'Month'
		BEGIN
			SET @StartTime = CAST(FORMAT(CAST(@StartTime As datetime), 'yyyy-MMM') AS datetime);
			SET @TimeInterval = @Interval * 2592000;
		END
		ELSE IF @Frequency = 'Year'
		BEGIN
			SET @StartTime = CAST(FORMAT(CAST(@StartTime As datetime), 'yyyy') AS datetime);
			SET @TimeInterval = @Interval * 31536000;
		END
	END
	
	---- ADD Where condition ----
	IF(@Frequency ='Minute' AND @Interval =1)
	BEGIN
		SET @Addwhere =' AND Is01Mint=1'
	END
	ELSE IF(@Frequency ='Minute' AND @Interval =5)
	BEGIN
		SET @Addwhere =' AND Is05Mints=1'
	END
	ELSE IF(@Frequency ='Minute' AND @Interval =10)
	BEGIN
		SET @Addwhere =' AND Is10Mints=1'
	END
	ELSE IF(@Frequency ='Minute' AND @Interval =15)
	BEGIN
		SET @Addwhere =' AND Is15Mints=1'
	END
	ELSE IF(@Frequency ='Minute' AND @Interval =30)
	BEGIN
		SET @Addwhere =' AND Is30Mints=1'
	END
	ELSE IF(@Frequency ='Hour' AND @Interval =1)
	BEGIN
		SET @Addwhere =' AND Is01Hour=1'
	END
	ELSE IF(@Frequency ='Day' AND @Interval =1)
	BEGIN
		SET @Addwhere =' AND Is01Day=1'
	END
	ELSE IF(@Frequency ='Week' AND @Interval =1)
	BEGIN
		SET @Addwhere =' AND Is01week=1'
	END
	ELSE IF(@Frequency ='Month' AND @Interval =1)
	BEGIN
		SET @Addwhere =' AND Is01Month=1'
	END

	---------- Prepare datatable list ----------
	BEGIN
		---------- Load data table list between start-date and end-date for full retrieval ----------
		DECLARE @DATATABLE AS TABLE ([DatabaseName] VARCHAR(100) NULL, [Name] VARCHAR(100) NULL, [StartDate] DATETIME NULL, [EndDate] DATETIME NULL, [TableType] VARCHAR(100) NULL, [TableTagValueDataType] VARCHAR(100) NULL, [IsProcessed] BIT NULL);

		---------- Insert data table list in to variable table ----------
		INSERT INTO @DATATABLE
		SELECT [DatabaseName], [Name], [StartDate], [EndDate], [TableType], [TableTagValueDataType], [IsProcessed] FROM XHS_Datatable_Mst_Tbl WITH (NOLOCK) 
		WHERE [IsSystem] = 0 AND [IsDeleted] = 0 AND [EndDate] >= '' + @StartTime + '' AND  [StartDate] <= '' + @EndTime + '' 
		AND ([TableType] = 'BUFFER' OR [TableType] = 'QUARTERLY')
		AND [TableTagValueDataType] != 'ALARM'
		ORDER BY [StartDate]
		
	END
   
	---------- Prepare cyclic datetime range table ----------
	BEGIN
		DECLARE @strDateTable AS VARCHAR(MAX);
        
		SET @strDateTable = '
		DECLARE @Date AS TABLE([Date] [Datetime] NULL, [NextDate] [Datetime] NULL);
		
		DECLARE @StartDateTime DATETIME = CAST(''' + @StartTime + ''' AS DATETIME);
		DECLARE @EndDateTime DATETIME = CAST(''' + @EndTime + ''' AS DATETIME);

		WITH DateRanges AS (
			SELECT 
				@StartDateTime AS StartDate,
				' + CASE WHEN @Frequency = 'MILLISECOND' THEN 'DATEADD(MILLISECOND, ' + @TimeInterval + ', @StartDateTime) ' ELSE '1DATEADD(SECOND, ' + @TimeInterval + ', @StartDateTime) ' END + ' AS EndDate
			UNION ALL
			SELECT 
				EndDate AS StartDate,
				' + CASE WHEN @Frequency = 'MILLISECOND' THEN 'DATEADD(MILLISECOND, ' + @TimeInterval + ', EndDate) ' ELSE 'DATEADD(SECOND, ' + @TimeInterval + ', EndDate) ' END + ' AS EndDate
			FROM DateRanges
			WHERE EndDate < @EndDateTime
		)

		INSERT INTO @Date ([Date], [NextDate])
		SELECT StartDate, EndDate
		FROM DateRanges WHERE EndDate < @EndDateTime
		OPTION (MAXRECURSION 0);';
   END

	DECLARE @STRFINALQUERY NVARCHAR(MAX);
	DECLARE @STRANALOGQUERY NVARCHAR(MAX);
	DECLARE @STRSTRINGQUERY NVARCHAR(MAX);
	DECLARE @STRDISCRETEQUERY NVARCHAR(MAX);

	DECLARE @TAGTABLE TABLE(Name VARCHAR(100), TagNo VARCHAR(100),TagType VARCHAR(100), TagID VARCHAR(100), StorageType VARCHAR(100), Unit VARCHAR(100), Description VARCHAR(MAX), DataSource VARCHAR(100), AliasName VARCHAR(100), SR INT);
	INSERT INTO @TAGTABLE SELECT  TAG.Name, TagNo, TagType, TagID, StorageType, U.Name as Unit, TAG.Description, DataSource, AliasName, ROW_NUMBER()OVER(ORDER BY GETDATE()) as SR FROM STRING_SPLIT(@TagName, ',') AS T
	JOIN XHS_Tag_Mst_Tbl AS TAG ON TAG.Name = T.value
	JOIN XHS_Unit_Mst_Tbl U ON TAG.UnitID = U.ID;

	DECLARE @ANALOGTAGTABLE TABLE(Name VARCHAR(100), TagNo VARCHAR(100), TagType VARCHAR(100));
	INSERT INTO @ANALOGTAGTABLE SELECT Name, TagNo, TagType FROM XHS_Tag_Mst_Tbl WHERE TagType = 'Analog' AND Name IN (select value from  string_split(@TagName, ','));

	DECLARE @STRINGTAGTABLE TABLE(Name VARCHAR(100), TagNo VARCHAR(100), TagType VARCHAR(100));
	INSERT INTO @STRINGTAGTABLE SELECT Name, TagNo, TagType FROM XHS_Tag_Mst_Tbl WHERE TagType = 'String' AND Name IN (select value from  string_split(@TagName, ','));

	DECLARE @DISCRETETAGTABLE TABLE(Name VARCHAR(100), TagNo VARCHAR(100), TagType VARCHAR(100));
	INSERT INTO @DISCRETETAGTABLE SELECT Name, TagNo, TagType FROM XHS_Tag_Mst_Tbl WHERE TagType = 'Discrete' AND Name IN (select value from  string_split(@TagName, ','));

	DECLARE @TableAnalogTags NVARCHAR(MAX), @TableStringTags NVARCHAR(MAX), @TableDiscreteTags NVARCHAR(MAX);
	
	---------- Prepare and select tag cyclic data as in wide or narrow form ----------
	BEGIN
	
		DECLARE @STRFINALANALOGQUERY NVARCHAR(MAX), @STRFINALSTRINGQUERY NVARCHAR(MAX), @STRFINALDISCRETEQUERY NVARCHAR(MAX);

		SET @TableAnalogTags = STUFF((SELECT ', ' + t.TagNo + '' FROM @ANALOGTAGTABLE as t FOR XML PATH ('')), 1, 2, '');
		SET @TableStringTags = STUFF((SELECT ', ' + t.TagNo + '' FROM @STRINGTAGTABLE as t FOR XML PATH ('')), 1, 2, '');
		SET @TableDiscreteTags = STUFF((SELECT ', ' + t.TagNo + '' FROM @DISCRETETAGTABLE as t FOR XML PATH ('')), 1, 2, '');
		
		SELECT @STRANALOGQUERY = STUFF(( SELECT ' UNION ALL '+ 'SELECT [TagID], [CreatedDate], [Quality], [Val] FROM [' + DatabaseName + '].[dbo].[' + Name + '] WITH(NOLOCK) WHERE TagID IN ('+@TableAnalogTags+') AND [Val] IS NOT NULL AND [CreatedDate] BETWEEN CONVERT(DATETIME,'''+@StartTime+''') AND CONVERT(DATETIME,'''+@EndTime+''') '+@Addwhere+'' FROM @DATATABLE WHERE TableTagValueDataType = 'ANALOG'  ORDER BY Name FOR XML PATH ('')), 1, 10, '');

		SELECT @STRSTRINGQUERY = STUFF(( SELECT ' UNION ALL '+ 'SELECT [TagID], [CreatedDate], [Quality], CAST([Val] AS VARCHAR(MAX)) AS [Val] FROM [' + DatabaseName + '].[dbo].[' + Name + '] WITH(NOLOCK) WHERE TagID IN ('+@TableStringTags+') AND [Val] IS NOT NULL AND [CreatedDate] BETWEEN CONVERT(DATETIME,'''+@StartTime+''') AND CONVERT(DATETIME,'''+@EndTime+''') '+@Addwhere+'' FROM @DATATABLE WHERE TableTagValueDataType = 'STRING' ORDER BY Name FOR XML PATH ('')), 1, 10, '');
		
		SELECT @STRDISCRETEQUERY = STUFF(( SELECT ' UNION ALL '+ 'SELECT [TagID], [CreatedDate], [Quality], CAST([Val] AS TINYINT) AS [Val] FROM [' + DatabaseName + '].[dbo].[' + Name + '] WITH(NOLOCK) WHERE TagID IN ('+@TableDiscreteTags+') AND [Val] IS NOT NULL AND [CreatedDate] BETWEEN CONVERT(DATETIME,'''+@StartTime+''') AND CONVERT(DATETIME,'''+@EndTime+''') '+@Addwhere+'' FROM @DATATABLE WHERE TableTagValueDataType = 'DISCRETE' ORDER BY Name FOR XML PATH ('')), 1, 10, '');

		SET @STRFINALANALOGQUERY = 'SELECT [Name], Dates.[NextDate] AS Timestamps,
        CAST(LAST_VALUE([Val]) OVER(PARTITION BY Dates.[NextDate],[Name] ORDER BY [CreatedDate]) AS VARCHAR(MAX)) AS [VAL],
		CAST(LAST_VALUE([Quality]) OVER(PARTITION BY Dates.[NextDate],[Name] ORDER BY [CreatedDate]) AS VARCHAR(MAX))  AS [Quality]
		FROM ('+@STRANALOGQUERY+') AS XData
		RIGHT JOIN (SELECT Date,[Name],TagNO,NextDate FROM @Date CROSS APPLY XHS_Tag_Mst_Tbl where Tagno IN ('+@TableAnalogTags+')) AS Dates
		ON (XData.[CreatedDate] > Dates.[Date] AND XData.[CreatedDate] <= Dates.[NextDate]) AND Dates.TagNo = XData.TagID ';

		SET @STRFINALSTRINGQUERY = 'SELECT [Name], Dates.[NextDate] AS Timestamps, 
        CAST(LAST_VALUE([Val]) OVER(PARTITION BY Dates.[NextDate],[Name] ORDER BY [CreatedDate]) AS VARCHAR(MAX)) AS [VAL],
		CAST(LAST_VALUE([Quality]) OVER(PARTITION BY Dates.[NextDate],[Name] ORDER BY [CreatedDate]) AS VARCHAR(MAX)) AS [Quality]
		FROM ('+@STRSTRINGQUERY+') AS XData
		RIGHT JOIN (SELECT Date,[Name],TagNO,NextDate FROM @Date CROSS APPLY XHS_Tag_Mst_Tbl where Tagno IN ('+@TableStringTags+')) AS Dates
		ON (XData.[CreatedDate] BETWEEN Dates.[Date] AND Dates.[NextDate]) AND Dates.TagNo = XData.TagID ';

		SET @STRFINALDISCRETEQUERY = 'SELECT [Name], Dates.[NextDate] AS Timestamps,
        CAST(LAST_VALUE([Val]) OVER(PARTITION BY Dates.[NextDate],[Name] ORDER BY [CreatedDate]) AS VARCHAR(MAX)) AS [VAL],
		CAST(LAST_VALUE([Quality]) OVER(PARTITION BY Dates.[NextDate],[Name] ORDER BY [CreatedDate]) AS VARCHAR(MAX)) AS [Quality]
		FROM ('+@STRDISCRETEQUERY+') AS XData
		RIGHT JOIN (SELECT Date,[Name],TagNO,NextDate FROM @Date CROSS APPLY XHS_Tag_Mst_Tbl where Tagno IN ('+@TableDiscreteTags+')) AS Dates
		ON (XData.[CreatedDate] BETWEEN Dates.[Date] AND Dates.[NextDate]) AND Dates.TagNo = XData.TagID ';


	IF(@Format = 'Narrow')
	BEGIN
		SELECT @STRFINALQUERY= ' SELECT [Name], [Timestamps], LAST_VALUE([VAL]) IGNORE NULLS OVER (ORDER BY [Timestamps] ) AS [VAL],LAST_VALUE([Quality]) IGNORE NULLS OVER (ORDER BY [Timestamps] )  AS  [Quality]  FROM ( '+
		CASE WHEN (ISNULL((SELECT COUNT(*) FROM @ANALOGTAGTABLE),0)) <> 0 THEN @STRFINALANALOGQUERY ELSE '' END +
		CASE WHEN (ISNULL((SELECT COUNT(*) FROM @STRINGTAGTABLE),0)) <> 0 THEN 
			CASE WHEN LEN(ISNULL(@STRFINALANALOGQUERY,'')) <> 0 THEN ' UNION ALL ' ELSE '' END + @STRFINALSTRINGQUERY ELSE '' END +
		CASE WHEN (ISNULL((SELECT COUNT(*) FROM @DISCRETETAGTABLE),0))<>0 THEN 
			CASE WHEN LEN(ISNULL(@STRFINALANALOGQUERY,'')) <> 0 THEN ' UNION ALL '
				WHEN LEN(ISNULL(@STRFINALSTRINGQUERY,'')) <> 0 THEN ' UNION ALL ' ELSE '' END + @STRFINALDISCRETEQUERY ELSE '' END +
				') AS T ORDER BY [Name],[Timestamps]';
		--print(@strDateTable +'  '+@STRFINALQUERY)
		EXEC (@strDateTable +'  '+@STRFINALQUERY);
	END
	ELSE
	BEGIN 

		DECLARE @FinalTagList VARCHAR(MAX), @InTagList VARCHAR(MAX);

		SELECT	@FinalTagList = STUFF((SELECT  ', MAX(['+Name+']) AS [' + (REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(@HeaderFormat, 'AliasName', ISNULL(AliasName,'')), 'Unit', ISNULL(Unit,'')), 
		'Description', ISNULL(Description,'')), 'TagNo', ISNULL(TagNo,'')), 'TagType', ISNULL(TagType,'')), 'TagID', ISNULL(TagID,'')), 'StorageType', ISNULL(StorageType,'')), 'Name', ISNULL(Name,''))) + ']' FROM @TAGTABLE ORDER BY SR FOR XML PATH ('')),1,1,'');

		SELECT	@InTagList = STUFF((SELECT  ',['+Name+']' FROM @TAGTABLE ORDER BY SR FOR XML PATH ('')),1,1,'');

		SELECT @STRFINALQUERY= ' SELECT Timestamps, ' + @FinalTagList + ' FROM(
		SELECT [Name], [Timestamps],LAST_VALUE([VAL]) IGNORE NULLS OVER (ORDER BY [Timestamps] ) AS [VAL],LAST_VALUE([Quality]) IGNORE NULLS OVER (ORDER BY [Timestamps] )  AS  [Quality] FROM ( '+
		CASE WHEN (ISNULL((SELECT COUNT(*) FROM @ANALOGTAGTABLE),0)) <> 0 THEN @STRFINALANALOGQUERY ELSE '' END +
		CASE WHEN (ISNULL((SELECT COUNT(*) FROM @STRINGTAGTABLE),0)) <> 0 THEN 
			CASE WHEN LEN(ISNULL(@STRFINALANALOGQUERY,'')) <> 0 THEN ' UNION ALL ' ELSE '' END + @STRFINALSTRINGQUERY ELSE '' END +
		CASE WHEN (ISNULL((SELECT COUNT(*) FROM @DISCRETETAGTABLE),0))<>0 THEN 
			CASE WHEN LEN(ISNULL(@STRFINALANALOGQUERY,'')) <> 0 THEN ' UNION ALL '
				WHEN LEN(ISNULL(@STRFINALSTRINGQUERY,'')) <> 0 THEN ' UNION ALL ' ELSE '' END + @STRFINALDISCRETEQUERY ELSE '' END +
		') AS T
		)AS T1
		Pivot(
			MAX(Val) FOR Name IN ('+@InTagList+')
		) AS pvt
		GROUP BY [Timestamps]
		ORDER BY [Timestamps]';
		--print(@strDateTable +'  '+@STRFINALQUERY)
		EXEC (@strDateTable +'  '+@STRFINALQUERY);
	END
	END
END
GO


