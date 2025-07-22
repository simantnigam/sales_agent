import sqlite3
import pandas as pd


def get_active_agents():
    db_path = "sales_agent_co_pilot.db"
    conn = sqlite3.connect(db_path)

    query = """
        SELECT Agent_ID, Name 
        FROM sales_agents
    """
    agents_df = pd.read_sql_query(query, conn)
    
    conn.close()
    
    if agents_df.empty:
        return "No active agents found."
    
    return agents_df