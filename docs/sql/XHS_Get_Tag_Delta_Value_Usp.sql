USE [XStudio_Historian]
GO

/****** Object:  StoredProcedure [dbo].[XHS_Get_Tag_Delta_Value_Usp]    Script Date: 28-10-2025 12:51:21 ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO


-- =============================================
-- Author:			Paras Patel
-- Create date:		2022-04-28
-- Description:		Calculate delta value of selected tag beetween given time range.
-- =============================================

CREATE OR ALTER   PROCEDURE [dbo].[XHS_Get_Tag_Delta_Value_Usp] 
	@TableName    VARCHAR(MAX)	= '[XHS_History_22040808].[dbo].[XHS_Analog_Quaterly_22_4_8_00_TO_22_4_8_03]', 
	@TagId        VARCHAR(8)	= '2', 
	@StartDate    VARCHAR(25)	= '2022-04-08 00:00:00.000', 
	@EndDate      VARCHAR(25)	= '2022-04-08 03:00:00.000', 
	@PerVal		  FLOAT			= 1
	WITH RECOMPILE
AS
    BEGIN
        SET NOCOUNT ON;
        DECLARE @dtSourceCount AS INT= 0;
        DECLARE @CurrentCount AS INT= 1;
        DECLARE @CurrentValue FLOAT;
        DECLARE @CurrentQuality SMALLINT;
        DECLARE @CurrentTime DATETIME;
        DECLARE @NextValue FLOAT;
        DECLARE @NextQuality SMALLINT;
        DECLARE @NextTime DATETIME;
        DECLARE @Diff FLOAT;
        DBCC FREESYSTEMCACHE('ALL');
        DBCC FREESESSIONCACHE;
        DBCC FREEPROCCACHE;

        CREATE TABLE #dtSource
        (
			[RowNum] [INT] NOT NULL IDENTITY(1, 1), 
			[TagID] [INT] NULL INDEX clst CLUSTERED, 
			[Val] [FLOAT] NULL, 
			[CreatedDate] [DATETIME] NULL, 
			[Quality] [INT] NULL, 
			[DiffVal] [FLOAT] NULL, 
			[RFlag] [BIT] DEFAULT 0 UNIQUE NONCLUSTERED ([RowNum], TagID, [Val], [CreatedDate], [Quality])
        );

        EXEC ('INSERT INTO #dtSource (TagId, Val, CreatedDate, Quality)   
		SELECT XDATA.TagId, XDATA.Val, XDATA.CreatedDate, XDATA.Quality FROM '+@TableName+' XDATA 
		WHERE XDATA.CreatedDate >= '''+@StartDate+''' AND XDATA.CreatedDate <= '''+@EndDate+'''');

        SET @dtSourceCount = (SELECT COUNT(*) FROM #dtSource WHERE TagID = @TagId);
        IF @dtSourceCount >= 0
		BEGIN

            SELECT @CurrentValue = Val, @CurrentTime = CreatedDate, @CurrentQuality = Quality FROM #dtSource WHERE RowNum = @CurrentCount;
            UPDATE #dtSource SET RFlag = 1 WHERE RowNum = @CurrentCount;  

            SET @CurrentCount = @CurrentCount + 1;
            WHILE @CurrentCount <= @dtSourceCount
                BEGIN  
                    BEGIN TRY
                        SELECT @NextValue = Val, @NextTime = CreatedDate, @NextQuality = Quality FROM #dtSource
                        WHERE RowNum = @CurrentCount;
                        IF @NextValue IS NULL
						BEGIN
							UPDATE #dtSource SET RFlag = 1 WHERE RowNum = @CurrentCount;
                        END;
                        ELSE
                        BEGIN
                            SET @Diff = ABS(100 * ABS((@CurrentValue - @NextValue))) / ISNULL(NULLIF(@CurrentValue, 0), 1);
                            IF @Diff >= @PerVal 
							BEGIN  
								UPDATE #dtSource SET RFlag = 1 WHERE RowNum = @CurrentCount;  
								SET @CurrentValue = @NextValue;
								SET @CurrentTime = @NextTime;
								SET @CurrentQuality = @NextQuality;
                            END;
                        END;
                        SET @CurrentCount = @CurrentCount + 1;
					END TRY
                    BEGIN CATCH
                        PRINT 'SOMETHING MISS IN EXECUTION : Diff:' + CONVERT(VARCHAR, ISNULL(@Diff, 0.0)) + ' , Current Value : ' + CONVERT(VARCHAR, @CurrentValue) + ' , Next Value : ' + CONVERT(VARCHAR, @NextValue);
				END CATCH;
			END; 

			SELECT * FROM #dtSource WHERE RFlag = 1 AND TagID = @TagId;  
        END;
    END;
GO
