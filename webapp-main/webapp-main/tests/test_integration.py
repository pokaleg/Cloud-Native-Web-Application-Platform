import pytest
import random
import requests
from requests.auth import HTTPBasicAuth
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8080"

def get_unique_email():
    """Generate unique email"""
    return f"test_{int(time.time() * 1000000)}_{random.randint(1000, 9999)}@example.com"

#
# ============================================================================
# HEALTH CHECK ENDPOINT - GET /healthz
# Status Codes: 200, 400, 405, 503
# ============================================================================
#

class TestHealthCheckEndpoint:
    """Test /healthz endpoint according to Swagger specification"""
    
    # ===== 200 OK =====
    def test_healthz_200_success(self):
        """
        Status: 200 - Service is healthy and database connection is successful
        Headers: Cache-Control, Pragma
        """
        response = requests.get(f"{BASE_URL}/healthz")
        
        assert response.status_code == 200
        assert response.text == ""  # No body
        
        # Verify required headers
        cache_control = response.headers.get("Cache-Control", "")
        assert "no-cache" in cache_control
        assert "no-store" in cache_control
        assert "must-revalidate" in cache_control
        assert response.headers.get("Pragma") == "no-cache"
    
    # ===== 400 Bad Request =====
    def test_healthz_400_with_body(self):
        """
        Status: 400 - Bad Request
        Reason: Request contains body (not allowed)
        """
        response = requests.get(
            f"{BASE_URL}/healthz",
            data=json.dumps({"test": "data"}),
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
    
    def test_healthz_400_with_query_params(self):
        """
        Status: 400 - Bad Request
        Reason: Request contains query parameters (not allowed)
        """
        response = requests.get(f"{BASE_URL}/healthz?param=value")
        assert response.status_code == 400
    
    def test_healthz_400_with_multiple_query_params(self):
        """
        Status: 400 - Bad Request
        Reason: Multiple query parameters
        """
        response = requests.get(f"{BASE_URL}/healthz?param1=value1&param2=value2")
        assert response.status_code == 400
    
    # ===== 405 Method Not Allowed =====
    def test_healthz_405_post_method(self):
        """
        Status: 405 - Method Not Allowed
        Reason: POST not supported, only GET allowed
        """
        response = requests.post(f"{BASE_URL}/healthz")
        assert response.status_code == 405
    
    def test_healthz_405_put_method(self):
        """
        Status: 405 - Method Not Allowed
        Reason: PUT not supported
        """
        response = requests.put(f"{BASE_URL}/healthz")
        assert response.status_code == 405
    
    def test_healthz_405_delete_method(self):
        """
        Status: 405 - Method Not Allowed
        Reason: DELETE not supported
        """
        response = requests.delete(f"{BASE_URL}/healthz")
        assert response.status_code == 405
    
    def test_healthz_405_patch_method(self):
        """
        Status: 405 - Method Not Allowed
        Reason: PATCH not supported
        """
        response = requests.patch(f"{BASE_URL}/healthz")
        assert response.status_code == 405
    
    def test_healthz_405_head_method(self):
        """
        Status: 405 - Method Not Allowed
        Reason: HEAD not supported
        """
        response = requests.head(f"{BASE_URL}/healthz")
        assert response.status_code == 405
    
    def test_healthz_405_options_method(self):
        """
        Status: 405 - Method Not Allowed
        Reason: OPTIONS not supported
        """
        response = requests.options(f"{BASE_URL}/healthz")
        assert response.status_code == 405
    
    # ===== 503 Service Unavailable =====
    # Note: This is difficult to test without stopping the database
    # You would need to stop PostgreSQL to trigger this


# ============================================================================
# USER CREATION ENDPOINT - POST /v1/user
# Status Codes: 201, 400, 409, 415
# ============================================================================

class TestUserCreationEndpoint:
    """Test POST /v1/user endpoint according to Swagger specification"""
    
    # ===== 201 Created =====
    def test_user_creation_201_success(self):
        """
        Status: 201 - User created successfully
        Validates: Response body structure, Location header
        """
        user_data = {
            "username": get_unique_email(),
            "password": "SecurePass123!",
            "first_name": "Jane",
            "last_name": "Doe"
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        
        assert response.status_code == 201
        assert response.headers.get("Location") == "/v1/user/self"
        
        data = response.json()
        
        # Verify required fields are present
        assert "id" in data
        assert "username" in data
        assert "first_name" in data
        assert "last_name" in data
        assert "account_created" in data
        assert "account_updated" in data
        
        # Verify field values
        assert data["username"] == user_data["username"].lower()
        assert data["first_name"] == user_data["first_name"]
        assert data["last_name"] == user_data["last_name"]
        
        # Verify password is NOT in response
        assert "password" not in data
        
        # Verify timestamps are valid ISO 8601
        datetime.fromisoformat(data["account_created"].replace("Z", "+00:00"))
        datetime.fromisoformat(data["account_updated"].replace("Z", "+00:00"))
    
    def test_user_creation_201_email_case_insensitive(self):
        """
        Status: 201 - User created with uppercase email
        Validates: Email stored as lowercase
        """
        user_data = {
            "username": get_unique_email().upper(),
            "password": "SecurePass123!",
            "first_name": "John",
            "last_name": "Smith"
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == user_data["username"].lower()
    
    def test_user_creation_201_minimal_password(self):
        """
        Status: 201 - User created with exactly 8 character password
        Validates: Minimum password length boundary
        """
        user_data = {
            "username": get_unique_email(),
            "password": "Pass123!",  # Exactly 8 characters
            "first_name": "Alice",
            "last_name": "Brown"
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response.status_code == 201
    
    def test_user_creation_201_maximum_password(self):
        """
        Status: 201 - User created with 128 character password
        Validates: Maximum password length boundary
        """
        user_data = {
            "username": get_unique_email(),
            "password": "P" * 128,  # Exactly 128 characters
            "first_name": "Bob",
            "last_name": "Wilson"
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response.status_code == 201
    
    def test_user_creation_201_maximum_name_length(self):
        """
        Status: 201 - User created with 100 character names
        Validates: Maximum name length boundary
        """
        user_data = {
            "username": get_unique_email(),
            "password": "SecurePass123!",
            "first_name": "A" * 100,  # Maximum 100 characters
            "last_name": "B" * 100
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response.status_code == 201
    
    def test_user_creation_201_special_characters_in_name(self):
        """
        Status: 201 - User created with special characters in name
        Validates: Name field accepts special characters
        """
        user_data = {
            "username": get_unique_email(),
            "password": "SecurePass123!",
            "first_name": "Jean-Pierre",
            "last_name": "O'Neill"
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response.status_code == 201
    
    # ===== 400 Bad Request =====
    def test_user_creation_400_invalid_email_format(self):
        """
        Status: 400 - Validation Error
        Reason: Username is not a valid email format
        Validates: Error response structure (error, message, timestamp, path)
        """
        user_data = {
            "username": "not-an-email",
            "password": "SecurePass123!",
            "first_name": "John",
            "last_name": "Doe"
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        
        assert response.status_code == 400
        
        data = response.json()
        assert data["error"] == "Validation Error"
        assert "email" in data["message"].lower() or "username" in data["message"].lower()
        assert "timestamp" in data
        assert data["path"] == "/v1/user"
    
    def test_user_creation_400_missing_username(self):
        """
        Status: 400 - Validation Error
        Reason: Missing required field 'username'
        """
        user_data = {
            "password": "SecurePass123!",
            "first_name": "John",
            "last_name": "Doe"
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response.status_code == 400
    
    def test_user_creation_400_missing_password(self):
        """
        Status: 400 - Validation Error
        Reason: Missing required field 'password'
        """
        user_data = {
            "username": get_unique_email(),
            "first_name": "John",
            "last_name": "Doe"
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response.status_code == 400
    
    def test_user_creation_400_missing_first_name(self):
        """
        Status: 400 - Validation Error
        Reason: Missing required field 'first_name'
        """
        user_data = {
            "username": get_unique_email(),
            "password": "SecurePass123!",
            "last_name": "Doe"
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response.status_code == 400
    
    def test_user_creation_400_missing_last_name(self):
        """
        Status: 400 - Validation Error
        Reason: Missing required field 'last_name'
        """
        user_data = {
            "username": get_unique_email(),
            "password": "SecurePass123!",
            "first_name": "John"
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response.status_code == 400
    
    def test_user_creation_400_password_too_short(self):
        """
        Status: 400 - Validation Error
        Reason: Password less than 8 characters
        """
        user_data = {
            "username": get_unique_email(),
            "password": "Pass12",  # Only 6 characters
            "first_name": "John",
            "last_name": "Doe"
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response.status_code == 400
        
        data = response.json()
        assert "password" in data["message"].lower() or "8" in data["message"]
    
    def test_user_creation_400_password_too_long(self):
        """
        Status: 400 - Validation Error
        Reason: Password exceeds 128 characters
        """
        user_data = {
            "username": get_unique_email(),
            "password": "P" * 129,  # 129 characters
            "first_name": "John",
            "last_name": "Doe"
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response.status_code == 400
    
    def test_user_creation_400_first_name_too_long(self):
        """
        Status: 400 - Validation Error
        Reason: first_name exceeds 100 characters
        """
        user_data = {
            "username": get_unique_email(),
            "password": "SecurePass123!",
            "first_name": "A" * 101,  # 101 characters
            "last_name": "Doe"
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response.status_code == 400
    
    def test_user_creation_400_last_name_too_long(self):
        """
        Status: 400 - Validation Error
        Reason: last_name exceeds 100 characters
        """
        user_data = {
            "username": get_unique_email(),
            "password": "SecurePass123!",
            "first_name": "John",
            "last_name": "D" * 101  # 101 characters
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response.status_code == 400
    
    def test_user_creation_400_empty_first_name(self):
        """
        Status: 400 - Validation Error
        Reason: first_name is empty string
        """
        user_data = {
            "username": get_unique_email(),
            "password": "SecurePass123!",
            "first_name": "",
            "last_name": "Doe"
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response.status_code == 400
    
    def test_user_creation_400_empty_last_name(self):
        """
        Status: 400 - Validation Error
        Reason: last_name is empty string
        """
        user_data = {
            "username": get_unique_email(),
            "password": "SecurePass123!",
            "first_name": "John",
            "last_name": ""
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response.status_code == 400
    
    def test_user_creation_400_malformed_json(self):
        """
        Status: 400 - Validation Error
        Reason: Malformed JSON in request body
        """
        response = requests.post(
            f"{BASE_URL}/v1/user",
            data="{'invalid': json}",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
    
    def test_user_creation_400_extra_fields(self):
        """
        Status: 400 - Validation Error
        Reason: Extra fields not allowed (id, account_created, etc.)
        """
        user_data = {
            "username": get_unique_email(),
            "password": "SecurePass123!",
            "first_name": "John",
            "last_name": "Doe",
            "id": "fake-id",  # Not allowed
            "account_created": "2024-01-01T00:00:00Z"  # Not allowed
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response.status_code == 400
    
    def test_user_creation_400_empty_request_body(self):
        """
        Status: 400 - Validation Error
        Reason: Empty request body
        """
        response = requests.post(f"{BASE_URL}/v1/user", json={})
        assert response.status_code == 400
    
    # ===== 409 Conflict =====
    def test_user_creation_409_duplicate_email(self):
        """
        Status: 409 - Conflict
        Reason: User with this email address already exists
        Validates: Error response indicates conflict
        """
        # Create first user
        user_data = {
            "username": f"duplicate_{int(time.time())}@example.com",
            "password": "SecurePass123!",
            "first_name": "John",
            "last_name": "Doe"
        }
        
        response1 = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response1.status_code == 201
        
        # Try to create duplicate
        response2 = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        
        assert response2.status_code == 409
        
        data = response2.json()
        assert data["error"] == "Conflict"
        assert "already exists" in data["message"].lower()
        assert "timestamp" in data
        assert data["path"] == "/v1/user"
    
    def test_user_creation_409_duplicate_email_different_case(self):
        """
        Status: 409 - Conflict
        Reason: Email already exists (case insensitive check)
        """
        # Create first user with lowercase
        user_data1 = {
            "username": f"case_{int(time.time())}@example.com",
            "password": "SecurePass123!",
            "first_name": "John",
            "last_name": "Doe"
        }
        
        response1 = requests.post(f"{BASE_URL}/v1/user", json=user_data1)
        assert response1.status_code == 201
        
        # Try with uppercase
        user_data2 = {
            "username": user_data1["username"].upper(),
            "password": "SecurePass123!",
            "first_name": "Jane",
            "last_name": "Smith"
        }
        
        response2 = requests.post(f"{BASE_URL}/v1/user", json=user_data2)
        assert response2.status_code == 409
    
    # ===== 415 Unsupported Media Type =====
    def test_user_creation_415_wrong_content_type(self):
        """
        Status: 415 - Unsupported Media Type
        Reason: Content-Type is not application/json
        """
        user_data = {
            "username": get_unique_email(),
            "password": "SecurePass123!",
            "first_name": "John",
            "last_name": "Doe"
        }
        
        response = requests.post(
            f"{BASE_URL}/v1/user",
            data=json.dumps(user_data),
            headers={"Content-Type": "text/plain"}
        )
        
        assert response.status_code == 415
    
    def test_user_creation_415_xml_content_type(self):
        """
        Status: 415 - Unsupported Media Type
        Reason: Content-Type is application/xml
        """
        response = requests.post(
            f"{BASE_URL}/v1/user",
            data="<user><username>test@example.com</username></user>",
            headers={"Content-Type": "application/xml"}
        )
        
        assert response.status_code == 415


# ============================================================================
# USER RETRIEVAL ENDPOINT - GET /v1/user/self
# Status Codes: 200, 401, 403, 404
# ============================================================================

class TestUserRetrievalEndpoint:
    """Test GET /v1/user/self endpoint according to Swagger specification"""
    
    @pytest.fixture
    def created_user(self):
        """Fixture to create a user for testing"""
        user_data = {
            "username": get_unique_email(),  # Use helper function
            "password": "SecurePass123!",
            "first_name": "Jane",
            "last_name": "Doe"
        }
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response.status_code == 201, f"Failed to create user: {response.text}"
        return user_data
    
    # ===== 200 OK =====
    def test_user_retrieval_200_success(self, created_user):
        """
        Status: 200 - User information retrieved successfully
        Validates: Response body structure, no password in response
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        response = requests.get(f"{BASE_URL}/v1/user/self", auth=auth)
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify required fields
        assert "id" in data
        assert "username" in data
        assert "first_name" in data
        assert "last_name" in data
        assert "account_created" in data
        assert "account_updated" in data
        
        # Verify values
        assert data["username"] == created_user["username"].lower()
        assert data["first_name"] == created_user["first_name"]
        assert data["last_name"] == created_user["last_name"]
        
        # Verify password NOT in response
        assert "password" not in data
    
    def test_user_retrieval_200_timestamps_valid(self, created_user):
        """
        Status: 200 - Verify timestamps are valid ISO 8601 format
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        response = requests.get(f"{BASE_URL}/v1/user/self", auth=auth)
        
        assert response.status_code == 200
        data = response.json()
        
        # Parse timestamps to verify format
        account_created = datetime.fromisoformat(data["account_created"].replace("Z", "+00:00"))
        account_updated = datetime.fromisoformat(data["account_updated"].replace("Z", "+00:00"))
        
        # Verify timestamps are reasonable (not in far future/past)
        now = datetime.now(account_created.tzinfo)
        assert (now - account_created).total_seconds() < 60  # Created within last minute
    
    # ===== 401 Unauthorized =====
    def test_user_retrieval_401_no_authentication(self):
        """
        Status: 401 - Unauthorized
        Reason: Missing authentication credentials
        Validates: WWW-Authenticate header present
        """
        response = requests.get(f"{BASE_URL}/v1/user/self")
        
        assert response.status_code == 401
        
        # Verify WWW-Authenticate header
        assert "WWW-Authenticate" in response.headers
        assert "Basic" in response.headers["WWW-Authenticate"]
        
        # Verify error response structure
        data = response.json()
        assert data["error"] == "Unauthorized"
        assert "authentication" in data["message"].lower() or "credentials" in data["message"].lower()
        assert "timestamp" in data
        assert data["path"] == "/v1/user/self"
    
    def test_user_retrieval_401_invalid_password(self, created_user):
        """
        Status: 401 - Unauthorized
        Reason: Invalid password
        """
        auth = HTTPBasicAuth(created_user["username"], "WrongPassword123!")
        response = requests.get(f"{BASE_URL}/v1/user/self", auth=auth)
        
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers
    
    def test_user_retrieval_401_invalid_username(self):
        """
        Status: 401 - Unauthorized
        Reason: User does not exist
        """
        auth = HTTPBasicAuth("nonexistent@example.com", "Password123!")
        response = requests.get(f"{BASE_URL}/v1/user/self", auth=auth)
        
        assert response.status_code == 401
    
    def test_user_retrieval_401_malformed_credentials(self):
        """
        Status: 401 - Unauthorized
        Reason: Malformed authentication credentials
        """
        response = requests.get(
            f"{BASE_URL}/v1/user/self",
            headers={"Authorization": "Basic invalid_base64"}
        )
        
        assert response.status_code == 401
    
    def test_user_retrieval_401_empty_password(self, created_user):
        """
        Status: 401 - Unauthorized
        Reason: Empty password provided
        """
        auth = HTTPBasicAuth(created_user["username"], "")
        response = requests.get(f"{BASE_URL}/v1/user/self", auth=auth)
        
        assert response.status_code == 401
    
    # ===== 403 Forbidden =====
    
    
    # ===== 404 Not Found =====


# ============================================================================
# USER UPDATE ENDPOINT - PUT /v1/user/self
# Status Codes: 204, 400, 401, 403, 415
# ============================================================================

class TestUserUpdateEndpoint:
    """Test PUT /v1/user/self endpoint according to Swagger specification"""
    
    @pytest.fixture
    def created_user(self):
        """Fixture to create a user for testing"""
        user_data = {
            "username": get_unique_email(),
            "password": "SecurePass123!",
            "first_name": "Jane",
            "last_name": "Doe"
        }
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response.status_code == 201, f"Failed to create user: {response.text}"
        return user_data
    
    # ===== 204 No Content =====
    def test_user_update_204_update_first_name(self, created_user):
        """
        Status: 204 - User updated successfully
        Updates: first_name only
        Validates: No content returned, field updated
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        update_data = {"first_name": "Janet"}
        
        response = requests.put(f"{BASE_URL}/v1/user/self", json=update_data, auth=auth)
        
        assert response.status_code == 204
        assert response.text == ""  # No content
        
        # Verify update by retrieving user
        get_response = requests.get(f"{BASE_URL}/v1/user/self", auth=auth)
        data = get_response.json()
        assert data["first_name"] == "Janet"
        assert data["last_name"] == created_user["last_name"]  # Unchanged
    
    def test_user_update_204_update_last_name(self, created_user):
        """
        Status: 204 - User updated successfully
        Updates: last_name only
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        update_data = {"last_name": "Smith"}
        
        response = requests.put(f"{BASE_URL}/v1/user/self", json=update_data, auth=auth)
        
        assert response.status_code == 204
        
        # Verify update
        get_response = requests.get(f"{BASE_URL}/v1/user/self", auth=auth)
        data = get_response.json()
        assert data["last_name"] == "Smith"
        assert data["first_name"] == created_user["first_name"]  # Unchanged
    
    def test_user_update_204_update_password(self, created_user):
        """
        Status: 204 - User updated successfully
        Updates: password only
        Validates: Can login with new password, old password fails
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        new_password = "NewSecurePass456!"
        update_data = {"password": new_password}
        
        response = requests.put(f"{BASE_URL}/v1/user/self", json=update_data, auth=auth)
        
        assert response.status_code == 204
        
        # Verify old password no longer works
        old_auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        response_old = requests.get(f"{BASE_URL}/v1/user/self", auth=old_auth)
        assert response_old.status_code == 401
        
        # Verify new password works
        new_auth = HTTPBasicAuth(created_user["username"], new_password)
        response_new = requests.get(f"{BASE_URL}/v1/user/self", auth=new_auth)
        assert response_new.status_code == 200
    
    def test_user_update_204_update_all_fields(self, created_user):
        """
        Status: 204 - User updated successfully
        Updates: first_name, last_name, and password
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        new_password = "NewSecurePass789!"
        update_data = {
            "first_name": "Janet",
            "last_name": "Smith",
            "password": new_password
        }
        
        response = requests.put(f"{BASE_URL}/v1/user/self", json=update_data, auth=auth)
        
        assert response.status_code == 204
        
        # Verify all updates with new password
        new_auth = HTTPBasicAuth(created_user["username"], new_password)
        get_response = requests.get(f"{BASE_URL}/v1/user/self", auth=new_auth)
        data = get_response.json()
        assert data["first_name"] == "Janet"
        assert data["last_name"] == "Smith"
    
    def test_user_update_204_account_updated_timestamp_changes(self, created_user):
        """
        Status: 204 - Verify account_updated timestamp changes
        Validates: account_updated is newer than account_created after update
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        
        # Get original timestamps
        get_response1 = requests.get(f"{BASE_URL}/v1/user/self", auth=auth)
        data1 = get_response1.json()
        original_updated = data1["account_updated"]
        
        # Wait a moment and update
        time.sleep(2)
        update_data = {"first_name": "UpdatedName"}
        requests.put(f"{BASE_URL}/v1/user/self", json=update_data, auth=auth)
        
        # Get new timestamps
        get_response2 = requests.get(f"{BASE_URL}/v1/user/self", auth=auth)
        data2 = get_response2.json()
        new_updated = data2["account_updated"]
        
        # Verify account_updated changed
        assert new_updated != original_updated
        
        # Verify account_created did not change
        assert data2["account_created"] == data1["account_created"]
    
    # ===== 400 Bad Request =====
    def test_user_update_400_empty_body(self, created_user):
        """
        Status: 400 - Bad Request
        Reason: Empty request body (no fields to update)
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        
        response = requests.put(f"{BASE_URL}/v1/user/self", json={}, auth=auth)
        
        assert response.status_code == 400
        
        data = response.json()
        assert data["error"] == "Bad Request" or data["error"] == "Validation Error"
    
    def test_user_update_400_attempt_update_username(self, created_user):
        """
        Status: 400 - Bad Request
        Reason: Attempted to update read-only field 'username'
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        update_data = {"username": "newemail@example.com"}
        
        response = requests.put(f"{BASE_URL}/v1/user/self", json=update_data, auth=auth)
        
        assert response.status_code == 400
        
        data = response.json()
        assert "username" in data["message"].lower() or "cannot be updated" in data["message"].lower()
    
    def test_user_update_400_attempt_update_id(self, created_user):
        """
        Status: 400 - Bad Request
        Reason: Attempted to update read-only field 'id'
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        update_data = {"id": "fake-id-123"}
        
        response = requests.put(f"{BASE_URL}/v1/user/self", json=update_data, auth=auth)
        
        assert response.status_code == 400
    
    def test_user_update_400_attempt_update_account_created(self, created_user):
        """
        Status: 400 - Bad Request
        Reason: Attempted to update read-only field 'account_created'
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        update_data = {"account_created": "2020-01-01T00:00:00Z"}
        
        response = requests.put(f"{BASE_URL}/v1/user/self", json=update_data, auth=auth)
        
        assert response.status_code == 400
    
    def test_user_update_400_attempt_update_account_updated(self, created_user):
        """
        Status: 400 - Bad Request
        Reason: Attempted to update read-only field 'account_updated'
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        update_data = {"account_updated": "2024-01-01T00:00:00Z"}
        
        response = requests.put(f"{BASE_URL}/v1/user/self", json=update_data, auth=auth)
        
        assert response.status_code == 400
    
    def test_user_update_400_password_too_short(self, created_user):
        """
        Status: 400 - Bad Request
        Reason: New password is less than 8 characters
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        update_data = {"password": "Short1"}
        
        response = requests.put(f"{BASE_URL}/v1/user/self", json=update_data, auth=auth)
        
        assert response.status_code == 400
    
    def test_user_update_400_password_too_long(self, created_user):
        """
        Status: 400 - Bad Request
        Reason: New password exceeds 128 characters
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        update_data = {"password": "P" * 129}
        
        response = requests.put(f"{BASE_URL}/v1/user/self", json=update_data, auth=auth)
        
        assert response.status_code == 400
    
    def test_user_update_400_first_name_too_long(self, created_user):
        """
        Status: 400 - Bad Request
        Reason: first_name exceeds 100 characters
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        update_data = {"first_name": "A" * 101}
        
        response = requests.put(f"{BASE_URL}/v1/user/self", json=update_data, auth=auth)
        
        assert response.status_code == 400
    
    def test_user_update_400_last_name_too_long(self, created_user):
        """
        Status: 400 - Bad Request
        Reason: last_name exceeds 100 characters
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        update_data = {"last_name": "B" * 101}
        
        response = requests.put(f"{BASE_URL}/v1/user/self", json=update_data, auth=auth)
        
        assert response.status_code == 400
    
    def test_user_update_400_empty_first_name(self, created_user):
        """
        Status: 400 - Bad Request
        Reason: first_name is empty string
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        update_data = {"first_name": ""}
        
        response = requests.put(f"{BASE_URL}/v1/user/self", json=update_data, auth=auth)
        
        assert response.status_code == 400
    
    def test_user_update_400_empty_last_name(self, created_user):
        """
        Status: 400 - Bad Request
        Reason: last_name is empty string
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        update_data = {"last_name": ""}
        
        response = requests.put(f"{BASE_URL}/v1/user/self", json=update_data, auth=auth)
        
        assert response.status_code == 400
    
    def test_user_update_400_malformed_json(self, created_user):
        """
        Status: 400 - Bad Request
        Reason: Malformed JSON in request body
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        
        response = requests.put(
            f"{BASE_URL}/v1/user/self",
            data="{'invalid': json}",
            headers={"Content-Type": "application/json"},
            auth=auth
        )
        
        assert response.status_code == 400
    
    # ===== 401 Unauthorized =====
    def test_user_update_401_no_authentication(self):
        """
        Status: 401 - Unauthorized
        Reason: Missing authentication credentials
        """
        update_data = {"first_name": "Test"}
        response = requests.put(f"{BASE_URL}/v1/user/self", json=update_data)
        
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers
    
    def test_user_update_401_invalid_credentials(self, created_user):
        """
        Status: 401 - Unauthorized
        Reason: Invalid authentication credentials
        """
        auth = HTTPBasicAuth(created_user["username"], "WrongPassword")
        update_data = {"first_name": "Test"}
        
        response = requests.put(f"{BASE_URL}/v1/user/self", json=update_data, auth=auth)
        
        assert response.status_code == 401
    
    # ===== 403 Forbidden =====
    
    # ===== 415 Unsupported Media Type =====
    def test_user_update_415_wrong_content_type(self, created_user):
        """
        Status: 415 - Unsupported Media Type
        Reason: Content-Type is not application/json
        """
        auth = HTTPBasicAuth(created_user["username"], created_user["password"])
        update_data = {"first_name": "Test"}
        
        response = requests.put(
            f"{BASE_URL}/v1/user/self",
            data=json.dumps(update_data),
            headers={"Content-Type": "text/plain"},
            auth=auth
        )
        
        assert response.status_code == 415


# ============================================================================
# ADDITIONAL EDGE CASE TESTS
# ============================================================================

class TestEdgeCases:
    """Additional edge case tests not covered by specific status codes"""
    
    def test_concurrent_user_creation(self):
        """
        Test: Multiple users created concurrently
        Validates: No race conditions, all created successfully
        """
        import concurrent.futures
        
        def create_user(index):
            user_data = {
                "username": f"concurrent_{index}_{int(time.time())}@example.com",
                "password": "SecurePass123!",
                "first_name": f"User{index}",
                "last_name": "Test"
            }
            return requests.post(f"{BASE_URL}/v1/user", json=user_data)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_user, i) for i in range(5)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should succeed
        for response in responses:
            assert response.status_code == 201
    
    def test_unicode_characters_in_names(self):
        """
        Test: Unicode characters in first_name and last_name
        Validates: Unicode properly stored and retrieved
        """
        user_data = {
            "username": f"unicode_{int(time.time())}@example.com",
            "password": "SecurePass123!",
            "first_name": "José",
            "last_name": "Müller"
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        assert response.status_code == 201
        
        # Verify unicode preserved
        auth = HTTPBasicAuth(user_data["username"], user_data["password"])
        get_response = requests.get(f"{BASE_URL}/v1/user/self", auth=auth)
        data = get_response.json()
        assert data["first_name"] == "José"
        assert data["last_name"] == "Müller"
    
    def test_sql_injection_attempt_in_username(self):
        """
        Test: SQL injection attempt in username field
        Validates: Proper input sanitization
        """
        user_data = {
            "username": "test' OR '1'='1@example.com",
            "password": "SecurePass123!",
            "first_name": "Test",
            "last_name": "User"
        }
        
        # Should either fail validation (invalid email) or be safely escaped
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        # Will likely be 400 due to invalid email format
        assert response.status_code in [400, 201]
    
    def test_xss_attempt_in_name_fields(self):
        """
        Test: XSS attempt in name fields
        Validates: Proper output encoding
        """
        user_data = {
            "username": f"xss_{int(time.time())}@example.com",
            "password": "SecurePass123!",
            "first_name": "<script>alert('xss')</script>",
            "last_name": "<img src=x onerror=alert('xss')>"
        }
        
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        
        # Should either be rejected or safely stored
        if response.status_code == 201:
            # If accepted, verify it's stored as-is (not executed)
            auth = HTTPBasicAuth(user_data["username"], user_data["password"])
            get_response = requests.get(f"{BASE_URL}/v1/user/self", auth=auth)
            data = get_response.json()
            # Data should be returned as string, not executed
            assert "<script>" in data["first_name"]
    
    def test_health_check_response_time(self):
        """
        Test: Health check responds quickly
        Validates: Response time under 1 second
        """
        start_time = time.time()
        response = requests.get(f"{BASE_URL}/healthz")
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 1.0  # Should respond in under 1 second
    
    def test_user_creation_response_time(self):
        """
        Test: User creation responds in reasonable time
        Validates: Response time under 2 seconds
        """
        user_data = {
            "username": f"perf_{int(time.time())}@example.com",
            "password": "SecurePass123!",
            "first_name": "Performance",
            "last_name": "Test"
        }
        
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/v1/user", json=user_data)
        end_time = time.time()
        
        assert response.status_code == 201
        assert (end_time - start_time) < 2.0

