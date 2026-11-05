# Visit Counter

This mini project demonstrates my knowledge and hands-on experience with Docker
and Kubernetes by containerizing and deploying a small web application.

A small Flask application that tracks visits and displays statistics in a
dashboard. It uses Redis to store state, keeping data independent of the
application container and allowing multiple replicas to share it.

## Features

- Total and daily visits, estimated unique visitors, and a chart of traffic
  over the last 24 hours.
- Recent visits and the container that served each request.
- Health endpoints for liveness and readiness checks.
- Prometheus metrics at `/metrics`.
- Docker Compose setup with separate frontend/backend networks and a persistent
  volume for Redis data.

## Requirements

- Docker Desktop or Docker Engine with Docker Compose v2.

## Run with Docker Compose

From the repository root, run:

```shell
docker compose up --build
```

The first run builds the application image and starts the `redis` and `app`
services. When startup is complete, open
[http://localhost:8000](http://localhost:8000). Redis does not publish a port
to the host; it is only accessible to the application over Docker's internal
network.

To run in the background:

```shell
docker compose up --build -d
```

Useful commands:

```shell
# Container status
docker compose ps

# Logs from all services
docker compose logs -f

# Application logs only
docker compose logs -f app

# Stop containers and remove networks
docker compose down
```

Redis data is stored in the named volume `redis-data` and persists after
`docker compose down`. To remove the data as well:

```shell
docker compose down --volumes
```

Deleting the volume permanently removes the Redis data.

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Web dashboard |
| `POST` | `/api/visit` | Records a visit and returns updated statistics |
| `GET` | `/api/stats` | Current statistics as JSON |
| `GET` | `/health` | Liveness check — verifies that the application is running |
| `GET` | `/ready` | Readiness check — also verifies the Redis connection |
| `GET` | `/metrics` | Prometheus metrics |

## Configuration

The application reads configuration from environment variables, including
`REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `APP_TITLE`, `APP_VERSION`,
`APP_ENV`, and `LOG_LEVEL`. In Docker Compose, `REDIS_HOST` is set to `redis`,
the name of the Redis service. See
[`visit-counter-app/README.md`](./visit-counter-app/README.md) for defaults and
the complete list of settings.

## Repository layout

- [`visit-counter-app/`](./visit-counter-app/) — application source code,
  Dockerfile, and tests.
- [`docker-compose.yml`](./docker-compose.yml) — local Docker Compose setup.
- [`kubernetes-enviroment/`](./kubernetes-enviroment/) — Kubernetes manifests and
  deployment instructions.