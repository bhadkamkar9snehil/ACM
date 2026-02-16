
import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# Add parent directory to path to import core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SQLClient
from core.config import Config

def debug_regime_query():
    print("Initializing SQL Client...")
    sql_client = SQLClient()
    
    # Parameters from the failure log
    equip_id = 5073
    # Approximate entries from the 1885h window mention in logs
    # Log: Data anchor: 2022-09-09 17:30:00, window cutoff: 2022-06-11 17:30:00
    start_ts = pd.to_datetime("2022-06-11 17:30:00")
    end_ts = pd.to_datetime("2022-09-09 17:30:00")
    
    query = """
        SELECT Timestamp, RegimeLabel
        FROM ACM_RegimeTimeline
        WHERE EquipID = ? AND Timestamp BETWEEN ? AND ?
        ORDER BY Timestamp ASC
    """
    
    print(f"Executing query for EquipID={equip_id} from {start_ts} to {end_ts}")
    
    try:
        with sql_client.get_cursor() as cur:
            cur.execute(query, (equip_id, start_ts, end_ts))
            rows = cur.fetchall()
            
        print(f"Query returned {len(rows)} rows.")
        
        if not rows:
            print("No rows returned.")
            return

        print(f"First row type: {type(rows[0])}")
        print(f"First row content: {rows[0]}")
        print(f"First row length: {len(rows[0])}")
        
        # Check if rows are Row objects or tuples
        if hasattr(rows[0], 'cursor_description'):
             print(f"Row description: {rows[0].cursor_description}")

        # Try to reproduce the pandas failure
        print("\nAttempting to create DataFrame...")
        try:
            df = pd.DataFrame(rows, columns=['Timestamp', 'RegimeLabel'])
            print(f"DataFrame created successfully within shape: {df.shape}")
            print(df.head())
        except Exception as e:
            print(f"DataFrame creation FAILED: {e}")
            # Analyze deeper
            sample = rows[:5]
            print(f"Sample data: {sample}")

    except Exception as e:
        print(f"SQL Execution failed: {e}")

if __name__ == "__main__":
    debug_regime_query()
