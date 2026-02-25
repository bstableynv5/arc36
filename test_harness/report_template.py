from datetime import datetime as dt
from itertools import groupby

from constants import PSEUDO_ISO_FMT

RUN_ROW_TEMPLATE = r"<TR><TD>{0}</TD><TD>{1}</TD><TD>{2}</TD></TR>"
TEST_ROW_TEMPLATE = r"<TR><TD>{0}</TD><TD>{1}</TD><TD>{2}</TD><TD>{3}</TD><TD data-result='{4}'>{4}</TD><TD data-result='{5}'>{5}</TD></TR>"

RUN_PASSED_ROW_TEMPLATE = r"<TR><TD>{0}</TD><TD>{1}</TD><TD>{2}</TD><TD>{3}</TD><TD>{4}</TD><TD data-result='{5}'></TD></TR>"
TEST_PASSED_ROW_TEMPLATE = r"<TR><TD>{0}</TD><TD>{1}</TD><TD data-result='{2}'></TD><TD data-result='{3}'></TD><TD data-result='{4}'></TD></TR>"

CSS = r"""
        /*  https://github.com/kevquirk/simple.css/blob/main/simple.css */
        /* Global variables. */
        :root{--sans-font:-apple-system,BlinkMacSystemFont,"Avenir Next",Avenir,"Nimbus Sans L",Roboto,"Noto Sans","Segoe UI",Arial,Helvetica,"Helvetica Neue",sans-serif;--serif-font:ui-serif,Georgia,Cambria,"Times New Roman",Times,serif;--mono-font:Consolas,Menlo,Monaco,"Andale Mono","Ubuntu Mono",monospace;--standard-border-radius:5px;--border-width:1px;--bg:#fff;--accent-bg:#f5f7ff;--text:#212121;--text-light:#585858;--border:#898EA4;--accent:#0d47a1;--accent-hover:#1266e2;--accent-text:var(--bg);--code:#d81b60;--preformatted:#444;--marked:#ffdd33;--disabled:#efefef}
        table{border-collapse:collapse;margin:1.5rem 0}
        figure>table{width:max-content;margin:0}
        td,th{border:var(--border-width) solid var(--border);text-align:start;padding:.5rem}
        th{background-color:var(--accent-bg);font-weight:700}
        tr:nth-child(2n){background-color:var(--accent-bg)}
        table caption{font-weight:700;margin-bottom:.5rem}
        body{font-family:var(--sans-font);margin:2em}
        td[data-result='PASS']{background-color:#98fb98}
        td[data-result='1']{background-color:#98fb98}
        td[data-result='1']:after{content:'PASS'}
        td[data-result='FAIL']{background-color:#ffb6c1}
        td[data-result='0']{background-color:#ffb6c1}
        td[data-result='0']:after{content:'FAIL'}
"""


def make_report_html(runs_passing: list[tuple], test_passing: list[tuple]) -> str:
    run_html = "\n".join(RUN_PASSED_ROW_TEMPLATE.format(*row) for row in runs_passing)
    test_html = ""
    for run_id, group in groupby(test_passing, lambda r: r[0]):
        test_html += f"<h3>Run {run_id}</h3><table><TR><TH>run id</TH><TH>test id</TH><TH>execution</TH><TH>comparison</TH><TH>overall</TH></TR>"
        test_html += "\n".join(TEST_PASSED_ROW_TEMPLATE.format(*row) for row in group)
        test_html += "\n</table>"

    return rf"""<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Results</title>

    <style>
        {CSS}
    </style>
</head>

<body>
    <h1>Test Results</h1>
    <p>generated: {dt.now():{PSEUDO_ISO_FMT}}</p>

    <h2>Runs</h2>
    <table>
        <TR>
            <TH>run id</TH>
            <TH>start</TH>
            <TH>end</TH>
            <TH>tests run</TH>
            <TH>passed</TH>
            <TH>overall</TH>
        </TR>
        {run_html}
    </table>

    <h2>Run Details</h2>
    {test_html}

</body>
</html>"""
