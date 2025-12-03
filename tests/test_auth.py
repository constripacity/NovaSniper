"""
Tests for Authentication API
"""
import pytest
from fastapi.testclient import TestClient


class TestRegistration:
    """Test user registration"""
    
    def test_register_user(self, client: TestClient):
        """Test successful user registration"""
        payload = {
            "email": "newuser@example.com",
            "password": "securepassword123",
            "username": "newuser",
        }
        
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201
        
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["username"] == "newuser"
        assert "api_key" in data
        assert "password" not in data
        assert "hashed_password" not in data
    
    def test_register_duplicate_email(self, client: TestClient, test_user):
        """Test registration with existing email"""
        payload = {
            "email": test_user.email,
            "password": "anotherpassword123",
        }
        
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]
    
    def test_register_weak_password(self, client: TestClient):
        """Test registration with weak password"""
        payload = {
            "email": "weak@example.com",
            "password": "short",
        }
        
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422


class TestLogin:
    """Test user login"""
    
    def test_login_success(self, client: TestClient, test_user):
        """Test successful login"""
        payload = {
            "email": "test@example.com",
            "password": "testpassword123",
        }
        
        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
    
    def test_login_wrong_password(self, client: TestClient, test_user):
        """Test login with wrong password"""
        payload = {
            "email": "test@example.com",
            "password": "wrongpassword",
        }
        
        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 401
    
    def test_login_nonexistent_user(self, client: TestClient):
        """Test login with non-existent user"""
        payload = {
            "email": "nobody@example.com",
            "password": "somepassword",
        }
        
        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 401


class TestAPIKeyAuth:
    """Test API key authentication"""
    
    def test_auth_with_api_key(self, client: TestClient, test_user, auth_headers):
        """Test authentication using API key"""
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["email"] == test_user.email
    
    def test_auth_invalid_api_key(self, client: TestClient):
        """Test authentication with invalid API key"""
        headers = {"X-API-Key": "invalid-key"}
        
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
    
    def test_auth_no_credentials(self, client: TestClient):
        """Test accessing protected endpoint without credentials"""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401


class TestUserManagement:
    """Test user profile management"""
    
    def test_get_current_user(self, client: TestClient, auth_headers, test_user):
        """Test getting current user info"""
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["email"] == test_user.email
        assert "tracked_products_count" in data
        assert "active_alerts_count" in data
    
    def test_update_user(self, client: TestClient, auth_headers):
        """Test updating user profile"""
        payload = {
            "username": "updatedname",
            "timezone": "America/New_York",
        }
        
        response = client.patch("/api/v1/auth/me", json=payload, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["username"] == "updatedname"
        assert data["timezone"] == "America/New_York"
    
    def test_regenerate_api_key(self, client: TestClient, auth_headers, test_user):
        """Test regenerating API key"""
        old_key = test_user.api_key
        
        response = client.post("/api/v1/auth/api-key/regenerate", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["api_key"] != old_key
    
    def test_delete_account(self, client: TestClient, auth_headers):
        """Test deleting user account"""
        response = client.delete("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 204
        
        # Verify can't login anymore
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 401


class TestAdminAuth:
    """Test admin-only endpoints"""
    
    def test_admin_access(self, client: TestClient, admin_headers):
        """Test admin accessing admin endpoint"""
        response = client.get("/api/v1/admin/dashboard", headers=admin_headers)
        assert response.status_code == 200
    
    def test_non_admin_denied(self, client: TestClient, auth_headers):
        """Test non-admin accessing admin endpoint"""
        response = client.get("/api/v1/admin/dashboard", headers=auth_headers)
        assert response.status_code == 403
    
    def test_unauthenticated_denied(self, client: TestClient):
        """Test unauthenticated access to admin endpoint"""
        response = client.get("/api/v1/admin/dashboard")
        assert response.status_code == 401
