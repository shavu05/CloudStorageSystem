# Cloud Storage System

A private, browser-based file manager built with **Python, Flask, and Amazon S3**. Sign in to upload, browse, search, download, rename, and delete objects in your own S3 bucket.

> **Security note:** This project is designed as a single-admin portfolio/demo application. Keep the S3 bucket private, use least-privilege IAM permissions, configure a strong password hash and Flask secret, and deploy behind HTTPS with a production WSGI server. Do not use Flask's development server for public deployment.
>
> ## 📸 Project Screenshots

### CloudVault Dashboard
![CloudVault Dashboard](cloudvault-dashboard.png)

### Login Page
![CloudVault Login](cloudvault-login.png)

## Features

- Password-protected dashboard with sign-in and sign-out.
- Upload files to a private Amazon S3 bucket.
- List and search stored files, with file size and last-modified information.
- Generate temporary download links that expire after five minutes.
- Rename and delete stored objects.
- CSRF protection on every form that changes data.
- Configurable upload size limit and secure filename handling.
- Responsive interface for desktop and mobile screens.
- AWS credentials loaded through boto3's standard credential chain (no keys in source code).

## Technology stack

- **Backend:** Python, Flask, Flask-WTF
- **Cloud storage:** Amazon S3, Boto3
- **Frontend:** HTML, CSS, JavaScript
- **Configuration:** python-dotenv

## Project structure

    CloudStorageSystem/
    ├── .github/
    │   └── workflows/
    │       └── tests.yml
    ├── app.py
    ├── requirements.txt
    ├── requirements-dev.txt
    ├── .env.example
    ├── .gitignore
    ├── README.md
    ├── SECURITY.md
    ├── static/
    │   └── style.css
    ├── templates/
    │   ├── index.html
    │   └── login.html
    └── tests/
        └── test_app.py

## Prerequisites

- Python 3.10 or newer.
- An AWS account and an S3 bucket in a region you choose.
- AWS credentials configured locally (for example, through an AWS CLI profile) or an IAM role when hosted on AWS.

## 1. Clone and install

    git clone https://github.com/shavu05/CloudStorageSystem.git
    cd CloudStorageSystem
    python -m venv .venv

Activate the environment:

**Windows PowerShell**

    .\.venv\Scripts\Activate.ps1

**macOS / Linux**

    source .venv/bin/activate

Install packages:

    python -m pip install -r requirements.txt

## 2. Create and secure your S3 bucket

1. Create an S3 bucket in your chosen AWS region.
2. Keep **Block Public Access** enabled. This application does not need public bucket access.
3. Enable default encryption (SSE-S3 or an appropriate KMS key).
4. Create a dedicated IAM identity/role for this application. Do not use AWS root credentials.
5. Grant only the S3 permissions required for the one bucket. An example identity policy is shown below; replace YOUR_BUCKET_NAME with your bucket name.

    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "ListOnlyThisBucket",
          "Effect": "Allow",
          "Action": ["s3:ListBucket"],
          "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME"
        },
        {
          "Sid": "ManageObjectsInThisBucket",
          "Effect": "Allow",
          "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
          "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/*"
        }
      ]
    }

Configure your local AWS profile using the AWS CLI or another supported credential provider. Boto3 automatically discovers credentials from its standard credential chain. **Never put AWS access keys in app.py, .env.example, README files, or Git.**

## 3. Configure environment variables

Copy .env.example to .env:

**Windows PowerShell**

    Copy-Item .env.example .env

**macOS / Linux**

    cp .env.example .env

Generate a strong Flask secret key:

    python -c "import secrets; print(secrets.token_hex(32))"

Generate a password hash (you will be prompted for the password):

    python -c "from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass('New admin password: ')))"

Paste the generated values into .env:

- FLASK_SECRET_KEY: the generated random secret.
- APP_USERNAME: your chosen admin username.
- APP_PASSWORD_HASH: the generated Werkzeug password hash (not the plain password).
- AWS_REGION: your bucket's region, such as ap-south-1.
- S3_BUCKET: your bucket name.
- APP_TIMEZONE: display timezone (default Asia/Kolkata).
- MAX_UPLOAD_MB: maximum upload size in MB (default 16).
- SESSION_COOKIE_SECURE: set to true when served over HTTPS.

The .env file is excluded by .gitignore and must remain private.

## 4. Run locally

    python app.py

Open http://127.0.0.1:5000 and sign in with the admin username and password you configured.

The built-in Flask server is intended only for local development. For production, use a production WSGI server (for example, Waitress on Windows or Gunicorn on Linux), terminate TLS with HTTPS, set SESSION_COOKIE_SECURE=true, and store secrets in your hosting platform's secret manager.

## 5. Run tests

Install development dependencies and run the test suite:

    python -m pip install -r requirements-dev.txt
    python -m pytest -q

The included GitHub Actions workflow also runs Python compilation and the test suite on pushes and pull requests.

## Important security considerations

- This is a **single-admin** application, not a multi-user storage service.
- Keep the S3 bucket private and use an IAM identity restricted to the bucket above.
- Presigned download URLs grant temporary access to one object; this app sets them to expire after five minutes.
- The app uses CSRF tokens for state-changing forms and stores a password hash rather than a plain-text password.
- Set HTTPS and SESSION_COOKIE_SECURE=true in production.
- Add rate limiting, monitoring, backups/versioning, and stronger identity management before offering this to external users.
- Renaming an S3 object is implemented as copy-then-delete; if the delete operation fails after the copy, both object names may temporarily exist.

## License

No license is included. Add a license only after deciding how you want others to use, modify, and distribute this project.
