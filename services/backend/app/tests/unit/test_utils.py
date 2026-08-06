"""Unit tests for utility functions."""

from packages.db import fix_database_url_for_asyncpg


class TestDatabaseUtils:
    """Test database utility functions."""

    def test_fix_database_url_for_asyncpg_with_sslmode(self):
        """Test that sslmode=require is converted to ssl=require."""
        url = "postgresql://user:pass@host/db?sslmode=require"
        fixed = fix_database_url_for_asyncpg(url)
        assert fixed == "postgresql+asyncpg://user:pass@host/db?ssl=require"
        assert "sslmode" not in fixed

    def test_fix_database_url_for_asyncpg_without_sslmode(self):
        """Test that standard PostgreSQL URLs are converted to asyncpg."""
        url = "postgresql://user:pass@host/db"
        fixed = fix_database_url_for_asyncpg(url)
        assert fixed == "postgresql+asyncpg://user:pass@host/db"

    def test_fix_database_url_for_asyncpg_with_async_driver(self):
        """Test that asyncpg URLs are unchanged."""
        url = "postgresql+asyncpg://user:pass@host/db"
        fixed = fix_database_url_for_asyncpg(url)
        assert fixed == url

    def test_fix_database_url_for_asyncpg_with_postgres_scheme(self):
        """Test Heroku-style postgres URLs are converted to asyncpg."""
        url = "postgres://user:pass@host/db"
        fixed = fix_database_url_for_asyncpg(url)
        assert fixed == "postgresql+asyncpg://user:pass@host/db"

    def test_fix_database_url_for_asyncpg_empty(self):
        """Test handling of empty URL."""
        assert fix_database_url_for_asyncpg("") == ""
        assert fix_database_url_for_asyncpg(None) is None

    def test_fix_database_url_for_asyncpg_other_params(self):
        """Test that other parameters are preserved."""
        url = "postgresql://user:pass@host/db?sslmode=require&pool_size=10"
        fixed = fix_database_url_for_asyncpg(url)
        assert fixed.startswith("postgresql+asyncpg://")
        assert "ssl=require" in fixed
        assert "pool_size=10" in fixed
        assert "sslmode" not in fixed
