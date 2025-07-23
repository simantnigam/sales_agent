import sqlite3
import pandas as pd
from typing import Dict, Union, List
from langchain_core.runnables import RunnableLambda


def fetch_retailer_info(inputs: Dict[str, Union[str, int]], db_path: str = "sales_agent_co_pilot.db") -> Dict:
    """
    Fetches information about a specific retailer.

    Args:
        inputs (Dict[str, Union[str, int]]): The ID of the retailer.
        db_path (str): Path to the SQLite database file.

    Returns:
        A dictionary containing the retailer's information.
    """

    retailer_id = inputs.get("Retailer_ID")

    conn = sqlite3.connect(db_path)

    # Fetch retailer information for the given retailer ID
    retailer_query = """
            SELECT Retailer_ID, Name, City, Channel, Latitude, Longitude
            FROM retailers
            WHERE Retailer_ID = ?
        """
    
    retailer_df = pd.read_sql_query(retailer_query, conn, params=(retailer_id,))
    if retailer_df.empty:
        conn.close()
        return {"message": f"No retailer found with ID {retailer_id}"}
    

    # Get latest visit_id for this retailer
    visit_query = """
        SELECT Visit_ID
        FROM visits
        WHERE Retailer_ID = ?
        ORDER BY Date DESC
        LIMIT 1
    """
    latest_visit = pd.read_sql_query(visit_query, conn, params=(retailer_id,))
    
    if not latest_visit.empty:
        visit_id = latest_visit["Visit_ID"].iloc[0]

        # Fetch stock for the latest visit
        stock_query = """
            SELECT v.Date as Visit_date,vs.Product_ID, p.Product_Name,p.Pack_size,p.Category, vs.Available_Stock
            FROM visits v
            JOIN visit_stock vs ON v.Visit_ID = vs.Visit_ID
            JOIN products p ON vs.Product_ID = p.Product_ID
            WHERE vs.Visit_ID = ?
        """
        stock_df = pd.read_sql_query(stock_query, conn, params=(visit_id,))
        stock_data = stock_df.to_dict(orient="records")
    else:
        stock_data = []


    # Get product recommendations
    rec_query = """
        SELECT prm.Product_ID, p.Product_Name, round(prm.Final_Score,2) Score
        FROM product_recommendations_ml prm
        JOIN products p ON prm.Product_ID = p.Product_ID
        WHERE prm.Retailer_ID = ?
        ORDER BY prm.Final_Score DESC
    """
    rec_df = pd.read_sql_query(rec_query, conn, params=(retailer_id,))
    rec_data = rec_df.to_dict(orient="records")

    conn.close()
    
    

    retailer_info = {
        "Retailer_Info": retailer_df.to_dict(orient="records")[0],
        "Product_Recommendations": rec_data,
        "Last_Visit_Stock": stock_data
    }

    return retailer_info


# Create a runnable function to fetch retailer information
GetRetailerInfoAgent = RunnableLambda(fetch_retailer_info)