"""Visit Counter - a tiny Flask + Redis app built to be containerised and orchestrated."""

import json
import logging
import os
import socket
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import redis
from flask import Flask, jsonify, render_template, request

STARTED_AT = time.time()
HOSTNAME = socket.gethostname()
VISITOR_COOKIE = "vid"
RECENT_LIMIT = 50


def _configure_logging() -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter('{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}')
    )
    logger = logging.getLogger("counter")
    if not logger.handlers:
        logger.addHandler(handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    return logger


def _redis_from_env() -> redis.Redis:
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASSWORD") or None,
        db=int(os.getenv("REDIS_DB", "0")),
        decode_responses=True,
        socket_timeout=2,
        socket_connect_timeout=2,
    )


def create_app(redis_client=None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        APP_TITLE=os.getenv("APP_TITLE", "Visit Counter"),
        APP_VERSION=os.getenv("APP_VERSION", "1.0.0"),
        APP_ENV=os.getenv("APP_ENV", "local"),
        KEY_PREFIX=os.getenv("REDIS_KEY_PREFIX", "vc"),
    )
    log = _configure_logging()
    r = redis_client if redis_client is not None else _redis_from_env()
    prefix = app.config["KEY_PREFIX"]

    def key(*parts: str) -> str:
        return ":".join((prefix, *parts))

    def now() -> datetime:
        return datetime.now(timezone.utc)

    def instance_info() -> dict:
        return {
            "host": HOSTNAME,
            "version": app.config["APP_VERSION"],
            "env": app.config["APP_ENV"],
            "uptime_seconds": int(time.time() - STARTED_AT),
        }

    def collect_stats() -> dict:
        ref = now()
        hours = [
            (ref - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
            for i in range(23, -1, -1)
        ]
        pipe = r.pipeline(transaction=False)
        pipe.get(key("total"))
        pipe.get(key("day", ref.strftime("%Y%m%d")))
        pipe.pfcount(key("visitors"))
        pipe.hgetall(key("served_by"))
        pipe.lrange(key("recent"), 0, 9)
        pipe.mget([key("hour", h.strftime("%Y%m%d%H")) for h in hours])
        total, today, unique, served, recent, hourly = pipe.execute()

        return {
            "total": int(total or 0),
            "today": int(today or 0),
            "unique": int(unique or 0),
            "hourly": [
                {"hour": h.isoformat(), "count": int(c or 0)} for h, c in zip(hours, hourly)
            ],
            "served_by": sorted(
                ({"host": h, "count": int(c)} for h, c in (served or {}).items()),
                key=lambda x: -x["count"],
            ),
            "recent": [json.loads(item) for item in recent],
            "instance": instance_info(),
        }

    # ---------- pages ----------

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            title=app.config["APP_TITLE"],
            version=app.config["APP_VERSION"],
            env=app.config["APP_ENV"],
            host=HOSTNAME,
        )

    # ---------- API ----------

    @app.post("/api/visit")
    def visit():
        existing = request.cookies.get(VISITOR_COOKIE)
        vid = existing or uuid.uuid4().hex
        ref = now()

        number = r.incr(key("total"))
        day_key = key("day", ref.strftime("%Y%m%d"))
        hour_key = key("hour", ref.strftime("%Y%m%d%H"))
        entry = {"n": number, "at": ref.isoformat(), "host": HOSTNAME, "visitor": vid[:6]}

        pipe = r.pipeline(transaction=True)
        pipe.incr(day_key)
        pipe.expire(day_key, 60 * 60 * 24 * 35)
        pipe.incr(hour_key)
        pipe.expire(hour_key, 60 * 60 * 48)
        pipe.pfadd(key("visitors"), vid)
        pipe.hincrby(key("served_by"), HOSTNAME, 1)
        pipe.lpush(key("recent"), json.dumps(entry))
        pipe.ltrim(key("recent"), 0, RECENT_LIMIT - 1)
        pipe.execute()

        log.info(f"visit n={number} visitor={vid[:6]} host={HOSTNAME}")

        stats = collect_stats()
        stats["you"] = {"number": number, "visitor": vid[:6], "returning": bool(existing)}
        resp = jsonify(stats)
        resp.set_cookie(
            VISITOR_COOKIE, vid, max_age=60 * 60 * 24 * 365, httponly=True, samesite="Lax"
        )
        return resp

    @app.get("/api/stats")
    def stats():
        return jsonify(collect_stats())

    # ---------- ops ----------

    @app.get("/health")
    def health():
        """Liveness: the process is up. Does not touch Redis."""
        return jsonify(status="ok", host=HOSTNAME)

    @app.get("/ready")
    def ready():
        """Readiness: we can serve traffic only if Redis answers."""
        try:
            r.ping()
            return jsonify(status="ready", redis="up", host=HOSTNAME)
        except redis.RedisError as exc:
            log.warning(f"readiness failed: {exc}")
            return jsonify(status="not_ready", redis="down", host=HOSTNAME), 503

    @app.get("/metrics")
    def metrics():
        """Prometheus text format."""
        lines = [
            "# HELP visit_counter_info Instance information.",
            "# TYPE visit_counter_info gauge",
            f'visit_counter_info{{host="{HOSTNAME}",version="{app.config["APP_VERSION"]}"}} 1',
            "# HELP visit_counter_uptime_seconds Seconds since the process started.",
            "# TYPE visit_counter_uptime_seconds gauge",
            f"visit_counter_uptime_seconds {int(time.time() - STARTED_AT)}",
        ]
        try:
            total = int(r.get(key("total")) or 0)
            unique = int(r.pfcount(key("visitors")) or 0)
            up = 1
        except redis.RedisError:
            total = unique = None
            up = 0
        lines += [
            "# HELP visit_counter_redis_up Whether Redis is reachable.",
            "# TYPE visit_counter_redis_up gauge",
            f"visit_counter_redis_up {up}",
        ]
        if up:
            lines += [
                "# HELP visit_counter_visits_total Total visits recorded.",
                "# TYPE visit_counter_visits_total counter",
                f"visit_counter_visits_total {total}",
                "# HELP visit_counter_unique_visitors Approximate unique visitors.",
                "# TYPE visit_counter_unique_visitors gauge",
                f"visit_counter_unique_visitors {unique}",
            ]
        return "\n".join(lines) + "\n", 200, {"Content-Type": "text/plain; version=0.0.4"}

    # ---------- errors & headers ----------

    @app.errorhandler(redis.RedisError)
    def redis_down(exc):
        log.error(f"redis error: {exc}")
        return jsonify(error="redis_unavailable", host=HOSTNAME), 503

    @app.after_request
    def headers(resp):
        resp.headers["X-Served-By"] = HOSTNAME
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        return resp

    return app
