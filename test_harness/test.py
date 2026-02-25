import configparser
import re
from dataclasses import dataclass, field, replace
from datetime import datetime as dt  # broken for no reason
from pathlib import Path
from typing import Any, Generator, Literal, Optional, Union

import arcpy
from formats import PSEUDO_ISO_FMT


def normalize_toolbox_name(toolbox: Union[Path, str]) -> str:
    """Normalize toolbox name by removing version info, change to lowercase,
    and replace non-alphanumerics with underscore.

    Args:
        toolbox (Union[Path, str]): absolute or relative path to toolbox atbx/tbx.

    Returns:
        str: normalized toolbox atbx stem.
    """
    toolbox_name = Path(toolbox).stem.lower()
    toolbox_name = re.sub(r"v?\d(\.\d){1,2}", r"", toolbox_name)  # v0.0.0
    toolbox_name = re.sub(r"\W", r"_", toolbox_name)  # \W = [^a-zA-Z0-9_]
    toolbox_name = toolbox_name.strip(" _")
    return toolbox_name


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

    def test_id(self, variant: str = "default") -> str:
        return ".".join([normalize_toolbox_name(self.toolbox), self.alias.lower(), variant])

    def test_path(self, tests_dir: Path, variant: str = "default") -> Path:
        test_id = self.test_id(variant)
        return tests_dir / test_id / f"{test_id}.ini"

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

    def resolve_outputs(
        self, input_dir: Path, output_dir: Path, inputs_dirname: str = "inputs"
    ) -> list[tuple[Path, Path]]:
        """produce source/destination pairs of paths for the files specified
        to be saved as outputs. output paths _should_ begin with `inputs` to
        mirror the way true input parameters are signaled, but this function
        will work when `inputs` is not a prefix on the output path."""
        path_parts = (Path(p).parts for p in self.outputs)  # break
        path_parts = (p[1:] if p[0] == inputs_dirname else p for p in path_parts)  # filter
        cleaned_outputs = (Path(*p) for p in path_parts)  # join
        return [(input_dir / src, output_dir / src) for src in cleaned_outputs]


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
        for pi in param_info  # type: ignore
    ]


def make_tests(toolbox_path: Union[str, Path], relative_to: Optional[Path] = None) -> list[Test]:
    """arcpy
    toolbox_path: absolute path to a toolbox
    relative_to: a parent in `toolbox_path` to make the test's toolbox property relative to.
    """
    toolbox_path = Path(toolbox_path)
    relative_toolbox = toolbox_path
    if relative_to is not None:
        relative_toolbox = toolbox_path.relative_to(relative_to)
    # https://pro.arcgis.com/en/pro-app/latest/arcpy/functions/importtoolbox.htm
    toolbox = arcpy.ImportToolbox(str(toolbox_path))
    return [
        Test(
            toolbox=str(relative_toolbox),
            alias=alias,
            parameters=get_parameters(toolbox_path, alias),
        )
        for alias in toolbox.__all__  # type: ignore
    ]


def parse_test_ini(contents: str) -> Test:
    parser = configparser.ConfigParser(allow_no_value=True)
    parser.optionxform = str  # type: ignore # preserve case of ini keys. default converts to lower...
    parser.read_string(contents)
    return Test(
        toolbox=parser["test"]["toolbox"],
        alias=parser["test"]["alias"],
        description=parser["test"]["description"],
        run_local=parser.getboolean("test", "run_local", fallback=True),
        parameters=[Parameter(name=k, value=v) for k, v in parser["parameters"].items()],
        outputs=[str(k).strip(" '\"") for k, _ in parser["outputs"].items()],
    )
