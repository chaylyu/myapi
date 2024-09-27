from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter
from pydantic import BaseModel
from typing import List

app = FastAPI()

# Define a function that creates a closure for the Prometheus Counter
def create_counter(metric_name, description, labelname):
    # Create a Counter metric
    counter = Counter(
        metric_name,
        description,
        labelnames=(labelname,)
    )
    
    # Define a function that increments the counter
    def increment_counter(label_value):
        counter.labels(label_value).inc()
    
    # Return the function that increments the counter
    return increment_counter

# Create a counter increment function using the closure
increment_store_code_counter = create_counter(
    "http_requested_kb_store_codes_total",
    "Number of requests for each unique KB store code.",
    "kb_store_code"
)

# Pydantic model for request body
class KBStoreRequest(BaseModel):
    kb_store_codes: List[str]

# Sample endpoint for testing
@app.post("/log-kb-stores")
async def log_kb_stores(request: KBStoreRequest):
    """
    Logs KB store codes and tracks the count of requests for each unique KB store code.
    - **kb_store_codes**: A list of KB store codes to be logged.
    """
    kb_store_codes = request.kb_store_codes
    for code in kb_store_codes:
        store_code = code.strip().lower()
        if store_code:  # Check that store code is valid and non-empty
            increment_store_code_counter(store_code)  # Use the closure to increment the counter
    return {"received_kb_store_codes": kb_store_codes}

# Restrict unnecessary metrics with proper instrumentation
instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_instrument_requests_inprogress=False,
    excluded_handlers=["/metrics"]  # Exclude metrics endpoint itself
)
instrumentator.instrument(app).expose(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
