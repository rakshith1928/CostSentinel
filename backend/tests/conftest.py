"""Pytest configuration for backend tests.

Adds backend dir to sys.path so `app.*` imports resolve.
Tests use @pytest.mark.asyncio decorators explicitly.
"""

import sys
from pathlib import Path

# Add backend directory to Python path so `app.*` imports work
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
