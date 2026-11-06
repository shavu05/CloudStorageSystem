# Security Policy

## Supported use

This repository is a portfolio/demo project. It currently supports one configured administrator account and should not be treated as a multi-tenant file-hosting service.

## Reporting a vulnerability

Please do not publish credentials, private bucket names, or exploit details in a public issue. Contact the repository owner privately with a concise description and reproduction steps.

## Deployment checklist

- Keep the S3 bucket's Block Public Access settings enabled.
- Use a dedicated IAM role or user with permissions scoped to the required bucket only.
- Store AWS credentials in an AWS credential provider or hosting secret manager, never in Git.
- Use a strong FLASK_SECRET_KEY and password hash.
- Serve over HTTPS and set SESSION_COOKIE_SECURE=true.
- Run behind a production WSGI server; never expose Flask's development server.
- Rotate any AWS credential that has been exposed or committed.
