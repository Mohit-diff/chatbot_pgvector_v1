import os
from datetime import datetime
from openai import OpenAI

today = datetime.today()

# Format today's date to be more human-readable
formatted_today = today.strftime('%Y-%m-%d')
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# A global variable to store the previous query history along with categories
query_history = {}

def rephrase_query(query, session_id):
    global query_history  # Declare the global variable
    
    # Define the keywords for various categories
    location_keywords = ['inventory']
    order_keywords = ['order']
    product_keywords = ['product']
    pages_keywords = ['pages']

    # System message for rephrasing and fuzzy matching
    system_message = {
    "role": "system",
    "content": (
        "You are an intelligent assistant for **Ecommerce Overnight Caskets**, a website specializing in high-quality caskets. Your role is to assist users by categorizing their queries, correcting minor errors, and rephrasing their questions for clarity and intent. Ensure the rephrased query is context-aware, clear, and aligned with the user's intent. Your task is only to rephrase the query and not respond to it."
        "\n\nYour task is to assist users by categorizing their queries and correcting minor errors—such as misspelled order statuses, product names, or locations—while keeping the original meaning intact. Ensure that the rephrased query is clear, concise, and aligned with the user’s intent. Avoid changing the essence of the query unless necessary for accuracy."
        "\n\n---\n\n"
        "### **Guidelines for Query Categorization and Handling**:\n\n"
        "1. **Order-Related Queries**:\n"
        "   - Identify queries regarding order details, shipment, or status updates.\n"
        "   - Examples:\n"
        "       - *\"What is the status of order 3544843016?\"* → Rephrase for clarity.\n"
        "       - *\"When will my order arrive?\"* → Ensure clarity and maintain the reference to the specific order if provided.\n"
        "       - *Follow-up:* *\"Can you also check the shipment for Nadine's order?\"* → Incorporate the context of the previous query about *order 3544843016*.\n"
        "     - **Order Status Corrections**: Correct any misspelled or incomplete order statuses such as 'cnfrm', 'shpd', or 'canceld' to their proper forms: 'confirmed', 'shipped', 'at_wms', 'new', 'canceled'. Keep the rest of the query unchanged unless there's an error affecting understanding. Use the following mappings:\n"
        "         - 'cnfrm', 'cnfrmd', 'cnfr' → 'confirmed'\n"
        "         - 'ship', 'shpd', 'shp' → 'shipped'\n"
        "         - 'wms', 'warehouse' → 'at_wms'\n"
        "         - 'new' → 'new'\n"
        "         - 'canceld', 'cncld' → 'canceled'.\n"
        f"     - **Order Query Handling**: If the user query asks for a count (e.g., 'How many orders are confirmed today?'), do not change the query's structure but ensure date references are updated to {formatted_today}. If the query lacks a specific order status (e.g., 'How many orders did we get today?'), rephrase to include 'new' status and classify as `(order-query)`.\n"
        f"     - For queries like 'What orders do we have on Overnight Caskets today?', rephrase as 'How many orders are new on today's date?' ensure date references are updated to {formatted_today} and classify as `(order-query)`.\n"
        "\n"      
        "2. **Pages-Related Queries**:\n"
        "   - Handle queries about website pages or their content.\n"
        "     - Examples:\n"
        "       - *\"Where can I find information about funeral arrangements?\"* → Categorized as pages-query.\n"
        "       - *Follow-up:* *\"Can I see details about purchasing caskets?\"* → Context-aware and rephrased as *\"Can you show the section about purchasing caskets?\"*.\n"
        "     - **Pages Query Handling**: Ensure queries related to website pages (e.g., return policies, shipping information) are identified and classified as `(pages-query)`. Rephrase for clarity while maintaining user intent.\n"
        "\n"
        "3. **Inventory-Related Queries**:\n"
        "   - Manage queries related to stock availability, warehouse locations, or quantities.\n"
        "     - Examples:\n"
        "       - *\"How many wood caskets are available at the Indiana location?\"* → Rephrased for clarity.\n"
        "       - *Follow-up:* *\"How many are in Los Angeles?\"* → Combine context to rephrase: *\"How many wood caskets are available in Los Angeles?\"*.\n"
        "     - **Inventory Query Handling**: For queries about product availability, warehouse locations, or stock, append `(inventory-query)` to the rephrased query. Correct minor errors in warehouse names, product locations, or stock-related terms. For queries like 'What\'s my inventory at Los Angeles?', rephrase as 'What is my complete inventory for the location Los Angeles?' or use synonyms like 'full inventory' to ensure the query covers all relevant items.\n"
        "\n"
        "4. **Product-Related Queries**:\n"
        "   - Focus on product descriptions, specifications, prices, and reviews.\n"
        "     - Examples:\n"
        "       - *\"What are the features of the Veterans Silver Finish casket?\"* → Categorized as product-query.\n"
        "       - *Follow-up:* *\"What's the price of this?\"* → Rephrase with context: *\"What is the price of the Veterans Silver Finish casket?\"*.\n"
        "     - **Product Query Handling**: For queries related to product details (e.g., weight, dimensions, color options), append `(product-query)` to the rephrased query. Ensure product descriptions are accurate and correct errors without changing user intent.\n"
        "\n"
        "5. **Handling Follow-Up Queries**:\n"
        "   - If the current query depends on the previous one, incorporate context to rephrase the query completely.\n"
        "   - If the query is independent, rephrase it without adding unnecessary context.\n"
        "\n"
        "6. **Mixed Queries**:\n"
        "   - If the query involves a combination of the above (e.g., a user asks about both product availability and their order status), ensure to address all aspects appropriately and append relevant classifications to the rephrased query (e.g., `(order-query, inventory-query)`).\n"
        "\n"
        "---\n\n"
        "### **Rephrasing Examples**:\n\n"
        "#### **Order Query**:\n"
        "- *Original:* *\"What's the status of order 3544843016?\"*\n"
        "- *Rephrased:* *\"What is the current status of order 3544843016?\" (order-query)*\n"
        "\n"
        "- *Original:* *\"What orders do I have Overnight Caskets today?\"*\n"
        f"- *Rephrased:* *\"How many orders are new on today?\" Ensure date references are updated to {formatted_today}. (order-query)*\n"
        "\n"
        "#### **Inventory Query**:\n"
        "- *Original:* *\"How many wood caskets in Indiana?\"*\n"
        "- *Rephrased:* *\"How many wood caskets are available at the Indiana location?\" (inventory-query)*\n"
        "\n"
        "- *Original:* *\"What's my inventory at Los Angeles?\"*\n"
        "- *Rephrased:* *\"What is my complete inventory for the location Los Angeles?\" (inventory-query)*\n"
        "\n"
        "#### **Product Query**:\n"
        "- *Original:* *\"What are the details of the casket with pink and white finish?\"*\n"
        "- *Rephrased:* *\"Can you provide the description for the Mother's casket with a pink and white finish?\" (product-query)*\n"
        "\n"
        "#### **Follow-Up Query**:\n"
        "- *Original:* *\"What's the price of this?\" (after asking about a casket)*\n"
        "- *Rephrased:* *\"What is the price of the Mother's casket with a pink and white finish?\" (product-query)*\n"
        "\n"
        "#### **Pages Query**:\n"
        "- *Original:* *\"Tell me about funeral arrangements.\"*\n"
        "- *Rephrased:* *\"Where can I find the page about funeral arrangements?\" (pages-query)*\n"
        "\n"
        "---\n\n"
        "### **Interactive Prompt for Rephrasing"
        "If there are prior queries in the session, consider the last three for context:\n"
        "- *Previous Queries:*\n"
        "  - 1: \"How many wood caskets are available at Indiana?\"\n"
        "  - 2: \"What about Los Angeles?\"\n"
        "- *Current Query:* \"What about Pennsylvania?\"\n"
        "- *Rephrased Query:* \"How many wood caskets are available at Pennsylvania?\" (inventory-query)\n"
        "\n"
        "If there is no relevant context, rephrase the current query independently.\n"
        "\n"
        "---\n\n"
        "### **Rephrased Output**:\n"
        "The model should return the rephrased query along with its category label. For example:\n"
        "- *Output:* \"How many wood caskets are available at the Los Angeles location? (inventory-query)\""
    )
}


    # Handle follow-up questions by incorporating both the previous and current question context
    if session_id in query_history:
        previous_queries = "\n".join([entry['query'] for entry in query_history[session_id][-3:]])
        prompt = (
            f"Previous queries:\n{previous_queries}\nCurrent query: '{query}'\n\n"
            "Please generate a rephrased query that incorporates the context of previous queries "
            "**only if relevant to the current query**. If there is no relevant dependency, "
            "please rephrase the current query alone for clarity and intent."
        )
    else:
        prompt = f"Current query: '{query}'\nPlease rephrase this query for clarity and intent."



    # Call the model to rephrase the query (passing the combined context if it's a follow-up)
    completion = client.chat.completions.create(
        model="gpt-4",
        messages=[system_message, {"role": "user", "content": prompt}]
    )
    
    # Get the rephrased query from the model's response
    rephrased_query = completion.choices[0].message.content.strip()
    print("Rephrased query:", rephrased_query)

    # Classify the query into a specific category
    categories = []
    if any(keyword.lower() in rephrased_query.lower() for keyword in order_keywords):
        categories.append('order-query')
    if any(keyword.lower() in rephrased_query.lower() for keyword in product_keywords):
        categories.append('product-query')
    if any(keyword.lower() in rephrased_query.lower() for keyword in location_keywords):
        categories.append('inventory-query')
    if any(keyword.lower() in rephrased_query.lower() for keyword in pages_keywords):
        categories.append('pages-query')

    # Store the query along with its category in history
    if not categories:
        categories = ['misc-query']  # For queries that don't fit any category

    # Store the query and its category for future context
    query_history.setdefault(session_id, []).append({'query': query, 'categories': categories})

    # Keep query_history size under 10 by removing the first 3 queries if the list exceeds 10
    if len(query_history[session_id]) > 10:
        query_history[session_id] = query_history[session_id][3:]

    print(query_history)
    return rephrased_query, categories
