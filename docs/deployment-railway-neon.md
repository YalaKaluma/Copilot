# Railway + Neon Deployment

This repo deploys as two Railway services from the same GitHub repository:

- `backend`: FastAPI API service using `services/backend/Dockerfile`
- `frontend`: React/Vite static site served by nginx using `services/frontend/Dockerfile`

The backend uses Neon PostgreSQL through `DATABASE_URL`. Startup migrations run automatically by default.

## Corporate-PC workflow

No frontend or backend build is required on the local computer. Commit and push
the source files only. The `Railway Server Build` GitHub Actions workflow builds
both production Docker images on GitHub-hosted Ubuntu runners. Railway's GitHub
integration then detects the pushed commit and performs the deployment using the
service Dockerfiles and `railway.toml` files.

Do not commit `node_modules`, `.venv`, `dist`, or local environment files. They
are intentionally excluded by `.gitignore`.

Configure these GitHub repository values for the server-side frontend build:

- Repository variable `VITE_BACKEND_URL`
- Repository variable `VITE_PUBLIC_URL` (optional)
- Repository secret `VITE_CLERK_PUBLISHABLE_KEY`

Configure the runtime secrets listed below directly on the appropriate Railway
service. GitHub Actions does not need the SKAI, OpenAI, Cognito, Clerk secret, or
database credentials to compile the images.

## 1. Create the Neon database

Create a Neon project and copy the pooled or direct connection string. Either of these formats works:

```text
postgresql://user:password@host.neon.tech/dbname?sslmode=require
postgresql+asyncpg://user:password@host.neon.tech/dbname?sslmode=require
```

The backend normalizes standard Neon/Postgres URLs for the async database driver.

## 2. Create Railway services

Create two Railway services from this repository.

For the backend service:

- Leave the service root directory at the repository root.
- Set the Railway config file path to `/services/backend/railway.toml`.
- The config points Railway at `services/backend/Dockerfile`.
- Health check path: `/api/health`.

For the frontend service:

- Leave the service root directory at the repository root.
- Set the Railway config file path to `/services/frontend/railway.toml`.
- The config points Railway at `services/frontend/Dockerfile`.
- Health check path: `/`.

Railway's monorepo docs note that config file paths are absolute from the repo root, even when a service root directory is set.
This project keeps the root directory at the repo root because the Dockerfiles copy files from more than one folder.

## 3. Backend variables

Set these on the backend Railway service:

```text
ENV=production
DEBUG=false
LOG_LEVEL=INFO
DATABASE_URL=<your Neon connection string>
OPENAI_API_KEY=<your OpenAI API key>
CLERK_SECRET_KEY=<your Clerk secret key>
CLERK_WEBHOOK_SECRET=<your Clerk webhook secret>
CORS_ORIGINS=https://<your-frontend-domain>
RUN_DB_MIGRATIONS_ON_STARTUP=true
```

Optional, depending on which features you use:

```text
GCP_PROJECT_ID=<your GCP project>
GCS_BUCKET_NAME=<your bucket>
GOOGLE_SERVICE_ACCOUNT_JSON=<single-line service account JSON>
LANGFUSE_PUBLIC_KEY=<optional>
LANGFUSE_SECRET_KEY=<optional>
LANGFUSE_HOST=https://cloud.langfuse.com
SKAI_API_URL=<SKAI API URL>
SKAI_API_ORIGIN=<SKAI origin>
SKAI_API_REFERER=<SKAI referer>
SKAI_COGNITO_REGION=<region>
SKAI_COGNITO_USER_POOL_ID=<pool id>
SKAI_COGNITO_CLIENT_ID=<client id>
```

If you do not need startup migrations, set:

```text
RUN_DB_MIGRATIONS_ON_STARTUP=false
```

## 4. Frontend variables

Set these on the frontend Railway service before building:

```text
VITE_BACKEND_URL=https://<your-backend-domain>
VITE_CLERK_PUBLISHABLE_KEY=<your Clerk publishable key>
VITE_ENVIRONMENT=prod
VITE_DEBUG=false
VITE_LOG_LEVEL=error
```

`VITE_BACKEND_URL` should not include `/api`; the app adds `/api` itself.

## 5. Clerk URLs

In Clerk, add the Railway frontend domain to the allowed origins/redirect URLs. If you use Clerk webhooks, point the webhook at the backend Railway domain.

## 6. Verify

After deployment:

- Backend liveness: `https://<backend-domain>/api/health`
- Backend readiness: `https://<backend-domain>/api/health/ready`
- Backend docs: `https://<backend-domain>/docs`
- Frontend: `https://<frontend-domain>`

If readiness fails but liveness succeeds, check the backend deployment logs first. Database URL, migrations, or missing required integration variables are the most likely causes.
