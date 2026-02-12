import configparser
from dataclasses import dataclass, field
from datetime import datetime as dt  # broken for no reason
from itertools import chain
from pathlib import Path
from typing import Any, Union

import arcpy

toolbox_path: str = (
    r"I:\test\ArcGISPro_VersionTesting\toolboxes\NV5_Tools_v0.3.0\nv5_toolbox_v0.3.0.atbx"
)
# toolname: str = "AOILandCover"
# params: dict[str, Any] = {
#     "input_fc": r"I:\test\ben\landcover\duke_giant\merged_spans.shp",
#     "output_fc": r"I:\test\ben\landcover\duke_giant\merged_spans_landcover.shp",
#     "landcover_raster": "CONUS",
#     "output_classes": "3 class - urban, mixed, rural",
#     "buffer_distance": 152,
#     "dissolve_all": True,
#     "group_field": None,
# }


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
    description: str = "default"
    """SHORT description of test"""
    parameters: list[Parameter] = field(default_factory=list)
    """extracted parameter info"""
    outputs: list[str] = field(default_factory=list)
    """output files from script to be kept and compared"""

    @property
    def filename(self) -> str:
        return f"test.{self.alias}.{self.description.replace(' ', '_')}.ini"

    def terrible_ini(self) -> str:
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
'''
        for p in self.parameters:
            content += f'; display name: {p.display_name} | type: {p.datatype}\n'
            content += f'{p.name} = {p.value}\n'
        return content


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
    parser = configparser.ConfigParser()
    parser.read_string(contents)
    return Test(
        toolbox=parser["test"]["toolbox"],
        alias=parser["test"]["alias"],
        description=parser["test"]["description"] if parser["test"]["description"] else "default",
        parameters=[Parameter(name=k, value=v) for k, v in parser["parameters"].items()],
    )
    # d = dict(parser["tool"])
    # d["parameters"] = dict(parser["parameters"])
    # arcpy.AddMessage(str(d))


def find_toolboxes(root: Union[str, Path]) -> list[Test]:
    root = Path(root)
    toolboxes = chain(root.glob("*/*.atbx"), root.glob("*/*.tbx"))
    tests: list[Test] = []
    for toolbox in toolboxes:
        print(toolbox)
        tests.extend(make_tests(toolbox))
    return tests


def run(toolbox_path: str, tool_alias: str, params: dict[str, Any]):
    toolbox = arcpy.ImportToolbox(toolbox_path)
    tool = getattr(toolbox, tool_alias)
    tool(**params)


def main():
    tests = find_toolboxes(r"I:\test\ArcGISPro_VersionTesting\toolboxes")
    tests_dir = Path("tests")
    tests_dir.mkdir(exist_ok=True)
    for t in tests:
        Path(tests_dir, t.filename).write_text(t.terrible_ini())


if __name__ == "__main__":
    main()
