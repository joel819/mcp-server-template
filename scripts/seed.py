"""Load the recorded fixtures (fixtures/github/*.json) into the SQLite response cache.
Runs automatically on server start when SEED_ON_STARTUP=true.

Usage: python -m scripts.seed
"""
from app.github.fixtures import FIXTURE_DIR
from app.server import seed_cache

if __name__ == "__main__":
    n = seed_cache()
    total = len(list(FIXTURE_DIR.glob("*.json")))
    if total == 0:
        print("No fixtures found. Record some with: python -m scripts.record_fixtures")
    else:
        print(f"Loaded {n} new/updated fixture(s) of {total} into the cache.")
