USE [XStudio_Historian]
GO

/****** Object:  StoredProcedure [dbo].[XHS_Tag_Count_Value_Usp]    Script Date: 28-10-2025 12:56:03 ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO


-- =============================================
-- Author:			Vikesh Ramani
-- Create date:		2023-Feb-03
-- Description:		Calculate Count of selected tags.
-- =============================================

CREATE OR ALTER   PROCEDURE [dbo].[XHS_Tag_Count_Value_Usp] 
	@STARTDATE DATETIME   , 
	@ENDDATE   DATETIME   , 
	@ID		VARCHAR(36)
AS
    BEGIN

        SET NOCOUNT ON;
		SET ANSI_WARNINGS OFF;

       DECLARE @Condition TABLE ([TAGID] INT,[Condition] varchar(500));

		insert into @Condition([TAGID],[Condition])
		SELECT [TAGID],[Condition] FROM #Tag_condition WHERE [ID]=@ID;

		DECLARE @TableType VARCHAR(100) = 'ANALOG';

		DECLARE @STR NVARCHAR(MAX),@STR1 NVARCHAR(MAX);

		DECLARE @Where Nvarchar(MAX);

		BEGIN TRY

		IF ((SELECT COUNT(TAGID) FROM @Condition)=(SELECT COUNT(DISTINCT TAGID) FROM @Condition))
			BEGIN
				SET @Where= STUFF(( select ' OR '+ CONCAT( '( TagID = ', Convert(varchar,TAGID) ,case when Condition is not null then +' AND '+ Condition +' )'else ')' end) from @Condition FOR XML PATH ('')),1,3,'');
			
				
				SELECT 
				@STR=STUFF(( SELECT N' UNION ALL '+ N'SELECT [TagID], [CreatedDate], [Val] FROM ['+DatabaseName+'].[dbo].['+Name+'] WHERE ( @Where ) AND [Val] IS NOT NULL AND [CreatedDate] BETWEEN CONVERT(DATETIME,@STARTDATE) AND CONVERT(DATETIME,@ENDDATE)'
				FROM (
					SELECT dt.Name, dt.DatabaseName, dt.TableType FROM XHS_Datatable_Mst_Tbl dt
					INNER JOIN XHS_Database_Mst_Tbl db ON db.Name = dt.DatabaseName
					WHERE (dt.IsDeleted = 0 AND dt.IsSystem = 0 AND dt.TableTagValueDataType = @TableType AND dt.TableType = 'BUFFER' AND dt.EndDate	>= @STARTDATE AND dt.StartDate <= @ENDDATE)
					OR ( dt.IsDeleted = 0 AND dt.IsSystem = 0 AND dt.TableTagValueDataType = @TableType AND TableType = 'QUARTERLY' AND dt.EndDate >=	@STARTDATE AND dt.StartDate <= @ENDDATE)
				) AS TBL ORDER BY [Name] FOR XML PATH ('')),1,10,'');

				set @STR=REPLACE(@STR,'@where',@Where);
				set @STR=REPLACE(REPLACE(@STR,'&lt;','<'),'&gt;','>');

				SELECT @STR1=N'SELECT [TagID],
								CAST(COUNT([val]) AS VARCHAR(MAX)) AS [COUNT] 
							FROM  ('+@STR+') AS Result
							GROUP BY [TagID] ORDER BY [TagID]';
				
				EXECUTE SP_EXECUTESQL @STR1,N'@STARTDATE DATETIME,@ENDDATE DATETIME',@STARTDATE=@STARTDATE,@ENDDATE=@ENDDATE;
			END
		

		END TRY
		BEGIN CATCH
			
			DECLARE @ERROR_MSG VARCHAR(MAX)='SP : XHS_Tag_Count_Value_Usp | Line No :'+CONVERT(VARCHAR(100),ERROR_LINE())+' | Message :'+ ERROR_MESSAGE()
		END CATCH

    END;
GO


