USE [XStudio_Historian]
GO

/****** Object:  StoredProcedure [dbo].[XHS_Get_Tag_Full_Value_Usp]    Script Date: 28-10-2025 12:48:07 ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO


-- =============================================
-- Author:			Paras Patel
-- Create date:		2022-04-28
-- Description:		Load full/all value of selected tag beetween given time range.
-- =============================================

CREATE OR ALTER   PROCEDURE [dbo].[XHS_Get_Tag_Full_Value_Usp]
	@TableName	VARCHAR(MAX)	= '[XHS_History_22053131].[dbo].[XHS_Analog_Quaterly_22_5_31_18_TO_22_5_31_21]', 
	@TagId		VARCHAR(8)		= '501', 
	@StartDate	VARCHAR(25)		= '2022-04-08 00:00:00.000', 
	@EndDate	VARCHAR(25)		= '2022-04-08 03:00:00.000'
	WITH RECOMPILE
AS
BEGIN

	SET NOCOUNT ON;

	Declare @strTempxDataTable as VARCHAR(Max);

	Set @strTempxDataTable = '
	DECLARE @xData AS TABLE ([TagID] [int] NULL, [CreatedDate] [datetime] NULL INDEX clstTagid CLUSTERED, [Quality] [int] NULL, [Val] varchar(200) NULL);

	INSERT INTO @xData SELECT XData.TagID, XData.CreatedDate, XData.Quality, XData.Val FROM ' + @TableName +' XData WHERE XData.TagID = ' + @TagId + '' 

	Declare @strSelectStatement as varchar(Max) 
	Set @strSelectStatement = ' SELECT * FROM @xData WHERE [CreatedDate] BETWEEN ''' + @StartDate + ''' AND ''' + @EndDate + ''' Order By [CreatedDate] Desc'

	EXEC (@strTempxDataTable + @strSelectStatement)
END
GO


