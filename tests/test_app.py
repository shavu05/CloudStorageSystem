from datetime import datetime, timezone
from io import BytesIO

import pytest
from werkzeug.security import generate_password_hash

from app import create_app


class FakePaginator:
    def paginate(self, **kwargs):
        return [
            {
                "Contents": [
                    {
                        "Key": "sample.txt",
                        "Size": 1024,
                        "LastModified": datetime(2025, 1, 1, tzinfo=timezone.utc),
                    }
                ]
            }
        ]


class FakeS3:
    def __init__(self):
        self.uploads = []
        self.deletions = []

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return FakePaginator()

    def upload_fileobj(self, fileobj, bucket, key, ExtraArgs=None):
        self.uploads.append((bucket, key, fileobj.read(), ExtraArgs))

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        assert operation == "get_object"
        assert ExpiresIn == 300
        return "https://example.test/temporary-download"

    def head_object(self, Bucket, Key):
        from botocore.exceptions import ClientError

        raise ClientError(
            {
                "Error": {"Code": "404", "Message": "Not found"},
                "ResponseMetadata": {"HTTPStatusCode": 404},
            },
            "HeadObject",
        )

    def copy_object(self, **kwargs):
        self.copied = kwargs

    def delete_object(self, Bucket, Key):
        self.deletions.append((Bucket, Key))


@pytest.fixture()
def app_and_s3():
    fake_s3 = FakeS3()
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only-secret",
            "APP_USERNAME": "test-admin",
            "APP_PASSWORD_HASH": generate_password_hash("test-password"),
            "AWS_REGION": "ap-south-1",
            "S3_BUCKET": "test-bucket",
            "S3_CLIENT": fake_s3,
            "WTF_CSRF_ENABLED": False,
        }
    )
    return app, fake_s3


def test_dashboard_requires_login(app_and_s3):
    app, _ = app_and_s3
    response = app.test_client().get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_and_dashboard(app_and_s3):
    app, _ = app_and_s3
    client = app.test_client()
    response = client.post("/login", data={"username": "test-admin", "password": "test-password"})
    assert response.status_code == 302
    response = client.get("/")
    assert response.status_code == 200
    assert b"sample.txt" in response.data


def test_rejects_invalid_login(app_and_s3):
    app, _ = app_and_s3
    response = app.test_client().post(
        "/login", data={"username": "test-admin", "password": "wrong-password"}
    )
    assert response.status_code == 401


def test_upload_uses_sanitized_filename(app_and_s3):
    app, fake_s3 = app_and_s3
    client = app.test_client()
    client.post("/login", data={"username": "test-admin", "password": "test-password"})
    response = client.post(
        "/upload",
        data={"file": (BytesIO(b"hello"), "hello world.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    assert fake_s3.uploads[0][1] == "hello_world.txt"
    assert fake_s3.uploads[0][2] == b"hello"
