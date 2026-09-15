"""
Concurrency-Safe Pareto Frontier & Lessons Registry for Graph-Powered GEPA.

Implements Spec §4 and §5:
  - Global companion lock on artifacts/gepa/gepa_ledger.lock using non-blocking
    fcntl.flock with exponential backoff retry.
  - Atomic publication of pareto_frontier.json and lessons.json via staging files.
  - Append-only audit logging to mutations.jsonl.
  - Taxonomy-indexed Pareto-optimal prompt retrieval and lesson storage.
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .clock import RunClock
from .reflector_schemas import (
    TaxonomyBucket,
    get_static_baseline_prompt,
)

logger = logging.getLogger("gepa.pareto_registry")

DEFAULT_GEPA_DIR = Path("artifacts/gepa")
DEFAULT_LOCK_TIMEOUT_SECONDS = 5.0
DEFAULT_HALF_LIFE_DAYS = 30.0
DEFAULT_MIN_CORROBORATION = 2


# ---------------------------------------------------------------------------
# §5.2  Concurrency Lock Context Manager
# ---------------------------------------------------------------------------


class GepaLockTimeoutError(TimeoutError):
    """Raised when unable to acquire the global GEPA companion lock within timeout."""


@contextmanager
def gepa_lock(
    lock_file: Path,
    timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
    initial_sleep: float = 0.01,
    max_sleep: float = 0.5,
) -> Iterator[int]:
    """
    Acquire a process-safe exclusive lock on `lock_file` using non-blocking
    fcntl.flock with exponential backoff retry.

    Args:
        lock_file: Path to the .lock file.
        timeout: Maximum seconds to wait before raising GepaLockTimeoutError.
        initial_sleep: Initial retry interval in seconds.
        max_sleep: Maximum sleep cap per retry.

    Yields:
        Open file descriptor of the acquired lock.
    """
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        os.fchmod(fd, 0o600)
    except OSError:
        pass
    start_time = time.monotonic()
    sleep_interval = initial_sleep

    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    raise GepaLockTimeoutError(
                        f"Failed to acquire GEPA lock on {lock_file} after {elapsed:.2f}s (timeout={timeout}s)"
                    )
                time.sleep(min(sleep_interval, timeout - elapsed))
                sleep_interval = min(sleep_interval * 1.5, max_sleep)

        yield fd
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(fd)


# ---------------------------------------------------------------------------
# §5.2  Atomic File I/O Helpers
# ---------------------------------------------------------------------------


def atomic_write_json(file_path: Path, data: Any) -> None:
    """
    Atomically serialize data to a JSON file via a temporary file and os.replace.
    Prevents partial reads or corrupted JSON on interrupted writes.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = file_path.with_name(
        f"{file_path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}"
    )
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, file_path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def append_audit_log(entry: Dict[str, Any], log_path: Path) -> None:
    """Append a single structured JSON audit record to the JSONL log file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


# ---------------------------------------------------------------------------
# §5.1 / §5.2  Pareto Frontier & Lessons Registry
# ---------------------------------------------------------------------------


class ParetoRegistry:
    """
    Concurrency-safe storage and retrieval manager for:
      - Taxonomy-indexed Pareto prompt variants (pareto_frontier.json)
      - Experiential lessons and dead ends (lessons.json)
      - Immutable audit log of prompt mutations (mutations.jsonl)
    """

    def __init__(self, gepa_dir: Path | str = DEFAULT_GEPA_DIR) -> None:
        self.gepa_dir = Path(gepa_dir).resolve()
        self.lock_path = self.gepa_dir / "gepa_ledger.lock"
        self.frontier_path = self.gepa_dir / "pareto_frontier.json"
        self.lessons_path = self.gepa_dir / "lessons.json"
        self.mutations_log_path = self.gepa_dir / "mutations.jsonl"
        self.traces_log_path = self.gepa_dir / "traces.jsonl"
        self.gepa_dir.mkdir(parents=True, exist_ok=True)

    def _lock(self, timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS):
        """Helper to acquire the global GEPA lock."""
        return gepa_lock(self.lock_path, timeout=timeout)

    def _load_json_unlocked(self, path: Path, default: Any) -> Any:
        """Load JSON from path if it exists, otherwise return default."""
        if not path.exists():
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to parse %s, using default: %s", path, e)
            return default

    # ── Pareto Frontier Operations ─────────────────────────────────────────

    def get_pareto_prompt(self, taxonomy: TaxonomyBucket) -> str:
        """
        Retrieve the current best Pareto-optimal system prompt for the given taxonomy bucket.
        Falls back to the static specialist baseline prompt if no variant is registered.
        """
        with self._lock():
            frontier = self._load_json_unlocked(self.frontier_path, {})
            bucket_data = frontier.get(taxonomy)
            if bucket_data and isinstance(bucket_data, dict) and bucket_data.get("prompt"):
                return str(bucket_data["prompt"])

        # Fallback to static baseline specialist prompt per Spec §3.4
        try:
            return get_static_baseline_prompt(taxonomy)
        except KeyError:
            return ""

    def get_pareto_variant_id(self, taxonomy: TaxonomyBucket) -> str:
        """Return the active variant ID for the given taxonomy bucket (or 'baseline_v0')."""
        with self._lock():
            frontier = self._load_json_unlocked(self.frontier_path, {})
            bucket_data = frontier.get(taxonomy)
            if bucket_data and isinstance(bucket_data, dict) and bucket_data.get("variant_id"):
                return str(bucket_data["variant_id"])
        return "baseline_v0"

    def register_pareto_prompt(
        self,
        taxonomy: TaxonomyBucket,
        prompt: str,
        variant_id: str,
        score: float,
        rationale: str = "",
        topological_rule: str = "",
    ) -> None:
        """
        Register a new or updated Pareto prompt variant for a taxonomy bucket.
        Updates pareto_frontier.json atomically and logs to mutations.jsonl.
        """
        timestamp = RunClock.from_env().now_iso()
        with self._lock():
            frontier = self._load_json_unlocked(self.frontier_path, {})
            current_entry = frontier.get(taxonomy, {})
            current_score = current_entry.get("score", -float("inf"))
            current_prompt = str(current_entry.get("prompt", "")).strip()
            baseline_prompt = get_static_baseline_prompt(taxonomy).strip()
            is_current_baseline = (
                not current_prompt
                or current_prompt == baseline_prompt
                or current_entry.get("variant_id") in ("baseline_v0", "", None)
            )

            # Update if strictly better score, fresh entry, or replacing static baseline with a validated variant
            if not current_entry or score > current_score or (is_current_baseline and score >= 0):
                effective_score = score if is_current_baseline else max(score, current_score)
                frontier[taxonomy] = {
                    "variant_id": variant_id,
                    "prompt": prompt,
                    "score": round(effective_score, 6),
                    "rationale": rationale,
                    "topological_rule": topological_rule,
                    "updated_at": timestamp,
                }
                atomic_write_json(self.frontier_path, frontier)

            # Log unconditionally to append-only audit trail
            append_audit_log(
                {
                    "event": "prompt_mutation",
                    "taxonomy_bucket": taxonomy,
                    "variant_id": variant_id,
                    "score": round(score, 6),
                    "rationale": rationale,
                    "topological_rule": topological_rule,
                    "timestamp": timestamp,
                },
                self.mutations_log_path,
            )

    def _group_traces_by_bucket_and_variant(
        self, traces: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        traces_by_bucket: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for t in traces:
            bucket = t.get("taxonomy_bucket")
            var_id = t.get("canonical_mutation_id")
            if bucket and var_id and var_id != "baseline_v0":
                traces_by_bucket.setdefault(bucket, {}).setdefault(var_id, []).append(t)
        return traces_by_bucket

    def _find_best_variant_for_bucket(
        self,
        var_dict: Dict[str, List[Dict[str, Any]]],
        now_iso: str,
    ) -> Optional[tuple[str, Dict[str, Any], float]]:
        from .reflector import calculate_rule_score  # local import breaks cycle
        best_var = None
        best_score = -float("inf")
        for var_id, var_traces in var_dict.items():
            score = calculate_rule_score(var_traces, now_iso)
            if score > best_score:
                best_score = score
                best_var = (var_id, var_traces[-1], score)
        return best_var

    @staticmethod
    def _extract_prompt_from_traces(var_traces: List[Dict[str, Any]], bucket: TaxonomyBucket) -> str:
        """Extract the most recent prompt from trace details, falling back to static baseline."""
        for t in reversed(var_traces):
            prompt = t.get("details", {}).get("prompt") or t.get("prompt")
            if prompt and str(prompt).strip():
                return str(prompt).strip()
        try:
            return get_static_baseline_prompt(bucket)
        except KeyError:
            return ""

    def _compute_bucket_frontier_entry(
        self,
        bucket: TaxonomyBucket,
        var_dict: Dict[str, List[Dict[str, Any]]],
        now_iso: str,
    ) -> Optional[Dict[str, Any]]:
        """Compute the highest-scoring Pareto entry for a taxonomy bucket."""
        best = self._find_best_variant_for_bucket(var_dict, now_iso)
        if not best or best[2] <= 0:
            return None

        var_id, last_trace, score = best
        var_traces = var_dict.get(var_id, [last_trace])
        prompt = self._extract_prompt_from_traces(var_traces, bucket)
        if not prompt or not prompt.strip():
            return None
        return {
            "variant_id": var_id,
            "prompt": prompt,
            "score": round(score, 6),
            "updated_at": now_iso,
        }

    def sync_pareto_frontier(self) -> None:
        """
        Consolidate all recorded attempt traces across mutations and update
        the active pareto_frontier.json entry for each taxonomy bucket based on
        highest empirical time-decayed signed score.
        """
        with self._lock():
            traces = self._load_recent_traces_unlocked(limit=1000)
            if not traces:
                return

            traces_by_bucket = self._group_traces_by_bucket_and_variant(traces)
            frontier = self._load_json_unlocked(self.frontier_path, {})
            now_iso = RunClock.from_env().now_iso()

            for bucket, var_dict in traces_by_bucket.items():
                entry = self._compute_bucket_frontier_entry(bucket, var_dict, now_iso)
                if entry:
                    frontier[bucket] = entry

            if frontier:
                atomic_write_json(self.frontier_path, frontier)

    # ── Lessons & Dead-End Operations ──────────────────────────────────────

    def get_lessons(self, taxonomy: Optional[TaxonomyBucket] = None) -> Dict[str, Any]:
        """
        Retrieve experiential lessons (preferred rules, contested rules, known dead ends).
        Optionally filtered to a specific taxonomy bucket.
        """
        with self._lock():
            data = self._load_json_unlocked(self.lessons_path, {})
            if taxonomy is not None:
                return data.get(taxonomy, {"preferred_rules": [], "known_dead_ends": []})
            return data

    def get_known_dead_ends(self, taxonomy: TaxonomyBucket) -> List[str]:
        """Return the list of negative constraints / known dead-ends for a taxonomy bucket."""
        with self._lock():
            data = self._load_json_unlocked(self.lessons_path, {})
            bucket_data = data.get(taxonomy, {})
            return list(bucket_data.get("known_dead_ends", []))

    def record_attempt_trace(
        self,
        taxonomy: TaxonomyBucket,
        predicate_family: str,
        seed_id: str,
        scenario_id: str,
        attempt_index: int,
        outcome: str,
        canonical_mutation_id: str,
        observed_at: str,
        evaluated_at: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record an immutable attempt evaluation trace in traces.jsonl."""
        record: Dict[str, Any] = {
            "taxonomy_bucket": taxonomy,
            "seed_id": seed_id,
            "scenario_id": scenario_id,
            "predicate_family": predicate_family,
            "attempt_index": attempt_index,
            "outcome": outcome,
            "canonical_mutation_id": canonical_mutation_id,
            "observed_at": observed_at,
            "evaluated_at": evaluated_at,
            "details": details or {},
        }
        with self._lock():
            append_audit_log(record, self.traces_log_path)

    def add_dead_end_constraint(self, taxonomy: TaxonomyBucket, constraint: str) -> None:
        """Add an explicit negative constraint / dead end to lessons.json."""
        with self._lock():
            data = self._load_json_unlocked(self.lessons_path, {})
            bucket_data = data.setdefault(taxonomy, {
                "preferred_rules": [],
                "known_dead_ends": [],
            })
            dead_ends: List[str] = bucket_data.setdefault("known_dead_ends", [])
            if constraint not in dead_ends:
                dead_ends.append(constraint)
                atomic_write_json(self.lessons_path, data)

    def _load_recent_traces_unlocked(
        self,
        taxonomy: Optional[TaxonomyBucket] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if not self.traces_log_path.exists():
            return []
        traces: List[Dict[str, Any]] = []
        try:
            with open(self.traces_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        t = json.loads(line)
                        if taxonomy is None or t.get("taxonomy_bucket") == taxonomy:
                            traces.append(t)
                    except json.JSONDecodeError:
                        continue
        except OSError as e:
            logger.warning("Error reading traces log %s: %s", self.traces_log_path, e)
        return traces[-limit:] if limit > 0 else traces

    def get_recent_traces(
        self,
        taxonomy: Optional[TaxonomyBucket] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return recent historical traces, optionally filtered by taxonomy bucket."""
        with self._lock():
            return self._load_recent_traces_unlocked(taxonomy, limit)

    def get_recent_traces_for_mutation(
        self,
        taxonomy: TaxonomyBucket,
        canonical_mutation_id: str,
    ) -> List[Dict[str, Any]]:
        """Return all historical traces for a specific mutation identifier in a taxonomy bucket."""
        with self._lock():
            if not self.traces_log_path.exists():
                return []
            matching_traces: List[Dict[str, Any]] = []
            try:
                with open(self.traces_log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            t = json.loads(line)
                            if (
                                t.get("taxonomy_bucket") == taxonomy
                                and t.get("canonical_mutation_id") == canonical_mutation_id
                            ):
                                matching_traces.append(t)
                        except json.JSONDecodeError:
                            continue
            except OSError as e:
                logger.warning("Error reading traces log %s: %s", self.traces_log_path, e)
            return matching_traces
