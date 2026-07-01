"""
conftest.py — pytest configuration for CSYE6225 webapp tests.

S3 Note: Tests run against a live app process (started separately with
python -m app.main). The app itself handles missing S3_BUCKET_NAME by
skipping real S3 calls (see app/core/s3.py). No mocking needed here.

For CI: ensure .env has S3_BUCKET_NAME= (empty) so the app uses
local dev mode automatically.
"""
