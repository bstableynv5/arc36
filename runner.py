import configparser
import logging
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, replace
from datetime import datetime as dt  # broken for no reason
from datetime import timedelta
from itertools import chain
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Generator, Literal, Union

import arcpy

PSEUDO_ISO_FMT = "%Y-%m-%d %H:%M:%S"
EXTRA_PSEUDO_ISO_FMT = "%Y%m%d%H%M%S"

# save these for logger before kibana (from toolbox import) clobbers things
real_stdout = sys.stdout
real_stderr = sys.stderr


def setup_test_logger(test_path: Path, run_id: int, env: str) -> logging.Logger:
    logger = logging.getLogger(test_path.stem)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(asctime)s:%(levelname)5s: %(message)s", datefmt=PSEUDO_ISO_FMT)

    log_dir = test_path.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    logname = f"{run_id:03d}_{env}_{logger.name}_{dt.now():{EXTRA_PSEUDO_ISO_FMT}}.log"
    fh = logging.FileHandler(str(log_dir / logname), mode="w", encoding="utf-8")
    fh.setFormatter(formatter)
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)

    sh = logging.StreamHandler(stream=real_stdout)  # anti-kibana measure
    sh.setFormatter(formatter)
    sh.setLevel(logging.INFO)
    logger.addHandler(sh)

    return logger


# toolbox_path: str = (
#     r"I:\test\ArcGISPro_VersionTesting\toolboxes\NV5_Tools_v0.3.0\nv5_toolbox_v0.3.0.atbx"
# )
#
# toolname: str = "AOILandCover"
#
# params: dict[str, Any] = {
#     "input_fc": r"I:\test\ben\landcover\duke_giant\merged_spans.shp",
#     "output_fc": r"I:\test\ben\landcover\duke_giant\merged_spans_landcover.shp",
#     "landcover_raster": "CONUS",
#     "output_classes": "3 class - urban, mixed, rural",
#     "buffer_distance": 152,
#     "dissolve_all": True,
#     "group_field": None,
# }
#
# test_config = f"test.{tool_alias}.ini"


@dataclass(frozen=True)
class Parameter:
    name: str
    """name in code"""
    value: str
    """default value from arcpy, or entered value from a test config"""
    display_name: str = ""
    """name in arc gui"""
    datatype: str = ""
    """pretty arc type ('Feature Class')"""


@dataclass(frozen=True)
class Test:
    toolbox: str
    """absolute path to atbx/tbx"""
    alias: str
    """tool name/alias, not display name"""
    description: str = ""
    """SHORT description of test"""
    run_local: bool = True
    """copy inputs to C: if True. set False to keep inputs on I: (ie condor)"""
    parameters: list[Parameter] = field(default_factory=list)
    """extracted parameter info"""
    outputs: list[str] = field(default_factory=list)
    """output files from script to be kept and compared"""

    @property
    def filename(self) -> str:
        return f"test.{self.alias}.default.ini"

    def terrible_ini(self) -> str:

        parameter_lines = []
        for p in self.parameters:
            parameter_lines.append(f'; display name: {p.display_name} | type: {p.datatype}')
            parameter_lines.append(f'{p.name} = {p.value}')
        parameter_content = "\n".join(parameter_lines)

        outputs_content = "\n".join(self.outputs)  # this is a bit weird ini format

        now = dt.now()
        content = f'''; generated {now:{PSEUDO_ISO_FMT}}
[test]
; full path to toolbox (atbx/tbx) being tested.
toolbox = {self.toolbox}
; alias (tool's internal name) of tool being tested.
alias = {self.alias}
; SHORT description of test. letters, numbers, and spaces only.
description = {self.description}
; inputs will copy to machine C: before run. set false if inputs must stay on I: (ie condor)
run_local = {str(self.run_local).lower()}

[parameters]
; tool input parameters.
{parameter_content}

[outputs]
; list expected output files one per line.
; these are what will be compared between ArcPro 3.1 and ArcPro 3.6.
{outputs_content}
'''
        return content

    def resolve_inputs(self, input_dir: Path, inputs_dirname: str = "inputs") -> list[Parameter]:
        """stick together the relative parameter inputs with input_dir"""
        # TODO: improve this function?
        resolved: list[Parameter] = []
        for p in self.parameters:
            path_parts = Path(p.value).parts  # is there a better way?
            if path_parts and path_parts[0] == inputs_dirname:
                value = input_dir.joinpath(*path_parts[1:])
                target = str(input_dir.parent / value)
                resolved.append(replace(p, value=target))
            else:
                resolved.append(p)

        return resolved

    def resolve_outputs(self, input_dir: Path, output_dir: Path) -> list[tuple[Path, Path]]:
        return [(input_dir / src, output_dir / src) for src in self.outputs]


def parameter_dict(params: list[Parameter]) -> dict[str, Any]:
    return {p.name: p.value for p in params}


def get_parameters(toolbox_path: Union[str, Path], tool_alias: str) -> list[Parameter]:
    """arcpy"""
    param_info = arcpy.GetParameterInfo(str(Path(toolbox_path, tool_alias)))
    return [
        Parameter(
            name=pi.name,
            value=pi.valueAsText if pi.value is not None else "",
            display_name=pi.displayName,
            datatype=pi.datatype,
        )
        for pi in param_info
    ]


def make_tests(toolbox_path: Union[str, Path]) -> list[Test]:
    """arcpy"""
    # https://pro.arcgis.com/en/pro-app/latest/arcpy/functions/importtoolbox.htm
    toolbox = arcpy.ImportToolbox(str(toolbox_path))
    return [
        Test(
            toolbox=str(toolbox_path),
            alias=alias,
            parameters=get_parameters(toolbox_path, alias),
        )
        for alias in toolbox.__all__
    ]


def parse_test_ini(contents: str) -> Test:
    parser = configparser.ConfigParser(allow_no_value=True)
    parser.optionxform = str  # preserve case of ini keys. default converts to lower...
    parser.read_string(contents)
    return Test(
        toolbox=parser["test"]["toolbox"],
        alias=parser["test"]["alias"],
        description=parser["test"]["description"],
        run_local=parser.getboolean("test", "run_local", fallback=True),
        parameters=[Parameter(name=k, value=v) for k, v in parser["parameters"].items()],
        outputs=[str(k).strip(" '\"") for k, _ in parser["outputs"].items()],
    )
    # d = dict(parser["tool"])
    # d["parameters"] = dict(parser["parameters"])
    # arcpy.AddMessage(str(d))


def find_tests(root: Union[str, Path]) -> Generator[tuple[Path, Test], None, None]:
    root = Path(root)
    test_configs = root.glob("**/test*.ini")
    tests = ((c.absolute(), parse_test_ini(c.read_text())) for c in test_configs)
    yield from tests


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
    # del tool # no effect against locked gdbs
    # del toolbox


def delete_temp_inputs_cause_arcpy_is_stupid(inputs: Path):
    # arcpy can't even delete its own crap!
    for file in inputs.iterdir():
        print(file)
        # compacting supposedly clears locks, but didnt work
        # if file.suffix.lower() == ".gdb":
        #     print("compacting")
        #     arcpy.Compact_management(str(file))
        arcpy.Delete_management(str(file.absolute()))


class OutputCapture:
    _orig_message = arcpy.AddMessage  # real arcpy funcs?
    _orig_warning = arcpy.AddWarning
    _orig_error = arcpy.AddError

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def __enter__(self) -> logging.Logger:
        arcpy.AddMessage = self
        arcpy.AddWarning = self
        arcpy.AddError = self
        return self.logger

    def __exit__(self, exc_type, exc_value, traceback):
        arcpy.AddMessage = OutputCapture._orig_message
        arcpy.AddWarning = OutputCapture._orig_warning
        arcpy.AddError = OutputCapture._orig_error

    def __call__(self, message: str, *args: Any, **kwds: Any) -> Any:
        self.logger.debug(message.strip("\n"))  # densify


def run_single_test(test_path: Path, run_id: int, env: Literal["baseline", "target"]):
    # need run id, env
    test = parse_test_ini(test_path.read_text())
    print("PARSED TEST")
    test_id = test_path.stem
    logger = setup_test_logger(test_path, run_id, env)
    with OutputCapture(logger):
        inputs = test_path.parent / "inputs"
        outputs = test_path.parent / f"outputs_{env}_{test_id}"  # TODO: not sure about this

        logger.debug(f"{run_id=}")
        logger.debug(f"{env=}")
        logger.info(f"Test:        {test_id}")
        logger.info(f"Toolbox:     {test.toolbox}")
        logger.info(f"Alias:       {test.alias}")
        logger.info(f"Description: {test.description}")
        logger.info(f"Run Local:   {test.run_local}")
        logger.debug(f"{inputs=!s}")
        logger.debug(f"{outputs=!s}")

        if len(list(inputs.glob("*"))) == 0:
            logger.error(f"FAIL: {test_id}. No inputs.")
            return

        # running the inputs from network drive is slooooow
        # TODO: something weird happening with tempdir deletion. gdb stays opened by some process.
        # blast2dem creates a feature layer...
        temp_dir_parent = None if test.run_local else test_path.parent
        temp_inputs = TemporaryDirectory(dir=temp_dir_parent, prefix=f"inputs_{env}_").name
        # with TemporaryDirectory(dir=temp_dir_parent, prefix="inputs_") as temp_inputs:
        # copy inputs to temp
        temp_inputs = Path(temp_inputs)
        logger.debug(f"{temp_inputs=!s}")
        logger.info("copying inputs to temp directory")
        shutil.copytree(str(inputs), str(temp_inputs), dirs_exist_ok=True)
        final_params = test.resolve_inputs(temp_inputs)  # inputs_dirname=inputs.stem
        transfers = test.resolve_outputs(temp_inputs, outputs)
        logger.debug(parameter_dict(final_params))
        logger.debug([(str(src), str(dst)) for src, dst in transfers])

        # run on temp inputs
        try:
            start = time.perf_counter()
            logger.info("running...")
            logger.debug("\n--- start tool output ---")
            run(test.toolbox, test.alias, parameter_dict(final_params))
            logger.debug("\n---  end tool output  ---")
            took = time.perf_counter() - start
            logger.info(f"took {timedelta(seconds=took)}")
        except Exception as e:
            logger.error(f"FAIL: {test_id}. Exception: {e}")
            return

        # copy outputs
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

        # delete_temp_inputs_cause_arcpy_is_stupid(temp_inputs)
        # logger.info("exit tempdir")

        logger.info("test finished\n")


@dataclass(frozen=True)
class GeneralConfig:
    baseline_name: str  # could maybe get 'name' from python.exe parent dir (env name)
    baseline_python: str  # abs path to env python.exe
    target_name: str
    target_python: str  # abs path to env python.exe

    root_dir: str  # abs path I:\test\ArcGISPro_VersionTesting
    toolbox_dir: str  # toolboxes
    tests_dir: str  # tests


def create_new_tests() -> int:
    tests = find_toolboxes(r"I:\test\ArcGISPro_VersionTesting\toolboxes")
    tests_dir = Path("tests")  # r"I:\test\ArcGISPro_VersionTesting\tests"
    tests_dir.mkdir(exist_ok=True)
    count = 0
    for t in tests:
        toolbox_dir = tests_dir / Path(t.toolbox).stem.lower().replace(" ", "_")
        existing_test = any(toolbox_dir.glob(f"*{t.alias}*"))
        if not existing_test:
            test_path = toolbox_dir / f"{t.alias}.default" / t.filename  # defaults all over. meh
            test_path.parent.mkdir(exist_ok=True, parents=True)
            test_path.write_text(t.terrible_ini())
            count += 1
    return count


def main():
    # SUBCOMMAND 1 - scan toolboxs, create default test no test for the tool exists
    # automatic creation of test configs
    # count_created = create_new_tests()
    # print(f"created {count_created} new tests")

    # SUBCOMMAND 2 - run single test
    if len(sys.argv) == 2:
        print("SINGLE")
        run_single_test(Path(sys.argv[1]), 0, "baseline")
    # SUBCOMMAND 3 - run waiting tests for env
    else:
        # running all tests found
        print("RUN ALL")
        print(str(sys.argv))
        for test_path, test in find_tests(r"I:\test\ArcGISPro_VersionTesting\tests"):
            print("ATTEMPT RUN")
            subprocess.run(
                [
                    r"C:\Users\ben.stabley\AppData\Local\ESRI\conda\envs\arcgispro-py3_prod_env_v1.4\python.exe",
                    "runner.py",
                    str(test_path),
                ]
            )
            for tempdir in test_path.parent.glob("inputs_*"):  # TODO: need targeted delete
                print("RM", tempdir)
                shutil.rmtree(str(tempdir))

    # --- env independent ---
    # SUBCOMMAND 1 - see above
    # SUBCOMMAND 4 - enqueue tests for both envs, option to skip tests where both envs passed
    # SUBCOMMAND 5 - update sqlite database with test results


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
