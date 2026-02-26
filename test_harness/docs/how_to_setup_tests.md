# How to setup tool tests for ArcPro v3.1 ⇨ v3.6

## Overview

This portion of testing toolboxes for compatibility with ArcGIS Pro v3.6 is largely automated. The core idea is that the tool will be run in v3.1 and v3.6 with the same input data and parameters. The tool will be evaluated based on (1) did it run without a crash? (2) is the output data the same? If both are true, the tool passes. When a tool fails, the JTree team will investigate the cause, modify the tool, and retest. This process will repeat iteratively until all tools pass.

This automation requires that each tool has some configuration describing the input data, tool parameters, and expected outputs to be compared.

After preparing this configuration, you will not have to run

toolboxes: I:\test\ArcGISPro_VersionTesting\toolboxes\baseline
tests: I:\test\ArcGISPro_VersionTesting\tests

### Anatomy of a test

toolbox.tool.variant
inputs/
config .ini: toolbox.tool.variant.subtest

inputs:
think of this as a snapshot of all the things you need to run this particular tool
outputs:
what does the tool do that i really care about?

## Choosing good data

smallish but representative.
might be a subset of a "normal" dataset, for example 6 las files from 100. you might have to remake tile indexes or other ancillary inputs to match the subset.

## Essential workflow

### Prepare ArcGIS
1. Open ArcGIS Pro v3.1. You may want to create a new project to start fresh.
1. Add the toolboxes from `I:\test\ArcGISPro_VersionTesting\toolboxes\baseline` to your project's Catalog. You can drag-and-drop from the toolboxes folder or use Add Folder Connection in Catalog. This is the same as you'd do normally when using production toolboxes in ArcGIS, but they're already unzipped for you.
1. You'll need to see the tool's "alias", which is the tool's internal name that ArcGIS uses. The alias is used to refer to the tool in most subsequent steps.
    1. Right click on the tool and choose Properties.
    2. The alias is shown in the "Name" field of the Properties dialog.
    ![alias1](img/toolproperties_01.png)
    ![alias2](img/toolproperties_02.png)

### Gather input data
1. You will find each tool's test in a folder within `I:\test\ArcGISPro_VersionTesting\tests`. It will be named `toolbox.alias.default`. Within that folder will be 2 items: a folder named `inputs` and a .ini file with a name that matches the test folder.
1. Any input data (GDBs, shapefiles, las, tifs, txt, csv, xml, dxf, npy, ...) should be copied to `inputs`. You can organize files within `inputs` as you like.

### Setup tool parameters
1. When the data is setup in `inputs`, open the tool in ArcPro and adjust the tools parameters as if you were going to run it on the data in `inputs`.
2. Any newly created outputs files should _also_ be saved in the `inputs` folder.
3. 

![get_params](img/01_arc_tool_params_prjforlas.png)
![get_params](img/02_python_to_ini_prjforlas.png)
![get_params](img/03_param_tweaks_prjforlas.png)

## Advanced configurations

stuff about variants:
subtest ini .default -> .default.cfg1, .default.cfg2
folders .default -> .something

## Glossary

baseline: anything related to the prior version of ArcGIS
target: anything related to the new version of ArcGIS
toolbox: a collection of geoprocessing tools, usually contained in a folder with an atbx or tbx file, scripts, and other additional files.
tool: TODO a single item within a toolbox, usually corresponding to a script
test: a folder containing `inputs` and `toolbox.tool.default.ini` for an individual tool.
configuration file:
input:
outputs:
alias: a tool's internal name