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
    def __init__(self, file: Union[str, Path]) -> None:
        self._lockfile = Path(file).absolute()

    def __enter__(self) -> None:
        while self._lockfile.exists():
            time.sleep(0.1)
        self._lockfile.touch()

    def __exit__(self, exc_type, exc_value, traceback):
        self._lockfile.unlink()


class DB:
    def __init__(self, sqlite_file: str) -> None:
        self._sqlite_file = sqlite_file
        self._lockfile = Lockfile(Path(sqlite_file).parent / "db.lock")

    def _fk_constraints(self, conn: sqlite3.Connection):
        conn.execute("PRAGMA foreign_keys = ON")

    def get_everything(self) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
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

    def update_test_status(
        self,
        run_id: int,
        env: str,
        test_id: str,
        status: str,
        run_result: Optional[str] = None,
        compare_result: Optional[str] = None,
    ) -> None:
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
        self, test_ids: Iterable[str], fails: bool = False, start_local: Optional[dt] = None
    ) -> tuple[int, list[str]]:
        # query_next_runid = "SELECT ifnull(max(run_id)+1, 0) FROM test_instances"
        insert_run = "INSERT INTO runs (start) VALUES (?)"
        query_failures = (
            "SELECT id FROM test_instances "
            "WHERE run_result='FAIL' "
            "AND run_id=(SELECT max(run_id) FROM test_instances WHERE id=id) "
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
            next_runid = conn.execute(insert_run, (start,)).lastrowid
            if fails:
                failures = set(id for (id,) in conn.execute(query_failures).fetchall())
                test_ids = set(test_ids) & failures
            if not test_ids:
                # cancel add_run if no tests to add
                conn.rollback()
                return (-1, [])
            baseline = [(next_runid, "baseline", id) for id in test_ids]
            # target = [(next_runid, "target", id) for id in test_ids]
            target = []  # TODO DEBUG PURPOSES
            conn.executemany(insert_instance, baseline + target)
            return (next_runid, sorted(test_ids))

    def dequeue_tests(self, env: str) -> tuple[int, set[str]]:
        query_queued = (
            "SELECT run_id, id FROM test_instances WHERE env=? AND status='queued' "
            "AND run_id=(SELECT max(id) FROM runs WHERE start<=datetime('now')"
        )
        update_status = "UPDATE test_instances SET status='waiting' WHERE run_id=? AND env=?"

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
        update_end = "UPDATE runs WHERE id=? SET end=?"

        with (
            self._lockfile,
            closing(sqlite3.connect(self._sqlite_file)) as conn,
            conn,
        ):
            now = dt.now().astimezone(timezone.utc)
            conn.execute(update_end, (run_id, now))
