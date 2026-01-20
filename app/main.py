"""
Bear GitOps Payment Service

A demo payment service that simulates latency based on configuration.
When connection_pool_size is too low, it introduces artificial latency
to simulate the real-world effect of connection pool exhaustion.
"""

import asyncio
import os
import random
import time
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel

# Load configuration
CONFIG_PATH = Path(__file__).parent.parent / "config" / "payment-service.yaml"


def load_config():
    """Load configuration from YAML file."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f)
    return {
        "database": {"connection_pool_size": 50},
        "service": {"timeout_ms": 100},
    }


config = load_config()

# Setup tracing
resource = Resource.create({"service.name": "payment-service"})
provider = TracerProvider(resource=resource)

otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317")
try:
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
except Exception:
    pass  # Tracing optional

trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Reload config on startup."""
    global config
    config = load_config()
    print(f"🐻 Bear GitOps Payment Service starting...")
    print(f"   Config: {CONFIG_PATH}")
    print(f"   Pool size: {config.get('database', {}).get('connection_pool_size', 'unknown')}")
    yield


app = FastAPI(
    title="Bear GitOps Payment Service",
    description="Demo payment service for AutoSRE",
    version="1.0.0",
    lifespan=lifespan,
)

FastAPIInstrumentor.instrument_app(app)


class PaymentRequest(BaseModel):
    amount: float
    currency: str = "USD"
    customer_id: str
    order_id: str


class PaymentResponse(BaseModel):
    transaction_id: str
    status: str
    message: str
    processing_time_ms: float


def calculate_latency() -> float:
    """
    Calculate artificial latency based on connection pool size.
    
    Lower pool size = higher latency (simulating connection contention)
    """
    pool_size = config.get("database", {}).get("connection_pool_size", 50)
    
    # Simulate connection pool exhaustion
    # With pool_size=2, we get ~2-5 second delays
    # With pool_size=50, we get ~10-50ms delays
    if pool_size < 10:
        # Severe contention - very high latency
        base_latency = 2000 + random.uniform(0, 3000)  # 2-5 seconds
    elif pool_size < 25:
        # Moderate contention
        base_latency = 500 + random.uniform(0, 1000)  # 0.5-1.5 seconds
    else:
        # Healthy pool size
        base_latency = 10 + random.uniform(0, 40)  # 10-50ms
    
    return base_latency


@app.get("/health")
async def health():
    """Health check endpoint."""
    pool_size = config.get("database", {}).get("connection_pool_size", 50)
    status = "healthy" if pool_size >= 25 else "degraded"
    
    return {
        "status": status,
        "service": "payment-service",
        "version": config.get("service", {}).get("version", "1.0.0"),
        "config": {
            "connection_pool_size": pool_size,
            "warning": "Pool size too low!" if pool_size < 25 else None,
        },
    }


@app.get("/config")
async def get_config():
    """Return current configuration (for debugging)."""
    return config


@app.post("/reload")
async def reload_config():
    """Reload configuration from file."""
    global config
    config = load_config()
    return {"status": "reloaded", "config": config}


@app.post("/api/v1/payments", response_model=PaymentResponse)
async def process_payment(payment: PaymentRequest):
    """
    Process a payment transaction.
    
    Latency is affected by the database.connection_pool_size setting.
    Low pool size causes connection contention and high latency.
    """
    with tracer.start_as_current_span("process_payment") as span:
        start_time = time.time()
        
        # Add span attributes
        span.set_attribute("payment.amount", payment.amount)
        span.set_attribute("payment.currency", payment.currency)
        span.set_attribute("payment.customer_id", payment.customer_id)
        span.set_attribute("payment.order_id", payment.order_id)
        
        pool_size = config.get("database", {}).get("connection_pool_size", 50)
        span.set_attribute("db.connection_pool_size", pool_size)
        
        # Simulate database operation with latency based on pool size
        with tracer.start_as_current_span("acquire_db_connection") as db_span:
            latency = calculate_latency()
            db_span.set_attribute("latency_ms", latency)
            
            if pool_size < 10:
                db_span.set_attribute("warning", "connection_pool_exhausted")
            
            await asyncio.sleep(latency / 1000)
        
        # Simulate payment processing
        with tracer.start_as_current_span("payment_processor"):
            await asyncio.sleep(0.01)  # 10ms for actual processing
        
        processing_time = (time.time() - start_time) * 1000
        span.set_attribute("processing_time_ms", processing_time)
        
        # Generate transaction ID
        transaction_id = f"txn_{payment.order_id}_{int(time.time())}"
        
        return PaymentResponse(
            transaction_id=transaction_id,
            status="success",
            message="Payment processed successfully",
            processing_time_ms=processing_time,
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
