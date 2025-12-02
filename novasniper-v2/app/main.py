"""
NovaSniper v2.0 - Price Tracking Service
Main FastAPI Application
"""
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import create_tables, get_db, DatabaseManager
from app.models import APIRequestLog
from app.schemas import HealthCheck
from app.services.scheduler import scheduler_service

# Import routers
from app.routers import tracked_products, auth, watchlists, notifications, webhooks, admin

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Initialize database
    create_tables()
    logger.info("Database tables created")
    
    # Start scheduler
    scheduler_service.start()
    logger.info("Scheduler started")
    
    yield
    
    # Shutdown
    scheduler_service.stop()
    logger.info("Scheduler stopped")
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-platform price tracking service with alerts and notifications",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log API requests for monitoring"""
    start_time = time.time()
    
    response = await call_next(request)
    
    # Calculate response time
    process_time = (time.time() - start_time) * 1000
    
    # Log to database (skip for static files and health checks)
    if not request.url.path.startswith("/static") and request.url.path != "/health":
        try:
            # Get user from request state if authenticated
            user_id = getattr(request.state, "user_id", None)
            api_key = request.headers.get(settings.API_KEY_HEADER)
            
            # Use a new session for logging
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                log = APIRequestLog(
                    user_id=user_id,
                    api_key=api_key[:10] + "..." if api_key else None,
                    endpoint=request.url.path,
                    method=request.method,
                    status_code=response.status_code,
                    response_time_ms=process_time,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent", "")[:500],
                )
                db.add(log)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to log request: {e}")
    
    # Add response time header
    response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
    
    return response


# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(tracked_products.router, prefix="/api/v1")
app.include_router(watchlists.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


# Health check endpoint
@app.get("/health", response_model=HealthCheck, tags=["System"])
async def health_check():
    """Health check endpoint for monitoring"""
    db_status = "connected" if DatabaseManager.health_check() else "disconnected"
    scheduler_status = "running" if scheduler_service.is_running() else "stopped"
    
    return HealthCheck(
        status="healthy" if db_status == "connected" else "degraded",
        version=settings.APP_VERSION,
        database=db_status,
        scheduler=scheduler_status,
        timestamp=datetime.utcnow(),
    )


# Root endpoint
@app.get("/", tags=["System"])
async def root():
    """Root endpoint with API info"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "dashboard": "/dashboard",
    }


# Simple dashboard (HTML)
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NovaSniper - Price Tracker</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        .gradient-bg { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <nav class="gradient-bg text-white p-4 shadow-lg">
        <div class="container mx-auto flex justify-between items-center">
            <h1 class="text-2xl font-bold">🎯 NovaSniper</h1>
            <div class="space-x-4">
                <a href="/docs" class="hover:underline">API Docs</a>
                <a href="/health" class="hover:underline">Health</a>
            </div>
        </div>
    </nav>
    
    <main class="container mx-auto p-6">
        <div id="app">
            <!-- Stats Cards -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div class="bg-white rounded-lg shadow p-6">
                    <div class="text-gray-500 text-sm">Tracked Products</div>
                    <div class="text-3xl font-bold text-indigo-600" id="stat-products">-</div>
                </div>
                <div class="bg-white rounded-lg shadow p-6">
                    <div class="text-gray-500 text-sm">Pending Alerts</div>
                    <div class="text-3xl font-bold text-yellow-600" id="stat-alerts">-</div>
                </div>
                <div class="bg-white rounded-lg shadow p-6">
                    <div class="text-gray-500 text-sm">Price Checks Today</div>
                    <div class="text-3xl font-bold text-green-600" id="stat-checks">-</div>
                </div>
                <div class="bg-white rounded-lg shadow p-6">
                    <div class="text-gray-500 text-sm">Scheduler Status</div>
                    <div class="text-3xl font-bold" id="stat-scheduler">-</div>
                </div>
            </div>
            
            <!-- Add Product Form -->
            <div class="bg-white rounded-lg shadow p-6 mb-8">
                <h2 class="text-xl font-bold mb-4">Track New Product</h2>
                <form id="add-product-form" class="space-y-4">
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700">Platform</label>
                            <select id="platform" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2 border">
                                <option value="amazon">Amazon</option>
                                <option value="ebay">eBay</option>
                                <option value="walmart">Walmart</option>
                                <option value="bestbuy">Best Buy</option>
                                <option value="target">Target</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700">Product URL or ID</label>
                            <input type="text" id="product-id" placeholder="https://amazon.com/dp/..." class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2 border">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700">Target Price ($)</label>
                            <input type="number" id="target-price" step="0.01" min="0" placeholder="99.99" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2 border">
                        </div>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Notification Email (optional)</label>
                        <input type="email" id="notify-email" placeholder="you@example.com" class="mt-1 block w-full md:w-1/3 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2 border">
                    </div>
                    <button type="submit" class="gradient-bg text-white px-6 py-2 rounded-md hover:opacity-90 transition">
                        Add Product
                    </button>
                </form>
            </div>
            
            <!-- Products List -->
            <div class="bg-white rounded-lg shadow p-6">
                <h2 class="text-xl font-bold mb-4">Tracked Products</h2>
                <div id="products-list" class="space-y-4">
                    <p class="text-gray-500">Loading...</p>
                </div>
            </div>
        </div>
    </main>
    
    <script>
        const API_BASE = '/api/v1';
        
        // Load stats
        async function loadStats() {
            try {
                const response = await fetch('/health');
                const data = await response.json();
                document.getElementById('stat-scheduler').textContent = data.scheduler;
                document.getElementById('stat-scheduler').className = 
                    'text-3xl font-bold ' + (data.scheduler === 'running' ? 'text-green-600' : 'text-red-600');
            } catch (e) {
                console.error('Failed to load stats:', e);
            }
        }
        
        // Load products
        async function loadProducts() {
            try {
                const response = await fetch(`${API_BASE}/tracked-products`);
                const products = await response.json();
                
                document.getElementById('stat-products').textContent = products.length;
                document.getElementById('stat-alerts').textContent = 
                    products.filter(p => p.alert_status === 'pending').length;
                
                const container = document.getElementById('products-list');
                
                if (products.length === 0) {
                    container.innerHTML = '<p class="text-gray-500">No products tracked yet. Add one above!</p>';
                    return;
                }
                
                container.innerHTML = products.map(p => `
                    <div class="border rounded-lg p-4 flex justify-between items-center hover:bg-gray-50">
                        <div class="flex items-center space-x-4">
                            ${p.image_url ? `<img src="${p.image_url}" class="w-16 h-16 object-cover rounded">` : '<div class="w-16 h-16 bg-gray-200 rounded flex items-center justify-center">📦</div>'}
                            <div>
                                <div class="font-medium">${p.title || 'Loading...'}</div>
                                <div class="text-sm text-gray-500">${p.platform} • Target: $${p.target_price}</div>
                            </div>
                        </div>
                        <div class="text-right">
                            <div class="text-2xl font-bold ${p.current_price && p.current_price <= p.target_price ? 'text-green-600' : 'text-gray-800'}">
                                ${p.current_price ? '$' + p.current_price.toFixed(2) : 'Checking...'}
                            </div>
                            <div class="text-sm">
                                <span class="px-2 py-1 rounded text-xs ${
                                    p.alert_status === 'triggered' ? 'bg-green-100 text-green-800' :
                                    p.alert_status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                                    'bg-gray-100 text-gray-800'
                                }">${p.alert_status}</span>
                            </div>
                        </div>
                        <div class="ml-4 space-x-2">
                            <button onclick="checkPrice(${p.id})" class="text-blue-600 hover:text-blue-800">Check</button>
                            <button onclick="deleteProduct(${p.id})" class="text-red-600 hover:text-red-800">Delete</button>
                        </div>
                    </div>
                `).join('');
            } catch (e) {
                console.error('Failed to load products:', e);
                document.getElementById('products-list').innerHTML = '<p class="text-red-500">Failed to load products</p>';
            }
        }
        
        // Add product
        document.getElementById('add-product-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const data = {
                platform: document.getElementById('platform').value,
                product_id: document.getElementById('product-id').value,
                target_price: parseFloat(document.getElementById('target-price').value),
                notify_email: document.getElementById('notify-email').value || null,
            };
            
            try {
                const response = await fetch(`${API_BASE}/tracked-products`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data),
                });
                
                if (response.ok) {
                    document.getElementById('add-product-form').reset();
                    loadProducts();
                } else {
                    const error = await response.json();
                    alert('Error: ' + (error.detail || 'Failed to add product'));
                }
            } catch (e) {
                alert('Error: ' + e.message);
            }
        });
        
        // Check price
        async function checkPrice(id) {
            try {
                await fetch(`${API_BASE}/tracked-products/${id}/check`, { method: 'POST' });
                loadProducts();
            } catch (e) {
                alert('Error checking price');
            }
        }
        
        // Delete product
        async function deleteProduct(id) {
            if (!confirm('Delete this product?')) return;
            
            try {
                await fetch(`${API_BASE}/tracked-products/${id}`, { method: 'DELETE' });
                loadProducts();
            } catch (e) {
                alert('Error deleting product');
            }
        }
        
        // Initial load
        loadStats();
        loadProducts();
        
        // Auto-refresh every 30 seconds
        setInterval(() => {
            loadStats();
            loadProducts();
        }, 30000);
    </script>
</body>
</html>
"""


@app.get("/dashboard", response_class=HTMLResponse, tags=["System"])
async def dashboard():
    """Simple web dashboard"""
    return DASHBOARD_HTML


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": "Not found", "path": request.url.path},
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.exception(f"Internal error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
