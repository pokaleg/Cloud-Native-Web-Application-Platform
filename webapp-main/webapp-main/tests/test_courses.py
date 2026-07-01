import pytest
import requests
import psycopg2
import io
import uuid
import time
import os

BASE_URL = "http://localhost:8080"


# ── Helpers ────────────────────────────────────────────────────────────────────

def create_user(username, password="Test1234!", first_name="John", last_name="Doe"):
    return requests.post(
        f"{BASE_URL}/v1/user",
        json={"username": username, "password": password,
              "first_name": first_name, "last_name": last_name}
    )

def auth_header(username, password="Test1234!"):
    return (username, password)

def create_course(auth, payload):
    return requests.post(f"{BASE_URL}/v1/courses", json=payload, auth=auth)

def delete_course(auth, course_id):
    return requests.delete(f"{BASE_URL}/v1/courses/{course_id}", auth=auth)

def delete_syllabus(auth, course_id):
    return requests.delete(f"{BASE_URL}/v1/courses/{course_id}/syllabus", auth=auth)

def upload_syllabus(auth, course_id, content=b"Test syllabus content", filename="syllabus.pdf"):
    return requests.post(
        f"{BASE_URL}/v1/courses/{course_id}/syllabus",
        files={"file": (filename, io.BytesIO(content), "application/pdf")},
        auth=auth,
    )

def unique_course_payload(**overrides):
    uid = uuid.uuid4().hex
    letters = ''.join(c for c in uid if c.isalpha()).upper()
    dept_code = letters[:4] if len(letters) >= 4 else (letters + "ABCD")[:4]
    digits = ''.join(c for c in uid if c.isdigit())
    number = digits[:4] if len(digits) >= 4 else (digits + "0000")[:4]
    base = {
        "department_code": dept_code,
        "number": number,
        "title": "Test Course",
        "credit_hours": 4,
        "classification": "core",
    }
    base.update(overrides)
    return base


def _mark_user_verified(username: str) -> None:
    """Directly update the DB to mark a user as verified.
    Used in CI where there is no email flow."""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "webapp_db"),
        user=os.getenv("DB_USER", "webapp_user"),
        password=os.getenv("DB_PASSWORD", ""),
    )
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET is_verified = TRUE WHERE username = %s",
            (username.lower(),)
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def test_user():
    """Create one test user for the entire module and mark it as verified."""
    username = f"coursetest_{uuid.uuid4().hex[:8]}@example.com"
    password = "Test1234!"
    resp = create_user(username, password)
    # User may already exist if tests are re-run — that's fine
    assert resp.status_code in (201, 400, 409)

    # Mark as verified directly in DB — bypasses email flow in CI
    _mark_user_verified(username)

    return {"username": username, "password": password, "auth": (username, password)}


@pytest.fixture
def created_course(test_user):
    """
    Creates a unique course before each test and deletes it after.
    Uses unique_course_payload() so there are never dept_code+number conflicts.
    """
    payload = unique_course_payload()
    resp = create_course(test_user["auth"], payload)
    assert resp.status_code == 201, f"Setup failed: {resp.text}"
    course = resp.json()
    yield course
    # Cleanup — delete syllabus first if present, then course
    delete_syllabus(test_user["auth"], course["id"])
    delete_course(test_user["auth"], course["id"])

# ── POST /v1/courses ───────────────────────────────────────────────────────────

class TestCreateCourse:

    def test_create_course_success(self, test_user):
        """201 Created with all required fields."""
        payload = unique_course_payload()
        resp = create_course(test_user["auth"], payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["department_code"] == payload["department_code"]
        assert data["number"] == payload["number"]
        assert data["title"] == payload["title"]
        assert data["credit_hours"] == 4
        assert data["classification"] == "core"
        assert data["has_syllabus"] is False
        assert "id" in data
        assert "date_created" in data
        assert "date_updated" in data
        # Cleanup
        delete_course(test_user["auth"], data["id"])

    def test_create_course_with_optional_fields(self, test_user):
        """201 Created with optional description and prerequisites."""
        payload = unique_course_payload(
            description="Covers data analytics in advisory services",
            prerequisites="ACCT 2301 with a minimum grade of D-",
        )
        resp = create_course(test_user["auth"], payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == "Covers data analytics in advisory services"
        assert data["prerequisites"] == "ACCT 2301 with a minimum grade of D-"
        delete_course(test_user["auth"], data["id"])

    def test_create_course_elective_classification(self, test_user):
        """201 Created with elective classification."""
        payload = unique_course_payload(classification="elective")
        resp = create_course(test_user["auth"], payload)
        assert resp.status_code == 201
        assert resp.json()["classification"] == "elective"
        delete_course(test_user["auth"], resp.json()["id"])

    def test_create_course_duplicate_returns_409(self, test_user, created_course):
        """409 Conflict when dept_code + number already exists."""
        # Try to create same course again using same dept_code + number
        duplicate = {
            "department_code": created_course["department_code"],
            "number": created_course["number"],
            "title": "Duplicate",
            "credit_hours": 3,
            "classification": "elective",
        }
        resp = create_course(test_user["auth"], duplicate)
        assert resp.status_code == 409

    def test_create_course_no_auth_returns_401(self):
        """401 Unauthorized when no credentials provided."""
        resp = requests.post(f"{BASE_URL}/v1/courses", json=unique_course_payload())
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers

    def test_create_course_invalid_auth_returns_401(self):
        """401 with wrong credentials."""
        resp = create_course(("wrong@example.com", "wrongpass"), unique_course_payload())
        assert resp.status_code == 401

    def test_create_course_missing_title_returns_400(self, test_user):
        """400 Bad Request when required field title is missing."""
        payload = unique_course_payload()
        del payload["title"]
        resp = create_course(test_user["auth"], payload)
        assert resp.status_code == 400

    def test_create_course_missing_dept_code_returns_400(self, test_user):
        """400 Bad Request when required field department_code is missing."""
        payload = unique_course_payload()
        del payload["department_code"]
        resp = create_course(test_user["auth"], payload)
        assert resp.status_code == 400

    def test_create_course_invalid_dept_code_lowercase_returns_400(self, test_user):
        """400 when department_code contains lowercase letters."""
        resp = create_course(test_user["auth"], unique_course_payload(department_code="csye"))
        assert resp.status_code == 400

    def test_create_course_invalid_dept_code_too_long_returns_400(self, test_user):
        """400 when department_code exceeds 6 characters."""
        resp = create_course(test_user["auth"], unique_course_payload(department_code="TOOLONG"))
        assert resp.status_code == 400

    def test_create_course_invalid_dept_code_too_short_returns_400(self, test_user):
        """400 when department_code is only 1 character."""
        resp = create_course(test_user["auth"], unique_course_payload(department_code="A"))
        assert resp.status_code == 400

    def test_create_course_credit_hours_zero_returns_400(self, test_user):
        """400 when credit_hours is 0 (below minimum of 1)."""
        resp = create_course(test_user["auth"], unique_course_payload(credit_hours=0))
        assert resp.status_code == 400

    def test_create_course_credit_hours_nine_returns_400(self, test_user):
        """400 when credit_hours is 9 (above maximum of 8)."""
        resp = create_course(test_user["auth"], unique_course_payload(credit_hours=9))
        assert resp.status_code == 400

    def test_create_course_credit_hours_boundary_min(self, test_user):
        """201 when credit_hours is 1 (minimum allowed)."""
        resp = create_course(test_user["auth"], unique_course_payload(credit_hours=1))
        assert resp.status_code == 201
        delete_course(test_user["auth"], resp.json()["id"])

    def test_create_course_credit_hours_boundary_max(self, test_user):
        """201 when credit_hours is 8 (maximum allowed)."""
        resp = create_course(test_user["auth"], unique_course_payload(credit_hours=8))
        assert resp.status_code == 201
        delete_course(test_user["auth"], resp.json()["id"])

    def test_create_course_invalid_classification_returns_400(self, test_user):
        """400 when classification is not core or elective."""
        resp = create_course(test_user["auth"], unique_course_payload(classification="mandatory"))
        assert resp.status_code == 400

    def test_create_course_immutable_fields_rejected(self, test_user):
        """400 when immutable fields like id or has_syllabus are sent (extra=forbid)."""
        payload = unique_course_payload()
        payload["has_syllabus"] = True
        resp = create_course(test_user["auth"], payload)
        assert resp.status_code == 400

    def test_create_course_wrong_content_type_returns_415(self, test_user):
        """415 when Content-Type is not application/json."""
        resp = requests.post(
            f"{BASE_URL}/v1/courses",
            data="title=test",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            auth=test_user["auth"],
        )
        assert resp.status_code == 415

    def test_create_course_location_header_present(self, test_user):
        """201 response includes Location header."""
        resp = create_course(test_user["auth"], unique_course_payload())
        assert resp.status_code == 201
        assert "Location" in resp.headers
        assert resp.headers["Location"].startswith("/v1/courses/")
        delete_course(test_user["auth"], resp.json()["id"])


# ── GET /v1/courses ────────────────────────────────────────────────────────────

class TestListCourses:

    def test_list_courses_success(self, test_user, created_course):
        """200 OK — list contains the created course."""
        resp = requests.get(f"{BASE_URL}/v1/courses", auth=test_user["auth"])
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.json()]
        assert created_course["id"] in ids

    def test_list_courses_sorted_by_dept_and_number(self, test_user):
        """Results are sorted by department_code ascending."""
        c1 = create_course(test_user["auth"], unique_course_payload(department_code="ZZZZ"))
        c2 = create_course(test_user["auth"], unique_course_payload(department_code="AAAA"))
        assert c1.status_code == 201
        assert c2.status_code == 201

        resp = requests.get(f"{BASE_URL}/v1/courses", auth=test_user["auth"])
        assert resp.status_code == 200
        dept_codes = [c["department_code"] for c in resp.json()]
        assert dept_codes == sorted(dept_codes)

        delete_course(test_user["auth"], c1.json()["id"])
        delete_course(test_user["auth"], c2.json()["id"])

    def test_list_courses_no_auth_returns_401(self):
        """401 when no credentials provided."""
        resp = requests.get(f"{BASE_URL}/v1/courses")
        assert resp.status_code == 401

    def test_list_courses_returns_array(self, test_user):
        """Response is always a JSON array."""
        resp = requests.get(f"{BASE_URL}/v1/courses", auth=test_user["auth"])
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ── GET /v1/courses/{course_id} ────────────────────────────────────────────────

class TestGetCourse:

    def test_get_course_success(self, test_user, created_course):
        """200 OK with correct course data."""
        resp = requests.get(
            f"{BASE_URL}/v1/courses/{created_course['id']}",
            auth=test_user["auth"]
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == created_course["id"]
        assert data["department_code"] == created_course["department_code"]

    def test_get_course_not_found_returns_404(self, test_user):
        """404 for non-existent course ID."""
        resp = requests.get(
            f"{BASE_URL}/v1/courses/00000000-0000-0000-0000-000000000000",
            auth=test_user["auth"]
        )
        assert resp.status_code == 404

    def test_get_course_no_auth_returns_401(self, created_course):
        """401 when no credentials provided."""
        resp = requests.get(f"{BASE_URL}/v1/courses/{created_course['id']}")
        assert resp.status_code == 401

    def test_get_course_all_fields_present(self, test_user, created_course):
        """Response includes all required fields."""
        resp = requests.get(
            f"{BASE_URL}/v1/courses/{created_course['id']}",
            auth=test_user["auth"]
        )
        data = resp.json()
        for field in ["id", "department_code", "number", "title",
                      "credit_hours", "classification", "has_syllabus",
                      "date_created", "date_updated"]:
            assert field in data, f"Missing field: {field}"


# ── PUT /v1/courses/{course_id} ────────────────────────────────────────────────

class TestUpdateCourse:

    def test_update_course_title_success(self, test_user, created_course):
        """200 OK when updating title."""
        resp = requests.put(
            f"{BASE_URL}/v1/courses/{created_course['id']}",
            json={"title": "Updated Title"},
            auth=test_user["auth"]
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    def test_update_course_credit_hours_success(self, test_user, created_course):
        """200 OK when updating credit_hours."""
        resp = requests.put(
            f"{BASE_URL}/v1/courses/{created_course['id']}",
            json={"credit_hours": 3},
            auth=test_user["auth"]
        )
        assert resp.status_code == 200
        assert resp.json()["credit_hours"] == 3

    def test_update_course_classification_success(self, test_user, created_course):
        """200 OK when updating classification."""
        resp = requests.put(
            f"{BASE_URL}/v1/courses/{created_course['id']}",
            json={"classification": "elective"},
            auth=test_user["auth"]
        )
        assert resp.status_code == 200
        assert resp.json()["classification"] == "elective"

    def test_update_course_date_updated_changes(self, test_user, created_course):
        """date_updated changes after a successful update."""
        original = created_course["date_updated"]
        time.sleep(1)
        requests.put(
            f"{BASE_URL}/v1/courses/{created_course['id']}",
            json={"title": "New Title"},
            auth=test_user["auth"]
        )
        resp = requests.get(
            f"{BASE_URL}/v1/courses/{created_course['id']}",
            auth=test_user["auth"]
        )
        assert resp.json()["date_updated"] != original

    def test_update_course_unmodified_fields_unchanged(self, test_user, created_course):
        """Updating one field does not affect other fields."""
        requests.put(
            f"{BASE_URL}/v1/courses/{created_course['id']}",
            json={"title": "Only Title Changed"},
            auth=test_user["auth"]
        )
        resp = requests.get(
            f"{BASE_URL}/v1/courses/{created_course['id']}",
            auth=test_user["auth"]
        )
        data = resp.json()
        assert data["department_code"] == created_course["department_code"]
        assert data["number"] == created_course["number"]
        assert data["credit_hours"] == created_course["credit_hours"]

    def test_update_course_immutable_department_code_returns_400(self, test_user, created_course):
        """400 when attempting to update department_code."""
        resp = requests.put(
            f"{BASE_URL}/v1/courses/{created_course['id']}",
            json={"department_code": "XXXX"},
            auth=test_user["auth"]
        )
        assert resp.status_code == 400

    def test_update_course_immutable_number_returns_400(self, test_user, created_course):
        """400 when attempting to update number."""
        resp = requests.put(
            f"{BASE_URL}/v1/courses/{created_course['id']}",
            json={"number": "9999"},
            auth=test_user["auth"]
        )
        assert resp.status_code == 400

    def test_update_course_immutable_id_returns_400(self, test_user, created_course):
        """400 when attempting to update id."""
        resp = requests.put(
            f"{BASE_URL}/v1/courses/{created_course['id']}",
            json={"id": "00000000-0000-0000-0000-000000000000"},
            auth=test_user["auth"]
        )
        assert resp.status_code == 400

    def test_update_course_immutable_has_syllabus_returns_400(self, test_user, created_course):
        """400 when attempting to update has_syllabus."""
        resp = requests.put(
            f"{BASE_URL}/v1/courses/{created_course['id']}",
            json={"has_syllabus": True},
            auth=test_user["auth"]
        )
        assert resp.status_code == 400

    def test_update_course_empty_body_returns_400(self, test_user, created_course):
        """400 when request body has no updatable fields."""
        resp = requests.put(
            f"{BASE_URL}/v1/courses/{created_course['id']}",
            json={},
            auth=test_user["auth"]
        )
        assert resp.status_code == 400

    def test_update_course_invalid_credit_hours_returns_400(self, test_user, created_course):
        """400 when credit_hours is out of range."""
        resp = requests.put(
            f"{BASE_URL}/v1/courses/{created_course['id']}",
            json={"credit_hours": 9},
            auth=test_user["auth"]
        )
        assert resp.status_code == 400

    def test_update_course_not_found_returns_404(self, test_user):
        """404 for non-existent course."""
        resp = requests.put(
            f"{BASE_URL}/v1/courses/00000000-0000-0000-0000-000000000000",
            json={"title": "Ghost"},
            auth=test_user["auth"]
        )
        assert resp.status_code == 404

    def test_update_course_no_auth_returns_401(self, created_course):
        """401 when no credentials provided."""
        resp = requests.put(
            f"{BASE_URL}/v1/courses/{created_course['id']}",
            json={"title": "No Auth"},
        )
        assert resp.status_code == 401


# ── DELETE /v1/courses/{course_id} ────────────────────────────────────────────

class TestDeleteCourse:

    def test_delete_course_success(self, test_user):
        """204 No Content when deleting a course without a syllabus."""
        resp = create_course(test_user["auth"], unique_course_payload())
        assert resp.status_code == 201
        course_id = resp.json()["id"]

        del_resp = delete_course(test_user["auth"], course_id)
        assert del_resp.status_code == 204

        get_resp = requests.get(
            f"{BASE_URL}/v1/courses/{course_id}", auth=test_user["auth"]
        )
        assert get_resp.status_code == 404

    def test_delete_course_not_found_returns_404(self, test_user):
        """404 for non-existent course."""
        resp = delete_course(
            test_user["auth"], "00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    def test_delete_course_no_auth_returns_401(self, created_course):
        """401 when no credentials provided."""
        resp = requests.delete(f"{BASE_URL}/v1/courses/{created_course['id']}")
        assert resp.status_code == 401

    def test_delete_course_with_syllabus_returns_409(self, test_user):
        """409 Conflict when course has an attached syllabus."""
        resp = create_course(test_user["auth"], unique_course_payload())
        assert resp.status_code == 201
        course_id = resp.json()["id"]

        upload_resp = upload_syllabus(test_user["auth"], course_id)
        assert upload_resp.status_code == 201, f"Syllabus upload failed: {upload_resp.text}"

        del_resp = delete_course(test_user["auth"], course_id)
        assert del_resp.status_code == 409

        # Cleanup
        delete_syllabus(test_user["auth"], course_id)
        delete_course(test_user["auth"], course_id)


# ── POST /v1/courses/{course_id}/syllabus ─────────────────────────────────────

class TestUploadSyllabus:

    def test_upload_syllabus_success(self, test_user, created_course):
        """201 Created with correct SyllabusResponse metadata."""
        file_content = b"This is a test syllabus"
        resp = upload_syllabus(test_user["auth"], created_course["id"], file_content)
        assert resp.status_code == 201
        data = resp.json()
        assert data["file_name"] == "syllabus.pdf"
        assert data["content_type"] == "application/pdf"
        assert data["file_size"] == len(file_content)
        assert data["course_id"] == created_course["id"]
        assert "s3_bucket_name" in data
        assert "s3_object_key" in data
        assert "url" in data
        assert "id" in data
        assert "date_created" in data

    def test_upload_syllabus_sets_has_syllabus_true(self, test_user, created_course):
        """has_syllabus becomes true after upload."""
        upload_syllabus(test_user["auth"], created_course["id"])
        course_resp = requests.get(
            f"{BASE_URL}/v1/courses/{created_course['id']}",
            auth=test_user["auth"]
        )
        assert course_resp.json()["has_syllabus"] is True

    def test_upload_syllabus_duplicate_returns_409(self, test_user, created_course):
        """409 when course already has a syllabus."""
        upload_syllabus(test_user["auth"], created_course["id"])
        second_resp = upload_syllabus(
            test_user["auth"], created_course["id"], b"Second", "second.pdf"
        )
        assert second_resp.status_code == 409

    def test_upload_syllabus_no_file_returns_400(self, test_user, created_course):
        """400 when no file is provided."""
        resp = requests.post(
            f"{BASE_URL}/v1/courses/{created_course['id']}/syllabus",
            auth=test_user["auth"],
        )
        assert resp.status_code == 400

    def test_upload_syllabus_empty_file_returns_400(self, test_user, created_course):
        """400 when file is empty (0 bytes)."""
        resp = upload_syllabus(test_user["auth"], created_course["id"], b"")
        assert resp.status_code == 400

    def test_upload_syllabus_course_not_found_returns_404(self, test_user):
        """404 when course does not exist."""
        resp = upload_syllabus(
            test_user["auth"], "00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    def test_upload_syllabus_no_auth_returns_401(self, created_course):
        """401 when no credentials provided."""
        resp = requests.post(
            f"{BASE_URL}/v1/courses/{created_course['id']}/syllabus",
            files={"file": ("syllabus.pdf", io.BytesIO(b"content"), "application/pdf")},
        )
        assert resp.status_code == 401

    def test_upload_syllabus_unique_s3_keys_across_courses(self, test_user):
        """Same filename uploaded to two courses gets unique S3 keys."""
        c1 = create_course(test_user["auth"], unique_course_payload())
        c2 = create_course(test_user["auth"], unique_course_payload())
        assert c1.status_code == 201, f"c1 failed: {c1.text}"
        assert c2.status_code == 201, f"c2 failed: {c2.text}"
        id1, id2 = c1.json()["id"], c2.json()["id"]

        r1 = upload_syllabus(test_user["auth"], id1, b"Same filename content")
        r2 = upload_syllabus(test_user["auth"], id2, b"Same filename content")
        assert r1.status_code == 201, f"Upload 1 failed: {r1.text}"
        assert r2.status_code == 201, f"Upload 2 failed: {r2.text}"

        assert r1.json()["s3_object_key"] != r2.json()["s3_object_key"]

        # Cleanup
        for cid in [id1, id2]:
            delete_syllabus(test_user["auth"], cid)
            delete_course(test_user["auth"], cid)

    def test_upload_syllabus_location_header_present(self, test_user, created_course):
        """201 response includes Location header."""
        resp = upload_syllabus(test_user["auth"], created_course["id"])
        assert resp.status_code == 201
        assert "Location" in resp.headers


# ── GET /v1/courses/{course_id}/syllabus ──────────────────────────────────────

class TestGetSyllabus:

    def test_get_syllabus_success(self, test_user, created_course):
        """200 OK with correct metadata when syllabus exists."""
        file_content = b"Syllabus for retrieval test"
        upload_syllabus(test_user["auth"], created_course["id"],
                        file_content, "get_test.pdf")
        resp = requests.get(
            f"{BASE_URL}/v1/courses/{created_course['id']}/syllabus",
            auth=test_user["auth"]
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["file_name"] == "get_test.pdf"
        assert data["course_id"] == created_course["id"]
        assert data["file_size"] == len(file_content)
        assert "s3_object_key" in data
        assert "url" in data

    def test_get_syllabus_not_found_returns_404(self, test_user, created_course):
        """404 when course has no syllabus."""
        resp = requests.get(
            f"{BASE_URL}/v1/courses/{created_course['id']}/syllabus",
            auth=test_user["auth"]
        )
        assert resp.status_code == 404

    def test_get_syllabus_course_not_found_returns_404(self, test_user):
        """404 when course does not exist."""
        resp = requests.get(
            f"{BASE_URL}/v1/courses/00000000-0000-0000-0000-000000000000/syllabus",
            auth=test_user["auth"]
        )
        assert resp.status_code == 404

    def test_get_syllabus_no_auth_returns_401(self, created_course):
        """401 when no credentials provided."""
        resp = requests.get(
            f"{BASE_URL}/v1/courses/{created_course['id']}/syllabus"
        )
        assert resp.status_code == 401


# ── DELETE /v1/courses/{course_id}/syllabus ───────────────────────────────────

class TestDeleteSyllabus:

    def test_delete_syllabus_success(self, test_user, created_course):
        """204 No Content after deleting syllabus."""
        upload_syllabus(test_user["auth"], created_course["id"])
        resp = delete_syllabus(test_user["auth"], created_course["id"])
        assert resp.status_code == 204

    def test_delete_syllabus_sets_has_syllabus_false(self, test_user, created_course):
        """has_syllabus becomes false after deletion."""
        upload_syllabus(test_user["auth"], created_course["id"])
        delete_syllabus(test_user["auth"], created_course["id"])
        course_resp = requests.get(
            f"{BASE_URL}/v1/courses/{created_course['id']}",
            auth=test_user["auth"]
        )
        assert course_resp.json()["has_syllabus"] is False

    def test_delete_syllabus_then_get_returns_404(self, test_user, created_course):
        """GET syllabus returns 404 after deletion."""
        upload_syllabus(test_user["auth"], created_course["id"])
        delete_syllabus(test_user["auth"], created_course["id"])
        get_resp = requests.get(
            f"{BASE_URL}/v1/courses/{created_course['id']}/syllabus",
            auth=test_user["auth"]
        )
        assert get_resp.status_code == 404

    def test_delete_syllabus_not_found_returns_404(self, test_user, created_course):
        """404 when course has no syllabus to delete."""
        resp = delete_syllabus(test_user["auth"], created_course["id"])
        assert resp.status_code == 404

    def test_delete_syllabus_course_not_found_returns_404(self, test_user):
        """404 when course does not exist."""
        resp = delete_syllabus(
            test_user["auth"], "00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    def test_delete_syllabus_no_auth_returns_401(self, created_course):
        """401 when no credentials provided."""
        resp = requests.delete(
            f"{BASE_URL}/v1/courses/{created_course['id']}/syllabus"
        )
        assert resp.status_code == 401

    def test_delete_syllabus_allows_reupload(self, test_user, created_course):
        """After deleting a syllabus, a new one can be uploaded successfully."""
        upload_syllabus(test_user["auth"], created_course["id"], b"First")
        delete_syllabus(test_user["auth"], created_course["id"])
        second_resp = upload_syllabus(
            test_user["auth"], created_course["id"], b"Second", "second.pdf"
        )
        assert second_resp.status_code == 201
