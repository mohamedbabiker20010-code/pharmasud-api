import os

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@test.neon.tech/pharmasud_test?sslmode=require")
os.environ.setdefault("SECRET_KEY", "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef")
os.environ.setdefault("ENVIRONMENT", "test")
