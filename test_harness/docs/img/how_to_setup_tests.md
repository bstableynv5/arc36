# How to setup tool tests for ArcPro v3.1 ⇨ v3.6

## Overview

This portion of testing toolboxes for compatibility with ArcGIS Pro v3.6 is largely automated. The core idea is that the tool will be run in v3.1 and v3.6 with the same input data and parameters. The tool will be evaluated based on (1) did it run without a crash? (2) is the output data the same? If both are true, the tool passes. When a tool fails, the JTree team will investigate the cause, modify the tool, and retest. This process will repeat iteratively until all tools pass.

This automation requires that each tool has some configuration describing the input data, tool parameters, and expected outputs to be compared.