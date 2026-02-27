"""
This gets each tool's actual display name. It only works on ATBX because
it reaches into the zip and grabs the information from the tool's rc file.
I made a quick-and-dirty atbx for the couple TBX files in the "baseline"
set of toolboxes.
"""

import json
from pathlib import Path
from zipfile import ZipFile

import pandas as pd


def scrape_data(toolbox_dir: Path) -> tuple[list[tuple[str, str, str, str]], list[str]]:
    data = []
    for tb in toolbox_dir.glob("*/*.atbx"):
        tb_name = tb.stem
        with ZipFile(tb) as zf:
            info = [
                (Path(n), json.loads(zf.open(n).read().decode('utf-8')))
                for n in zf.namelist()
                if Path(n).name == "tool.content.rc"
            ]
            clean = [
                (tb_name, m["map"]["title"], p.parent.stem, f"{tb_name}.{p.parent.stem.lower()}")
                for p, m in info
            ]
            data.extend(clean)
    return data, ["toolbox_name", "tool_display_name", "tool_alias", "test_name"]


def main():
    toolbox_dir = Path(r"I:\test\ArcGISPro_VersionTesting\toolboxes\baseline")
    outdir = Path("toolnames")
    outdir.mkdir(parents=True, exist_ok=True)

    data, cols = scrape_data(toolbox_dir)
    names = pd.DataFrame(data, columns=cols)
    names.sort_values(["toolbox_name", "tool_display_name"], inplace=True)

    names.to_csv(outdir / "data.csv", index=False)
    (outdir / "data.md").write_text(names.to_markdown(index=False))
    (outdir / "data.json").write_text(names.to_json(orient="split", index=False, indent=2))


if __name__ == "__main__":
    main()
