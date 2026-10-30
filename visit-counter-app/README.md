# Visit Counter

A tiny Flask + Redis app that counts visits, built as a playground for **Docker**, **Kubernetes** and **Terraform**.
The app is intentionally simple. The interesting part is how it's packaged, deployed and operated.

It shows which instance (container / pod) served each request, so load balancing across replicas is visible right in the UI.

## Features

- Live dashboard: your visitor number, totals, unique visitors (HyperLogLog), last-24h chart, traffic per instance, recent visits
- Stateless app, all state in Redis, so you can scale horizontally
- Ops endpoints ready for orchestration: liveness, readiness, Prometheus metrics
- 12-factor config via environment variables
- Structured JSON logs to stdout
- Dark/light theme, responsive, honours reduced motion

## Run locally

```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine   # or any local Redis

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python wsgi.py                                          # http://localhost:8000
```

Production server:

```bash
gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app
```

## Configuration

| Variable           | Default         | Description                      |
|--------------------|-----------------|----------------------------------|
| `REDIS_HOST`       | `localhost`     | Redis hostname / service name    |
| `REDIS_PORT`       | `6379`          | Redis port                       |
| `REDIS_PASSWORD`   | *(empty)*       | Redis password (use a Secret)    |
| `REDIS_DB`         | `0`             | Redis database index             |
| `REDIS_KEY_PREFIX` | `vc`            | Prefix for all Redis keys        |
| `APP_TITLE`        | `Visit Counter` | Title shown in the UI            |
| `APP_VERSION`      | `1.0.0`         | Shown in UI and `/metrics`       |
| `APP_ENV`          | `local`         | Environment badge in the UI      |
| `LOG_LEVEL`        | `INFO`          | Python log level                 |
| `PORT`             | `8000`          | Port for the dev server only     |

## Endpoints

| Method | Path          | Purpose                                                    |
|--------|---------------|------------------------------------------------------------|
| GET    | `/`           | Web UI                                                     |
| POST   | `/api/visit`  | Record a visit, return stats + your visitor number         |
| GET    | `/api/stats`  | Current stats (JSON)                                       |
| GET    | `/health`     | **Liveness**: process is up (never touches Redis)          |
| GET    | `/ready`      | **Readiness**: 200 if Redis answers, 503 otherwise         |
| GET    | `/metrics`    | Prometheus metrics                                         |

Every response carries an `X-Served-By` header with the hostname, e.g.
`curl -sI localhost:8000/health | grep -i served`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Tests use `fakeredis`, so no Redis is needed.

## Project layout

```
counter/
  __init__.py        # app factory, routes, Redis logic
  templates/index.html
  static/style.css
  static/app.js
tests/test_app.py
wsgi.py              # entrypoint (gunicorn wsgi:app)
```

## Roadmap

- [ ] Docker: Dockerfile + docker-compose (app + Redis + volume)
- [ ] Kubernetes: Deployment, Service, Ingress, ConfigMap, Secret, PVC, probes
- [ ] Terraform: provision a local cluster and deploy the stack
