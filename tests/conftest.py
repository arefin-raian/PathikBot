import os

# Force file-based backend for tests — clear MONGODB_URL BEFORE any test imports
os.environ.pop("MONGODB_URL", None)
