-- Initialize TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Note: The request_history table will be created by the application
-- using SQLAlchemy migrations or alembic.
-- This script ensures TimescaleDB extension is enabled on startup.
