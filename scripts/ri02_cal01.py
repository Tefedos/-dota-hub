"""RI-02-CAL-01 research only: bounded public fetch and offline ruiner_v1 replay.

Run from the repository root with .venv/bin/python scripts/ri02_cal01.py collect.
Raw snapshots stay in docs/qa/ri02/cal01/raw/, which is gitignored.
"""

import argparse
import asyncio
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from statistics import mean, median
import subprocess
import sys
import time
from collections import Counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import Settings  # noqa: E402
from app.integrations.opendota import parse_match_response  # noqa: E402
from app.services.match_normalization import normalize_match_snapshot  # noqa: E402
from app.services.performance import analyze_performance  # noqa: E402
from app.services.performance_config import PerformanceConfig  # noqa: E402
from app.services.performance import METRICS  # noqa: E402
from app.services.player_catalog import hero_catalog  # noqa: E402

DATA = ROOT / "docs/qa/ri02/cal01"
RAW = DATA / "raw"
PILOTS = (9051271323, 9057722463)
MAX_FULL_REQUESTS = 40


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write_json(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))


def collect() -> None:
    if (DATA / "fetch_journal.json").exists():
        print("Frozen fetch journal exists; use 'analyze' for offline replay")
        return
    discovery = json.loads((DATA / "candidate_discovery.json").read_text())
    queue = [c for c in discovery["candidates"] if c["pre_screen_eligible"]]
    RAW.mkdir(exist_ok=True)
    requests = 0
    included = 0
    journal = []
    for candidate in queue:
        if included >= 10 or requests >= MAX_FULL_REQUESTS:
            break
        mid = candidate["match_id"]
        path = RAW / f"{mid}.json"
        if path.exists():
            snapshot = json.loads(path.read_text())
            journal.append({"match_id": mid, "status": "reused_local_copy"})
        else:
            url = f"https://api.opendota.com/api/matches/{mid}"
            response = None
            for attempt in range(2):
                if requests >= MAX_FULL_REQUESTS:
                    break
                requests += 1
                try:
                    req = Request(url, headers={"Accept": "application/json", "User-Agent": "DotaHub-RI02-CAL01/1.0 research"})
                    with urlopen(req, timeout=20) as result:
                        response = json.load(result)
                    break
                except HTTPError as exc:
                    journal.append({"match_id": mid, "http_status": exc.code, "retry_after": exc.headers.get("Retry-After")})
                    if exc.code == 429:
                        try:
                            wait = int(exc.headers.get("Retry-After", "0"))
                        except ValueError:
                            wait = 0
                        if 0 < wait <= 60 and attempt == 0:
                            time.sleep(wait)
                            continue
                        write_json(DATA / "fetch_journal.json", journal)
                        print("Stopped at rate limit", mid)
                        return
                    break
                except (URLError, TimeoutError, ValueError) as exc:
                    journal.append({"match_id": mid, "error": type(exc).__name__})
                    break
            if response is None:
                time.sleep(1)
                continue
            result = parse_match_response(mid, response, datetime.now(UTC))
            if result.snapshot is None:
                journal.append({"match_id": mid, "status": result.status.value})
                time.sleep(1)
                continue
            snapshot = result.snapshot
            write_json(path, snapshot)
            journal.append({"match_id": mid, "status": result.status.value, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        try:
            normalized = normalize_match_snapshot(snapshot)
            players = normalized.players
            good = (len(players) == 10 and len({p.player_slot for p in players}) == 10
                    and len({p.hero_id for p in players}) == 10
                    and len([p for p in players if p.team.value == "radiant"]) == 5
                    and len([p for p in players if p.team.value == "dire"]) == 5
                    and normalized.summary.winner is not None
                    and normalized.summary.duration is not None and normalized.summary.duration >= 900
                    and normalized.summary.game_mode in (1, 2, 22))
            journal[-1]["included"] = good
            if good:
                included += 1
            else:
                journal[-1]["exclusion"] = "failed_full_snapshot_roster_duration_mode_or_winner"
        except Exception as exc:
            journal[-1]["included"] = False
            journal[-1]["exclusion"] = type(exc).__name__
        write_json(DATA / "fetch_journal.json", journal)
        time.sleep(1)
    print(f"Full requests={requests}; included={included}; checked={len(journal)}")


async def pilots() -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    secret = Settings().database_url
    if secret is None:
        print("No local database configured")
        return
    engine = create_async_engine(secret.get_secret_value(), hide_parameters=True)
    RAW.mkdir(exist_ok=True)
    metadata = []
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            for mid in PILOTS:
                result = await connection.execute(text("SELECT m.raw_payload, m.fetched_at, a.report_payload, a.computed_at FROM matches m LEFT JOIN match_analyses a ON a.match_id=m.match_id AND a.algorithm_version='group_flow_v1:ruiner' WHERE m.match_id=:mid"), {"mid": mid})
                row = result.first()
                if row is None or row[0] is None:
                    metadata.append({"match_id": mid, "available": False})
                    continue
                snapshot = row[0]
                if not (RAW / f"{mid}.json").exists():
                    write_json(RAW / f"{mid}.json", snapshot)
                report = row[2]
                stored_data = report.get("data", {}) if isinstance(report, dict) else {}
                metadata.append({"match_id": mid, "available": True, "raw_sha256": hashlib.sha256((RAW / f"{mid}.json").read_bytes()).hexdigest(), "fetched_at": row[1].isoformat() if row[1] else None, "stored_model_version": report.get("model_version") if isinstance(report, dict) else None, "stored_config_digest": stored_data.get("config_digest"), "stored_computed_at": row[3].isoformat() if row[3] else None,
                                 "stored_player_indices": [p.get("error_index") for p in stored_data.get("players", [])]})
    finally:
        await engine.dispose()
    write_json(DATA / "pilot_sources.json", metadata)
    print("Pilot snapshots available:", [m["match_id"] for m in metadata if m["available"]])


def comparison_details(player: object, report: object, duration: int, team_score: int | None) -> dict[str, object]:
    """Reconstruct evaluator peer arithmetic, including deviations below signal threshold."""
    p = player
    peers = [other for other in report.players if other.team == p.team and other.player_slot != p.player_slot
             and (p.role_group == "unknown" or other.role_group == p.role_group)]
    out = {}
    for metric in METRICS:
        value = p.observed_metrics.get(metric)
        usable = [(other.player_slot, other.observed_metrics.get(metric)) for other in peers
                  if other.observed_metrics.get(metric) is not None]
        reference = median(v for _, v in usable) if usable else None
        higher_is_bad = metric == "deaths_per_min"
        floor = 1 / team_score if metric == "kill_participation" and team_score else (60 / duration if metric.endswith("_per_min") and duration else 1)
        comparable = value is not None and bool(usable) and not (reference == 0 and not higher_is_bad)
        denom = max(reference, floor) if comparable else None
        bad = min(1, max(0, (value - reference if higher_is_bad else reference - value) / denom)) if comparable else None
        good = min(1, max(0, (reference - value if higher_is_bad else value - reference) / denom)) if comparable else None
        out[metric] = {"value": value, "peer_slots": [slot for slot, _ in usable], "peer_values": [v for _, v in usable],
                       "reference_median": reference, "denominator_floor": floor, "comparison_denominator": denom,
                       "bad_deviation": bad, "good_deviation": good,
                       "comparison_status": "available" if comparable else "missing_value_or_peer_or_zero_reference"}
    return out


def analyze() -> None:
    discovery = json.loads((DATA / "candidate_discovery.json").read_text())
    journal = {entry["match_id"]: entry for entry in json.loads((DATA / "fetch_journal.json").read_text())}
    pilot_sources = {entry["match_id"]: entry for entry in json.loads((DATA / "pilot_sources.json").read_text())}
    config = PerformanceConfig()
    hero_revision, heroes = hero_catalog()
    registry = []
    players = []
    breakdown = []
    cards = []
    reports = {}
    selected = set(PILOTS) | {discovery["initial_full_match_queue"][0]}
    candidate_by_id = {c["match_id"]: c for c in discovery["candidates"]}
    for candidate in discovery["candidates"]:
        mid = candidate["match_id"]
        path = RAW / f"{mid}.json"
        registry.append({"match_id": mid, "source": "OpenDota GET /publicMatches", "discovery_order": candidate["discovery_order"],
                         "pre_screen_eligible": candidate["pre_screen_eligible"],
                         "included": bool(journal.get(mid, {}).get("included")),
                         "status": "included" if journal.get(mid, {}).get("included") else "excluded_pre_screen" if not candidate["pre_screen_eligible"] else "excluded_full_check_or_not_fetched",
                         "reason": candidate["pre_screen_reason"] if not candidate["pre_screen_eligible"] else journal.get(mid, {}).get("exclusion"),
                         "fetch_status": journal.get(mid, {}).get("status"),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None,
                         "avg_rank_tier_discovery": candidate["avg_rank_tier"], "model_version": config.model_version if path.exists() else None})
    for mid in (*PILOTS, *(c["match_id"] for c in discovery["candidates"] if journal.get(c["match_id"], {}).get("included"))):
        path = RAW / f"{mid}.json"
        if not path.exists():
            continue
        snapshot = json.loads(path.read_text())
        normalized = normalize_match_snapshot(snapshot)
        report = analyze_performance(normalized, config=config)
        assert report == analyze_performance(normalized, config=config)
        reports[str(mid)] = report.model_dump(mode="json")
        raw = snapshot["match"]
        if mid in PILOTS:
            registry.append({"match_id": mid, "source": "local PostgreSQL matches.raw_payload (read-only copy)",
                             "included": True, "status": "included_pilot", "reason": "pre_registered_pilot",
                             "fetch_status": snapshot.get("status"), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                             "stored_model_version": pilot_sources.get(mid, {}).get("stored_model_version"),
                             "stored_config_digest": pilot_sources.get(mid, {}).get("stored_config_digest")})
        entry = next(e for e in registry if e["match_id"] == mid and e["included"])
        entry.update({"raw_path": str(path.relative_to(ROOT)), "fetched_at": snapshot.get("source_fetched_at"),
                      "match_date_utc": datetime.fromtimestamp(raw["start_time"], UTC).date().isoformat() if isinstance(raw.get("start_time"), int) else None,
                      "game_mode": normalized.summary.game_mode, "duration_seconds": normalized.summary.duration,
                      "radiant_score": normalized.summary.radiant.score, "dire_score": normalized.summary.dire.score,
                      "winner": normalized.summary.winner.value if normalized.summary.winner else None,
                      "patch_source_id": normalized.summary.patch,
                      "parsed_events_available": bool(raw.get("objectives") or raw.get("teamfights")),
                      "scored_players": sum(p.error_index is not None for p in report.players),
                      "scored_radiant": sum(p.error_index is not None and p.team.value == "radiant" for p in report.players),
                      "scored_dire": sum(p.error_index is not None and p.team.value == "dire" for p in report.players),
                      "null_players": sum(p.error_index is None for p in report.players),
                      "model_version": report.model_version, "config_digest": report.config_digest,
                      "report_quality": report.quality})
        entry["team_selection"] = {team.value: {"strict": value.selection.selection_status,
                                                   "preliminary": value.preliminary_selection.status if value.preliminary_selection else None}
                                   for team, value in report.teams.items()}
        if mid in PILOTS:
            entry["stored_indices_equal_replay"] = (pilot_sources[mid].get("stored_player_indices") == [p.error_index for p in report.players])
        raw_players = {p.get("player_slot"): p for p in raw.get("players", [])}
        for p in report.players:
            stat = next(s for s in normalized.players if s.player_slot == p.player_slot)
            rp = raw_players.get(p.player_slot, {})
            team_score = normalized.summary.radiant.score if p.team.value == "radiant" else normalized.summary.dire.score
            comparisons = comparison_details(p, report, normalized.summary.duration or 0, team_score)
            peers = [other.player_slot for other in report.players if other.team == p.team and other.player_slot != p.player_slot
                     and (p.role_group == "unknown" or other.role_group == p.role_group)]
            row = {"match_id": mid, "player_slot": p.player_slot, "team": p.team.value, "team_won": p.team == normalized.summary.winner,
                   "hero_id": p.hero_id, "hero_name": heroes.get(p.hero_id, {}).get("name") if p.hero_id else None,
                   "position": p.position.position, "position_evidence": p.position.evidence.value,
                   "role_group": p.role_group, "peer_slots": peers, "peer_count": len(peers),
                   "error_index": p.error_index, "confidence": p.confidence, "evidence_coverage": p.evidence_coverage,
                   "axes": p.axes, "positive_credit": p.positive_credit,
                   "positive_signals": [s.model_dump(mode="json") for s in p.positive_signals],
                   "negative_signals": [s.model_dump(mode="json") for s in p.negative_signals],
                   "missing_metrics": list(p.missing_metrics), "reason_codes": list(p.reason_codes),
                   "observed_metrics": p.observed_metrics,
                   "comparison_slots": {metric: detail["peer_slots"] for metric, detail in comparisons.items()},
                   "input_stats": {k: getattr(stat, k) for k in ("kills", "deaths", "assists", "gpm", "xpm", "hero_damage", "tower_damage", "hero_healing", "obs_placed", "sen_placed", "observer_kills", "sentry_kills")},
                   "raw_leaver_status": rp.get("leaver_status"), "raw_lane_role": rp.get("lane_role"),
                   "source_sha256": entry["sha256"]}
            players.append(row)
            weights_all = config.core_weights if p.role_group == "core" else config.fallback_weights
            available_all = {axis: value for axis, value in p.axes.items() if value is not None}
            coverage_all = sum(weights_all[axis] for axis in available_all)
            independent_index = (int(max(0, 100 * sum(weights_all[axis] * value for axis, value in available_all.items()) / coverage_all - p.positive_credit) + .5)
                                 if len(available_all) >= config.minimum_axes and coverage_all + 1e-9 >= config.minimum_coverage else None)
            assert independent_index == p.error_index, (mid, p.player_slot)
            if mid in selected and (mid == 9051271323 or p.player_slot < 5):
                weights = config.core_weights if p.role_group == "core" else config.fallback_weights
                available = {axis: value for axis, value in p.axes.items() if value is not None}
                coverage = sum(weights[axis] for axis in available)
                weighted = sum(weights[axis] * value for axis, value in available.items())
                uncredited = 100 * weighted / coverage if coverage else None
                expected = int(max(0, uncredited - p.positive_credit) + .5) if uncredited is not None and len(available) >= config.minimum_axes and coverage + 1e-9 >= config.minimum_coverage else None
                credit_metric_names = ("tower_damage_per_min", "healing_per_min", "obs_placed", "sen_placed", "observer_kills", "sentry_kills")
                if p.role_group != "core":
                    credit_metric_names = ("hero_damage_per_min", *credit_metric_names)
                credit_components = {name: comparisons[name]["good_deviation"] for name in credit_metric_names}
                details = {name: comparisons[name] for name in ("deaths_per_min", "kill_participation", "gpm", "xpm", "hero_damage_per_min", *credit_metric_names)}
                breakdown.append({"match_id": mid, "player_slot": p.player_slot, "team_won": row["team_won"],
                                  "hero_id": p.hero_id, "hero_name": row["hero_name"], "role_group": p.role_group, "peer_slots": peers,
                                  "raw_input": row["input_stats"], "observed_metrics": p.observed_metrics,
                                  "comparisons": details, "axes": p.axes, "weights": weights,
                                  "weighted_sum": weighted, "coverage_weight": coverage,
                                  "base_before_credit": uncredited, "positive_credit": p.positive_credit,
                                  "positive_credit_components": credit_components,
                                  "recomputed_index": expected, "actual_index": p.error_index,
                                  "negative_signals": row["negative_signals"], "positive_signals": row["positive_signals"],
                                  "reason_codes": row["reason_codes"]})
                first_signal = p.negative_signals[0] if p.negative_signals else None
                cards.append({"match_id": mid, "player_slot": p.player_slot, "hero_id": p.hero_id, "hero_name": row["hero_name"],
                              "role_group": p.role_group, "position_evidence": p.position.evidence.value,
                              "signal": first_signal.code if first_signal else None,
                              "metric": first_signal.metric if first_signal else None,
                              "value": first_signal.value if first_signal else None,
                              "peer_reference": first_signal.reference if first_signal else None,
                              "peer_slots": list(first_signal.comparison_slots) if first_signal else peers,
                              "evidence": "OpenDota counters in local snapshot; no event-level action validation",
                              "assessment": "confirmed_statistical_deviation" if first_signal else "insufficient_evidence",
                              "gameplay_error_confirmed": False})
    numeric = [p["error_index"] for p in players if p["error_index"] is not None]
    groups = {}
    for name, subset in (("core", [p for p in players if p["role_group"] == "core"]),
                         ("support", [p for p in players if p["role_group"] == "support"]),
                         ("unknown", [p for p in players if p["role_group"] == "unknown"]),
                         ("winning", [p for p in players if p["team_won"]]),
                         ("losing", [p for p in players if not p["team_won"]])):
        vals = [p["error_index"] for p in subset if p["error_index"] is not None]
        groups[name] = {"players": len(subset), "scored": len(vals), "null": len(subset)-len(vals),
                        "mean": mean(vals) if vals else None, "median": median(vals) if vals else None}
    coverage = {"matches": sum(e["included"] for e in registry), "players": len(players), "scored": len(numeric),
                "null": len(players)-len(numeric), "min": min(numeric) if numeric else None,
                "max": max(numeric) if numeric else None, "mean": mean(numeric) if numeric else None,
                "median": median(numeric) if numeric else None,
                "histogram": {label: sum(lo <= x <= hi for x in numeric) for label, lo, hi in (("0",0,0),("1-19",1,19),("20-39",20,39),("40-59",40,59),("60-79",60,79),("80-100",80,100))},
                "confidence": dict(Counter(p["confidence"] for p in players)),
                "position_evidence": dict(Counter(p["position_evidence"] for p in players)),
                "role_groups": groups, "peer_counts": dict(Counter(str(p["peer_count"]) for p in players)),
                "by_snapshot_status": {status: {"players": len(subset), "scored": sum(p["error_index"] is not None for p in subset)}
                                       for status in ("FOUND_FULL", "FOUND_PARTIAL")
                                       if (subset := [p for p in players if next(e for e in registry if e["match_id"] == p["match_id"] and e["included"])["fetch_status"] == status])},
                "reason_codes_among_null_players": dict(Counter(reason for p in players if p["error_index"] is None for reason in p["reason_codes"])),
                "by_match": [{"match_id": e["match_id"], "winner": e["winner"], "scored": e["scored_players"], "scored_radiant": e["scored_radiant"], "scored_dire": e["scored_dire"], "null": e["null_players"]} for e in registry if e["included"]]}
    assert len(players) == 10 * coverage["matches"]
    assert len({e["match_id"] for e in registry}) == len(registry)
    assert all(b["recomputed_index"] == b["actual_index"] for b in breakdown)
    assert all(e.get("stored_indices_equal_replay", True) for e in registry if e["included"])
    write_json(DATA / "match_registry.json", registry)
    write_json(DATA / "player_dataset.json", players)
    write_json(DATA / "ruiner_reports.json", reports)
    write_json(DATA / "coverage.json", coverage)
    write_json(DATA / "score_breakdown.json", breakdown)
    write_json(DATA / "blind_review_cards.json", cards)
    code_paths = ("backend/app/services/performance.py", "backend/app/services/performance_config.py",
                  "backend/app/services/performance_preliminary.py", "backend/app/services/match_normalization.py",
                  "backend/app/models/performance.py", "backend/app/models/matches.py",
                  "backend/app/data/hero_catalog.json")
    write_json(DATA / "model_freeze.json", {"git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                                           "model_version": config.model_version, "config": config.model_dump(mode="json"),
                                           "config_digest": next(e["config_digest"] for e in registry if e["included"]),
                                           "hero_catalog_revision": hero_revision,
                                           "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in code_paths},
                                           "normalization_source": "backend/app/services/match_normalization.py at working tree; RI-02-FIX-01 uncommitted safe contract only"})
    print("Analyzed", coverage["matches"], "matches;", coverage["scored"], "/", coverage["players"], "scored;", len(breakdown), "breakdowns")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("collect", "pilots", "analyze"))
    args = parser.parse_args()
    if args.action == "collect":
        collect()
    elif args.action == "pilots":
        asyncio.run(pilots())
    else:
        analyze()


if __name__ == "__main__":
    main()
