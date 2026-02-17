import argparse
import math
from pprint import pprint
import random
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, replace
from datetime import datetime as dt  # broken for no reason
from datetime import timedelta
from itertools import chain
from pathlib import Path
from tempfile import gettempdir
from typing import Any, Generator, Literal, Optional, Union

import arcpy
from db import DB
from test import Parameter, Test, make_tests, parameter_dict, parse_test_ini
from test_logging import OutputCapture, setup_logger


def find_tests(root: Union[str, Path]) -> list[tuple[Path, str, Test]]:
    root = Path(root)
    test_configs = root.glob("*/*.ini")
    tests = [(c.absolute(), c.stem, parse_test_ini(c.read_text())) for c in test_configs]
    return tests


def find_toolboxes(root: Union[str, Path]) -> list[Test]:
    root = Path(root)
    toolboxes = chain(root.glob("*/*.atbx"), root.glob("*/*.tbx"))
    tests: list[Test] = []
    for toolbox in toolboxes:
        tests.extend(make_tests(toolbox))
    return tests


def run(toolbox_path: str, tool_alias: str, params: dict[str, Any]):
    toolbox = arcpy.ImportToolbox(toolbox_path)
    tool = getattr(toolbox, tool_alias)
    tool(**params)


class TestFailException(Exception):
    """when a toolbox test fails"""


def run_single_test(test_path: Path, run_id: int, env: Literal["baseline", "target"]):
    try:
        results = DB(r"I:\test\ArcGISPro_VersionTesting\results.sqlite")
        test_id = test_path.stem
        results.post_results(run_id, env, test_id, status="running")

        # need run id, env
        test = parse_test_ini(test_path.read_text())
        # print("PARSED TEST")
        test_logfile = test_path.parent / "logs" / f"{run_id:03d}_{env}_{test_id}.log"
        logger = setup_logger(test_id, test_logfile)

        temp_inputs_parent = Path(gettempdir()) if test.run_local else test_path.parent

        inputs = test_path.parent / "inputs"
        temp_inputs = temp_inputs_parent / f"inputs_{env}_{test_id}"
        outputs = test_path.parent / f"outputs_{env}_{test_id}"  # TODO: not sure about this

        logger.debug(f"{run_id=}")
        logger.debug(f"{env=}")
        logger.info(f"Test:        {test_id}")
        logger.info(f"Toolbox:     {test.toolbox}")
        logger.info(f"Alias:       {test.alias}")
        logger.info(f"Description: {test.description}")
        logger.info(f"Run Local:   {test.run_local}")
        logger.debug(f"{inputs=!s}")
        logger.debug(f"{temp_inputs=!s}")
        logger.debug(f"{outputs=!s}")

        if len(list(inputs.glob("*"))) == 0:
            raise TestFailException("No inputs.")

        # copy inputs to temp
        logger.info("copying inputs to temp directory")
        temp_inputs.mkdir(exist_ok=True)
        shutil.copytree(str(inputs), str(temp_inputs), dirs_exist_ok=True)

        # run on temp inputs
        try:
            final_params = test.resolve_inputs(temp_inputs)  # inputs_dirname=inputs.stem
            logger.debug(parameter_dict(final_params))
            start = time.perf_counter()
            logger.info("running...")
            logger.debug("\n--- start tool output ---")
            if random.random() < 0.5:
                raise TestFailException("random error")
            with OutputCapture(logger):
                run(test.toolbox, test.alias, parameter_dict(final_params))
            logger.debug("\n---  end tool output  ---")
            took = time.perf_counter() - start
            logger.info(f"took {timedelta(seconds=took)}")
        except Exception as e:
            raise TestFailException(f"Exception: {e}")

        # copy outputs
        transfers = test.resolve_outputs(temp_inputs, outputs)
        logger.debug([(str(src), str(dst)) for src, dst in transfers])
        shutil.rmtree(outputs, ignore_errors=True)
        if transfers:
            logger.info("copying expected outputs to output directory")
            outputs.mkdir(exist_ok=True)
            for i, (src, dst) in enumerate(transfers):
                logger.debug(f"{i} {src=!s}")
                logger.debug(f"{i} {dst=!s}")
                if src.is_file():
                    shutil.copyfile(str(src), str(dst))
                elif src.is_dir():
                    shutil.copytree(str(src), str(dst))
                else:
                    logger.critical("BAD")
                    raise Exception("BAD")
        else:
            logger.info("saving no outputs")

        results.post_results(run_id, env, test_id, status="complete", run_result="PASS")
        logger.info("test finished\n")

    except TestFailException as e:
        logger.error(f"FAIL: {e}\n")
        results.post_results(run_id, env, test_id, status="complete", run_result="FAIL")


def run_all_tests(
    root: Path, run_id: int, env: str, env_python: str, test_ids_to_run: Optional[set[str]] = None
):
    tests_dir = root / "tests"
    log_dir = root / "logs"
    run_logfile = log_dir / f"{run_id:03d}_{env}.log"
    logger = setup_logger(f"run_{run_id}", run_logfile)
    logger.info("RUN ALL")
    logger.debug(f"{env=}")
    logger.debug(f"{env_python=}")
    logger.debug(f"{tests_dir=}")

    tests = find_tests(tests_dir)
    if test_ids_to_run is not None:
        tests = [t for t in tests if t[1] in test_ids_to_run]

    logger.info(f"found {len(tests)} tests to run")
    for i, (test_path, test_id, test) in enumerate(tests):
        logger.debug(f"{i} RUN {test_path.relative_to(tests_dir)}")
        subprocess.run(
            [
                env_python,
                "runner.py",
                "run_one",
                "--path",
                str(test_path),
                "--run_id",
                str(run_id),
                "--env",
                env,
            ]
        )

        temp_inputs = f"inputs_{env}_{test_id}"
        for tempdir in (test_path.parent, Path(gettempdir())):
            rm = tempdir / temp_inputs
            logger.debug(f"REMOVE {rm}")
            shutil.rmtree(str(rm), ignore_errors=True)
    logger.info("FINISHED ALL")


@dataclass(frozen=True)
class GeneralConfig:
    baseline_name: str  # could maybe get 'name' from python.exe parent dir (env name)
    baseline_python: str  # abs path to env python.exe
    target_name: str
    target_python: str  # abs path to env python.exe

    root_dir: str  # abs path I:\test\ArcGISPro_VersionTesting
    toolboxes_dir: str  # toolboxes
    tests_dir: str  # tests
    database: str  # sqlite database


def create_new_tests(toolbox_dir: Path, tests_dir: Path) -> int:
    tests = find_toolboxes(toolbox_dir)
    tests_dir.mkdir(exist_ok=True)
    count = 0
    for t in tests:
        search_name = t.test_path(tests_dir, "*").stem  # find any variant
        existing_test = any(tests_dir.glob(search_name))
        if not existing_test:
            test_path = t.test_path(tests_dir)
            test_path.parent.mkdir(exist_ok=True, parents=True)
            test_path.write_text(t.terrible_ini())
            (test_path.parent / "inputs").mkdir(exist_ok=True)
            count += 1
    return count


def cmd_create_new_tests(args: argparse.Namespace):
    print("scanning")
    tb_dir = Path(r"I:\test\ArcGISPro_VersionTesting\toolboxes")
    t_dir = Path("arctests")  # r"I:\test\ArcGISPro_VersionTesting\tests"
    count_created = create_new_tests(tb_dir, t_dir)
    print(f"created {count_created} new tests")


def cmd_run_single_test(args: argparse.Namespace):
    run_single_test(Path(args.path).absolute(), args.run_id, args.env)


def cmd_run_all_tests(args: argparse.Namespace):
    db = DB(r"I:\test\ArcGISPro_VersionTesting\results.sqlite")
    run_id, test_ids_to_run = db.waiting_tests("baseline")
    # test_ids_to_run = set(id for _, id in to_run)
    # assert len(set(run_id for run_id, _ in to_run)) == 1
    print("got", len(test_ids_to_run), "test ids")
    if not test_ids_to_run:
        return
    root = Path(r"I:\test\ArcGISPro_VersionTesting")
    # run_id = to_run[0][0]
    env = "baseline"  # args.env
    env_python = r"C:\Users\ben.stabley\AppData\Local\ESRI\conda\envs\arcgispro-py3_prod_env_v1.4\python.exe"  # fmt:off
    run_all_tests(root, run_id, env, env_python, test_ids_to_run)


def cmd_enqueue_tests(args: argparse.Namespace):
    test_ids = [id for _, id, _ in find_tests(r"I:\test\ArcGISPro_VersionTesting\tests")]
    print("found", len(test_ids), "tests")
    print("start=", args.start)  # start is assumed to be LOCAL time
    db = DB(r"I:\test\ArcGISPro_VersionTesting\results.sqlite")
    run_id, test_ids_queued = db.add_run(test_ids, args.fails, args.start)
    print("run_id", run_id)
    print("queued", len(test_ids_queued), "tests")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    ######
    run_one = subparsers.add_parser("run_one", help="run a single test")
    run_one.add_argument(
        "--path",
        type=str,
        help="path to test config ini",
    )
    run_one.add_argument(
        "--run_id",
        type=int,
        help="run id number",
    )
    run_one.add_argument(
        "--env",
        type=str,
        choices=["baseline", "target"],
        help="environment name to run",
    )
    run_one.set_defaults(func=cmd_run_single_test)

    ######
    run_all = subparsers.add_parser("run_all", help="run all tests")
    run_all.add_argument(
        "--env",
        type=str,
        choices=["baseline", "target"],
        help="environment name to run",
    )
    run_all.set_defaults(func=cmd_run_all_tests)

    ######
    create = subparsers.add_parser("create", help="scans toolboxes and creates test templates")
    create.set_defaults(func=cmd_create_new_tests)

    ######
    enqueue = subparsers.add_parser("enqueue", help="add new test runs in waiting status")
    enqueue.add_argument(
        "--fails",
        action="store_true",
        help="enqueue only tests that have not passed",
    )
    enqueue.add_argument(
        "--start",
        type=dt.fromisoformat,
        default=None,
        help="date and time for the run to start",
    )
    enqueue.set_defaults(func=cmd_enqueue_tests)

    return parser.parse_args()


def main():

    args = parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        print("error")

    # --- needs env specified ---
    # SUBCOMMAND 2 - run single test -- for running single in subprocess
    # SUBCOMMAND 3 - run queued tests for env -- this will be run periodically via "cron"

    # --- env independent ---
    # SUBCOMMAND 1 - scan toolboxes, create default test no test for the tool exists
    # SUBCOMMAND 4 - enqueue tests for both envs, option to skip tests where both envs passed, set start time
    # SUBCOMMAND 5 - ?update sqlite database with test results


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
