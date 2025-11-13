# core/historian.py
# === ACM V8 SQL Edition ===
# Purpose: Python wrapper for XStudio_Historian stored procedures
# Provides high-level interface to query time-series tag data from historian
#
# Available SPs in XStudio_Historian:
# 1. XHS_Retrieve_Tag_Cyclic_Value_Usp  - Retrieve tag values at regular intervals (resampled)
# 2. XHS_Retrieve_Tag_Full_Value_Usp    - Retrieve ALL tag values (raw historian data)
# 3. XHS_Get_Tag_Cyclic_Value_Usp       - Calculate cyclic values (flat or interpolated)
# 4. XHS_Get_Tag_Full_Value_Usp         - Load full values for single tag
# 5. XHS_Get_Tag_Delta_Value_Usp        - Calculate delta-based compression (% change filter)
# 6. XHS_Tag_Count_Value_Usp            - Count tag values with conditions
# 7. XHS_Tag_Last_Value_Usp             - Get last value for tags

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Literal
import pandas as pd

from core.sql_client import SQLClient


class HistorianClient:
    """
    High-level interface to XStudio_Historian database.
    
    Wraps stored procedures for retrieving time-series tag data.
    Primary methods for ACM integration:
    - retrieve_cyclic_tags(): Get resampled tag data at regular intervals
    - retrieve_full_tags(): Get raw historian data (all recorded values)
    
    Usage:
        historian = HistorianClient()
        df = historian.retrieve_cyclic_tags(
            tag_names=['MT00001', 'MT00002', 'MT00015'],
            start_time='2025-08-07 08:00:00',
            end_time='2025-08-07 14:00:00',
            interval=60,
            frequency='Second'
        )
    """
    
    def __init__(self, sql_client: Optional[SQLClient] = None):
        """
        Initialize historian client.
        
        Args:
            sql_client: Pre-configured SQLClient for XStudio_Historian DB.
                       If None, creates new client from INI [xstudio_historian] section.
        """
        if sql_client is None:
            self.client = SQLClient.from_ini('xstudio_historian')
        else:
            self.client = sql_client
        
        # Ensure connection is established
        self.client.connect()
    
    def retrieve_cyclic_tags(
        self,
        tag_names: List[str],
        start_time: str | datetime,
        end_time: str | datetime,
        interval: int = 60,
        frequency: Literal['MILLISECOND', 'Second', 'Minute', 'Hour', 'Day', 'Month', 'Year'] = 'Second',
        format: Literal['Narrow', 'Wide'] = 'Wide',
        header_format: str = 'Name'
    ) -> pd.DataFrame:
        """
        Retrieve tag values at regular intervals (resampled/cyclic).
        
        Uses XHS_Retrieve_Tag_Cyclic_Value_Usp stored procedure.
        This is the PRIMARY method for ACM integration - provides clean, evenly-spaced
        time-series data suitable for anomaly detection algorithms.
        
        Args:
            tag_names: List of tag names to retrieve (e.g., ['MT00001', 'MT00002'])
            start_time: Start datetime (string 'YYYY-MMM-DD HH:MM:SS' or datetime object)
            end_time: End datetime (string or datetime)
            interval: Time interval size (e.g., 60 for 60 seconds, 5 for 5 minutes)
            frequency: Time unit - 'MILLISECOND', 'Second', 'Minute', 'Hour', 'Day', 'Month', 'Year'
            format: 'Narrow' (long format) or 'Wide' (pivot table, one column per tag)
            header_format: Column naming - 'Name', 'Unit', 'Description', 'TagNo', etc.
        
        Returns:
            DataFrame with columns:
                - Wide format: [Timestamps, Tag1, Tag2, Tag3, ...]
                - Narrow format: [Name, Timestamps, VAL, Quality]
        
        Example:
            # Get 1-minute resampled data for 3 tags over 6 hours
            df = historian.retrieve_cyclic_tags(
                tag_names=['MT00001', 'MT00002', 'MT00015'],
                start_time='2025-08-07 08:00:00',
                end_time='2025-08-07 14:00:00',
                interval=1,
                frequency='Minute',
                format='Wide'
            )
            # Result: DataFrame with timestamp index and 3 columns (one per tag)
        """
        # Convert tag list to comma-separated string
        tag_str = ','.join(tag_names)
        
        # Format datetimes
        if isinstance(start_time, datetime):
            start_time = start_time.strftime('%Y-%b-%d %H:%M:%S')
        if isinstance(end_time, datetime):
            end_time = end_time.strftime('%Y-%b-%d %H:%M:%S')
        
        # Build and execute stored procedure call
        cursor = self.client.cursor()
        try:
            # Call stored procedure with parameters
            sql = """
            EXEC [dbo].[XHS_Retrieve_Tag_Cyclic_Value_Usp]
                @StartTime = ?,
                @EndTime = ?,
                @TagName = ?,
                @Frequency = ?,
                @Interval = ?,
                @Format = ?,
                @HeaderFormat = ?
            """
            cursor.execute(sql, (start_time, end_time, tag_str, frequency, interval, format, header_format))
            
            # Fetch results into DataFrame
            rows = cursor.fetchall()
            if not rows:
                # Return empty DataFrame with expected columns
                if format == 'Wide':
                    return pd.DataFrame(columns=['Timestamps'] + tag_names)
                else:
                    return pd.DataFrame(columns=['Name', 'Timestamps', 'VAL', 'Quality'])
            
            # Convert to DataFrame
            columns = [desc[0] for desc in cursor.description]
            df = pd.DataFrame.from_records(rows, columns=columns)
            
            # Convert Timestamps column to datetime if present
            if 'Timestamps' in df.columns:
                df['Timestamps'] = pd.to_datetime(df['Timestamps'])
            elif 'CreatedDate' in df.columns:
                df['CreatedDate'] = pd.to_datetime(df['CreatedDate'])
            
            return df
        finally:
            cursor.close()
    
    def retrieve_full_tags(
        self,
        tag_names: List[str],
        start_time: str | datetime,
        end_time: str | datetime,
        format: Literal['Narrow', 'Wide'] = 'Wide',
        header_format: str = 'Name'
    ) -> pd.DataFrame:
        """
        Retrieve ALL raw tag values from historian (no resampling).
        
        Uses XHS_Retrieve_Tag_Full_Value_Usp stored procedure.
        Returns every recorded value in the time range - can be very large datasets.
        
        Args:
            tag_names: List of tag names to retrieve
            start_time: Start datetime (string or datetime)
            end_time: End datetime (string or datetime)
            format: 'Narrow' (long) or 'Wide' (pivot)
            header_format: Column naming format
        
        Returns:
            DataFrame with all raw historian values
                - Wide format: [CreatedDate, Tag1, Tag2, ...]
                - Narrow format: [Name, CreatedDate, Quality, Val]
        
        Note:
            Use retrieve_cyclic_tags() for ACM processing - it provides
            cleaner, resampled data. Use this method only for:
            - Raw data inspection
            - High-frequency event detection
            - Data quality analysis
        """
        tag_str = ','.join(tag_names)
        
        if isinstance(start_time, datetime):
            start_time = start_time.strftime('%Y-%b-%d %H:%M:%S')
        if isinstance(end_time, datetime):
            end_time = end_time.strftime('%Y-%b-%d %H:%M:%S')
        
        cursor = self.client.cursor()
        try:
            sql = """
            EXEC [dbo].[XHS_Retrieve_Tag_Full_Value_Usp]
                @StartTime = ?,
                @EndTime = ?,
                @TagName = ?,
                @Format = ?,
                @HeaderFormat = ?
            """
            cursor.execute(sql, (start_time, end_time, tag_str, format, header_format))
            
            rows = cursor.fetchall()
            if not rows:
                if format == 'Wide':
                    return pd.DataFrame(columns=['CreatedDate'] + tag_names)
                else:
                    return pd.DataFrame(columns=['Name', 'CreatedDate', 'Quality', 'Val'])
            
            columns = [desc[0] for desc in cursor.description]
            df = pd.DataFrame.from_records(rows, columns=columns)
            
            # Convert timestamp columns
            if 'CreatedDate' in df.columns:
                df['CreatedDate'] = pd.to_datetime(df['CreatedDate'])
            if 'Timestamps' in df.columns:
                df['Timestamps'] = pd.to_datetime(df['Timestamps'])
            
            return df
        finally:
            cursor.close()
    
    def get_tag_last_value(
        self,
        tag_ids: List[int],
        start_time: str | datetime,
        end_time: str | datetime,
        condition_id: str
    ) -> pd.DataFrame:
        """
        Get last recorded value for each tag in time range.
        
        Uses XHS_Tag_Last_Value_Usp.
        Requires temp table #Tag_condition with (ID, TAGID, Condition) columns.
        
        Args:
            tag_ids: List of tag IDs (integers, not names)
            start_time: Start datetime
            end_time: End datetime
            condition_id: Condition ID for filtering (varchar(36))
        
        Returns:
            DataFrame with [TagID, Last] columns
        """
        if isinstance(start_time, datetime):
            start_time = start_time.strftime('%Y-%m-%d %H:%M:%S.%f')
        if isinstance(end_time, datetime):
            end_time = end_time.strftime('%Y-%m-%d %H:%M:%S.%f')
        
        cursor = self.client.cursor()
        try:
            # Create temp table (required by SP)
            cursor.execute("""
                CREATE TABLE #Tag_condition (
                    ID VARCHAR(36),
                    TAGID INT,
                    Condition VARCHAR(500)
                )
            """)
            
            # Insert tag IDs
            for tag_id in tag_ids:
                cursor.execute(
                    "INSERT INTO #Tag_condition (ID, TAGID) VALUES (?, ?)",
                    (condition_id, tag_id)
                )
            
            # Call stored procedure
            cursor.execute(
                "EXEC [dbo].[XHS_Tag_Last_Value_Usp] @STARTDATE = ?, @ENDDATE = ?, @ID = ?",
                (start_time, end_time, condition_id)
            )
            
            rows = cursor.fetchall()
            if not rows:
                return pd.DataFrame(columns=['TagID', 'Last'])
            
            columns = [desc[0] for desc in cursor.description]
            df = pd.DataFrame.from_records(rows, columns=columns)
            return df
        finally:
            cursor.close()
    
    def close(self):
        """Close the historian database connection."""
        if self.client:
            self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ============================================================
# Utility functions for ACM integration
# ============================================================

def fetch_equipment_tags_for_acm(
    equipment_code: str,
    start_time: datetime,
    end_time: datetime,
    tag_mappings: Dict[str, str],
    resample_interval: int = 60,
    resample_freq: str = 'Second'
) -> pd.DataFrame:
    """
    Fetch historian data for one equipment instance, formatted for ACM pipeline.
    
    This is the MAIN ENTRY POINT for ACM's SQL mode data acquisition.
    
    Args:
        equipment_code: Equipment identifier (e.g., 'FD_FAN_001')
        start_time: Data start time
        end_time: Data end time
        tag_mappings: Dict mapping signal names to historian tag names
                     e.g., {'flow': 'MT00001', 'pressure': 'MT00002'}
        resample_interval: Resampling interval (default: 60)
        resample_freq: Resampling frequency unit (default: 'Second')
    
    Returns:
        DataFrame ready for ACM processing:
        - Columns: ['timestamp', 'flow', 'pressure', 'temperature', ...]
        - Index: DatetimeIndex
        - Clean, evenly-spaced time-series data
    
    Example:
        # Get tag mappings from XStudio_DOW (equipment discovery)
        tag_map = {'flow': 'MT00001', 'pressure': 'MT00002', 'temp': 'MT00015'}
        
        # Fetch historian data
        df = fetch_equipment_tags_for_acm(
            equipment_code='FD_FAN_001',
            start_time=datetime(2025, 8, 7, 8, 0),
            end_time=datetime(2025, 8, 7, 14, 0),
            tag_mappings=tag_map,
            resample_interval=1,
            resample_freq='Minute'
        )
        
        # df is now ready for ACM pipeline
        # core.acm_main.run_acm_pipeline(df, equipment_code, ...)
    """
    with HistorianClient() as historian:
        # Get list of historian tag names
        tag_names = list(tag_mappings.values())
        
        # Retrieve cyclic (resampled) data
        df_hist = historian.retrieve_cyclic_tags(
            tag_names=tag_names,
            start_time=start_time,
            end_time=end_time,
            interval=resample_interval,
            frequency=resample_freq,
            format='Wide',
            header_format='Name'
        )
        
        if df_hist.empty:
            raise ValueError(f"No historian data found for {equipment_code} in time range {start_time} to {end_time}")
        
        # Rename columns from historian tag names to signal names
        reverse_map = {v: k for k, v in tag_mappings.items()}  # tag_name -> signal_name
        df_hist.rename(columns=reverse_map, inplace=True)
        
        # Rename 'Timestamps' to 'timestamp' (ACM convention)
        if 'Timestamps' in df_hist.columns:
            df_hist.rename(columns={'Timestamps': 'timestamp'}, inplace=True)
        
        # Set timestamp as index
        if 'timestamp' in df_hist.columns:
            df_hist.set_index('timestamp', inplace=True)
        
        # Ensure numeric dtypes for all signal columns
        for col in df_hist.columns:
            if col != 'timestamp':
                df_hist[col] = pd.to_numeric(df_hist[col], errors='coerce')
        
        return df_hist
