"""Offline evaluation of an ingestion snapshot or audit evidence.json; no external effects."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.services.match_normalization import normalize_match_snapshot  # noqa: E402
from app.services.performance import analyze_performance  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.snapshot.read_text())
    report = analyze_performance(normalize_match_snapshot(data.get('snapshot', data)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report.model_dump_json(indent=2) + '\n')
    print(json.dumps({'match_id': report.match_id, 'quality': report.quality,
                      'scored_players': {k.value: v.scored_players for k, v in report.teams.items()},
                      'selection_status': report.summary.selection_status}, ensure_ascii=False))


if __name__ == '__main__':
    main()
