import argparse
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple


GENERIC_ANCHOR_PATTERNS = [
    r"\bmissing\b",
    r"\bno\b.*\bvalidation\b",
    r"\bbounds\s*check(ing)?\b",
    r"\bmemory\s+safety\b",
    r"\blogic\s+error(s)?\b",
    r"\bvulnerab(le|ility)\b",
    r"\bunsafe\b",
    r"\bexploit\b",
    r"\battack(er)?\b",
]

OUTPUT_PREDICATE_FIELD = "output.predicate"
OUTPUT_ANCHORS_FIELD = "output.anchors"
OUTPUT_COUNTERFACTUAL_FIELD = "output.counterfactual"
OUTPUT_VERIFIER_REPORT_FIELD = "output.verifier_report"
OUTPUT_SUPPORT_LEVEL_FIELD = "output.support_level"


def _iter_jsonl(path: str) -> Iterable[Tuple[int, Dict[str, Any]]]:
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield lineno, json.loads(line)
            except Exception as e:
                raise ValueError(f"Invalid JSON on line {lineno}: {e}") from e


def _get(d: Dict[str, Any], path: str) -> Any:
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _valid_verifier_report(value: Any) -> bool:
    if isinstance(value, dict):
        return len(value) > 0
    if isinstance(value, str):
        return value.strip() != ""
    return False


def _nonempty_logic_error(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _logic_error_from_raw_response(raw_response: Any) -> Optional[str]:
    if not isinstance(raw_response, str) or not raw_response.strip():
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(raw_response.strip())
    except Exception:
        return None
    if isinstance(data, dict):
        logic_error = data.get("logic_error")
        if _nonempty_logic_error(logic_error):
            return logic_error
    return None


def _logic_error_from_attempt(attempt: Dict[str, Any]) -> Optional[str]:
    logic_error = attempt.get("logic_error")
    if _nonempty_logic_error(logic_error):
        return logic_error

    verifier = attempt.get("verifier")
    if isinstance(verifier, dict):
        logic_error = verifier.get("logic_error")
        if _nonempty_logic_error(logic_error):
            return logic_error
        return _logic_error_from_raw_response(verifier.get("raw_response"))
    return None


def _logic_error_from_row(row: Dict[str, Any]) -> Optional[str]:
    verifier_report = _get(row, OUTPUT_VERIFIER_REPORT_FIELD)
    if isinstance(verifier_report, dict):
        logic_error = verifier_report.get("logic_error")
        if _nonempty_logic_error(logic_error):
            return logic_error
    return None


def _anchor_matches_input(anchor: str, input_text: str, *, case_insensitive: bool) -> bool:
    if not _is_nonempty_str(anchor) or not _is_nonempty_str(input_text):
        return False
    if case_insensitive:
        return anchor.lower() in input_text.lower()
    return anchor in input_text


def _is_generic_anchor(anchor: str) -> bool:
    if not _is_nonempty_str(anchor):
        return True
    lowered = anchor.lower()
    for pat in GENERIC_ANCHOR_PATTERNS:
        if re.search(pat, lowered):
            return True
    return False


@dataclass
class BGateThresholds:
    min_accepted_rows: int = 1
    max_unsupported_in_accepted_rate: float = 0.05
    max_inconclusive_in_accepted_rate: float = 0.20
    min_anchor_match_rate: float = 0.80
    min_verifier_pass_rate: float = 0.0
    min_verifier_parse_ok_rate: float = 0.0
    max_accepted_logic_error_rate: float = 0.0
    max_cost_per_accepted_row: Optional[float] = None
    max_tokens_per_accepted_row: Optional[float] = None

    def __post_init__(self) -> None:
        if self.min_accepted_rows < 1:
            raise ValueError(f"min_accepted_rows must be >= 1, got {self.min_accepted_rows}")


@dataclass
class BGateConfig:
    case_insensitive_anchor_match: bool = True
    require_fields: bool = True
    require_min_anchors: int = 2
    require_anchor_match: bool = True
    thresholds: Optional[BGateThresholds] = None


def _check_row_missing_fields(
    row: Dict[str, Any], required_fields: List[str], config: BGateConfig
) -> List[str]:
    missing_fields = []
    if not config.require_fields:
        return missing_fields

    for fpath in required_fields:
        val = _get(row, fpath)
        if fpath == OUTPUT_ANCHORS_FIELD:
            if not isinstance(val, list):
                missing_fields.append(fpath)
        elif fpath == OUTPUT_VERIFIER_REPORT_FIELD:
            if not _valid_verifier_report(val):
                missing_fields.append(fpath)
        elif not _is_nonempty_str(val):
            missing_fields.append(fpath)

    support_level = _get(row, OUTPUT_SUPPORT_LEVEL_FIELD)
    if support_level not in ("supported", "unsupported", "inconclusive"):
        missing_fields.append(f"{OUTPUT_SUPPORT_LEVEL_FIELD}(valid)")

    return missing_fields


def _eval_row_anchors(
    anchors: List[Any],
    input_text: Any,
    config: BGateConfig,
    lineno: int,
) -> Tuple[int, int, Optional[Dict[str, Any]]]:
    if len(anchors) < config.require_min_anchors:
        generic_cnt = sum(1 for a in anchors if _is_generic_anchor(str(a)))
        return 0, generic_cnt, {"line": lineno, "reason": "anchors_too_few", "anchors_len": len(anchors)}

    any_match = any(
        _anchor_matches_input(
            str(a),
            str(input_text or ""),
            case_insensitive=config.case_insensitive_anchor_match,
        )
        for a in anchors
    )
    match_cnt = 1 if any_match else 0
    failure = None
    if config.require_anchor_match and not any_match:
        failure = {"line": lineno, "reason": "no_anchor_matches_input"}

    generic_cnt = sum(1 for a in anchors if _is_generic_anchor(str(a)))
    return match_cnt, generic_cnt, failure


def _process_input_corpus(
    input_path: str, config: BGateConfig
) -> Tuple[int, int, int, int, int, int, int, int, List[Dict[str, Any]]]:
    total = accepted = unsupported = inconclusive = 0
    anchors_rows_total = anchors_with_match = anchors_items_total = anchors_generic_total = 0
    failures: List[Dict[str, Any]] = []

    required_fields = [
        OUTPUT_PREDICATE_FIELD,
        OUTPUT_ANCHORS_FIELD,
        OUTPUT_COUNTERFACTUAL_FIELD,
        OUTPUT_VERIFIER_REPORT_FIELD,
        OUTPUT_SUPPORT_LEVEL_FIELD,
    ]

    for lineno, row in _iter_jsonl(input_path):
        total += 1
        input_text = _get(row, "input")
        output_obj = _get(row, "output")
        if not isinstance(output_obj, dict):
            failures.append({"line": lineno, "reason": "missing_or_invalid_output_object"})
            continue

        missing_fields = _check_row_missing_fields(row, required_fields, config)
        anchors = _get(row, OUTPUT_ANCHORS_FIELD)
        if not isinstance(anchors, list):
            anchors = []

        if missing_fields:
            failures.append({"line": lineno, "reason": "missing_required_fields", "missing": missing_fields})
            continue

        accepted += 1
        support_level = _get(row, OUTPUT_SUPPORT_LEVEL_FIELD)
        if support_level == "unsupported":
            unsupported += 1
        elif support_level == "inconclusive":
            inconclusive += 1

        anchors_rows_total += 1
        anchors_items_total += len(anchors)

        match_cnt, generic_cnt, failure = _eval_row_anchors(anchors, input_text, config, lineno)
        anchors_with_match += match_cnt
        anchors_generic_total += generic_cnt
        if failure:
            failures.append(failure)

    return (
        total,
        accepted,
        unsupported,
        inconclusive,
        anchors_rows_total,
        anchors_with_match,
        anchors_items_total,
        anchors_generic_total,
        failures,
    )


def _accumulate_usage_breakdown(by_dict: Any, target_totals: Dict[str, Dict[str, float]]) -> None:
    if not isinstance(by_dict, dict):
        return
    for key, vals in by_dict.items():
        if isinstance(vals, dict):
            slot = target_totals.setdefault(
                str(key),
                {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0},
            )
            slot["calls"] += int(vals.get("calls") or 0)
            slot["prompt_tokens"] += int(vals.get("prompt_tokens") or 0)
            slot["completion_tokens"] += int(vals.get("completion_tokens") or 0)
            slot["total_tokens"] += int(vals.get("total_tokens") or 0)
            slot["cost_usd"] += float(vals.get("cost_usd") or 0.0)


@dataclass
class UsageAccumulator:
    gen_config_values: Dict[str, List[Any]]
    usage_stage_totals: Dict[str, Dict[str, float]]
    usage_model_totals: Dict[str, Dict[str, float]]
    usage_source_totals: Dict[str, int]


def _extract_gen_config(gen_config: Any, gen_config_values: Dict[str, List[Any]]) -> int:
    if isinstance(gen_config, dict) and gen_config:
        for k, v in gen_config.items():
            b = gen_config_values.setdefault(str(k), [])
            if v not in b:
                b.append(v)
        return 0
    return 1


def _extract_events_sources(events: Any, calls: int, missing_calls: int, source_totals: Dict[str, int]) -> None:
    if isinstance(events, list):
        for ev in events:
            if isinstance(ev, dict):
                src = str(ev.get("usage_source", "unknown"))
                source_totals[src] = source_totals.get(src, 0) + 1
    else:
        est = max(calls - missing_calls, 0)
        if est:
            source_totals["estimated_or_provider"] = source_totals.get("estimated_or_provider", 0) + est
        if missing_calls:
            source_totals["missing"] = source_totals.get("missing", 0) + missing_calls


def _process_attempt_usage(
    llm_usage: Dict[str, Any],
    acc: UsageAccumulator,
) -> Tuple[int, int, int, int, float, int, int]:
    missing_gen_config = _extract_gen_config(llm_usage.get("generation_config"), acc.gen_config_values)

    totals = llm_usage.get("totals") if isinstance(llm_usage.get("totals"), dict) else {}
    calls = int(totals.get("calls") or 0)
    prompt_tokens = int(totals.get("prompt_tokens") or 0)
    completion_tokens = int(totals.get("completion_tokens") or 0)
    total_tokens = int(totals.get("total_tokens") or 0)
    cost_usd = float(totals.get("cost_usd") or 0.0)
    missing_calls = int(totals.get("missing_usage_calls") or 0)

    _extract_events_sources(llm_usage.get("events"), calls, missing_calls, acc.usage_source_totals)
    _accumulate_usage_breakdown(llm_usage.get("by_stage"), acc.usage_stage_totals)
    _accumulate_usage_breakdown(llm_usage.get("by_model"), acc.usage_model_totals)

    return calls, prompt_tokens, completion_tokens, total_tokens, cost_usd, missing_calls, missing_gen_config


@dataclass
class AttemptMetrics:
    attempts_total: int = 0
    attempts_unsupported: int = 0
    attempts_inconclusive: int = 0
    attempts_soft_aboutness_total: int = 0
    attempts_soft_aboutness_fail: int = 0
    attempts_predicate_quality_total: int = 0
    attempts_predicate_quality_fail: int = 0
    attempts_soft_mech_total: int = 0
    attempts_soft_mech_fail: int = 0
    verifier_called: int = 0
    verifier_parse_ok: int = 0
    verifier_pass: int = 0
    prowin_total: int = 0
    verifier_called_on_prowin: int = 0
    accepted_with_not_applicable: int = 0
    accepted_attempt_logic_error_count: int = 0
    accepted_corpus_logic_error_count: int = 0
    accepted_logic_error_examples: List[Dict[str, Any]] = field(default_factory=list)
    disagreement_missing_or_parse_fail: int = 0
    disagreement_verifier_pass_anchor_strict_fail: int = 0
    attempts_b2_strict_total: int = 0
    attempts_b2_strict_fail: int = 0
    attempts_anchor_too_few: int = 0
    attempts_anchor_no_match: int = 0
    attempts_mechanism_evidence_failed: int = 0
    usage_calls_total: int = 0
    usage_prompt_tokens_total: int = 0
    usage_completion_tokens_total: int = 0
    usage_total_tokens_total: int = 0
    usage_cost_usd_total: float = 0.0
    usage_missing_usage_calls_total: int = 0
    generation_config_missing_attempts: int = 0
    usage_stage_totals: Dict[str, Dict[str, float]] = field(default_factory=dict)
    usage_model_totals: Dict[str, Dict[str, float]] = field(default_factory=dict)
    usage_source_totals: Dict[str, int] = field(default_factory=dict)
    generation_config_values: Dict[str, List[Any]] = field(default_factory=dict)


def _eval_attempt_soft_checks(attempt: Dict[str, Any], m: AttemptMetrics) -> None:
    soft = attempt.get("soft_checks") if isinstance(attempt, dict) else None
    if not isinstance(soft, dict):
        return

    pq = soft.get("predicate_quality")
    if isinstance(pq, dict) and "pass" in pq:
        m.attempts_predicate_quality_total += 1
        if not bool(pq.get("pass")):
            m.attempts_predicate_quality_fail += 1

    pa = soft.get("predicate_aboutness")
    if isinstance(pa, dict) and "pass" in pa:
        m.attempts_soft_aboutness_total += 1
        if not bool(pa.get("pass")):
            m.attempts_soft_aboutness_fail += 1

    mg = soft.get("mechanism_grounding")
    if isinstance(mg, dict) and "pass" in mg:
        m.attempts_soft_mech_total += 1
        if not bool(mg.get("pass")):
            m.attempts_soft_mech_fail += 1


def _record_verifier_stats(verifier: Optional[Dict[str, Any]], m: AttemptMetrics) -> None:
    if isinstance(verifier, dict):
        if bool(verifier.get("called")):
            m.verifier_called += 1
        if bool(verifier.get("parse_ok")):
            m.verifier_parse_ok += 1
        if verifier.get("passes_audit") is True:
            m.verifier_pass += 1


def _record_judge_prowin(
    attempt: Dict[str, Any], verifier: Optional[Dict[str, Any]], m: AttemptMetrics
) -> None:
    judge_eval = attempt.get("judge_eval") if isinstance(attempt, dict) else None
    if isinstance(judge_eval, dict) and judge_eval.get("winner") == "pro_debater":
        m.prowin_total += 1
        if isinstance(verifier, dict) and bool(verifier.get("called")):
            m.verifier_called_on_prowin += 1


def _record_accepted_attempt(
    attempt: Dict[str, Any], verifier: Optional[Dict[str, Any]], m: AttemptMetrics
) -> None:
    if attempt.get("decision") != "accepted":
        return

    parse_ok = bool(verifier.get("parse_ok")) if isinstance(verifier, dict) else False
    called = bool(verifier.get("called")) if isinstance(verifier, dict) else False
    if (not called) or (not parse_ok):
        m.disagreement_missing_or_parse_fail += 1

    logic_error = _logic_error_from_attempt(attempt)
    if _nonempty_logic_error(logic_error):
        m.accepted_attempt_logic_error_count += 1
        if len(m.accepted_logic_error_examples) < 5:
            m.accepted_logic_error_examples.append(
                {
                    "seed": attempt.get("seed"),
                    "predicate": attempt.get("predicate"),
                    "logic_error": logic_error,
                }
            )


def _record_disagreement_strict_fail(
    attempt: Dict[str, Any], verifier: Optional[Dict[str, Any]], m: AttemptMetrics
) -> None:
    if attempt.get("reject_reason") == "anchors_no_match":
        v_pass = False
        if isinstance(verifier, dict):
            v_pass = verifier.get("passes_audit") is True
        if v_pass:
            m.disagreement_verifier_pass_anchor_strict_fail += 1


def _eval_attempt_verifier_and_decision(attempt: Dict[str, Any], m: AttemptMetrics) -> None:
    verifier = attempt.get("verifier") if isinstance(attempt, dict) else None
    if isinstance(verifier, dict):
        _record_verifier_stats(verifier, m)
    else:
        verifier = None
    _record_judge_prowin(attempt, verifier, m)
    _record_accepted_attempt(attempt, verifier, m)
    _record_disagreement_strict_fail(attempt, verifier, m)


def _eval_attempt_b2_strict(attempt: Dict[str, Any], m: AttemptMetrics) -> None:
    reason = attempt.get("reject_reason")
    decision = attempt.get("decision")
    judge_eval = attempt.get("judge_eval")
    if isinstance(judge_eval, dict) or decision == "accepted":
        m.attempts_b2_strict_total += 1
        if reason in (
            "anchors_too_few_after_normalization",
            "anchors_no_match",
            "mechanism_evidence_failed",
        ):
            m.attempts_b2_strict_fail += 1
        if reason == "anchors_too_few_after_normalization":
            m.attempts_anchor_too_few += 1
        elif reason == "anchors_no_match":
            m.attempts_anchor_no_match += 1
        elif reason == "mechanism_evidence_failed":
            m.attempts_mechanism_evidence_failed += 1


REQUIRED_CORPUS_FIELDS = [
    OUTPUT_PREDICATE_FIELD,
    OUTPUT_ANCHORS_FIELD,
    OUTPUT_COUNTERFACTUAL_FIELD,
    OUTPUT_VERIFIER_REPORT_FIELD,
    OUTPUT_SUPPORT_LEVEL_FIELD,
]


def _process_single_attempt_item(attempt: Dict[str, Any], m: AttemptMetrics) -> None:
    m.attempts_total += 1
    lvl = attempt.get("support_level")
    if lvl == "unsupported":
        m.attempts_unsupported += 1
    elif lvl == "inconclusive":
        m.attempts_inconclusive += 1

    _eval_attempt_soft_checks(attempt, m)
    _eval_attempt_verifier_and_decision(attempt, m)
    _eval_attempt_b2_strict(attempt, m)

    llm_usage = attempt.get("llm_usage") if isinstance(attempt, dict) else None
    if isinstance(llm_usage, dict):
        acc = UsageAccumulator(
            gen_config_values=m.generation_config_values,
            usage_stage_totals=m.usage_stage_totals,
            usage_model_totals=m.usage_model_totals,
            usage_source_totals=m.usage_source_totals,
        )
        c, pt, ct, tt, cost, mc, mgc = _process_attempt_usage(llm_usage, acc)
        m.usage_calls_total += c
        m.usage_prompt_tokens_total += pt
        m.usage_completion_tokens_total += ct
        m.usage_total_tokens_total += tt
        m.usage_cost_usd_total += cost
        m.usage_missing_usage_calls_total += mc
        m.generation_config_missing_attempts += mgc


def _process_input_corpus_verifier_logic_errors(
    input_path: str, m: AttemptMetrics, config: Optional[BGateConfig] = None
) -> None:
    bg_config = config or BGateConfig()
    for _, row in _iter_jsonl(input_path):
        output_obj = _get(row, "output")
        if not isinstance(output_obj, dict):
            continue
        missing_fields = _check_row_missing_fields(row, REQUIRED_CORPUS_FIELDS, bg_config)
        if missing_fields:
            continue
        if output_obj.get("verifier_report") == "not_applicable":
            m.accepted_with_not_applicable += 1
        logic_error = _logic_error_from_row(row)
        if _nonempty_logic_error(logic_error):
            m.accepted_corpus_logic_error_count += 1


def _process_attempts_data(
    attempts_path: str, input_path: str, config: Optional[BGateConfig] = None
) -> AttemptMetrics:
    m = AttemptMetrics()
    for _, attempt in _iter_jsonl(attempts_path):
        if not isinstance(attempt, dict):
            continue
        _process_single_attempt_item(attempt, m)
    _process_input_corpus_verifier_logic_errors(input_path, m, config)
    return m


def _evaluate_threshold_checks(
    metrics: Dict[str, Any], thresholds: BGateThresholds, attempts_path: Optional[str]
) -> Tuple[Dict[str, bool], Dict[str, Any]]:
    unsupported_rate = (
        metrics["b1_unsupported_predicate_rate"] if attempts_path else metrics["b1_unsupported_in_accepted_rate"]
    )
    inconclusive_rate = (
        metrics["b1_inconclusive_predicate_rate"] if attempts_path else metrics["b1_inconclusive_in_accepted_rate"]
    )

    checks = {
        "max_unsupported_in_accepted_rate": unsupported_rate <= thresholds.max_unsupported_in_accepted_rate,
        "max_inconclusive_in_accepted_rate": inconclusive_rate <= thresholds.max_inconclusive_in_accepted_rate,
        "min_anchor_match_rate": (
            (metrics["b2_strict_fail_rate"] <= (1.0 - thresholds.min_anchor_match_rate))
            if attempts_path
            else (metrics["b2_anchor_match_rate"] >= thresholds.min_anchor_match_rate)
        ),
        "min_verifier_pass_rate": (
            True
            if not attempts_path
            else (
                metrics["verifier_pass_rate"] is not None
                and metrics["verifier_pass_rate"] >= thresholds.min_verifier_pass_rate
            )
        ),
        "min_verifier_parse_ok_rate": (
            True
            if not attempts_path
            else (
                metrics["verifier_parse_ok_rate"] is not None
                and metrics["verifier_parse_ok_rate"] >= thresholds.min_verifier_parse_ok_rate
            )
        ),
        "max_accepted_logic_error_rate": (
            True
            if not attempts_path
            else (
                metrics["accepted_attempt_logic_error_rate"] is not None
                and metrics["accepted_attempt_logic_error_rate"] <= thresholds.max_accepted_logic_error_rate
                and metrics["accepted_corpus_logic_error_rate"] is not None
                and metrics["accepted_corpus_logic_error_rate"] <= thresholds.max_accepted_logic_error_rate
            )
        ),
        "max_cost_per_accepted_row": (
            True
            if (not attempts_path or thresholds.max_cost_per_accepted_row is None)
            else (
                metrics["efficiency_cost_per_accepted_row"] is not None
                and metrics["efficiency_cost_per_accepted_row"] <= thresholds.max_cost_per_accepted_row
            )
        ),
        "max_tokens_per_accepted_row": (
            True
            if (not attempts_path or thresholds.max_tokens_per_accepted_row is None)
            else (
                metrics["efficiency_tokens_per_accepted_row"] is not None
                and metrics["efficiency_tokens_per_accepted_row"] <= thresholds.max_tokens_per_accepted_row
            )
        ),
    }

    thresholds_dict = {
        "min_accepted_rows": thresholds.min_accepted_rows,
        "max_unsupported_in_accepted_rate": thresholds.max_unsupported_in_accepted_rate,
        "max_inconclusive_in_accepted_rate": thresholds.max_inconclusive_in_accepted_rate,
        "min_anchor_match_rate": thresholds.min_anchor_match_rate,
        "min_verifier_pass_rate": thresholds.min_verifier_pass_rate,
        "min_verifier_parse_ok_rate": thresholds.min_verifier_parse_ok_rate,
        "max_accepted_logic_error_rate": thresholds.max_accepted_logic_error_rate,
        "max_cost_per_accepted_row": thresholds.max_cost_per_accepted_row,
        "max_tokens_per_accepted_row": thresholds.max_tokens_per_accepted_row,
    }
    return checks, thresholds_dict


def _build_attempts_metrics(m: Optional[AttemptMetrics], accepted: int) -> Dict[str, Any]:
    if m is None:
        return {
            "b1_unsupported_predicate_rate": None,
            "b1_inconclusive_predicate_rate": None,
            "attempts_total": None,
            "b2_predicate_aboutness_fail_rate": None,
            "b2_predicate_aboutness_total": None,
            "predicate_quality_fail_rate": None,
            "predicate_quality_total": None,
            "b2_mechanism_grounding_fail_rate": None,
            "b2_mechanism_grounding_total": None,
            "verifier_called_rate": None,
            "verifier_called_on_prowin_rate": None,
            "prowin_total": None,
            "verifier_parse_ok_rate": None,
            "verifier_pass_rate": None,
            "accepted_with_not_applicable_rate": None,
            "accepted_attempt_logic_error_count": None,
            "accepted_attempt_logic_error_rate": None,
            "accepted_corpus_logic_error_count": None,
            "accepted_corpus_logic_error_rate": None,
            "accepted_logic_error_examples": None,
            "disagreement_judge_accept_but_verifier_missing_or_parse_fail_count": None,
            "disagreement_verifier_pass_but_anchor_strict_fail_count": None,
            "b2_strict_fail_rate": None,
            "b2_strict_total": None,
            "b2_strict_failures": None,
            "usage_calls_total": None,
            "usage_prompt_tokens_total": None,
            "usage_completion_tokens_total": None,
            "usage_total_tokens_total": None,
            "usage_cost_usd_total": None,
            "usage_missing_usage_calls_total": None,
            "usage_by_stage_totals": None,
            "usage_by_model_totals": None,
            "usage_by_source_totals": None,
            "usage_by_source_rates": None,
            "efficiency_tokens_per_accepted_row": None,
            "efficiency_cost_per_accepted_row": None,
            "efficiency_tokens_per_attempt": None,
            "efficiency_cost_per_attempt": None,
            "efficiency_tokens_per_verifier_called_attempt": None,
            "efficiency_cost_per_verifier_called_attempt": None,
            "generation_config_values": None,
            "generation_config_missing_attempts": None,
        }

    attempts_max = max(m.attempts_total, 1)
    verifier_called_max = max(m.verifier_called, 1)
    prowin_max = max(m.prowin_total, 1)
    accepted_max = max(accepted, 1)

    return {
        "b1_unsupported_predicate_rate": m.attempts_unsupported / attempts_max,
        "b1_inconclusive_predicate_rate": m.attempts_inconclusive / attempts_max,
        "attempts_total": m.attempts_total,
        "b2_predicate_aboutness_fail_rate": m.attempts_soft_aboutness_fail / max(m.attempts_soft_aboutness_total, 1),
        "b2_predicate_aboutness_total": m.attempts_soft_aboutness_total,
        "predicate_quality_fail_rate": m.attempts_predicate_quality_fail / max(m.attempts_predicate_quality_total, 1),
        "predicate_quality_total": m.attempts_predicate_quality_total,
        "b2_mechanism_grounding_fail_rate": m.attempts_soft_mech_fail / max(m.attempts_soft_mech_total, 1),
        "b2_mechanism_grounding_total": m.attempts_soft_mech_total,
        "verifier_called_rate": m.verifier_called / attempts_max,
        "verifier_called_on_prowin_rate": m.verifier_called_on_prowin / prowin_max,
        "prowin_total": m.prowin_total,
        "verifier_parse_ok_rate": m.verifier_parse_ok / verifier_called_max,
        "verifier_pass_rate": m.verifier_pass / max(m.verifier_parse_ok, 1),
        "accepted_with_not_applicable_rate": m.accepted_with_not_applicable / accepted_max,
        "accepted_attempt_logic_error_count": m.accepted_attempt_logic_error_count,
        "accepted_attempt_logic_error_rate": m.accepted_attempt_logic_error_count / accepted_max,
        "accepted_corpus_logic_error_count": m.accepted_corpus_logic_error_count,
        "accepted_corpus_logic_error_rate": m.accepted_corpus_logic_error_count / accepted_max,
        "accepted_logic_error_examples": m.accepted_logic_error_examples,
        "disagreement_judge_accept_but_verifier_missing_or_parse_fail_count": m.disagreement_missing_or_parse_fail,
        "disagreement_verifier_pass_but_anchor_strict_fail_count": m.disagreement_verifier_pass_anchor_strict_fail,
        "b2_strict_fail_rate": m.attempts_b2_strict_fail / max(m.attempts_b2_strict_total, 1),
        "b2_strict_total": m.attempts_b2_strict_total,
        "b2_strict_failures": {
            "anchors_too_few_after_normalization": m.attempts_anchor_too_few,
            "anchors_no_match": m.attempts_anchor_no_match,
            "mechanism_evidence_failed": m.attempts_mechanism_evidence_failed,
        },
        "usage_calls_total": m.usage_calls_total,
        "usage_prompt_tokens_total": m.usage_prompt_tokens_total,
        "usage_completion_tokens_total": m.usage_completion_tokens_total,
        "usage_total_tokens_total": m.usage_total_tokens_total,
        "usage_cost_usd_total": m.usage_cost_usd_total,
        "usage_missing_usage_calls_total": m.usage_missing_usage_calls_total,
        "usage_by_stage_totals": m.usage_stage_totals,
        "usage_by_model_totals": m.usage_model_totals,
        "usage_by_source_totals": m.usage_source_totals,
        "usage_by_source_rates": {
            k: (v / max(m.usage_calls_total, 1)) for k, v in m.usage_source_totals.items()
        },
        "efficiency_tokens_per_accepted_row": m.usage_total_tokens_total / accepted_max,
        "efficiency_cost_per_accepted_row": m.usage_cost_usd_total / accepted_max,
        "efficiency_tokens_per_attempt": m.usage_total_tokens_total / attempts_max,
        "efficiency_cost_per_attempt": m.usage_cost_usd_total / attempts_max,
        "efficiency_tokens_per_verifier_called_attempt": m.usage_total_tokens_total / verifier_called_max,
        "efficiency_cost_per_verifier_called_attempt": m.usage_cost_usd_total / verifier_called_max,
        "generation_config_values": m.generation_config_values,
        "generation_config_missing_attempts": m.generation_config_missing_attempts,
    }


def compute_b_metrics(
    *,
    input_path: str,
    attempts_path: Optional[str] = None,
    config: BGateConfig,
) -> Dict[str, Any]:
    (
        total,
        accepted,
        unsupported,
        inconclusive,
        anchors_rows_total,
        anchors_with_match,
        anchors_items_total,
        anchors_generic_total,
        failures,
    ) = _process_input_corpus(input_path, config)

    accepted_samples = max(accepted, 1)
    m = _process_attempts_data(attempts_path, input_path, config) if attempts_path else None

    metrics: Dict[str, Any] = {
        "input_path": input_path,
        "attempts_path": attempts_path,
        "total_rows": total,
        "accepted_rows": accepted,
        "failures": failures,
        "b0_structural_completeness_pass_rate": (accepted / total) if total else 0.0,
        "b1_unsupported_in_accepted_rate": unsupported / accepted_samples,
        "b1_inconclusive_in_accepted_rate": inconclusive / accepted_samples,
        "b2_anchor_match_rate": anchors_with_match / max(anchors_rows_total, 1),
        "b2_generic_anchor_fraction": anchors_generic_total / max(anchors_items_total, 1),
    }

    metrics.update(_build_attempts_metrics(m, accepted))

    if config.thresholds:
        checks, thresholds_dict = _evaluate_threshold_checks(metrics, config.thresholds, attempts_path)
        metrics["thresholds"] = thresholds_dict
        metrics["checks"] = checks

        is_anti_gaming_valid, anti_gaming_violations = check_anti_gaming_invariants(
            metrics,
            min_anchor_match_rate=config.thresholds.min_anchor_match_rate,
            min_verifier_parse_ok_rate=config.thresholds.min_verifier_parse_ok_rate,
            max_accepted_logic_error_rate=config.thresholds.max_accepted_logic_error_rate,
            min_accepted_rows=config.thresholds.min_accepted_rows,
        )
        metrics["anti_gaming_valid"] = is_anti_gaming_valid
        metrics["anti_gaming_violations"] = anti_gaming_violations
        metrics["pass"] = all(checks.values()) and len(failures) == 0 and is_anti_gaming_valid
    else:
        metrics["pass"] = len(failures) == 0

    return metrics


def check_anti_gaming_invariants(
    metrics: Dict[str, Any],
    min_anchor_match_rate: float = 0.80,
    min_verifier_parse_ok_rate: float = 0.95,
    max_accepted_logic_error_rate: float = 0.0,
    min_accepted_rows: int = 1,
) -> Tuple[bool, List[str]]:
    """
    Evaluates strict anti-gaming invariants against a B-gate metrics dictionary.
    Rejects zero-yield collapses (accepted_rows < min_accepted_rows) and rate threshold violations.
    Returns (is_valid, list_of_violation_reasons).
    """
    if min_accepted_rows < 1:
        raise ValueError(f"min_accepted_rows must be >= 1, got {min_accepted_rows}")

    violations = []

    # Check for zero-yield collapse
    accepted_rows = metrics.get("accepted_rows")
    if accepted_rows is None:
        accepted_rows = metrics.get("total_accepted_rows")
    if accepted_rows is not None and accepted_rows < min_accepted_rows:
        violations.append(
            f"Anti-gaming violation: accepted_rows ({accepted_rows}) < min ({min_accepted_rows}) [zero-yield collapse]"
        )

    logic_error_rate = metrics.get("accepted_corpus_logic_error_rate")
    if logic_error_rate is None:
        logic_error_rate = metrics.get("accepted_attempt_logic_error_rate", 0.0)
    if logic_error_rate is not None and logic_error_rate > max_accepted_logic_error_rate:
        violations.append(
            f"Anti-gaming violation: accepted_logic_error_rate ({logic_error_rate:.4f}) > max ({max_accepted_logic_error_rate:.4f})"
        )

    parse_ok_rate = metrics.get("verifier_parse_ok_rate")
    if parse_ok_rate is not None and parse_ok_rate < min_verifier_parse_ok_rate:
        violations.append(
            f"Anti-gaming violation: verifier_parse_ok_rate ({parse_ok_rate:.4f}) < min ({min_verifier_parse_ok_rate:.4f})"
        )

    anchor_match_rate = metrics.get("b2_anchor_match_rate")
    if anchor_match_rate is not None and anchor_match_rate < min_anchor_match_rate:
        violations.append(
            f"Anti-gaming violation: b2_anchor_match_rate ({anchor_match_rate:.4f}) < min ({min_anchor_match_rate:.4f})"
        )

    is_valid = len(violations) == 0
    return is_valid, violations


def main() -> int:
    p = argparse.ArgumentParser(description="Offline B Gate (Grounding) for training_corpus.jsonl")
    p.add_argument("--input", required=True, help="Path to training_corpus.jsonl")
    p.add_argument("--attempts", default=None, help="Optional attempts.jsonl to compute true B1 (unsupported/total_attempts)")
    p.add_argument("--metrics-out", default=None, help="Write metrics JSON to this path")
    p.add_argument("--fail", action="store_true", help="Exit non-zero if gate fails")

    p.add_argument("--case-insensitive-anchor-match", action="store_true", default=True)
    p.add_argument("--case-sensitive-anchor-match", action="store_true", default=False)

    p.add_argument("--min-anchors", type=int, default=2)
    p.add_argument("--require-anchor-match", action="store_true", default=True)
    p.add_argument("--no-require-anchor-match", action="store_true", default=False)

    p.add_argument("--min-accepted-rows", type=int, default=1)
    p.add_argument("--max-unsupported-rate", type=float, default=0.05)
    p.add_argument("--max-inconclusive-rate", type=float, default=0.20)
    p.add_argument("--min-anchor-match-rate", type=float, default=0.80)
    p.add_argument("--min-verifier-pass-rate", type=float, default=0.0)
    p.add_argument("--min-verifier-parse-ok-rate", type=float, default=0.0)
    p.add_argument("--max-accepted-logic-error-rate", type=float, default=0.0)
    p.add_argument("--max-cost-per-accepted-row", type=float, default=-1.0)
    p.add_argument("--max-tokens-per-accepted-row", type=float, default=-1.0)
    args = p.parse_args()

    if args.min_accepted_rows < 1:
        p.error(f"--min-accepted-rows must be >= 1, got {args.min_accepted_rows}")

    case_insensitive = args.case_insensitive_anchor_match and not args.case_sensitive_anchor_match
    require_anchor_match = args.require_anchor_match and not args.no_require_anchor_match

    thresholds = BGateThresholds(
        min_accepted_rows=args.min_accepted_rows,
        max_unsupported_in_accepted_rate=args.max_unsupported_rate,
        max_inconclusive_in_accepted_rate=args.max_inconclusive_rate,
        min_anchor_match_rate=args.min_anchor_match_rate,
        min_verifier_pass_rate=args.min_verifier_pass_rate,
        min_verifier_parse_ok_rate=args.min_verifier_parse_ok_rate,
        max_accepted_logic_error_rate=args.max_accepted_logic_error_rate,
        max_cost_per_accepted_row=(
            args.max_cost_per_accepted_row if args.max_cost_per_accepted_row >= 0.0 else None
        ),
        max_tokens_per_accepted_row=(
            args.max_tokens_per_accepted_row if args.max_tokens_per_accepted_row >= 0.0 else None
        ),
    )
    config = BGateConfig(
        case_insensitive_anchor_match=case_insensitive,
        require_min_anchors=args.min_anchors,
        require_anchor_match=require_anchor_match,
        thresholds=thresholds,
    )

    metrics = compute_b_metrics(input_path=args.input, attempts_path=args.attempts, config=config)

    if args.metrics_out:
        os.makedirs(os.path.dirname(args.metrics_out) or ".", exist_ok=True)
        with open(args.metrics_out, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, sort_keys=True)
    else:
        print(json.dumps(metrics, indent=2, sort_keys=True))

    if args.fail and not metrics.get("pass", False):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
