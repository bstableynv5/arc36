from datetime import datetime as dt  # broken for no reason
import io
from pathlib import Path
from typing import Any, NamedTuple
import configparser
from pprint import pformat

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


def terrible_ini(toolbox_path: str, tool_alias: str) -> str:
    now = dt.now()
    content = f'''; generated {now:%Y-%m-%d %H:%M:%S}
[tool]
toolbox = {toolbox_path}
alias = {tool_alias}

[parameters]
'''
    param_info = arcpy.GetParameterInfo(str(Path(toolbox_path, tool_alias)))
    for pi in param_info:
        line = f'; display name: {pi.displayName} | type: {pi.datatype}\n'
        line += f'{pi.name} = {pi.valueAsText if pi.value is not None else ""}\n'
        content += line
    # arcpy.AddMessage(content)
    return content


def make_tests(toolbox_path: str) -> list[str]:
    toolbox = arcpy.ImportToolbox(toolbox_path)
    configs = []
    for tool_alias in toolbox.__all__:
        content = terrible_ini(toolbox_path, tool_alias)
        test_config = f"test.{tool_alias}.ini"
        Path(test_config).write_text(content)
        configs.append(test_config)
    return configs


class Test(NamedTuple):
    toolbox: str
    alias: str
    parameters: dict[str, Any]


def read_test(contents: str) -> Test:
    parser = configparser.ConfigParser()
    parser.read_string(contents)
    return Test(
        toolbox=parser["tool"]["toolbox"],
        alias=parser["tool"]["alias"],
        parameters=dict(parser["parameters"]),
    )
    # d = dict(parser["tool"])
    # d["parameters"] = dict(parser["parameters"])
    # arcpy.AddMessage(str(d))


def run(toolbox_path: str, tool_alias: str, params: dict[str, Any]):
    toolbox = arcpy.ImportToolbox(toolbox_path)
    tool = getattr(toolbox, tool_alias)
    tool(**params)


def main():
    configs = make_tests(toolbox_path)
    ts = [read_test(Path(c).read_text()) for c in configs]
    arcpy.AddMessage(pformat([t._asdict() for t in ts]))


if __name__ == "__main__":
    main()
