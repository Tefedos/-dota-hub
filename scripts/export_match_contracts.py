"""Export the match routes and their reachable OpenAPI schemas, without environment secrets."""
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from app.core.config import Settings
from app.main import create_app


def contract() -> dict[str, Any]:
    spec = create_app(Settings()).openapi()
    paths = {key: value for key, value in spec['paths'].items() if key.startswith('/api/v1/matches/')}
    schemas: dict[str, Any] = {}
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            ref = value.get('$ref')
            if isinstance(ref, str) and ref.startswith('#/components/schemas/'):
                name = ref.rsplit('/', 1)[1]
                if name not in schemas:
                    schemas[name] = spec['components']['schemas'][name]
                    visit(schemas[name])
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    visit(paths)
    return {'schema_version': 1, 'paths': paths, 'components': {'schemas': schemas}}


if __name__ == '__main__':
    path = ROOT / 'backend/tests/fixtures/group_flow/contracts.json'
    path.write_text(json.dumps(contract(), ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    print(path)
