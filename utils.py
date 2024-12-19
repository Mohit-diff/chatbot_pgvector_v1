import re
import html
import json
import requests
from core.config import settings


#Clean html tags
def remove_html_tags(text):
    # Remove HTML tags
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', text)  # Remove HTML tags
    text = html.unescape(text)  # Unescape HTML entities
    
    # Remove unwanted characters
    text = text.replace('\r', '')  # Remove carriage returns
    text = text.replace('\n', '')  # Remove newlines
    text = text.replace('\xa0', ' ')  # Replace non-breaking spaces with regular space
    text = text.strip()  # Remove leading and trailing whitespace
    
    return text

#json to text
def json_to_text(json_data):

    text = json.dumps(json_data, separators=(",", ":"))
    text = re.sub(r"\s+", " ", text)
    return text


#Inventory data
def get_extensive_inventory_data():
    url = "https://api.cartrover.com/v1/merchant/inventory?limit=250"

    response = requests.get(
        url, auth=(settings.EXTENSIVE_USERNAME, settings.EXTENSIVE_PASSWORD)
    )
    return response.json()

# Pages data
def get_bigcommerce_pages_data():
    url = (
        f"https://api.bigcommerce.com/stores/{settings.BIGCOMMERCE_STORE_HASH}/v2/pages"
    )

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Auth-Token": settings.BIGCOMMERCE_ACCESS_TOKEN,
    }

    response = requests.get(url, headers=headers)
    
    # Check if the response was successful
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return None

    # Parse the JSON response
    pages = response.json()

    # Create a new list to store cleaned pages data
    cleaned_pages = []

    for page in pages:
        cleaned_body = remove_html_tags(page["body"])  # Clean the body content
        cleaned_pages.append({
            "id": page["id"],
            "name": page["name"],
            "body": cleaned_body
        })

    return cleaned_pages

#Order data
def get_order_data_by_status(status: str):
    """
    Retrieves order data based on the provided status.

    Status Mapping:
    - new:              Order Created Date
    - at_wms:           Order Delivered to WMS Date
    - new_or_at_wms:    Order Created Date
    - partial:          Shipment Loaded Date
    - shipped:          Shipment Loaded Date
    - confirmed:        Date Shipment Sent to Cart
    - shipped_or_confirmed: Shipment Loaded Date
    - error:            Error Raised Date
    - canceled:         Canceled Date

    Args:
        status (str): The order status to filter by.

    Returns:
        dict: The JSON response containing the order data.
    """
    url = f"https://api.cartrover.com/v1/merchant/orders/list/{status}"

    try:
        response = requests.get(
            url, auth=(settings.EXTENSIVE_USERNAME, settings.EXTENSIVE_PASSWORD)
        )
        response.raise_for_status()
        
        if response.status_code != 200:
            #print(f"Error: {response.status_code} - {response.text}")
            return None

        order_data = response.json()
        cleaned_order = []

        for order in order_data['response']:
            # Common fields for all statuses
            common_fields = {
                'updated_date_time': order['updated_date_time'],
                'cust_ref': order['cust_ref'],
                'po_no': order['cust_po_no'],
                'cust_first_name': order['cust_first_name'],
                'cust_last_name': order['cust_last_name'],
                'cust_address_1': order['cust_address_1'],
                'cust_address_2': order['cust_address_2'],
                'cust_address_3': order['cust_address_3'],
                'cust_city': order['cust_city'],
                'cust_state': order['cust_state'],
                'cust_zip': order['cust_zip'],
                'cust_country': order['cust_country'],
                'cust_phone': order['cust_phone'],
                'cust_e_mail': order['cust_e_mail'],
                'requested_ship_date': order['requested_ship_date'],
                'ship_company': order['ship_company'],
                'ship_address_1': order['ship_address_1'],
                'ship_address_2': order['ship_address_2'],
                'ship_address_3': order['ship_address_3'],
                'ship_city': order['ship_city'],
                'ship_state': order['ship_state'],
                'ship_zip': order['ship_zip'],
                'ship_country': order['ship_country'],
                'ship_phone': order['ship_phone'],
                'ship_e_mail': order['ship_e_mail'],
                'order_source': order['order_source'],
                'order_date': order['order_date'],
            }

            # Specific fields based on status
            if status == 'new':
                # Return fields related to the new status
                cleaned_order.append({
                    **common_fields,
                    'order_status': order['order_status'],
                    'order_date/book_date': order['order_date'], # Specific to 'new'
                    'mark_in_progress_date': order['mark_in_progress_date'],
                    'item_description': order['items'][0]['Description'],
                    'line_item_id': order['items'][0]['line_item_id'],
                 })
            elif status == 'at_wms':
                # Return fields related to the at_wms status
                cleaned_order.append({
                    **common_fields,
                    'order_status': order['order_status'],
                    'order_date/book_date': order['order_date'],# Assuming similar fields; modify as needed
                    'mark_in_progress_date': order['mark_in_progress_date'],
                    'order_is_at_the_warehouse_or_wms': order['delivered_to_wms_date'],  # Specific to 'at_wms'
                    'item_description': order['items'][0]['Description'],
                    'line_item_id': order['items'][0]['line_item_id'],
                })
            elif status == 'shipped_or_confirmed':
                # Return fields related to the shipped_or_confirmed status
                cleaned_order.append({
                    **common_fields,
                    'order_status': order['order_status'],
                    'order_date/book_date': order['order_date'],  # Specific to 'shipped_or_confirmed'
                    'shipping_instructions': order['shipping_instructions'],  # Specific to 'shipped_or_confirmed'
                    'carrier': order['shipments'][0]['carrier'],
                    'tracking_no': order['shipments'][0]['tracking_no'],
                    'order_confirmed_or_shipped_date': order['requested_ship_date'],
                })
            else:
                # Handle other statuses as necessary
                cleaned_order.append(common_fields)

        return cleaned_order
    except requests.exceptions.RequestException as e:
        #print({"error": str(e)})
        return None
   
#Product data
def get_bigcommerce_data():

    url = f"https://api.bigcommerce.com/stores/{settings.BIGCOMMERCE_STORE_HASH}/v3/catalog/products?limit=100"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Auth-Token": settings.BIGCOMMERCE_ACCESS_TOKEN,
    }

    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return None
    
    products = response.json()

    # Use set comprehension to collect unique category IDs
    # categories_id = {
    #     category for product in products["data"] for category in product["categories"]
    # }

    # Process products
    """for product in products["data"][:10]:
        product["description"] = remove_html_tags(product["description"])
        product["reviews"] = get_bigcommerce_reviews_data(product["id"])"""

    # Fetch category data
    # categories_data = [
    #     get_bigcommerce_category_data(category_id) for category_id in categories_id
    # ]

    # categories_dict = {"data": categories_data, "total_categories": len(categories_id)}
    cleaned_products = []
    # Process products
    for product in products["data"]:
        cleaned_products.append({
            "id": product["id"],
            "name": product["name"],
            "type": product["type"],
            #"sku": product["sku"],
            "description": remove_html_tags(product["description"]),  # Clean the description
            "weight": product["weight"],
            "price": product["price"],
            #"retail_price": product["retail_price"],
            #"sale_price": product["sale_price"],
            #"calculated_price": product["calculated_price"],
            #"inventory_level": product["inventory_level"],
            #"inventory_warning_level": product["inventory_warning_level"],
            #"inventory_tracking": product["inventory_tracking"],
            #"total_sold": product["total_sold"],
            "is_free_shipping": product["is_free_shipping"],
            "meta_description": product["meta_description"],
            "date_created": product["date_created"],
            "date_modified": product["date_modified"],
            #"reviews": get_bigcommerce_reviews_data(product["id"])
        })
    #products["total_products"] = len(products["data"])
    #return products  # , categories_dict
    return  cleaned_products
