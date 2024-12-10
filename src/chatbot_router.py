from fastapi import APIRouter

"""from src.services import(
    get_similar_data,
    generate_response
)"""
data = []
products_dict = {}
router = APIRouter(prefix="/chatbot", tags=["Chatbot"])



from fastapi import Query

@router.post("/ask")
def search_products(query: str = Query(..., min_length=1, description="Query text for the chatbot")):
    # Ensure `query` is a non-empty string
    if not query:
        raise ValueError("Query cannot be empty")
    return "Hi! I am slack bot"
    """# Generate embedding for the query
    similar_data = await get_similar_data(query)
    
    # Format similar data for response
    context = ", ".join([f"{item}" for item in similar_data])
    
    # Generate and return response
    response = generate_response(query, context)
    return {"response": response}"""
