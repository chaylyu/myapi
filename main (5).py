from typing import Callable, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Form
from pydantic import BaseModel
from prometheus_client import REGISTRY, CollectorRegistry, Counter
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_fastapi_instrumentator.metrics import Info
from typing import List

app = FastAPI()

# Pydantic models for the requests
class AskRequest(BaseModel):
    kbStores: list[str]

def add_kb_stores_label(registry: CollectorRegistry = REGISTRY) -> Optional[Callable[[Info], None]]:
    def is_duplicated_time_series(error: ValueError) -> bool:
        return any(
            map(
                error.args[0].__contains__,
                [
                    "Duplicated timeseries in CollectorRegistry:",
                    "Duplicated time series in CollectorRegistry:",
                ],
            )
        )

    try:
        TOTAL = Counter(
            name="http_requests_total",
            documentation="Total number of requests by method, status, and handler.",
            labelnames=("method", "status", "handler", "kbStores"),
            registry=registry,
        )


        async def instrumentation(info: Info) -> None:
            method = info.method
            status = info.response.status_code
            handler = info.request.url.path

            if handler == "/rag/api/ask" and method == "POST":
                try:
                    body = await info.request.json()
                    kb_stores = body.get("kbStores", [])
                    kbStores_label = ",".join(kb_stores) if kb_stores else ""  # Avoid empty label
                    TOTAL.labels(method=method, status=status, handler=handler, kbStores=kbStores_label).inc()
                except Exception as e:
                    print(f"Error adding labels to /rag/api/ask: {e}")

            if handler == "/rag/api/upload" and method == "POST":
                try:
                    form_data = await info.request.form()
                    kbname = form_data.get('kbname')
                    kbStores_label = info.request.state.kbStores  # Ensure you set kbStores correctly
                    if kbname != "personal":
                        TOTAL.labels(method=method, status=status, handler=handler, kbStores=kbStores_label).inc()
                except Exception as e:
                    print(f"Error processing /rag/api/upload: {e}")

        return instrumentation

    except ValueError as e:
        if not is_duplicated_time_series(e):
            raise e

    return None

# Attach the instrumentation
instrumentator = Instrumentator()
instrumentator.instrument(app).add(add_kb_stores_label()).expose(app)

@app.post("/rag/api/ask")
async def ask_kb(request: Request, ask_request: AskRequest):
    """
    Endpoint to receive knowledge base stores.
    """
    try:
        request.state.kbStores = ask_request.kbStores  # Set kbStores
        print(f"Received kbStores: {request.state.kbStores}")  # Debug log
        return {"message": "Successfully received kbStores!"}
    except Exception as e:
        print(f"Error processing /rag/api/ask: {e}")
        raise HTTPException(status_code=400, detail="Bad request.")

@app.post("/rag/api/upload")
async def upload_kb(
    request: Request,
    kbname: str = Form(...),  # Include kbname as a form field
    file: UploadFile = File(...)
):
    # Check if file is uploaded
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    # Check if kbStores exists in the request state
    kbStores_label = getattr(request.state, 'kbStores', None)

    if kbStores_label is None:
        raise HTTPException(status_code=400, detail="kbStores not set. Please call /rag/api/ask first.")

    print(f"DEBUG: kbStores label in upload: {kbStores_label}")  # Debug log

    # If needed, log the filename for further debugging
    print(f"DEBUG: Uploaded file: {file.filename}")

    # Increment the counter for upload
    return {"message": f"File '{file.filename}' uploaded successfully!"}
