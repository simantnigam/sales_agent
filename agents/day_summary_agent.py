import os
import sqlite3
from datetime import datetime
from typing import Dict, List,Any
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from utils.get_day import get_current_day

load_dotenv(override=True)

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")


class DaySummaryAgent:
    """
    Generates a summary of the day's activities for the sales representative.
    """

    def __init__(self, db_path: str = "sales_agent_co_pilot.db"):
        self.db_path = db_path
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)


    def fetch_metrics(self, agent_id: str, date: str) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # date_today = datetime.now().strftime("%Y-%m-%d")
        current_day = get_current_day()

        # Total planned visits from beat plan
        cursor.execute("""
            select count(*) - 1
            FROM beat_route_plan a
            join beats b
            ON a.Beat_ID = b.Beat_ID
            WHERE b.Assigned_Agent = ? 
            AND b.Beat_day = ?
        """, (agent_id, current_day))
        total_planned_visits = cursor.fetchone()[0]

        # Total actual visits
        cursor.execute("""
            SELECT count(distinct Retailer_ID)
            FROM visits
            WHERE Agent_ID = ? AND DATE(Date) = DATE(?)
        """, (agent_id, date))
        total_actual_visits = cursor.fetchone()[0]

        # Total sales & revenue
        cursor.execute("""
            SELECT COUNT(DISTINCT Invoice_ID), SUM(Total_Amount) 
            FROM sales
            WHERE Retailer_ID IN (
                SELECT Retailer_ID FROM visits 
                WHERE Agent_ID = ? AND DATE(Date) = DATE(?)
            )
            AND DATE(Date) = DATE(?)
        """, (agent_id, date, date))
        total_orders, total_revenue = cursor.fetchone()

        # Top products
        cursor.execute("""
            SELECT p.Product_Name, SUM(s.Quantity) as qty
            FROM sales s
            JOIN products p ON s.Product_ID = p.Product_ID
            JOIN visits v ON s.Visit_ID = v.Visit_ID
            WHERE v.Agent_ID = ? AND DATE(s.Date) = DATE(?)
            GROUP BY p.Product_Name
            ORDER BY qty DESC LIMIT 3
        """, (agent_id, date))
        top_products = cursor.fetchall()

        return {
            "total_planned_visits": total_planned_visits or 0,
            "total_actual_visits": total_actual_visits or 0,
            "total_orders": total_orders or 0,
            "total_revenue": total_revenue or 0.0,
            "top_products": [f"{p[0]} ({p[1]})" for p in top_products]
        }

    def summarize_day(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a summary based on the current state.

        Returns:
            A string summary of the day's activities.
        """

        agent_id = state["sales_rep_id"]
        date = datetime.now().strftime("%Y-%m-%d")

        metrics = self.fetch_metrics(agent_id, date)
        
        # Structured summary
        structured_summary = (
            f"Sales Rep {agent_id} summary for {date}:\n"
            f"- Planned visits: {metrics['total_planned_visits']}\n"
            f"- Actual visits: {metrics['total_actual_visits']}\n"
            f"- Total orders: {metrics['total_orders']}\n"
            f"- Total revenue: ₹{metrics['total_revenue']:.2f}\n"
            f"- Top products: {', '.join(metrics['top_products']) if metrics['top_products'] else 'None'}\n"
        )

        # LLM-enhanced summary
        prompt = f"""
        Here are the structured sales metrics for a sales rep's daily activity:

        {structured_summary}

        Write a clear, professional, and motivating summary for the sales rep.
        Highlight visit adherence (planned vs. actual), sales performance, and suggest one area of improvement.
        """
        llm_summary = self.llm.invoke(prompt).content

        state["Day_Summary"] = llm_summary
        state["conversation_end"] = True 

        return state
    


from langchain_core.runnables import Runnable

class DaySummaryRunnable(Runnable):
    def __init__(self, agent: "DaySummaryAgent"):
        super().__init__()
        self.agent = agent

    def invoke(self, state: Dict[str, Any], config: Dict = None) -> Dict[str, Any]:
        """Runs the day summary agent inside a LangChain Runnable interface"""
        return self.agent.summarize_day(state)