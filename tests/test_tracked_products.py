"""
Tests for Tracked Products API
"""
import pytest
from fastapi.testclient import TestClient

from app.models import TrackedProduct, Platform, AlertStatus


class TestTrackedProductsCRUD:
    """Test CRUD operations for tracked products"""
    
    def test_list_products_empty(self, client: TestClient):
        """Test listing products when none exist"""
        response = client.get("/api/v1/tracked-products")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_list_products_with_auth(self, client: TestClient, auth_headers: dict, sample_products):
        """Test listing products for authenticated user"""
        response = client.get("/api/v1/tracked-products", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
    
    def test_create_product(self, client: TestClient, mock_price_fetcher):
        """Test creating a new tracked product"""
        payload = {
            "platform": "amazon",
            "product_id": "B08N5WRWNW",
            "target_price": 79.99,
            "currency": "USD",
        }
        
        response = client.post("/api/v1/tracked-products", json=payload)
        assert response.status_code == 201
        
        data = response.json()
        assert data["platform"] == "amazon"
        assert data["target_price"] == 79.99
        assert data["alert_status"] == "pending"
    
    def test_create_product_with_auth(self, client: TestClient, auth_headers: dict, mock_price_fetcher):
        """Test creating product for authenticated user"""
        payload = {
            "platform": "ebay",
            "product_id": "123456789",
            "target_price": 49.99,
        }
        
        response = client.post("/api/v1/tracked-products", json=payload, headers=auth_headers)
        assert response.status_code == 201
        
        data = response.json()
        assert data["platform"] == "ebay"
    
    def test_create_product_invalid_platform(self, client: TestClient):
        """Test creating product with invalid platform"""
        payload = {
            "platform": "invalid",
            "product_id": "test123",
            "target_price": 50.00,
        }
        
        response = client.post("/api/v1/tracked-products", json=payload)
        assert response.status_code == 422
    
    def test_get_product(self, client: TestClient, auth_headers: dict, sample_product):
        """Test getting a specific product"""
        response = client.get(f"/api/v1/tracked-products/{sample_product.id}", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == sample_product.id
        assert data["title"] == sample_product.title
    
    def test_get_product_not_found(self, client: TestClient):
        """Test getting non-existent product"""
        response = client.get("/api/v1/tracked-products/9999")
        assert response.status_code == 404
    
    def test_update_product(self, client: TestClient, auth_headers: dict, sample_product):
        """Test updating a product"""
        payload = {"target_price": 59.99}
        
        response = client.patch(
            f"/api/v1/tracked-products/{sample_product.id}",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["target_price"] == 59.99
    
    def test_delete_product(self, client: TestClient, auth_headers: dict, sample_product):
        """Test deleting a product"""
        response = client.delete(
            f"/api/v1/tracked-products/{sample_product.id}",
            headers=auth_headers
        )
        assert response.status_code == 204
        
        # Verify deleted
        response = client.get(f"/api/v1/tracked-products/{sample_product.id}")
        assert response.status_code == 404


class TestProductFiltering:
    """Test filtering and pagination"""
    
    def test_filter_by_platform(self, client: TestClient, auth_headers: dict, sample_products):
        """Test filtering products by platform"""
        response = client.get(
            "/api/v1/tracked-products?platform=amazon",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["platform"] == "amazon"
    
    def test_filter_by_active(self, client: TestClient, auth_headers: dict, sample_products):
        """Test filtering by active status"""
        response = client.get(
            "/api/v1/tracked-products?is_active=true",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert all(p["is_active"] for p in data)
    
    def test_pagination(self, client: TestClient, auth_headers: dict, sample_products):
        """Test pagination"""
        response = client.get(
            "/api/v1/tracked-products?skip=0&limit=2",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


class TestProductActions:
    """Test product actions like price check and alert reset"""
    
    def test_check_price(self, client: TestClient, auth_headers: dict, sample_product, mock_price_fetcher):
        """Test manual price check"""
        response = client.post(
            f"/api/v1/tracked-products/{sample_product.id}/check",
            headers=auth_headers
        )
        assert response.status_code == 200
    
    def test_reset_alert(self, client: TestClient, auth_headers: dict, sample_product, db):
        """Test resetting alert status"""
        # First trigger the alert
        sample_product.alert_status = AlertStatus.TRIGGERED
        db.commit()
        
        response = client.post(
            f"/api/v1/tracked-products/{sample_product.id}/reset-alert",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["alert_status"] == "pending"
