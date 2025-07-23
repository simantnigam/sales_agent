import sqlite3
import pandas as pd
from typing import Dict, Union, List
from langchain_core.runnables import RunnableLambda


def fetch_beat_route_plan(inputs: Dict[str, Union[str, int]], db_path: str = "sales_agent_co_pilot.db") -> List[dict]:
    """
    Fetches the beat route plan for a specific beat ID.

    Args:
        inputs (Dict[str, Union[str, int]]): The ID of the beat.
        db_path (str): Path to the SQLite database file.

    Returns:
        A List of dictionaries containing the beat route plan.
    """

    beat_id = inputs.get("Beat_ID")

    conn = sqlite3.connect(db_path)


    # Fetch beat route plan for the given beat ID
    query = """
            SELECT brp.Retailer_ID, r.Name, r.City,r.Channel,r.Latitude, r.Longitude,brp.Visit_Sequence
            FROM beat_route_plan brp
            JOIN retailers r ON brp.Retailer_ID = r.Retailer_ID
            WHERE brp.Beat_ID = ?
            ORDER BY brp.Visit_Sequence ASC
        """
    
    route_plan_df = pd.read_sql_query(query, conn, params=(beat_id,))
    
    conn.close()

    # Check if any route plan was found
    if route_plan_df.empty:
        return [{"message": f"No route plan found for Beat ID {beat_id}."}]
    
    # Convert DataFrame to a list of dictionaries
    route_plan_list = route_plan_df.to_dict(orient='records')
    route_plan_dict = {
        "Beat_Route_Plan" : route_plan_list
    }

    return route_plan_dict


# Create a runnable function to fetch beat route plan
GetBeatRoutePlanAgent = RunnableLambda(fetch_beat_route_plan)