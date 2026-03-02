import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

with patch("app.database.engine", MagicMock()):
    from app.main import app

spec = app.openapi()
output_path = backend_dir / "openapi.json"
output_path.write_text(json.dumps(spec, indent=2))
print(f"Wrote OpenAPI spec to {output_path}")
