import sqlite3
from contextlib import closing
from datetime import datetime as dt  # broken for no reason
from pathlib import Path
import time
from typing import Any, Generator, Literal, Optional, Union


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

    def post_results(
        self,
        run_id: int,
        env: str,
        test_id: str,
        status: str,
        run_result: Optional[str] = None,
        compare_result: Optional[str] = None,
    ) -> None:
        statement = (
            "INSERT INTO test_instances (run_id, env, id, status, run_result, compare_result) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT DO UPDATE SET "
            "status=excluded.status, "
            "run_result=excluded.run_result, "
            "compare_result=excluded.compare_result"
        )
        with self._lockfile:
            with closing(sqlite3.connect(self._sqlite_file)) as conn:
                with conn:
                    row_data = (run_id, env, test_id, status, run_result, compare_result)
                    conn.execute(statement, row_data)
                    conn.commit()
