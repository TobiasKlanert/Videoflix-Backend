# Videoflix Backend

Backend service for Videoflix. Runs a Django app with PostgreSQL and Redis via Docker Compose.

## Features

- Django backend API served by Gunicorn
- PostgreSQL database and Redis cache
- Background processing via RQ worker
- Email delivery via SMTP configuration
- HLS video conversion pipeline (ffmpeg)
- Containerized local setup with Docker Compose

## Prerequisites

- Git
- Docker Desktop (or Docker Engine)
- Docker Compose v2 (included with Docker Desktop)

## Project Structure (Docker)

- `web` container: Django + Gunicorn
- `worker` container: RQ worker
- `db` container: PostgreSQL
- `redis` container: Redis

## Environment Configuration

The stack is configured via a `.env` file. Use the template provided:

```
.env.template
```

Copy it to `.env` and fill in the values. Required fields include:

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- `REDIS_HOST`, `REDIS_LOCATION`, `REDIS_PORT`, `REDIS_DB`
- `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_PASSWORD`, `DJANGO_SUPERUSER_EMAIL`
- Email settings and frontend URLs if you use those features

## Configuration Notes

- `DEBUG`: Set to `True` only for local development. Always use `False` in production.
- `ALLOWED_HOSTS`: Comma-separated list of hostnames the Django app will serve. Include your domain(s) and `localhost` for local use.
- `CORS_ALLOWED_ORIGINS`: Define which frontend origins are allowed to call the API. Use full origins like `https://your-frontend.example`.
- Cookies: If you rely on auth/session cookies, align cookie settings with your frontend domain and HTTPS usage. For production, prefer secure cookies and an explicit `SameSite` policy.

## Step-by-Step: Clone and Start with Docker

1) Clone the repository

```
git clone https://github.com/TobiasKlanert/Videoflix-Backend.git
cd Videoflix-Backend
```

2) Create `.env` from the template

```
copy .env.template .env
```

3) Edit `.env` and set real values

Make sure at least the database credentials and `SECRET_KEY` are set.

4) Build and start the containers

```
docker compose up --build
```

On first start, the entrypoint will:

- wait for PostgreSQL
- run `collectstatic`
- apply migrations
- create a Django superuser using `DJANGO_SUPERUSER_*`

5) Open the app

- Backend API: `http://localhost:8000`

## Useful Commands

- Stop containers: `docker compose down`
- Remove volumes (data reset): `docker compose down -v`
- Rebuild images: `docker compose build --no-cache`

## Notes

- Media and static files are persisted in Docker volumes.
- The `worker` service runs `python manage.py rqworker default`.
- Migrations and superuser creation run only in the `web` container (`RUN_MIGRATIONS=1`) to avoid race conditions.
