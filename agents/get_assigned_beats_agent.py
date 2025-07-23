import sqlite3
import pandas as pd
from langchain_core.runnables import RunnableLambda
from typing import Dict, List, Union



def fetch_assigned_beats(inputs: Dict[str,Union[str, int]], db_path: str = "sales_agent_co_pilot.db") -> List[Dict]:
    """
    Fetches the beats assigned to a specific sales representative.

    Args:
        inputs Dict[str,Union[str, int]]: The ID of the sales representative and working day of the week.
        db_path (str): Path to the SQLite database file.

    Returns:
        A List of dictionaries containing the beats assigned to the sales rep.
    """

    sales_rep_id = inputs.get("sales_rep_id")
    weekday = inputs.get("Weekday", "Monday")  # Default to Monday if not provided

    conn = sqlite3.connect(db_path)

    # Check if sales_rep_id is provided
    if not sales_rep_id:
        conn.close()
        return "Sales Rep ID is required."
    
    # Validate sales_rep_id type
    if not isinstance(sales_rep_id, str):
        conn.close()
        return "Sales Rep ID must be a string."
    

    # Fetch assigned beats for the sales rep
    query = """
        SELECT DISTINCT Beat_ID,Beat_Name
        FROM beats 
        WHERE Assigned_Agent = ?
        AND Beat_day = ?
    """
    beats_df = pd.read_sql_query(query, conn, params=(sales_rep_id, weekday))

    conn.close()

    # Check if any beats were found
    if beats_df.empty:
        return [{"message": f"No beats found for {sales_rep_id} on {weekday}."}]
    
    # Convert DataFrame to a list of dictionaries
    beats_list = beats_df.to_dict(orient='records')[0]

    return beats_list




# Create a runnable function to fetch beats assigned to a sales rep
GetAssignedBeatsAgent = RunnableLambda(fetch_assigned_beats)

