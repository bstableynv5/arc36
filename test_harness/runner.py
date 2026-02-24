import argparse
import json
import logging
import math
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
from report_template import make_report_html
from test import Parameter, Test, make_tests, parameter_dict, parse_test_ini, normalize_toolbox_name
from test_logging import OutputCapture, setup_logger


def find_tests(root: Union[str, Path]) -> list[tuple[Path, str, Test]]:
    root = Path(root)
    test_configs = root.glob("*/*.ini")
    tests = [(c.absolute(), c.stem, parse_test_ini(c.read_text())) for c in test_configs]
    return tests


def find_toolboxes(root: Union[str, Path]) -> list[Test]:
    root = Path(root)  # I:/.../toolboxes/baseline
    toolboxes = chain(root.glob("*/*.atbx"), root.glob("*/*.tbx"))
    tests: list[Test] = []
    for toolbox in toolboxes:
        tests.extend(make_tests(toolbox, root))
    return tests


def run(toolbox_path: str, tool_alias: str, params: dict[str, Any]):
    toolbox = arcpy.ImportToolbox(toolbox_path)
    tool = getattr(toolbox, tool_alias)
    tool(**params)


class TestFailException(Exception):
    """when a toolbox test fails"""


def run_single_test(
    config: 'GeneralConfig', test_path: Path, run_id: int, env: Literal["baseline", "target"]
):
    try:
        results = DB(str(config.database))
        test_id = test_path.stem
        results.update_test_status(run_id, env, test_id, status="running")

        # need run id, env
        test = parse_test_ini(test_path.read_text())
        # print("PARSED TEST")
        test_logfile = test_path.parent / "logs" / f"{run_id:03d}_{env}_{test_id}.log"
        logger = setup_logger(test_id, test_logfile)

        toolbox_path = config.toolboxes_dir / env / test.toolbox  # test.toolbox is relative

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
        logger.debug(f"{toolbox_path=!s}")
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
            # if random.random() < 0.5:
            #     raise TestFailException("random error")
            with OutputCapture(logger):
                run(str(toolbox_path), test.alias, parameter_dict(final_params))
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

        results.update_test_status(run_id, env, test_id, status="complete", run_result="PASS")
        logger.info("test finished\n")

    except TestFailException as e:
        logger.error(f"FAIL: {e}\n")
        results.update_test_status(run_id, env, test_id, status="complete", run_result="FAIL")


def run_all_tests(
    config: 'GeneralConfig', run_id: int, env: str, test_ids_to_run: Optional[set[str]] = None
):
    tests_dir = config.tests_dir
    run_logfile = config.logs_dir / f"{run_id:03d}_{env}.log"
    env_python = config.environments[env]
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


def create_new_tests(toolbox_dir: Path, tests_dir: Path) -> int:
    tests = find_toolboxes(toolbox_dir)  # I:/.../toolboxes/baseline
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


@dataclass(frozen=True)
class GeneralConfig:
    # env name and abs path to python
    # "baseline": r"C:\...\ESRI\conda\envs\arcgispro-py3_prod_env_v1.4\python.exe""
    environments: dict[str, str]

    root_dir: Path  # abs path I:\test\ArcGISPro_VersionTesting
    toolboxes_dir: Path  # toolboxes
    tests_dir: Path  # tests
    logs_dir: Path  # logs
    database: Path  # sqlite database

    def get_general_logger(self) -> logging.Logger:
        return setup_logger("general", self.logs_dir / "general.log", add_timestamp=False)

    def cmd_normalize_toolboxes(self, args: argparse.Namespace):
        """convert folder and atbx(tbx) names to 'normalized' versions so that
        all toolbox paths are the same other than the 'env'-based root."""
        log = self.get_general_logger()
        log.debug("START CMD_TBNORMALIZE")
        for env in self.environments.keys():
            root = (self.toolboxes_dir / env).absolute()
            log.info(f"Normalizing {env}")
            log.info(f"Root: {root}")
            toolboxes = chain(root.glob("*/*.atbx"), root.glob("*/*.tbx"))
            for tb in toolboxes:
                normalized_name = normalize_toolbox_name(tb)
                # rename file then file's parent dir
                new_tb_atbx = tb.rename(tb.with_stem(normalized_name))
                new_tb_parent = tb.parent.rename(tb.parent.with_name(normalized_name))
                new_tb = new_tb_parent / new_tb_atbx.name
                log.info(f"{tb.relative_to(root)} -> {new_tb.relative_to(root)}")
        log.debug("END CMD_TBNORMALIZE")

    def cmd_create_new_tests(self, args: argparse.Namespace):
        scan_dir = self.toolboxes_dir / args.env
        log = self.get_general_logger()
        log.debug("START CMD_CREATE")
        log.info(f"Scanning {scan_dir}")
        testout_dir = Path("arctests")  # TODO for dev! r"I:\test\ArcGISPro_VersionTesting\tests"
        count_created = create_new_tests(scan_dir, testout_dir)
        log.info(f"Created {count_created} new tests")
        log.debug("END CMD_CREATE")

    def cmd_run_single_test(self, args: argparse.Namespace):
        run_single_test(self, Path(args.path).absolute(), args.run_id, args.env)

    def cmd_run_all_tests(self, args: argparse.Namespace):
        log = self.get_general_logger()
        log.debug("START CMD_RUN_ALL")
        db = DB(str(self.database))
        run_id, test_ids_to_run = db.dequeue_tests(args.env)
        if test_ids_to_run:
            log.info(f"{len(test_ids_to_run)} tests for {args.env} updated from queued to waiting")
            run_all_tests(self, run_id, args.env, test_ids_to_run)
            db.set_run_endtime(run_id)
        else:
            log.info("No queued tests eligible to run")
        log.debug("END CMD_RUN_ALL")

    def cmd_enqueue_tests(self, args: argparse.Namespace):
        log = self.get_general_logger()
        log.debug("START CMD_ENQUEUE")
        test_ids = [id for _, id, _ in find_tests(self.tests_dir)]
        envs = list(self.environments.keys())
        log.info(f"Found {len(test_ids)} tests")
        log.info(f"Found {len(envs)} environments: {envs}")
        log.debug(f"{args.start=}")  # input start is assumed to be LOCAL time
        db = DB(str(self.database))
        run_id, test_ids_queued = db.add_run_enqueue_tests(test_ids, envs, args.fails, args.start)
        log.info(f"Queued {len(test_ids_queued)} tests for run {run_id}")
        log.debug("END CMD_ENQUEUE")

    def cmd_generate_report(self, args: argparse.Namespace):
        run_rows, test_rows = DB(str(self.database)).get_everything()
        html = make_report_html(run_rows, test_rows)
        Path(args.path).write_text(html)

    def configure_parser(self) -> argparse.ArgumentParser:
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
        run_one.set_defaults(func=self.cmd_run_single_test)

        ######
        run_all = subparsers.add_parser("run_all", help="run all tests")
        run_all.add_argument(
            "--env",
            type=str,
            choices=["baseline", "target"],
            default="baseline",  # TODO: this is for dev only
            help="environment name to run",
        )
        run_all.set_defaults(func=self.cmd_run_all_tests)

        ######
        tbnormalize = subparsers.add_parser(
            "tbnormalize", help="normalizes toolbox folders and atbx filenames for all envs"
        )
        tbnormalize.set_defaults(func=self.cmd_normalize_toolboxes)

        ######
        create = subparsers.add_parser("create", help="scans toolboxes and creates test templates")
        create.add_argument(
            "--env",
            type=str,
            choices=["baseline", "target"],
            default="baseline",  # TODO: this is for dev only
            help="environment toolboxes to scan. always want default.",
        )
        create.set_defaults(func=self.cmd_create_new_tests)

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
        enqueue.set_defaults(func=self.cmd_enqueue_tests)

        ######
        report = subparsers.add_parser("report", help="html report of runs and tests")
        report.set_defaults(func=self.cmd_generate_report)
        report.add_argument(
            "--path",
            type=str,
            default="report.html",
            help="path to write report",
        )

        return parser


def open_config() -> GeneralConfig:
    """looks in cwd"""

    values = json.loads(Path("config.json").read_text())
    return GeneralConfig(
        environments=values["environments"],
        root_dir=Path(values["root_dir"]),
        toolboxes_dir=Path(values["root_dir"], values["toolboxes_dir"]),
        tests_dir=Path(values["root_dir"], values["tests_dir"]),
        logs_dir=Path(values["root_dir"], values["logs_dir"]),
        database=Path(values["root_dir"], values["database"]),
    )


def main():

    config = open_config()
    parser = config.configure_parser()
    args = parser.parse_args()
    args.func(args)

    # --- needs env specified ---
    # SUBCOMMAND 3 - run single test -- for running single in subprocess
    # SUBCOMMAND 4 - run queued tests for env -- this will be run periodically via "cron"

    # --- env independent ---
    # SUBCOMMAND 1 - scan toolboxes, create default test no test for the tool exists
    # SUBCOMMAND 2 - enqueue tests for both envs, option to skip tests where both envs passed, set start time
    # SUBCOMMAND 5 - create report (html)
    # SUBCOMMAND ? - ?update sqlite database with test results


if __name__ == "__main__":
    # try:
    main()
# except Exception as e:
#     print(e)
