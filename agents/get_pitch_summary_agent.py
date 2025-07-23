import os
from dotenv import load_dotenv
from typing import Dict,Any
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableLambda, RunnableMap

load_dotenv(override=True)

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")


# Create LLM instance
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

#Build prompt
def build_prompt(input_data: Dict[str, Any]) -> str:
    retailer = input_data.get('Retailer_Info')
    recommendations = input_data.get("Product_Recommendations")
    stock = input_data.get("Last_Visit_Stock")

    # Format product recommendations
    rec_lines = "\n".join(
        [f"- {item['Product_Name']} (Score: {item['Score']})"
         for item in recommendations]
    ) or "None"

    # Format last stock
    stock_lines = "\n".join(
        [f"- {item.get('Product_Name')} (Available stock: {item.get('Available_Stock')} units, Visit Date: {item.get('Visit_date')})"
         for item in stock]
    ) or "No stock data available."

    prompt = f"""
        You are a smart field sales assistant from India. Prepare a product pitch script for the upcoming visit.
        Dont include scores in the pitch.

        Retailer Details:
        - Name: {retailer['Name']}
        - Location: {retailer['City']} ({retailer['Channel']} channel)

        Last Visit Stock:
        {stock_lines}

        Recommended Products to Push:
        {rec_lines}

        Use this data to generate a persuasive but friendly pitch for the sales rep to use during the visit.
        Make sure the pitch is not too long, dont exceed 500 words
    """
    return prompt.strip()


#Pitch Summary Function
def generate_sales_pitch(inputs : Dict[str,Any]) -> Dict[str,Any]:
    prompt = build_prompt(input_data= inputs)
    response = llm.invoke(prompt)
    sales_pitch = {
        "Retailer_ID" : inputs.get('Retailer_Info').get("Retailer_ID"),
        "Pitch" : response.content
    }

    return sales_pitch


# LangChain Runnable
PitchSummarizationAgent = RunnableLambda(generate_sales_pitch)

