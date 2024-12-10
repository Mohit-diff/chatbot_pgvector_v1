from sqlalchemy.orm import Session
from models.model import InventoryNew, Orders, Products, Pages
from utils import(
    get_extensive_inventory_data,
    json_to_text,
    get_order_data_by_status,
    get_bigcommerce_data,
    get_bigcommerce_pages_data
)

from sqlalchemy.orm import Session
from sqlalchemy import func

import json

#**--------------------------------------------------------------------------**
#Inventory
def read_categories_from_file(file_path):
    """
    Reads the categories file and parses it as a dictionary.

    Args:
        file_path (str): Path to the categories.txt file.

    Returns:
        dict: A dictionary with product names (keys) and categories (values).
    """
    try:
        with open(file_path, "r") as file:
            categories = json.load(file)  # Parse the file as JSON
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        categories = {}
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON data in {file_path}: {e}")
        categories = {}
    return categories


def remove_duplicate_inventory(session: Session):
    """
    Remove duplicate entries in the InventoryNew table based on 'sku'.
    """
    # Query for duplicate 'sku' entries
    duplicates = (
        session.query(InventoryNew.sku)
        .group_by(InventoryNew.sku)
        .having(func.count(InventoryNew.sku) > 1)
        .all()
    )
    
    # For each duplicate 'sku', delete all but one record
    for sku, in duplicates:
        duplicate_records = (
            session.query(InventoryNew)
            .filter_by(sku=sku)
            .order_by(InventoryNew.id)  # Assuming 'id' can be used to determine order
            .all()
        )
        # Keep the first record and delete the others
        for record in duplicate_records[1:]:  # Keep the first record, remove others
            session.delete(record)
    
    session.commit()

def extensive_inv_data(db: Session):
    """
    Update the inventory data in the database and assign categories dynamically from a file.
    Only the 'inventory_json' field will be updated in each run.
    
    Args:
        db (Session): Database session object.
        categories_file (str): Path to the categories.txt file.
    """
    # Read categories from the file
    categories = read_categories_from_file("/home/differenz83/Documents/AI_Internal_Chatbot/chatbot_new/AI_chatbot/features/embeddings/categories.json")

    inventory = get_extensive_inventory_data()["response"]

    for inv in inventory:
        plain_text = json_to_text(inv)
        
        # Extract category for the current product name from the dictionary
        product_name = inv["sku"]  # Assuming "sku" in your inventory corresponds to product name
        category = categories.get(product_name, "Unknown")  # Default to "Unknown" if not found

        # Check if the record exists in the database
        existing_record = db.query(InventoryNew).filter_by(sku=inv["sku"]).first()
        
        if existing_record:
            # Update only the 'inventory_json' field
            existing_record.inventory_json = plain_text
        else:
            # Create a new record with all fields, but only update 'inventory_json'
            inv_model = InventoryNew(
                sku=inv["sku"],
                categories=category,  # Assign the category dynamically
                inventory_json=plain_text,
            )
            db.add(inv_model)
    
    db.commit()
    
    # Remove duplicates from the database
    remove_duplicate_inventory(db)
    db.commit()

#**--------------------------------------------------------------------------------**
#Orders
def is_order_json_unique(session: Session, po_no: str):
    """Fetch existing shipping record for the given purchase order number."""
    return session.query(Orders).filter_by(po_no=po_no).first()

def remove_duplicate_orders(session: Session):
    """Remove duplicates in the Orders table based on po_no."""
    # Query for duplicate po_no entries
    duplicates = (
        session.query(Orders.po_no)
        .group_by(Orders.po_no)
        .having(func.count(Orders.po_no) > 1)
        .all()
    )
    
    # For each duplicate po_no, delete all but one record
    for po_no, in duplicates:
        duplicate_records = (
            session.query(Orders)
            .filter_by(po_no=po_no)
            .all()
        )
        # Keep one record and delete the others
        for record in duplicate_records[1:]:  # Keep the first record, remove others
            session.delete(record)
    
    session.commit()

def update_bigcommerce_order_embeddings(db):
    """Update BigCommerce order embeddings and handle duplicates."""
    # Define the statuses you want to retrieve data for
    statuses = ['new', 'at_wms', 'shipped_or_confirmed']
    
    # Keep track of processed po_no in the current batch
    processed_po_nos = set()
    
    # Iterate through each status and fetch the corresponding order data
    for status in statuses:
        response_data = get_order_data_by_status(status=status)  # Call the function with the status parameter
        
        for order in response_data:
            if order["po_no"] in processed_po_nos:
                continue  # Skip duplicates in the current batch
            
            plain_text = json_to_text(order)
            # embeddings = text_to_embeddings_list(plain_text)

            # Create a new Orders instance
            order_model = Orders(
                po_no=order["po_no"],
                cust_ref=order["cust_ref"],
                order_status=order["order_status"],
                order_json=plain_text,
                # embeddings=embeddings,
            )

            # Check if the purchase order number already exists
            existing_order = is_order_json_unique(db, order_model.po_no)  # Check based on po_no
            if existing_order:
                # Update existing record with new values
                existing_order.order_status = order_model.order_status
                existing_order.order_json = order_model.order_json
                # existing_order.embeddings = order_model.embeddings
            else:
                # Insert new record if it doesn't exist
                db.add(order_model)  # This will insert the new record
            
            # Mark this po_no as processed
            processed_po_nos.add(order["po_no"])

    # Commit changes to the database
    db.commit()
    
    # Remove duplicates from the database
    remove_duplicate_orders(db)
    db.commit()
 
#**----------------------------------------------------------------------**   
#Product
def get_existing_product(session: Session, product_id: int) -> Products:
    """Fetch existing product record for the given product_id."""
    return session.query(Products).filter_by(product_id=product_id).first()

def update_product_embedding(db: Session):
    products = get_bigcommerce_data()
    for product in products:

        plain_text = json_to_text(product)
        #embeddings = text_to_embeddings_list(plain_text)
        
        # Create a new Products instance
        products_model = Products(
            product_id=product["id"],
            name = product["name"],
            #sku=product["sku"],
            #embedding=embeddings,
            product_json=str(product),
        )

        # Check if the SKU already exists
        existing_product = get_existing_product(db, products_model.product_id)
        if existing_product:
            # Update existing record with new values
            existing_product.product_id = products_model.product_id
            #existing_product.embedding = products_model.embedding
            existing_product.product_json = products_model.product_json
        elif not existing_product:
            # Insert new record if it doesn't exist
            db.add(products_model)  # This will insert the new record

    # Commit changes to the database
    db.commit()

#**---------------------------------------------------------------------------**
#Pages
def get_existing_page(session: Session, page_id: str) -> Pages:
    """Fetch existing page record for the given page ID."""
    return session.query(Pages).filter_by(page_id=page_id).first()

def update_bigcommerce_pages_embedding(db: Session):
    pages = get_bigcommerce_pages_data()
    
    for page in pages:
        plain_text = f"{page['name']}: {page['body']}"
        #embeddings = text_to_embeddings_list(plain_text)
        
        # Create a new Pages instance
        pages_model = Pages(
            page_id=page["id"],
            page_name=page["name"],
            page_json=str(page),
            #embedding=embeddings,
        )

        # Check if the page ID already exists
        existing_page = get_existing_page(db, pages_model.page_id)
        if existing_page:
            # Update existing record with new values
            existing_page.page_name = pages_model.page_name
            existing_page.page_json = pages_model.page_json
            #existing_page.embedding = pages_model.embedding
        elif not existing_page:
            # Insert new record if it doesn't exist
            db.add(pages_model)  # This will insert the new record

    # Commit changes to the database
    db.commit()
