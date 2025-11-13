USE [XStudio_Historian]
GO

/****** Object:  StoredProcedure [dbo].[XHS_Get_Tag_Cyclic_Value_Usp]    Script Date: 28-10-2025 12:50:58 ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO


-- =============================================
-- Author:			Paras Patel
-- Create date:		2022-04-28
-- Description:		Calculate cyclic value of selected tag beetween given time range.
-- =============================================

CREATE OR ALTER     PROCEDURE [dbo].[XHS_Get_Tag_Cyclic_Value_Usp]   
	@TableName    VARCHAR(MAX)	= '[XHS_History_25080707].[dbo].[XHS_Analog_Quaterly_25_8_7_06_TO_25_8_7_09]', 
	@TagId        VARCHAR(MAX)	= '1, 2, 4, 6, 10, 12, 19, 20', 
	@StartDate    VARCHAR(25)	= '2025-Aug-07 08:00:00', 
	@EndDate      VARCHAR(25)	= '2022-Aug-08 08:00:00', 
	@TimeInterval VARCHAR(10)	= '900', -- Second
	@RetriealMode VARCHAR(25)	= 'Flat' -- Flat or Interpolate
	WITH RECOMPILE
AS
    BEGIN  

        SET NOCOUNT ON;

        DECLARE @ValueField VARCHAR(500);

        SET @ValueField = CASE 
							WHEN @RetriealMode = 'FLAT' THEN ' XData.Val '
							ELSE ' XData.Val + (DATEDIFF_BIG(MILLISECOND, Dates.date, XData.CreatedDate)) * ((XData.NextValue - XData.Val) / (DATEDIFF_BIG(MILLISECOND,XData.NextDate, XData.CreatedDate))) AS [Val] '
                          END;

        DECLARE @strDateTable AS VARCHAR(MAX);

        SET @strDateTable = '
		DECLARE @Date AS TABLE([Date] [Datetime] NULL, [NextDate] [Datetime] NULL);
		
		DECLARE @StartDateTime DATETIME = CAST(''' + @StartDate + ''' AS DATETIME);
		DECLARE @EndDateTime DATETIME = CAST(''' + @EndDate + ''' AS DATETIME);

		WITH DateRanges AS (
			SELECT 
				@StartDateTime AS StartDate,
				DATEADD(SECOND, ' + @TimeInterval + ', @StartDateTime) AS EndDate
			UNION ALL
			SELECT 
				EndDate AS StartDate,
				DATEADD(SECOND, ' + @TimeInterval + ', EndDate) AS EndDate
			FROM DateRanges
			WHERE EndDate < @EndDateTime
		)

		INSERT INTO @Date ([Date], [NextDate])
		SELECT StartDate, EndDate
		FROM DateRanges WHERE EndDate < @EndDateTime
		OPTION (MAXRECURSION 0);';

        DECLARE @strTempxDataTable AS VARCHAR(MAX);

        SET @strTempxDataTable = '
		DECLARE @xData AS TABLE ([TagID] [int] NULL, [CreatedDate] [datetime] NULL, [Quality] [int] NULL, [Val] [float] NULL, [NextValue] [float] null, [NextDate] [datetime] NULL);

		INSERT INTO @xData 
		SELECT XData.TagID, XData.CreatedDate, XData.Quality, XData.Val, 
		LEAD(XData.Val) OVER (ORDER BY XData.TagID,XData.CreatedDate) NextValue,
		LEAD(XData.CreatedDate) OVER (Partition By XData.TagID  ORDER BY XData.CreatedDate) NextDate
		FROM ' + @TableName + ' XData WHERE XData.TagID IN (' + @TagId + ')';

        DECLARE @strFinalQuery AS VARCHAR(MAX);

        SET @strFinalQuery = '  
		SELECT DISTINCT XData.[TagID], Dates.[Date] AS [CreatedDate], ' + @ValueField + ', XData.[Quality], TC.Comments AS [Comment] FROM @xData XData  
		INNER JOIN @Date AS Dates ON (Dates.[Date] BETWEEN XData.[CreatedDate] And XData.[NextDate]) 
		LEFT JOIN XHS_Tag_Comment_Mst_Tbl TC ON TC.TagID = XData.TagID AND TC.Timestamps = Dates.Date';-- or (XData.CreatedDate Between Dates.Date and Dates.NextDate and  XData.Val is null)'  


        --PRINT @strDateTable;
        --PRINT '****';
        --PRINT @strTempxDataTable;
        --PRINT '****';
        --PRINT @strFinalQuery;
        EXEC (@strDateTable+'  '+@strTempxDataTable+'  '+@strFinalQuery);
    END;
GO


