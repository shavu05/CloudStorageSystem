"""A small, authenticated Flask interface for a private Amazon S3 bucket."""

from __future__ import annotations

import hmac
import logging
import os
from datetime import timedelta
from functools import wraps
from zoneinfo import ZoneInfo

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename


load_dotenv()
csrf = CSRFProtect()


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    """Read a positive integer environment setting safely."""
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{name} must be a whole number.") from exc
    if value < minimum:
        raise RuntimeError(f"{name} must be at least {minimum}.")
    return value


def create_app(test_config: dict | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("FLASK_SECRET_KEY"),
        APP_USERNAME=os.getenv("APP_USERNAME"),
        APP_PASSWORD_HASH=os.getenv("APP_PASSWORD_HASH"),
        AWS_REGION=os.getenv("AWS_REGION", "ap-south-1"),
        S3_BUCKET=os.getenv("S3_BUCKET"),
        APP_TIMEZONE=os.getenv("APP_TIMEZONE", "Asia/Kolkata"),
        MAX_CONTENT_LENGTH=_env_int("MAX_UPLOAD_MB", 16) * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        WTF_CSRF_ENABLED=True,
        WTF_CSRF_TIME_LIMIT=3600,
    )
    if test_config:
        app.config.update(test_config)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("Set FLASK_SECRET_KEY in your local .env file.")
    if not app.config.get("APP_USERNAME") or not app.config.get("APP_PASSWORD_HASH"):
        raise RuntimeError(
            "Set APP_USERNAME and APP_PASSWORD_HASH in your local .env file."
        )
    if not app.config.get("S3_BUCKET"):
        raise RuntimeError("Set S3_BUCKET in your local .env file.")

    csrf.init_app(app)
    app.logger.setLevel(logging.INFO)

    def get_s3_client():
        """Return an injected test client or a boto3 client using the AWS credential chain."""
        injected = app.config.get("S3_CLIENT")
        if injected is not None:
            return injected
        return boto3.client("s3", region_name=app.config["AWS_REGION"])

    def login_required(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            if not session.get("authenticated"):
                return redirect(url_for("login", next=request.path))
            return view(**kwargs)

        return wrapped_view

    def s3_error_message(exc: Exception) -> None:
        app.logger.exception("S3 request failed", exc_info=exc)
        flash(
            "The storage request could not be completed. Check your AWS configuration "
            "and bucket permissions, then try again.",
            "error",
        )

    @app.context_processor
    def inject_template_settings():
        return {"max_upload_mb": app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)}

    @app.get("/login")
    def login():
        if session.get("authenticated"):
            return redirect(url_for("index"))
        return render_template("login.html")

    @app.post("/login")
    def login_submit():
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        username_ok = hmac.compare_digest(username, app.config["APP_USERNAME"])
        password_ok = check_password_hash(app.config["APP_PASSWORD_HASH"], password)

        if username_ok and password_ok:
            session.clear()
            session["authenticated"] = True
            session.permanent = True
            flash("Welcome back. You are signed in.", "success")
            return redirect(url_for("index"))

        flash("The username or password is incorrect.", "error")
        return render_template("login.html"), 401

    @app.post("/logout")
    @login_required
    def logout():
        session.clear()
        flash("You have been signed out.", "success")
        return redirect(url_for("login"))

    @app.get("/")
    @login_required
    def index():
        files: list[dict] = []
        total_bytes = 0
        try:
            client = get_s3_client()
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=app.config["S3_BUCKET"]):
                for item in page.get("Contents", []):
                    item["LastModified"] = item["LastModified"].astimezone(
                        ZoneInfo(app.config["APP_TIMEZONE"])
                    )
                    files.append(item)
                    total_bytes += item.get("Size", 0)
            files.sort(key=lambda item: item["LastModified"], reverse=True)
        except (ClientError, BotoCoreError, ValueError, KeyError) as exc:
            s3_error_message(exc)

        total_mb = total_bytes / (1024 * 1024)
        return render_template(
            "index.html",
            files=files,
            total_bytes=total_bytes,
            total_mb=f"{total_mb:.2f}",
        )

    @app.post("/upload")
    @login_required
    def upload():
        uploaded = request.files.get("file")
        if uploaded is None or not uploaded.filename:
            flash("Choose a file before uploading.", "error")
            return redirect(url_for("index"))

        filename = secure_filename(uploaded.filename)
        if not filename:
            flash("That filename is not valid. Rename the file and try again.", "error")
            return redirect(url_for("index"))

        try:
            client = get_s3_client()
            try:
                client.head_object(Bucket=app.config["S3_BUCKET"], Key=filename)
                flash("A file with that name already exists. Rename your local file first.", "error")
                return redirect(url_for("index"))
            except ClientError as exc:
                status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                code = exc.response.get("Error", {}).get("Code")
                if status != 404 and code not in {"404", "NoSuchKey", "NotFound"}:
                    raise

            client.upload_fileobj(
                uploaded,
                app.config["S3_BUCKET"],
                filename,
                ExtraArgs={"ContentType": "application/octet-stream"},
            )
            flash(f'"{filename}" was uploaded successfully.', "success")
        except (ClientError, BotoCoreError):
            app.logger.exception("S3 upload failed")
            flash("Upload failed. Check the file and your S3 permissions.", "error")
        return redirect(url_for("index"))

    @app.post("/download")
    @login_required
    def download():
        key = request.form.get("key", "")
        if not key:
            abort(400)
        try:
            url = get_s3_client().generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": app.config["S3_BUCKET"],
                    "Key": key,
                    "ResponseContentDisposition": "attachment",
                },
                ExpiresIn=300,
            )
            return redirect(url, code=303)
        except (ClientError, BotoCoreError):
            app.logger.exception("S3 download link generation failed")
            flash("A download link could not be created for that file.", "error")
            return redirect(url_for("index"))

    @app.post("/rename")
    @login_required
    def rename():
        old_key = request.form.get("key", "")
        new_name = secure_filename(request.form.get("new_name", ""))
        if not old_key or not new_name:
            flash("Enter a valid new filename.", "error")
            return redirect(url_for("index"))
        if old_key == new_name:
            flash("The new name is the same as the current name.", "error")
            return redirect(url_for("index"))

        client = get_s3_client()
        try:
            try:
                client.head_object(Bucket=app.config["S3_BUCKET"], Key=new_name)
                flash("A file with that name already exists. Choose another name.", "error")
                return redirect(url_for("index"))
            except ClientError as exc:
                status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                code = exc.response.get("Error", {}).get("Code")
                if status != 404 and code not in {"404", "NoSuchKey", "NotFound"}:
                    raise

            client.copy_object(
                Bucket=app.config["S3_BUCKET"],
                CopySource={"Bucket": app.config["S3_BUCKET"], "Key": old_key},
                Key=new_name,
            )
            client.delete_object(Bucket=app.config["S3_BUCKET"], Key=old_key)
            flash(f'File renamed to "{new_name}".', "success")
        except (ClientError, BotoCoreError):
            app.logger.exception("S3 rename failed")
            flash("Rename failed. Check your S3 permissions and try again.", "error")
        return redirect(url_for("index"))

    @app.post("/delete")
    @login_required
    def delete():
        key = request.form.get("key", "")
        if not key:
            abort(400)
        try:
            get_s3_client().delete_object(Bucket=app.config["S3_BUCKET"], Key=key)
            flash("File deleted successfully.", "success")
        except (ClientError, BotoCoreError):
            app.logger.exception("S3 delete failed")
            flash("Delete failed. Check your S3 permissions and try again.", "error")
        return redirect(url_for("index"))

    @app.errorhandler(RequestEntityTooLarge)
    def upload_too_large(_error):
        flash(
            f"That file is larger than the configured {app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)} MB limit.",
            "error",
        )
        return redirect(url_for("index")), 413

    return app


app = create_app()

if __name__ == "__main__":
    # The built-in server is for local development only. Use a production WSGI server to deploy.
    app.run(host="127.0.0.1", port=_env_int("PORT", 5000), debug=False)
