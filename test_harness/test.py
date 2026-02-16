import configparser
import re
from dataclasses import dataclass, field, replace
from datetime import datetime as dt  # broken for no reason
from pathlib import Path
from typing import Any, Generator, Literal, Optional, Union

import arcpy
from constants import PSEUDO_ISO_FMT


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

    def normalize_toolbox_name(self) -> str:
        toolbox_name = Path(self.toolbox).stem.lower()
        toolbox_name = re.sub(r"v?\d(\.\d){1,2}", r"", toolbox_name)  # v0.0.0
        toolbox_name = re.sub(r"\W", r"_", toolbox_name)  # \W = [^a-zA-Z0-9_]
        toolbox_name = toolbox_name.strip(" _")
        return toolbox_name

    def test_path(self, tests_dir: Path, variant: str = "default") -> Path:
        toolbox_name = self.normalize_toolbox_name()
        test_id = ".".join([toolbox_name, self.alias, variant])
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
        for pi in param_info  # type: ignore
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
