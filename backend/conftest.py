import os

# auth.py refuses to import without a real JWT secret — set a test one before
# any test module imports it.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-for-production-0123456789abcdef")
