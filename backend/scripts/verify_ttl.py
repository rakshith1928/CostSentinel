"""
TTL Retention Policy Verification Script

This script verifies that the 90-day TTL retention policy is properly configured
and working on the request_history hypertable.

Usage:
    python scripts/verify_ttl.py

Exit codes:
    0 - All checks passed
    1 - One or more checks failed
"""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import init_database, close_database, get_session_no_yield


async def check_retention_policy(session) -> tuple[bool, str]:
    """Check if retention policy is active on request_history."""
    query = text("""
        SELECT
            hypertable_name,
            config_interval::text AS retention_period
        FROM timescaledb_information.retention_policies
        WHERE hypertable_name = 'request_history'
    """)

    result = await session.execute(query)
    row = result.first()

    if not row:
        return False, "No retention policy found for request_history"

    hypertable_name, retention_period = row

    if "90" not in retention_period:
        return False, f"Retention period is {retention_period}, expected 90 days"

    return True, f"Retention policy active: {retention_period}"


async def check_oldest_record(session) -> tuple[bool, str]:
    """Check that oldest record is within 90 days."""
    query = text("""
        SELECT
            MIN(timestamp) AS oldest_record,
            EXTRACT(DAY FROM (NOW() - MIN(timestamp))) AS days_old,
            COUNT(*) AS total_records
        FROM request_history
    """)

    result = await session.execute(query)
    row = result.first()

    if not row or row[2] == 0:
        return True, "No records in table (skip check)"

    oldest_record, days_old, total = row

    if days_old and days_old > 90:
        return False, f"Oldest record is {days_old:.1f} days old (exceeds 90 days)"

    return True, f"Oldest record: {oldest_record} ({days_old:.1f} days old, {total} total)"


async def check_expiring_soon(session) -> tuple[bool, str]:
    """Count records expiring in the next 24 hours."""
    query = text("""
        SELECT COUNT(*) AS expiring_count
        FROM request_history
        WHERE expires_at < NOW() + INTERVAL '1 day'
    """)

    result = await session.execute(query)
    count = result.scalar()

    return True, f"Records expiring in next 24h: {count}"


async def check_expires_at_index(session) -> tuple[bool, str]:
    """Check that expires_at field is indexed."""
    query = text("""
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'request_history'
          AND indexname LIKE '%expires%'
    """)

    result = await session.execute(query)
    indexes = [row[0] for row in result.all()]

    if not indexes:
        return False, "No index found on expires_at field"

    return True, f"Index on expires_at: {', '.join(indexes)}"


async def check_disk_usage(session) -> tuple[bool, str]:
    """Check disk usage of request_history hypertable."""
    query = text("""
        SELECT
            hypertable_name,
            pg_size_pretty(hypertable_size(hypertable_name)) AS size
        FROM timescaledb_information.hypertables
        WHERE hypertable_name = 'request_history'
    """)

    result = await session.execute(query)
    row = result.first()

    if not row:
        return False, "request_history is not a hypertable"

    hypertable_name, size = row
    return True, f"Disk usage: {size}"


async def check_retention_job_status(session) -> tuple[bool, str]:
    """Check last retention job status."""
    query = text("""
        SELECT
            last_run_started_at,
            last_run_finished_at,
            last_run_status
        FROM timescaledb_information.job_stats
        WHERE application_name LIKE '%Retention%'
        ORDER BY last_run_started_at DESC NULLS LAST
        LIMIT 1
    """)

    result = await session.execute(query)
    row = result.first()

    if not row:
        return True, "No retention job has run yet (will run on first schedule)"

    started, finished, status = row

    if status != "Success":
        return False, f"Last retention job status: {status}"

    return True, f"Last retention job: {status} at {finished}"


async def main():
    """Run all TTL verification checks."""
    print("=" * 70)
    print("TTL Retention Policy Verification")
    print("=" * 70)
    print()

    try:
        await init_database()
    except Exception as e:
        print(f"ERROR: Failed to connect to database: {e}")
        return 1

    checks = [
        ("Retention Policy Active", check_retention_policy),
        ("Oldest Record Within 90 Days", check_oldest_record),
        ("Records Expiring Soon", check_expiring_soon),
        ("Expires_at Index", check_expires_at_index),
        ("Disk Usage", check_disk_usage),
        ("Retention Job Status", check_retention_job_status),
    ]

    passed = 0
    failed = 0

    session = await get_session_no_yield()

    try:
        for check_name, check_func in checks:
            try:
                success, message = await check_func(session)
                status = "PASS" if success else "FAIL"
                print(f"[{status}] {check_name}")
                print(f"        {message}")
                print()

                if success:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"[ERROR] {check_name}")
                print(f"        Exception: {e}")
                print()
                failed += 1
    finally:
        await session.close()
        await close_database()

    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
