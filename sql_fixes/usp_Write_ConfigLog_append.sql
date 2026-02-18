CREATE PROC dbo.usp_Write_ConfigLog  
  @Rows dbo.TVP_ConfigLog READONLY  
AS  
BEGIN  
  SET NOCOUNT ON;  

  INSERT INTO dbo.ConfigLog (
      RunID, EquipID, EntryDateTime, ConfigHash, ConfigJSON, Active
  )  
  SELECT
      RunID, EquipID, EntryDateTime, ConfigHash, ConfigJSON, Active  
  FROM @Rows;  
END
