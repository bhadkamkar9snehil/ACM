IF (SELECT COUNT(DISTINCT RunID) FROM @Rows) > 1
BEGIN
    THROW 50092, 'Multiple RunIDs detected in TVP_ConfigLog', 1;
END
