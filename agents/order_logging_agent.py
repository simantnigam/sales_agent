import sqlite3
from datetime import datetime
from typing import Any, Dict, List
from utils.set_state import SalesRepState
import uuid

class OrderLoggingAgent:
    """
    Captures order details and writes them into:
    - sales
    - visits
    - visit_stock
    """

    def __init__(self,db_path: str = "sales_agent_co_pilot.db"):
        self.db_path = db_path
        

    def log_order(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Logs the order details into the database.

        Args:
        visit_id: Unique Visit ID
        retailer_id: Store Retailer ID
        agent_id: Sales Rep ID
        products: List of dicts → [{Product_ID, Quantity, Available_Stock, Price}]
        feedback: Optional feedback string

        Returns:
            A success or failure message.
        """

        products = state.get("order_products", [])
        feedback = state.get("feedback", "")
        visit_id = state.get("visit_id", str(uuid.uuid4()))
        retailer_id = state.get("Retailer_ID")
        agent_id = state.get("sales_rep_id")
        invoice_id = f"INV_{visit_id}"

        if not products:
            state["order_log"] = "No products to log."
            return state
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            date_today = datetime.now().strftime("%Y-%m-%d")

            

            # Insert into visits
            cursor.execute("""
                INSERT INTO visits (Visit_ID, Retailer_ID, Date, Products_Suggested, Feedback, Order_Placed, Agent_ID)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                visit_id,
                retailer_id,
                date_today,
                ", ".join([p["Product_ID"] for p in products]),
                feedback if feedback else "",
                1 if products else 0,
                agent_id
            ))

            

            # Insert into visit_stock + sales
            for prod in products:
                product_id = prod["Product_ID"]
                qty = prod["Quantity"]
                stock = prod["Available_Stock"]
                price = prod.get("Price", 0.0)
                total_amount = qty * price

                # visit_stock
                cursor.execute("""
                    INSERT INTO visit_stock (Visit_ID, Product_ID, Retailer_ID, Available_Stock)
                    VALUES (?, ?, ?, ?)
                """, (visit_id, product_id, retailer_id, stock))

                # sales
                cursor.execute("""
                    INSERT INTO sales (Invoice_ID, Visit_ID, Retailer_ID, Product_ID, Quantity, Date, Total_Amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    invoice_id,
                    visit_id,
                    retailer_id,
                    product_id,
                    qty,
                    date_today,
                    total_amount
                ))

            conn.commit()
            log_msg = f"Order logged for Visit ID: {visit_id}, Invoice ID: {invoice_id}"
            state["order_log"] = log_msg
            visited = state.get("visited_retailers", [])
            if retailer_id not in visited:
                visited.append(retailer_id)
            state["visited_retailers"] = visited
            return state

        except sqlite3.Error as e:
            state["order_log"] =  f"An error occurred: {e}"
            return state

        finally:
            if conn:
                conn.close()

# LangChain Runnable
from langchain_core.runnables import Runnable

class OrderLoggingRunnable(Runnable):
    def __init__(self, agent: "OrderLoggingAgent"):
        super().__init__()
        self.agent = agent

    def invoke(self, state: Dict[str, Any], config: Dict = None) -> Dict[str, Any]:
        """Runs the order logging agent inside a LangChain Runnable interface"""
        return self.agent.log_order(state)
