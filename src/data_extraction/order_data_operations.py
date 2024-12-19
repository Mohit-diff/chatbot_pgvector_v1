import re
import json
import psycopg
from datetime import datetime, timedelta
from dateutil import parser
from langchain.schema import Document
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import os
load_dotenv()

# Database connection string
CONNECTION_STRING = os.getenv("CONNECTION_STRING")

# Function to fetch only 'po_no', 'order_status', and 'order_json' columns from the Orders table
def fetch_order_columns():
    with psycopg.connect(CONNECTION_STRING) as conn:
        with conn.cursor() as cur:
            query = "SELECT cust_ref, po_no, order_status, order_source, order_json FROM orders;"
            cur.execute(query)
            results = cur.fetchall()
    return results

# Function to extract order numbers from the user query
def extract_order_numbers(query):
    pattern = r'\b\d+\b'  # Regex to match numeric order numbers
    matches = re.findall(pattern, query)
    return matches if matches else []


def extract_and_normalize_dates_with_relative_terms(text):
    """
    Extracts and normalizes all date formats and relative terms in the given text into YYYY-MM-DD.
    """
    current_date = datetime.now()
    print("current date:", current_date)
    current_year = current_date.year

    # Refined regex patterns for absolute and relative dates
    date_patterns = [
        r"\b\d{4}-\d{2}-\d{2}\b",  # Matches "2024-11-08"
        r"\b\d{2}/\d{2}/\d{4}\b",  # Matches "10/11/2024"
        r"\b\d{2}-\d{2}-\d{4}\b",  # Matches "10-11-2024"
        r"\b\d{1,2}(?:st|nd|rd|th)?\s+\w+\b",  # Matches "8th Dec"
        r"\b\w+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b",  # Matches "December 8th, 2024"
        r"\b\w+\s+\d{1,2}(?:st|nd|rd|th)?\b",  # Matches "December 8th" (without year)
    ]
    
    # Patterns for relative terms
    relative_terms = {
        "today": current_date,
        "yesterday": current_date - timedelta(days=1),
        #"this week": current_date - timedelta(days=current_date.weekday()),
        #"this month": current_date.replace(day=1),
        #"this year": current_date.replace(month=1, day=1),
    }

    combined_pattern = "|".join(date_patterns)  # Combine patterns for absolute dates
    matches = re.findall(combined_pattern, text)

    # Add relative terms to the normalized dates
    normalized_dates = []
    for word, reference_date in relative_terms.items():
        if word in text.lower():
            normalized_dates.append(reference_date.strftime("%Y-%m-%d"))
    
    for match in matches:
        try:
            # Check if the match contains a year
            if not re.search(r"\d{4}", match):
                # Append the current year if no year is present
                match = f"{match} {current_year}"
            
            # Parse the date into a datetime object
            parsed_date = parser.parse(match)
            
            # Format into YYYY-MM-DD
            normalized_dates.append(parsed_date.strftime("%Y-%m-%d"))
        except Exception:
            continue  # Ignore unparseable matches

    return list(set(normalized_dates))  # Remove duplicates


def order_data_retrieve(query):
    is_po_data = False
    is_po_no = False
    query = query.lower()
    order_numbers = extract_order_numbers(query)
    order_statuses = ['Confirmed', 'Shipped', 'New', 'Canceled', 'AT_WMS', 'Error']
    order_sources = ['BigCommerce', 'Costco']
    
    mentioned_status = None
    order_source = None
    
    # Detect if any valid status is mentioned in the query
    for status in order_statuses:
        if status.lower() in query:
            mentioned_status = status
            break
        
    for source in order_sources:
        if source.lower() in query:
            order_source = source
            print(order_source)
            break
        

    dates = extract_and_normalize_dates_with_relative_terms(query)
    result = []

    if not order_source and mentioned_status and dates:
        try:
            with psycopg.connect(CONNECTION_STRING) as conn:
                with conn.cursor() as cursor:
                    date = dates[0]  # Assuming `dates[0]` is a string in "YYYY-MM-DD" format
                    print("date:", date)  # Debugging output
                    query = """
                        SELECT COUNT(*)
                        FROM orders
                        WHERE order_status = %s
                        AND order_date = %s
                    """
                    #print("Query being executed:", query)
                    #print("Parameters:", (mentioned_status, date))
                    cursor.execute(query, (mentioned_status.lower(), date))
                    count = cursor.fetchone()  # Fetch single row as a tuple
                    #print("Count:", count[0] if count else 0)  # Debugging output
                    result_data = {"Status": status, "Order count": count[0] if count else 0, "Date": date}
                    
                    if count[0] > 0:
                            cust_ref_query = """
                            SELECT cust_ref, (order_json::jsonb)->>'updated_date_time'
                            FROM orders
                            WHERE order_status = %s
                            AND order_date = %s
                        """
                            cursor.execute(cust_ref_query, (mentioned_status.lower(), date))
                            # Fetch all customer references for the given status and date
                            cust_refs_and_times = cursor.fetchall()  
                            # Add cust_ref data to the result if there are any references
                            #result_data["Cust_Refs"] = [cust_ref[0] for cust_ref in cust_refs] if cust_refs else []
                            
                            if cust_refs_and_times:
                                result_data["Cust_Refs"]=[]
                                for cust_ref, updated_date_time in cust_refs_and_times:
                                    if updated_date_time:
                                        # Convert updated_date_time to human-readable format
                                        updated_time = datetime.fromisoformat(updated_date_time).strftime("%Y-%m-%d %H:%M:%S")
                                        # Split into Date and Time
                                        date_part, time_part = updated_time.split(" ")
                                        result_data["Cust_Refs"].append(f"Order Id: {cust_ref} - Date: {date_part} - {time_part}")
                                    else:
                                        # Handle the case where updated_date_time is None
                                        result_data["Cust_Refs"].append(f"Order Id: {cust_ref} - Date: No date time available")                    
                          
                    else:  # If count is zero, set a default message
                        result_data["Cust_Refs"] = ["No orders found for the given status and date."]

                    result.append(result_data)
        except Exception as e:
            print(f"Error occurred: {e}")
        return result, is_po_no, is_po_data

    elif not mentioned_status and dates:
        order_status = ['New', 'Confirmed', 'AT_WMS', 'Shipped']
        try:
            with psycopg.connect(CONNECTION_STRING) as conn:
                with conn.cursor() as cursor:
                    date = dates[0]  # Assuming `dates[0]` is a string in "YYYY-MM-DD" format
                    print("date:", date)  # Debugging output
                    for status in order_status:
                        query = """
                            SELECT COUNT(*)
                            FROM orders
                            WHERE order_status = %s
                            AND order_date = %s
                        """
                        #print(f"Query for status '{status}':", query)
                        #print("Parameters:", (status, date))
                        cursor.execute(query, (status.lower(), date))
                        count = cursor.fetchone()
                        #print(f"Count for status {status}:", count[0] if count else 0)  # Debugging output
                        result_data = {"Status": status, "Order count": count[0] if count else 0, "Date": date}
                        
                        if count[0] > 0:
                            cust_ref_query = """
                            SELECT cust_ref, (order_json::jsonb)->>'updated_date_time'
                            FROM orders
                            WHERE order_status = %s
                            AND order_date = %s
                        """
                            cursor.execute(cust_ref_query, (status.lower(), date))
                            # Fetch all customer references for the given status and date
                            cust_refs_and_times = cursor.fetchall()  
                            # Add cust_ref data to the result if there are any references
                            #result_data["Cust_Refs"] = [cust_ref[0] for cust_ref in cust_refs] if cust_refs else []
                            
                            if cust_refs_and_times:
                                result_data["Cust_Refs"]=[]
                                for cust_ref, updated_date_time in cust_refs_and_times:
                                    if updated_date_time:
                                        # Convert updated_date_time to human-readable format
                                        updated_time = datetime.fromisoformat(updated_date_time).strftime("%Y-%m-%d %H:%M:%S")
                                        # Split into Date and Time
                                        date_part, time_part = updated_time.split(" ")
                                        result_data["Cust_Refs"].append(f"Order Id: {cust_ref} - Date: {date_part} - {time_part}")
                                    else:
                                        # Handle the case where updated_date_time is None
                                        result_data["Cust_Refs"].append(f"Order Id: {cust_ref} - Date: No date time available")                            
                        
                        else:  # If count is zero, set a default message
                            result_data["Cust_Refs"] = ["No orders found for the given status and date."]

                        result.append(result_data)
        except Exception as e:
            print(f"Error occurred: {e}")
        return result, is_po_no, is_po_data
    
    elif order_source:
        order_status = ['New', 'Confirmed', 'AT_WMS', 'Shipped']
        try:
            with psycopg.connect(CONNECTION_STRING) as conn:
                with conn.cursor() as cursor:
                    date = dates[0] if dates and len(dates) > 0 else None   # Assuming `dates[0]` is a string in "YYYY-MM-DD" format
                    print("date:", date)  # Debugging output
                    for status in order_status:
                        # Check if only order_source is provided
                        if order_source and not date and not status:
                            print("order_source exists")
                            query = """
                                SELECT cust_ref, (order_json::jsonb)->>'updated_date_time'
                                FROM orders
                                WHERE order_source = %s
                            """
                            params = (order_source,)
                        else:
                            # General case with all conditions
                            query = """
                                SELECT cust_ref, (order_json::jsonb)->>'updated_date_time'
                                FROM orders
                                WHERE order_source = %s
                                AND (order_date = %s OR LOWER(order_status) = %s)
                            """
                            params = (order_source, date, status.lower())

                        # Execute the query
                        cursor.execute(query, params)
                        rows = cursor.fetchall()
                        print(rows)

                        # Prepare result_data
                        result_data = {
                            "Status": status,
                            "Order count": len(rows),  # Use len(rows) for count
                            "Date": date or "N/A",  # Display 'N/A' if no date
                            "Cust_Refs": []
                        }

                        # Populate Cust_Refs if rows exist
                        if rows:
                            for cust_ref, updated_date_time in rows:
                                try:
                                    updated_time = datetime.fromisoformat(updated_date_time).strftime("%Y-%m-%d %H:%M:%S")
                                    date_part, time_part = updated_time.split(" ")
                                    result_data["Cust_Refs"].append(
                                    f"Order Id: {cust_ref} - Date: {date_part} - {time_part}"
                                    )
                                except (TypeError, ValueError):
                                    result_data["Cust_Refs"].append(f"Order Id: {cust_ref} - Date: No date time available")
                        else:
                            result_data["Cust_Refs"].append("No orders found for the given status and date.")
                        result.append(result_data)
        except Exception as e:
            print(f"Error occurred: {e}")
        return result, is_po_no, is_po_data

    elif order_numbers:
        is_po_no = True
        result = []
        try:
            with psycopg.connect(CONNECTION_STRING) as conn:
                with conn.cursor() as cursor:
                    query = """
                        SELECT order_json
                        FROM orders
                        where po_no = %s
                        OR cust_ref = %s
                    """
                    print(f"Query: {query}")
                    print(f"Order number: {order_numbers}")
                    cursor.execute(query, (order_numbers[0], order_numbers[0]))
                    data = cursor.fetchall()
                    print(f"Fetched data: {data}")
                    if data:
                        is_po_data = True
                        for record in data:
                            print(f"Processing record: {record}")
                            result.append(Document(page_content=record[0], metadata={"order number": order_numbers}))
                    else:
                        result.append({"Status": "No info available", "Order count": 0, "Cust_Refs": ["N/A"], "Date": "N/A"})
        except Exception as e:
            print(f"Error occurred: {e}")
        return result, is_po_no, is_po_data
    
    else:
        result.append({"Status": "No info available", "Order count": 0, "Cust_Refs": ["N/A"], "Date": "N/A"})
        return result, is_po_no, is_po_data

        
                
                            
            