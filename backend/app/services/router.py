import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class WorkerState:
    name: str
    base_url: str
    busy: int = 0
    healthy: bool = True
    failures: int = 0
    last_latency_ms: float = 0.0
    last_checked_at: float = 0.0
    circuit_open_until: float = 0.0


WORKER_HOST = os.getenv("AI_WORKER_HOST", "127.0.0.1")
WORKER_PORTS = [part.strip() for part in os.getenv("AI_WORKER_PORTS", "8001,8002,8003").split(",") if part.strip()]
ROUTER_STRATEGY = os.getenv("ROUTER_STRATEGY", "least-busy").strip().lower()
ROUTER_HEALTH_TTL_SECONDS = float(os.getenv("ROUTER_HEALTH_TTL_SECONDS", "5"))
ROUTER_FAILURE_THRESHOLD = int(os.getenv("ROUTER_FAILURE_THRESHOLD", "2"))
ROUTER_CIRCUIT_OPEN_SECONDS = float(os.getenv("ROUTER_CIRCUIT_OPEN_SECONDS", "20"))
ROUTER_MAX_RETRIES = int(os.getenv("ROUTER_MAX_RETRIES", "2"))
ROUTER_TIMEOUT_SECONDS = float(os.getenv("ROUTER_TIMEOUT_SECONDS", "90"))

_workers: list[WorkerState] = [
    WorkerState(name=f"worker-{port}", base_url=f"http://{WORKER_HOST}:{port}")
    for port in WORKER_PORTS
]

_worker_select_lock = asyncio.Lock()
_round_robin_index = 0
_http_client = httpx.AsyncClient(
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=30),
    timeout=httpx.Timeout(ROUTER_TIMEOUT_SECONDS),
)


def _is_circuit_open(worker: WorkerState, now: float) -> bool:
    return worker.circuit_open_until > now


async def _probe_worker_health(worker: WorkerState, now: float) -> bool:
    if _is_circuit_open(worker, now):
        worker.healthy = False
        return False

    if now - worker.last_checked_at < ROUTER_HEALTH_TTL_SECONDS:
        return worker.healthy

    health_url = f"{worker.base_url}/worker/health"
    worker.last_checked_at = now

    try:
        started = time.perf_counter()
        response = await _http_client.get(health_url)
        elapsed_ms = (time.perf_counter() - started) * 1000
        worker.last_latency_ms = elapsed_ms
        worker.healthy = response.status_code == 200
        if worker.healthy:
            worker.failures = 0
        return worker.healthy
    except Exception as exc:
        worker.healthy = False
        worker.failures += 1
        logger.warning("health probe failed for %s: %s", worker.name, exc)
        if worker.failures >= ROUTER_FAILURE_THRESHOLD:
            worker.circuit_open_until = now + ROUTER_CIRCUIT_OPEN_SECONDS
        return False


def _worker_weight(worker: WorkerState) -> tuple[int, float]:
    return worker.busy, worker.last_latency_ms


async def _choose_worker(exclude: set[str] | None = None) -> WorkerState | None:
    now = time.time()
    excluded = exclude or set()

    available = []
    for worker in _workers:
        if worker.name in excluded:
            continue
        if await _probe_worker_health(worker, now):
            available.append(worker)

    if not available:
        return None

    if ROUTER_STRATEGY == "round-robin":
        global _round_robin_index
        async with _worker_select_lock:
            selected = available[_round_robin_index % len(available)]
            _round_robin_index += 1
            return selected

    # Default: least-busy with latency tie-breaker.
    available.sort(key=_worker_weight)
    return available[0]


def _mark_success(worker: WorkerState, elapsed_ms: float) -> None:
    worker.healthy = True
    worker.failures = 0
    worker.last_latency_ms = elapsed_ms


def _mark_failure(worker: WorkerState) -> None:
    worker.failures += 1
    worker.healthy = False
    if worker.failures >= ROUTER_FAILURE_THRESHOLD:
        worker.circuit_open_until = time.time() + ROUTER_CIRCUIT_OPEN_SECONDS


def _should_retry_status(status_code: int) -> bool:
    return status_code in (429, 500, 502, 503, 504)


def _is_quota_error_text(text: str) -> bool:
    value = (text or "").lower()
    return "rate_limit_exceeded" in value or "tokens per minute" in value or "quota" in value or "429" in value


async def route_request(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Route a request to the best available worker.

    Retries other workers on transient errors (429/5xx) or transport failures.
    """
    if not _workers:
        raise RuntimeError("No AI workers configured")

    attempted_workers: set[str] = set()
    total_attempts = ROUTER_MAX_RETRIES + 1
    last_error: str | None = None
    logger.info("router_incoming endpoint=%s payload_keys=%s", endpoint, list((payload or {}).keys()))

    for attempt in range(1, total_attempts + 1):
        worker = await _choose_worker(exclude=attempted_workers)
        if not worker:
            break

        attempted_workers.add(worker.name)
        worker.busy += 1
        started = time.perf_counter()

        try:
            url = f"{worker.base_url}{endpoint}"
            response = await _http_client.post(url, json=payload)
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "router_request endpoint=%s worker=%s status=%s duration_ms=%.1f attempt=%s",
                endpoint,
                worker.base_url,
                response.status_code,
                elapsed_ms,
                attempt,
            )

            if response.status_code == 200:
                _mark_success(worker, elapsed_ms)
                return response.json()

            if _should_retry_status(response.status_code):
                _mark_failure(worker)
                last_error = f"worker={worker.name} status={response.status_code}"
                logger.warning(
                    "router_retry endpoint=%s worker=%s status=%s attempt=%s",
                    endpoint,
                    worker.base_url,
                    response.status_code,
                    attempt,
                )
                continue

            _mark_failure(worker)
            response.raise_for_status()

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            _mark_failure(worker)
            last_error = str(exc)
            logger.warning(
                "router failure endpoint=%s worker=%s duration_ms=%.1f attempt=%s error=%s",
                endpoint,
                worker.base_url,
                elapsed_ms,
                attempt,
                exc,
            )
        finally:
            worker.busy = max(0, worker.busy - 1)

    if last_error and _is_quota_error_text(last_error):
        logger.error("router_fallback_triggered endpoint=%s reason=%s", endpoint, last_error)

    raise RuntimeError(f"All workers failed for endpoint {endpoint}. last_error={last_error or 'unknown'}")


async def get_workers_health() -> dict[str, Any]:
    now = time.time()
    workers = []

    for worker in _workers:
        healthy = await _probe_worker_health(worker, now)
        workers.append(
            {
                "name": worker.name,
                "base_url": worker.base_url,
                "healthy": healthy,
                "busy": worker.busy,
                "last_latency_ms": round(worker.last_latency_ms, 2),
                "failures": worker.failures,
                "circuit_open_until": worker.circuit_open_until,
            }
        )

    healthy_count = sum(1 for worker in workers if worker["healthy"])
    return {
        "strategy": ROUTER_STRATEGY,
        "healthy_workers": healthy_count,
        "total_workers": len(workers),
        "workers": workers,
    }
