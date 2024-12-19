import os
import logging
import hashlib
import uuid
import psycopg
from fastapi import FastAPI, Request
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
import uvicorn
from apis.routers import api_v1_router
from langchain_postgres import PostgresChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.runnables import RunnableLambda
from langchain.schema import Document
from src.data_extraction.data_opeartions import(
    create_pg_vector_store, 
    fetch_inventory_columns, 
    fetch_product_columns, 
    fetch_page_columns, 
    fetch_inventory)
from src.data_extraction.order_data_operations import order_data_retrieve
from src.query_service import rephrase_query
from datetime import datetime
from core.database.db import get_db
from core.database.database_services import(
    update_product_embedding,
    update_bigcommerce_pages_embedding,
    update_bigcommerce_order_embeddings,
    extensive_inv_data
)
from apscheduler.schedulers.background import BackgroundScheduler

# Get today's date in the desired format
formatted_today = datetime.today().strftime('%Y-%m-%d')
# Load environment variables
PROJECT_NAME = os.getenv("PROJECT_NAME")
API_V1_STR = os.getenv("API_V1_STR")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
BACKEND_CORS_ORIGINS = ["*"]  # Adjust as needed
PG_VECTOR_CONNECTION_STRING = os.getenv("PG_VECTOR_CONNECTION_STRING")
CONNECTION_STRING = os.getenv("CONNECTION_STRING")
# Set up logging
logger = logging.getLogger("main")

# Initialize FastAPI app
app = FastAPI(
    title=PROJECT_NAME,
    openapi_url=f"{API_V1_STR}/openapi.json",
)

# Generate a session ID based on the channel ID
def generate_session_id(channel_id: str) -> str:
    # Hash the channel_id and generate a UUID from it
    hash_object = hashlib.md5(channel_id.encode())
    return str(uuid.UUID(hash_object.hexdigest()[:32]))  # Create UUID from the hash

# Initialize Slack app
slack_app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
handler = SlackRequestHandler(slack_app)

# Establish synchronous connection to PostgreSQL using psycopg2
def get_sync_connection():
    return psycopg.connect(PG_VECTOR_CONNECTION_STRING)

#table_name = "chat_history"
#PostgresChatMessageHistory.create_tables(get_sync_connection(), table_name)

# Middleware for CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and include API router
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(api_v1_router)

# Initialize the scheduler
scheduler = BackgroundScheduler()

"""# Schedule daily jobs for pages and products at a specific time
scheduler.add_job(
    update_bigcommerce_pages_embedding,
    "cron",
    hour=14,  # Set to your desired hour (24-hour format)
    minute= 45,  # Set to your desired minute
    args=[next(get_db())],
    id="update_bigcommerce_pages_embedding",
)"""

"""scheduler.add_job(
    update_product_embedding,
    "cron",
    hour=12,  # Same time daily as pages, adjust if needed
    minute= 57,
    args=[next(get_db())],
    id="update_product_embedding",
)"""

# Schedule jobs to run every 5 minutes for orders and inventory
scheduler.add_job(
    update_bigcommerce_order_embeddings,
    "interval",
    minutes=3,
    args=[next(get_db())],
    id="update_bigcommerce_order_embeddings",
)

scheduler.add_job(
    extensive_inv_data,
    "interval",
    minutes=1,
    args=[next(get_db())],
    id= "extensive_inv_data",
)

# Start the scheduler
scheduler.start()
def fetch_product_from_vector_store(product_id: str):
    # Function to fetch product details directly from the full vector store
    # Adjust this based on your vector store setup to retrieve product data based on the `product_id`
    vectorstore = create_pg_vector_store("pg_vector")  # Use your actual collection name
    retriever = vectorstore.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={"score_threshold": 0.1, "k": 10}  # Adjust threshold and k as needed
    )
    retrieved_docs = retriever.invoke(f"product:{product_id}")
    
    # Assuming the first document returned contains the product data you're looking for
    if retrieved_docs:
        return retrieved_docs[0].page_content
    else:
        return None  # If no product found

def vector_store_retrieve(collection_name: str, query: str, category):
    retrieved_data = []
    
    # Load column data
    inventories = fetch_inventory_columns()
    products = fetch_product_columns()
    pages = fetch_page_columns()
    
    # Convert columns to dictionaries
    inventory_dict = {str(inv_id): inv_json for inv_id, inv_json in inventories}
    product_dict = {str(prod_id): prod_json for prod_id, prod_json in products}
    page_dict = {str(page_id): page_json for page_id, page_json in pages}
    
    # Create vector store and retriever
    vectorstore = create_pg_vector_store(collection_name)
    retriever = vectorstore.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={"score_threshold": 0.5, "k": 30}
    )
    
    # Retrieve documents
    retrieved_docs = retriever.invoke(query)
    print("Retrieved documents:", retrieved_docs)

    for doc in retrieved_docs:
        meta_id = doc.metadata.get("id")
        print(f"Processing document ID: {meta_id}")  # Debugging ID
        
        retrieved_content = None
        
        # Match against dictionaries
        if meta_id in inventory_dict and 'inventory' in query.lower():
            retrieved_content = inventory_dict[meta_id]
        elif meta_id in product_dict and 'product' in category[0].lower():
            retrieved_content = product_dict[meta_id]
        elif meta_id not in product_dict and 'product' in category[0].lower():
            print(f"Attempting fallback retrieval for product ID: {meta_id}")
            retrieved_content = fetch_product_from_vector_store(meta_id)
        elif meta_id in page_dict and 'page' in query.lower():
            retrieved_content = page_dict[meta_id]
        
        # Append retrieved content if found
        if retrieved_content is not None:
            retrieved_data.append(Document(page_content=str(retrieved_content), metadata=doc.metadata))
        else:
            print(f"No matching content found for document ID: {meta_id}")

    return retrieved_data

# Create retriever and chain setup
def create_conversational_chain(query: str, session_id):
    # Rephrase and categorize the user query
    user_query, category = rephrase_query(query, session_id)
    print("Categories:", category)
    if not isinstance(user_query, str):
        user_query = str(user_query)
    
    compl_inv= None
    order_data = None
    ord_data=None
    # Retrieve relevant data based on query category
    if 'order' in category[0] or any(keyword in user_query.lower() for keyword in ["bigcommerce", "costco"]):
        order_data, po_data, is_po = order_data_retrieve(user_query)
        print("order data:", order_data)
        
        if is_po:
            if po_data:
                relevant_data = order_data
                print("relevant_order_data:", relevant_data)
        else:
            ord_data = order_data
    elif 'inventory' in category[0]:
        if any(keyword in user_query.lower() for keyword in ["full","all","complete", "total", "entire","wood", "metal"]):
            if any(keyword in user_query.lower() for keyword in ["total","entire","complete", "all", "full","los angeles","indiana","pennsylvania", "wood", "metal"]):
                # Normalize the query if 'total' is found, replacing it with 'full'
                normalized_query = user_query.lower().replace('total', 'full')
                # Fetch the inventory using the normalized query
                print("normalized query", normalized_query)
                compl_inv = fetch_inventory(normalized_query)
            else:
                # Define `compl_inv` as a list of dictionaries with an appropriate message
                relevant_data = vector_store_retrieve("pg_vector", user_query, category)
        else:
            relevant_data = vector_store_retrieve("pg_vector", user_query, category)  # Retrieve top 3 results
            print("Retriever:", relevant_data) 
    else:
        relevant_data = vector_store_retrieve("pg_vector", user_query, category)  # Retrieve top 3 results
        print("Retriever:", relevant_data)
    
    contextualize_q_system_prompt = """Given a chat history and the latest user question \
        which might reference context in the chat history, formulate a standalone question \
        which can be understood without the chat history. Do NOT answer the question, \
        just reformulate it if needed and otherwise return it as is."""


    # Create the contextualize prompt
    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder("chat_history", n_messages=2),  # Use only the last 3 messages
            ("human", "{input}"),
        ]
    )
    
    retriever_runnable = RunnableLambda(lambda _: relevant_data)
    llm = ChatOpenAI(model="gpt-4", temperature=0.3)

    # History-aware retriever creation
    history_aware_retriever = create_history_aware_retriever(
        llm=llm,
        retriever=retriever_runnable,
        prompt=contextualize_q_prompt,
    )
    
    # Updated QA Prompt
    qa_system_prompt = (
    f"You are an intelligent assistant specializing in ecommerce caskets. Today's date is {formatted_today}."
    "Your task is to respond to user queries with accurate, concise answers based strictly on the provided context."

    "**Strict Guidelines:**"
    "1. Always prioritize the current query and provided context."
    "2. Reference chat history only under these conditions:"
       "- The user explicitly mentions or asks for details from previous interactions."
       "- The query cannot be understood or answered without historical details."
    "3. Provide specific information based on query type:"
       "- **Inventory**: Stock availability, levels, and location."
       "- **Product**: Material, dimensions, and other details."
       "- **Order Tracking**: Statuses like confirmed, shipped, or canceled."
       "- **Order Count**: Numbers of orders within a specified timeframe."

    "Examples:"
    "- What is the stock at Indiana? -> There are 50 units available in Indiana."
    "- What is the status of my last order? -> Refer to history only if explicitly required."

    "Additional Requirements:"
    "- For queries like 'What's my full/complete inventory at a specific location?', provide all inventory data related to the mentioned location that is present in the context."
    "- If unable to understand the user requirement, ask clarifying questions and, if possible, suggest a better-phrased question for future reference."
    "- Separate responses for orders, pages, inventory, and products based on the query type. Do not mix categories in your response."
    "- Provide answers strictly based on the provided context, query, and history. Do not use information outside the context."
    "Strictly adhere to these guidelines to avoid using irrelevant history and ensure accurate, context-based responses."
    "{context}"
)

    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", qa_system_prompt),
            MessagesPlaceholder("chat_history", n_messages=2),  # Include fewer messages from history
            ("human", "{input}"),
        ]
    )
    
    # Create chains
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
    
    return RunnableWithMessageHistory(
        rag_chain,
        get_session_history,  # Updated function for filtered history
        input_messages_key="input",
        history_messages_key="chat_history",
        output_messages_key="answer",
    ), compl_inv, ord_data

# Function to retrieve session history from PostgreSQL
def get_session_history(session_id: str) -> PostgresChatMessageHistory:
    return PostgresChatMessageHistory(
        "chat_history",
        session_id,
        sync_connection=get_sync_connection()
    )

# Slack event handler for mentions
@slack_app.event("app_mention")
def handle_mention(event, say):
    user = event["user"]
    text = event["text"]
    channel_id = event["channel"]

    logger.info(f"App mentioned by user: {user}, with message: {text} in channel: {channel_id}")
    
    # Generate session ID based on Slack channel
    session_id = generate_session_id(channel_id)
    
    # Initialize the conversational RAG chain
    conversational_rag_chain, inv, orders = create_conversational_chain(text, session_id)
    
    if inv:
        with get_sync_connection() as connection:
            chat_history = get_session_history(session_id)
            
            user_message = HumanMessage(content=text)
            chat_history.add_messages([user_message])
            
            # Assuming `inv` is the list of inventory items
            total_qty_available = sum(
            int(item['qty_available']) if isinstance(item['qty_available'], (int, float)) else 0
            for item in inv
            )


            # Create the response with the static text, bullet points, and total quantity
            response = (
                "Here is the list of inventory:\n\n"  # Static text
                + "\n".join([f"• {item['sku']} - Warehouse: {item['warehouse']} - Qty Available: {item['qty_available']}" for item in inv])
                + f"\n\nTotal Quantity Available: {total_qty_available}"  # Total quantity at the end
                )

            ai_message = AIMessage(content=response)
            chat_history.add_messages([ai_message])

            # Send the AI response back to Slack
            say(response)
            
    elif orders:
        with get_sync_connection() as connection:
            chat_history = get_session_history(session_id)
            
            user_message = HumanMessage(content=text)
            chat_history.add_messages([user_message])
            
            # Create the response with the static text, bullet points, and total quantity
            response = (
                        "Here is the list of orders:\n\n"  # Static text
                        + "\n\n".join(
                    [
                            f"• {item['Status']} - Order count: {item['Order count']} - Date: {item['Date']}\n"
                        + (
                        "\n".join([f"{cust_ref}" for cust_ref in item['Cust_Refs']])
                        if item['Cust_Refs'] != ["No orders found for the given status and date."]
                        else "   No orders found for the given status and date."
                        )
                        for item in orders
                    ]
                )
            )

            ai_message = AIMessage(content=response)
            chat_history.add_messages([ai_message])

            # Send the AI response back to Slack
            say(response)
            
    else:        
        # Run the conversational chain with input and retrieve the answer
        with get_sync_connection() as connection:
            # Initialize chat history in PostgreSQL
            chat_history = get_session_history(session_id)
            
            # Add the user's message to chat history
            #user_message = HumanMessage(content=text)
            #chat_history.add_messages([user_message])

            # Prepare the input payload
            input_payload = {"input": text, "chat_history": chat_history.get_messages(), "formatted_today": formatted_today}
            
            # Generate the response using the chain
            # Call the conversational RAG chain with session_id in the configuration
            response = conversational_rag_chain.invoke(
            input_payload,
            {"configurable": {"session_id": session_id}})["answer"]

            print("response:", response)
            logger.info(f"Generated response: {response}")
            
            # Add AI response to chat history
            #ai_message = AIMessage(content=response)
            #chat_history.add_messages([ai_message])

            # Send the AI response back to Slack
            say(response)

# Slack event handler for messages
@slack_app.event("message")
def handle_message_events(event, say):
    # Ignore bot messages to avoid loops
    if event.get("subtype") == "bot_message":
        return

    # Log the received message event for debugging purposes
    logger.info(f"Received message event: {event}")

# FastAPI endpoint for Slack events
@app.post("/slack/events")
async def slack_events(req: Request):
    return await handler.handle(req)

# Start the FastAPI app with Uvicorn
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
