"""
Code involving accessing an sqlite database to maintain run and individual
test status.
"""

from itertools import product
import sqlite3
from contextlib import closing
from datetime import datetime as dt  # broken for no reason
from datetime import timezone
from pathlib import Path
import time
from typing import Any, Generator, Iterable, Literal, Optional, Union


# keep multiple computers from writing to the sqlite db simultaneously
# using super janky and probably-wont-work "lock file" to attempt to
class Lockfile:
    """A context manager that attempts to use the existence of a file
    as a means of synchronization across multiple PCs."""

    def __init__(self, file: Union[str, Path]) -> None:
        self._lockfile = Path(file).absolute()

    def __enter__(self) -> None:
        while self._lockfile.exists():
            time.sleep(0.1)
        self._lockfile.touch()

    def __exit__(self, exc_type, exc_value, traceback):
        self._lockfile.unlink()


class DB:
    """Access methods for the test run data."""

    def __init__(self, sqlite_file: str) -> None:
        """Set up the DB.

        Args:
            sqlite_file (str): Path to the sqlite database.
        """
        self._sqlite_file = sqlite_file
        self._lockfile = Lockfile(Path(sqlite_file).parent / "db.lock")

    def _fk_constraints(self, conn: sqlite3.Connection):
        """Enables foreign key constraints on `conn`"""
        conn.execute("PRAGMA foreign_keys = ON")

    def get_raw_tables(self) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
        """Gets all rows and fields from both tables.

        Returns:
            tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]: The table data.
                `runs` and `test_instances`.
        """
        query_runs = "SELECT * FROM runs"
        query_tests = "SELECT * FROM test_instances"

        with (
            self._lockfile,
            closing(sqlite3.connect(self._sqlite_file)) as conn,
            conn,
        ):
            runs = conn.execute(query_runs).fetchall()
            test_instances = conn.execute(query_tests).fetchall()
            return (runs, test_instances)

    def get_passing_views(self) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
        """Get the rows from views summarizing what runs and tests have
        completed and their pass/fail status.

        Returns:
            tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]: The view data:
                `complete_runs_passing` and `complete_tests_passing`.
        """
        query_runs_passing = "SELECT * FROM complete_runs_passing ORDER BY id DESC"
        query_tests_passing = "SELECT * FROM complete_tests_passing ORDER BY run_id DESC"

        with (
            self._lockfile,
            closing(sqlite3.connect(self._sqlite_file)) as conn,
            conn,
        ):
            runs_passing = conn.execute(query_runs_passing).fetchall()
            tests_passing = conn.execute(query_tests_passing).fetchall()
            return (runs_passing, tests_passing)

    def update_test_status(
        self,
        run_id: int,
        env: str,
        test_id: str,
        status: str,
        run_result: Optional[str] = None,
        compare_result: Optional[str] = None,
    ) -> None:
        """Upserts an individual test instance.

        Args:
            run_id (int): the id of the run in question.
            env (str): test environment name (eg baseline or target)
            test_id (str): the test identifier (toolbox.alias.variant.subtest)
            status (str): status string
            run_result (Optional[str], optional): PASS/FAIL. Defaults to None.
            compare_result (Optional[str], optional): PASS/FAIL. Defaults to None.
        """
        upsert_status = (
            "INSERT INTO test_instances (run_id, env, id, status, run_result, compare_result) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT DO UPDATE SET "
            "status=excluded.status, "
            "run_result=excluded.run_result, "
            "compare_result=excluded.compare_result"
        )
        with (
            self._lockfile,
            closing(sqlite3.connect(self._sqlite_file)) as conn,
            conn,
        ):
            row_data = (run_id, env, test_id, status, run_result, compare_result)
            conn.execute(upsert_status, row_data)
            conn.commit()

    def add_run_enqueue_tests(
        self,
        test_ids: Iterable[str],
        envs: list[str],
        include_passes: bool = False,
        start_local: Optional[dt] = None,
    ) -> tuple[int, list[str]]:
        """Creates a new run and test instances for it.

        Args:
            test_ids (Iterable[str]): the new tests to perform during this run.
            envs (list[str]): which test environments to add tests for (eg baseline).
            include_passes (bool, optional): enqueue all tests in `test_ids` even
                if they previously passed. Defaults to False.
            start_local (Optional[datetime], optional): The date and time after
                which the test can begin, in the operator's local time zone.
                Defaults to None, which means 'now'.

        Returns:
            tuple[int, list[str]]: the newly added run ID and the test IDs enqueued.
        """
        # query_next_runid = "SELECT ifnull(max(run_id)+1, 0) FROM test_instances"
        insert_run = "INSERT INTO runs (start) VALUES (?)"
        query_failures = (
            "SELECT DISTINCT id FROM test_instances "  # DISTINCT not strictly required in sqlite
            "WHERE run_result='FAIL' "
            "AND run_id=(SELECT max(id) FROM runs) "
            "GROUP BY id"
        )
        insert_instance = (
            "INSERT INTO test_instances (run_id, env, id, status) VALUES (?, ?, ?, 'queued')"
        )

        start = dt.now().astimezone(timezone.utc)
        if start_local:
            start = start_local.astimezone(timezone.utc)

        with (
            self._lockfile,
            closing(sqlite3.connect(self._sqlite_file)) as conn,
            conn,
        ):
            if not include_passes:
                failures = set(id for (id,) in conn.execute(query_failures).fetchall())
                test_ids = set(test_ids) & failures
            if not test_ids:
                # cancel add_run if no tests to add
                conn.rollback()
                return (-1, [])

            next_runid = conn.execute(insert_run, (start,)).lastrowid
            instance_keys = [(next_runid, env, id) for env, id in product(envs, test_ids)]
            conn.executemany(insert_instance, instance_keys)
            return (next_runid, sorted(test_ids))

    def dequeue_tests(self, env: str) -> tuple[int, set[str]]:
        """Fetch 'queued' tests and change their status to 'waiting'.

        Args:
            env (str): the test environment to get tests for (eg baseline).

        Returns:
            tuple[int, set[str]]: the run ID of the tests and the test IDs.
        """
        query_queued = (
            "SELECT run_id, id FROM test_instances WHERE env=? AND status='queued' "
            "AND run_id=(SELECT max(id) FROM runs WHERE start<=datetime('now'))"
        )
        update_status = (
            "UPDATE test_instances SET status='waiting' "
            "WHERE run_id=? AND env=? AND status='queued'"
        )

        with (
            self._lockfile,
            closing(sqlite3.connect(self._sqlite_file)) as conn,
            conn,
        ):
            enqueued = conn.execute(query_queued, (env,)).fetchall()
            if not enqueued:
                return (-1, set())
            test_ids: set[str] = set(id for _, id in enqueued)
            run_ids: set[int] = set(run_id for run_id, _ in enqueued)
            assert len(run_ids) == 1
            run_id = run_ids.pop()  # get any since should be only 1
            conn.execute(update_status, (run_id, env))
            return run_id, test_ids

    def set_run_endtime(self, run_id: int):
        """Update a run's end time.

        Args:
            run_id (int): the ID for the run.
        """
        update_end = "UPDATE runs SET end=? WHERE id=?"

        with (
            self._lockfile,
            closing(sqlite3.connect(self._sqlite_file)) as conn,
            conn,
        ):
            now = dt.now().astimezone(timezone.utc)
            conn.execute(update_end, (now, run_id))
