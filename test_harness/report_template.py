RUN_ROW_TEMPLATE = r"<TR><TD>{0}</TD><TD>{1}</TD><TD>{2}</TD></TR>"
TEST_ROW_TEMPLATE = r"<TR><TD>{0}</TD><TD>{1}</TD><TD>{2}</TD><TD>{3}</TD><TD data-result='{4}'>{4}</TD><TD data-result='{5}'>{5}</TD></TR>"


def make_report_html(run_rows: list[tuple], test_rows: list[tuple]) -> str:
    run_html = "\n".join(RUN_ROW_TEMPLATE.format(*row) for row in run_rows)
    test_html = "\n".join(TEST_ROW_TEMPLATE.format(*row) for row in test_rows)

    part1 = r"""<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Results</title>

    <style>
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
        td[data-result=PASS]{background-color:#98fb98}
        td[data-result=FAIL]{background-color:#ffb6c1}
    </style>
</head>

<body>
    <h1>Test Results</h1>
    <h2>Runs</h2>
    <table>
        <TR>
            <TH>id</TH>
            <TH>start</TH>
            <TH>end</TH>
        </TR>"""

    part2 = r"""</table>

    <h2>Test Instances</h2>
    <table>
        <TR>
            <TH>run_id</TH>
            <TH>env</TH>
            <TH>id</TH>
            <TH>status</TH>
            <TH>run_result</TH>
            <TH>compare_result</TH>
        </TR>"""

    part3 = r"""</table>
</body>
</html>"""
    return "\n".join([part1, run_html, part2, test_html, part3])
