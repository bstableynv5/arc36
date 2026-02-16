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


def find_tests(root: Union[str, Path]) -> list[tuple[Path, Test]]:
    root = Path(root)
    test_configs = root.glob("*/*.ini")
    tests = [(c.absolute(), parse_test_ini(c.read_text())) for c in test_configs]
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


def run_all_tests(root: Path, run_id: int, env: str, env_python: str):
    tests_dir = root / "tests"
    log_dir = root / "logs"
    run_logfile = log_dir / f"{run_id:03d}_{env}.log"
    logger = setup_logger(f"run_{run_id}", run_logfile)
    logger.info("RUN ALL")
    logger.debug(f"{env=}")
    logger.debug(f"{env_python=}")
    logger.debug(f"{tests_dir=}")

    tests = find_tests(tests_dir)
    logger.info(f"found {len(tests)} tests to run")
    for i, (test_path, test) in enumerate(tests):
        logger.debug(f"{i} RUN {test_path.relative_to(tests_dir)}")
        subprocess.run([env_python, "runner.py", str(test_path)])

        temp_inputs = f"inputs_{env}_{test_path.stem}"
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


def create_new_tests() -> int:
    tests = find_toolboxes(r"I:\test\ArcGISPro_VersionTesting\toolboxes")
    tests_dir = Path("arctests")  # r"I:\test\ArcGISPro_VersionTesting\tests"
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


def main():
    # SUBCOMMAND 1 - scan toolboxs, create default test no test for the tool exists
    # automatic creation of test configs
    # count_created = create_new_tests()
    # print(f"created {count_created} new tests")
    # return

    # SUBCOMMAND 2 - run single test -- for running single in subprocess
    if len(sys.argv) == 2:
        # print("SINGLE")
        run_single_test(Path(sys.argv[1]), 0, "baseline")
    # SUBCOMMAND 3 - run waiting tests for env -- this will be run periodically via "cron"
    else:
        # running all tests found
        root = Path(r"I:\test\ArcGISPro_VersionTesting")
        run_id = 0
        env = "baseline"
        env_python = r"C:\Users\ben.stabley\AppData\Local\ESRI\conda\envs\arcgispro-py3_prod_env_v1.4\python.exe"
        run_all_tests(root, run_id, env, env_python)

    # --- env independent ---
    # SUBCOMMAND 1 - see above
    # SUBCOMMAND 4 - enqueue tests for both envs, option to skip tests where both envs passed
    # SUBCOMMAND 5 - ?update sqlite database with test results


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
