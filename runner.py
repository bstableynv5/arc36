import configparser
import logging
import shutil
from dataclasses import dataclass, field, replace
from datetime import datetime as dt  # broken for no reason
from itertools import chain
from pathlib import Path
from pprint import pprint
import sys
from tempfile import TemporaryDirectory
from typing import Any, Generator, Union

# save these for logger before kibana (from toolbox import) clobbers things
real_stdout = sys.stdout
real_stderr = sys.stderr


def setup_test_logger(test_path: Path) -> logging.Logger:
    logger = logging.getLogger(test_path.stem)
    logger.propagate = False
    logger.setLevel(logging.DEBUG)

    log_dir = test_path.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    logname = f"{logger.name}_{dt.now():%Y%m%d%H%M%S}.log"
    fh = logging.FileHandler(str(log_dir / logname), mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)

    sh = logging.StreamHandler(stream=real_stdout)  # anti-kibana measure
    sh.setLevel(logging.INFO)
    logger.addHandler(sh)

    return logger


import arcpy

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
        content = f'''; generated {now:%Y-%m-%d %H:%M:%S}
[test]
; full path to toolbox (atbx/tbx) being tested.
toolbox = {self.toolbox}
; alias (tool's internal name) of tool being tested.
alias = {self.alias}
; SHORT description of test. letters, numbers, and spaces only.
description = {self.description}

[parameters]
; tool input parameters.
{parameter_content}

[outputs]
; list expected output files one per line.
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
    parser.read_string(contents)
    return Test(
        toolbox=parser["test"]["toolbox"],
        alias=parser["test"]["alias"],
        description=parser["test"]["description"],
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
        self.logger.debug(message)


def main():
    # automatic creation of test configs
    # tests = find_toolboxes(r"I:\test\ArcGISPro_VersionTesting\toolboxes")
    # tests_dir = Path("tests")
    # tests_dir.mkdir(exist_ok=True)
    # for t in tests:
    #     Path(tests_dir, t.filename).write_text(t.terrible_ini())

    # running all tests found
    for test_path, test in find_tests(r"I:\test\ArcGISPro_VersionTesting\tests"):
        logger = setup_test_logger(test_path)
        with OutputCapture(logger):
            inputs = test_path.parent / "inputs"
            outputs = test_path.parent / f"outputs_{test_path.stem}"  # TODO: not sure about this

            logger.info(f"Test: {test_path.stem}")
            logger.info(f"Toolbox: {test.toolbox}")
            logger.info(f"Alias: {test.alias}")
            logger.info(f"Description: {test.description}")
            logger.debug(f"{inputs=}")
            logger.debug(f"{outputs=}")

            if len(list(inputs.glob("*"))) == 0:
                logger.error(f"FAIL: {test_path.stem}. No inputs.")
                continue

            with TemporaryDirectory(dir=test_path.parent, prefix="inputs_") as temp_inputs:
                # copy inputs to temp
                temp_inputs = Path(temp_inputs)
                logger.debug(f"{temp_inputs=}")
                shutil.copytree(str(inputs), str(temp_inputs), dirs_exist_ok=True)
                logger.info("copying inputs to temp directory")
                final_params = test.resolve_inputs(temp_inputs)  # inputs_dirname=inputs.stem
                transfers = test.resolve_outputs(temp_inputs, outputs)
                logger.debug(final_params)
                logger.debug(transfers)
                # run on temp inputs
                try:
                    logger.info("running...")
                    run(test.toolbox, test.alias, parameter_dict(final_params))
                except Exception as e:
                    logger.error(f"FAIL: {test_path.stem}. Exception: {e}")
                    continue
                # copy outputs
                logger.info("copying expected outputs to output directory")
                shutil.rmtree(outputs, ignore_errors=True)
                outputs.mkdir(exist_ok=True)
                for src, dst in transfers:
                    logger.debug(src)
                    logger.debug(dst)
                    if src.is_file():
                        shutil.copyfile(str(src), str(dst))
                    elif src.is_dir():
                        shutil.copytree(str(src), str(dst))
                    else:
                        raise Exception("BAD")

            logger.info("test finished\n")


if __name__ == "__main__":
    main()
