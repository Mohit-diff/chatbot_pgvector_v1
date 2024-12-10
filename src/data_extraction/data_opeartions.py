import re
import json
import psycopg
from langchain.schema import Document
from langchain_community.vectorstores import PGVector
from langchain_openai import OpenAIEmbeddings
import psycopg2
from langchain_community.utilities import SQLDatabase
from langchain.chains import create_sql_query_chain
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from urllib.parse import quote_plus
from dotenv import load_dotenv
import os
load_dotenv()

# Database connection string
CONNECTION_STRING = os.getenv("CONNECTION_STRING")

#Vector Store using PGVector
def create_pg_vector_store(collection_name: str):
    return PGVector(
        embedding_function=OpenAIEmbeddings(),
        collection_name=collection_name,
        connection_string=CONNECTION_STRING,
        use_jsonb=True
    )
# Function to fetch only 'id' and 'inventory' columns from Inventory table
def fetch_inventory_columns():
    # Establish a connection using the connection string
    with psycopg.connect(CONNECTION_STRING) as conn:
        # Open a cursor to perform database operations
        with conn.cursor() as cur:
            # Define the query to select only the 'id' and 'inventory' columns
            query = "SELECT id, inventory_json FROM inv_new;"
            
            # Execute the query
            cur.execute(query)
            
            # Fetch all rows with the selected columns
            results = cur.fetchall()
    return results

def fetch_product_columns():
    # Establish a connection using the connection string
    with psycopg.connect(CONNECTION_STRING) as conn:
        # Open a cursor to perform database operations
        with conn.cursor() as cur:
            # Define the query to select only the 'id' and 'inventory' columns
            query = "SELECT id, product_json FROM products;"
            
            # Execute the query
            cur.execute(query)
            
            # Fetch all rows with the selected columns
            results = cur.fetchall()
    return results

# Function to fetch only 'id' and 'inventory' columns from pages table
def fetch_page_columns():
    # Establish a connection using the connection string
    with psycopg.connect(CONNECTION_STRING) as conn:
        # Open a cursor to perform database operations
        with conn.cursor() as cur:
            # Define the query to select only the 'id' and 'inventory' columns
            query = "SELECT id, page_json FROM pages;"
            
            # Execute the query
            cur.execute(query)
            
            # Fetch all rows with the selected columns
            results = cur.fetchall()
    return results

# Function to fetch only 'po_no', 'order_status', and 'order_json' columns from the Orders table
def fetch_order_columns():
    with psycopg.connect(CONNECTION_STRING) as conn:
        with conn.cursor() as cur:
            query = "SELECT po_no, order_status, order_json FROM orders;"
            cur.execute(query)
            results = cur.fetchall()
    return results

# Function to extract order numbers from the user query
def extract_order_numbers(query):
    pattern = r'\b\d+\b'  # Regex to match numeric order numbers
    matches = re.findall(pattern, query)
    return matches if matches else []

# Function to retrieve order data based on the user's query
def order_data_retrieve(query):
    # Check if the query is about quantity
    """if any(keyword in query.lower() for keyword in ["latest","many", "much", "how many", "how much", "count"]):"""
    return order_data(query)

    """retrieved_data = []
    orders = fetch_order_columns()

    # Create dictionaries for quick lookup
    status_data = {}  # order_status -> list of order_json
    po_data = {}      # po_no -> order_json

    for order in orders:
        po_no, order_status, order_json = order

        # Populate status_data with lists of orders for each status
        if order_status in status_data:
            status_data[order_status].append(order_json)
        else:
            status_data[order_status] = [order_json]

        # Populate po_data with order JSONs indexed by po_no
        po_data[po_no] = order_json

    # Extract order numbers from the query
    order_numbers = extract_order_numbers(query)

    # Define order statuses to check in the query
    order_statuses = ['confirmed', 'shipped', 'new', 'canceled', 'at_wms']
    mentioned_status = None

    # Detect if any valid status is mentioned in the query
    for status in order_statuses:
        if status in query.lower():
            mentioned_status = status
            break

    # If a specific status is mentioned, retrieve all orders with that status
    if mentioned_status and mentioned_status in status_data:
        for order_json in status_data[mentioned_status]:
            retrieved_data.append(
                Document(
                    page_content=json.dumps(order_json, indent=2),
                    metadata={"status": mentioned_status}
                )
            )

    # Handle case where specific order numbers are mentioned
    if order_numbers:
        for po_no in order_numbers:
            if po_no in po_data:
                retrieved_data.append(
                    Document(
                        page_content=json.dumps(po_data[po_no], indent=2),
                        metadata={"po_no": po_no}
                    )
                )

    # Return retrieved data or a fallback message
    if not retrieved_data:
        return [Document(page_content="No relevant data found.", metadata={"query": query})]

    return retrieved_data"""


def format_query_result(result):
    """Helper function to format database query result."""
    if not result:
        return "No data found."
    
    # If the result is a single value like [(0,)], extract it
    if len(result) == 1 and len(result[0]) == 1:
        return str(result[0][0])
    
    # Otherwise, format the result as a string
    return "\n".join([str(row) for row in result])

def order_data(user_query):

    # Construct the PostgreSQL URI connection string
    uri = CONNECTION_STRING

    # Create the SQLDatabase object for PostgreSQL
    db = SQLDatabase.from_uri(uri)

    # ChatOpenAI model setup
    llm = ChatOpenAI(model="gpt-4", temperature=0.4)

    # Create a prompt for query validation
    system = """
You are an advanced SQL assistant specializing in generating efficient SQL queries for an e-commerce platform's `orders` table. This table contains these key columns:

1. `id`: Unique order ID.
2. `cust_ref`: Customer reference ID.
3. `po_no`: Purchase order number.
4. `order_status`: Order status (e.g., "new", "confirmed", "shipped", "canceled", "at\_wms").
5. `order_json`: JSON field with detailed order information, including:
   - Customer details (name, address, contact).
   - Shipping details (carrier, tracking, address).
   - Order attributes (dates, item descriptions, status).
   - `tracking_no` (Tracking number of the shipment).
   - `carrier` (Carrier service for the shipment).

Your responsibilities:

### 1. **Understand User Intent**:

- Interpret user queries, even with typos or ambiguities.
- Identify required SQL components such as columns, filters, and aggregation, especially for `tracking_no` and `carrier` within `order_json`.

### 2. **Generate Optimized SQL Queries**:

- Create properly structured queries that minimize resource usage while providing accurate results.
- Use JSON operators efficiently for filtering `order_json` fields.

### 3. **Ensure Compliance**:

- Use secure SQL practices.
- Validate ambiguous timeframes (e.g., "last week") as precise intervals.
- Always limit results to 10 rows if no specific limit is provided.

### Rules for Query Construction:

- **Count Queries**: Use `COUNT(*)` for totals, with filters like `order_status`, `tracking_no`, or `carrier`.
- **Details Queries**: Select relevant columns (e.g., `po_no`, `order_status`, `order_json`) to avoid unnecessary data retrieval.
- **Time Filters**: Handle time-based queries using date functions (e.g., `CURRENT_DATE`, intervals).
- **JSON Queries**: Access fields in `order_json` using JSON operators (e.g., `order_json::jsonb->>'key'`).
- If ambiguous, default to broad queries but include `LIMIT 10` to restrict the result set.

### Example User Queries and Corresponding SQL:

1. **User Query**: "How many orders are confirmed today?"
   **SQL Query**:

   
   SELECT COUNT(*) AS confirmed_orders_today
   FROM orders
   WHERE order_json::jsonb->>'order_date/book_date' = TO_CHAR(CURRENT_DATE, 'YYYY-MM-DD')
     AND order_json::jsonb->>'order_status' = 'confirmed';
   

2. **User Query**: "Give me the latest 5 orders."
   **SQL Query**:

   
   SELECT po_no, order_status, order_json
   FROM orders
   ORDER BY order_json::jsonb->>'order_date/book_date' DESC
   LIMIT 5;
   

3. **User Query**: "Give me the details of new orders."
   **SQL Query**:

   
   SELECT po_no, order_status, order_json
   FROM orders
   WHERE order_json::jsonb->>'order_status' = 'new'
   LIMIT 10;
   

4. **User Query**: "Give me the status of the latest orders."
   **SQL Query**:

   
   SELECT po_no, order_json::jsonb->>'order_status' AS order_status
   FROM orders
   ORDER BY order_json::jsonb->>'order_date/book_date' DESC
   LIMIT 10;
   

5. **User Query**: "Give me the total count of confirmed orders."
   **SQL Query**:

   
   SELECT COUNT(*) AS total_confirmed_orders
   FROM orders
   WHERE order_json::jsonb->>'order_status' = 'confirmed';
   

6. **User Query**: "Give me the details of this order no 30257."
   **SQL Query**:

   
   SELECT order_json
   FROM orders
   WHERE cust_ref = '30257'
      OR po_no = '30257';
   

7. **User Query**: "Give me the details of this po\_no 30390."
   **SQL Query**:

   
   SELECT order_json
   FROM orders
   WHERE cust_ref = '30390'
      OR po_no = '30390';
   

### Special Instructions:

- **Error Handling**: Correct user input errors such as misspellings or ambiguities without altering intent.
- **Query Classification**: Categorize queries (e.g., "count-query", "details-query") for logging and debugging purposes.
- **Output Format**: Provide the SQL query and a brief explanation of its functionality."""

    # prompt = ChatPromptTemplate.from_messages(
    #     [("system", system), ("human", "{input}")]
    # ).partial(dialect=db.dialect)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system), 
            ("human", "{question}")
        ]
    )
    # Generate table info from the database
    table_info = db.get_table_info()

    def parse_final_answer(output: str) -> str:
        # Extract the SQL query from the output, removing any markdown code block markers
        pattern = r"```sql\n(.*?)\n```"
        match = re.search(pattern, output.content, re.DOTALL)
        if match:
            return match.group(1).strip()
        else:
            raise ValueError("SQL query not found in the response.")


    # Fix the full chain to include required variables
    # full_chain = create_sql_query_chain(
    #     llm, db, prompt=prompt.partial(table_info=table_info)
    # ) | parse_final_answer
    full_chain = prompt | llm
    # Query example
    question = user_query
    query_output = full_chain.invoke({"question": question, "top_k": 10})  # Use "question" key

    try:
        # Parse the query from the model's output
        query = parse_final_answer(query_output)
        print("Parsed Query:", query)

        # Execute the query on the database
        conn = psycopg2.connect(uri)
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        print("Query Result:", result)

        # Close the cursor and connection
        cursor.close()
        conn.close()
        formatted_result = format_query_result(result)
        print("formatted_result", formatted_result)
        documents = [
            Document(page_content=f"The result of user query: {user_query} is result-> {formatted_result}", metadata={"query_id": "126382g2j2"})
        ]

        return documents
    
    except ValueError as e:
        print("Error:", str(e))
        return f"The output of the user query '{query}' is an error: {str(e)}"
    except psycopg2.Error as db_error:
        print("Database Error:", str(db_error))
        return f"The output of the user query '{query}' is a database error: {str(db_error)}"
    
# Predefined list of valid warehouse locations
VALID_LOCATIONS = ["Indiana", "Pennsylvania", "Los Angeles", "Tacoma 3PL", "Santa Clara 3PL"]

def fetch_inventory(user_query):
    """
    Fetch inventory details based on a user query and location.
    
    Args:
        user_query (str): The query from the user containing the location.
    
    Returns:
        list: A list of dictionaries containing SKU and available quantity.
    """
    # Convert query to lowercase for case-insensitive matching
    user_query = user_query.lower()
    
    # Check if the query contains "wood" and a valid location
    if "wood" in user_query:
        location = next((loc for loc in VALID_LOCATIONS if loc.lower() in user_query), None)
        
        """if not location:
            print("No valid location found in the query.")
            return []"""

        try:
            # Establish a connection using the connection string
            with psycopg.connect(CONNECTION_STRING) as conn:
                # Open a cursor to perform database operations
                with conn.cursor() as cursor:
                    # SQL query to fetch order_json and sku for wood category
                    query = """
                        SELECT inventory_json, sku
                        FROM inv_new
                        WHERE categories = 'Wood'
                    """
                    cursor.execute(query)
                    rows = cursor.fetchall()

                    if location is not None:
                        # Process data
                        results = []
                        for inv_json, sku in rows:
                            try:
                                data = json.loads(inv_json)  # Parse the JSON data
                                warehouses = data.get("warehouses", {})
                                for warehouse_id, warehouse_data in warehouses.items():
                                    if warehouse_data.get("warehouse", "").strip() == location:
                                        #warehouse_name = warehouse_data.get("warehouse", "").strip()  # Get the warehouse name and strip whitespace
                                        qty_available = warehouse_data.get("qty_available", 0)
                                        results.append({"sku": sku, "warehouse": location, "qty_available": qty_available})
                            except json.JSONDecodeError as e:
                                print(f"Error parsing JSON for SKU {sku}: {e}")

                        return results
                    
                    elif location is None and any(keyword in user_query.lower() for keyword in ["full","all","complete"]):
                        results = []
                        for inv_json, sku in rows:
                            try:
                                data = json.loads(inv_json)  # Parse the JSON data
                                warehouses = data.get("warehouses", {})
                                for warehouse_id, warehouse_data in warehouses.items():
                                    warehouse_name = warehouse_data.get("warehouse", "").strip()  # Get the warehouse name and strip whitespace
                                    qty_available = warehouse_data.get("qty_available", 0)
                                    results.append({"sku": sku, "warehouse": warehouse_name, "qty_available": qty_available})
                            except json.JSONDecodeError as e:
                                print(f"Error parsing JSON for SKU {sku}: {e}")
                        return results
                    else:
                       results =[{"sku": "N/A", "warehouse":"No info available", "qty_available": "The product you are looking for is not available"}]
                       return results 
        except psycopg.Error as db_error:
            print(f"Database error: {db_error}")
            return []
    elif "metal" in user_query:
        location = next((loc for loc in VALID_LOCATIONS if loc.lower() in user_query), None)
        
        """if not location:
            print("No valid location found in the query.")
            return []"""

        try:
            # Establish a connection using the connection string
            with psycopg.connect(CONNECTION_STRING) as conn:
                # Open a cursor to perform database operations
                with conn.cursor() as cursor:
                    # SQL query to fetch order_json and sku for wood category
                    query = """
                        SELECT inventory_json, sku
                        FROM inv_new
                        WHERE categories = 'Metal'
                    """
                    cursor.execute(query)
                    rows = cursor.fetchall()

                    if location is not None:
                        # Process data
                        results = []
                        for inv_json, sku in rows:
                            try:
                                data = json.loads(inv_json)  # Parse the JSON data
                                warehouses = data.get("warehouses", {})
                                for warehouse_id, warehouse_data in warehouses.items():
                                    if warehouse_data.get("warehouse", "").strip() == location:
                                        #warehouse_name = warehouse_data.get("warehouse", "").strip()  # Get the warehouse name and strip whitespace
                                        qty_available = warehouse_data.get("qty_available", 0)
                                        results.append({"sku": sku, "warehouse": location, "qty_available": qty_available})
                            except json.JSONDecodeError as e:
                                print(f"Error parsing JSON for SKU {sku}: {e}")

                        return results
                    
                    if location is None:
                        results = []
                        for inv_json, sku in rows:
                            try:
                                data = json.loads(inv_json)  # Parse the JSON data
                                warehouses = data.get("warehouses", {})
                                for warehouse_id, warehouse_data in warehouses.items():
                                    warehouse_name = warehouse_data.get("warehouse", "").strip()  # Get the warehouse name and strip whitespace
                                    qty_available = warehouse_data.get("qty_available", 0)
                                    results.append({"sku": sku, "warehouse": warehouse_name, "qty_available": qty_available})
                            except json.JSONDecodeError as e:
                                print(f"Error parsing JSON for SKU {sku}: {e}")
                        return results
                    else:
                       results =[{"sku": "N/A", "warehouse":"No info available", "qty_available": "The product you are looking for is not available"}]
                       return results
        except psycopg.Error as db_error:
            print(f"Database error: {db_error}")
            return []
    elif any(keyword in user_query.lower() for keyword in ["complete", "full", "all","los angeles","indiana","pennsylvania"]):
        location = next((loc for loc in VALID_LOCATIONS if loc.lower() in user_query), None)
        try:
            # Establish a connection using the connection string
            with psycopg.connect(CONNECTION_STRING) as conn:
                # Open a cursor to perform database operations
                with conn.cursor() as cursor:
                    # SQL query to fetch order_json and sku for wood category
                    query = """
                        SELECT inventory_json, sku
                        FROM inv_new
                    """
                    cursor.execute(query)
                    rows = cursor.fetchall()

                    if location is not None:
                        # Process data
                        results = []
                        for inv_json, sku in rows:
                            try:
                                data = json.loads(inv_json)  # Parse the JSON data
                                warehouses = data.get("warehouses", {})
                                for warehouse_id, warehouse_data in warehouses.items():
                                    if warehouse_data.get("warehouse", "").strip() == location:
                                        #warehouse_name = warehouse_data.get("warehouse", "").strip()  # Get the warehouse name and strip whitespace
                                        qty_available = warehouse_data.get("qty_available", 0)
                                        results.append({"sku": sku, "warehouse": location, "qty_available": qty_available})
                            except json.JSONDecodeError as e:
                                print(f"Error parsing JSON for SKU {sku}: {e}")

                        return results
                    
                    if location is None:
                        results = []
                        for inv_json, sku in rows:
                            try:
                                data = json.loads(inv_json)  # Parse the JSON data
                                warehouses = data.get("warehouses", {})
                                for warehouse_id, warehouse_data in warehouses.items():
                                    warehouse_name = warehouse_data.get("warehouse", "").strip()  # Get the warehouse name and strip whitespace
                                    qty_available = warehouse_data.get("qty_available", 0)
                                    results.append({"sku": sku, "warehouse": warehouse_name, "qty_available": qty_available})
                            except json.JSONDecodeError as e:
                                print(f"Error parsing JSON for SKU {sku}: {e}")
                        return results
                    else:
                       results =[{"sku": "N/A", "warehouse":"No info available", "qty_available": "The product you are looking for is not available"}]
                       return results
        except psycopg.Error as db_error:
            print(f"Database error: {db_error}")
            return []
    else:
        results =[{"sku": "N/A", "warehouse":"No info available", "qty_available": "The product you are looking for is not available"}]
        return results


