# How to setup tool tests for ArcPro v3.1 ⇨ v3.6 <span style='font-size:0.7rem;float:right'>version 1</span>

## Overview

This portion of testing toolboxes for compatibility with ArcGIS Pro v3.6 is largely automated. The core idea is that the tool will be run in v3.1 and v3.6 with the same input data and parameters. The tool will be evaluated based on (1) did it run without a crash? (2) is the output data the same? If both are true, the tool passes. When a tool fails, the JTree team will investigate the cause, modify the tool, and retest. This process will repeat iteratively until all tools pass.

This automation requires that each tool has some configuration describing the input data, tool parameters, and expected outputs to be compared.

!!! success ""
    Your task, as the expert in the tool's usual operation and data, is to prepare this input and configuration. You will not be required to run the tools over and over as JTree addresses issues.

#### Summary

For each tool you will help setup for testing...

1. [add input data](#gather-input-data)
2. [configure the tool parameters](#setup-tool-test-configuration).

#### Important folders

| Name | Path |
| ---  | --- |
| toolboxes | I:\test\ArcGISPro_VersionTesting\toolboxes\baseline |
| tool test folders | I:\test\ArcGISPro_VersionTesting\tests |


### Anatomy of a test

Each tool test is a folder containing a _configuration file_ and _input data_.

![test_folder](img/test_folder_01_annotated.png)

The **test folder** will be named according to the scheme `toolbox_name.tool_alias.variant`. For example `htcondor_tools.blast2demrasters.default`. The _variant_ portion will be `default` for all initial test folders. The purpose of a _variant_ is when you want to test the same tool multiple times _with different input data_.

Within the folder is a **configuration file** (refered to as "config .ini"). This file will be named the same as the test folder, for example `htcondor_tools.blast2demrasters.default.ini`. You can create multiple configuration files in the same test folder if you want to run the same tool multiple times _on the same input data_ with different non-data parameters. This is a _subtest_.

See [Advanced configurations](#advanced-configurations) for more information about setting up test variants and subtests.

The other item in a test folder is an **empty folder named `inputs`**. This will contain [all the data required](#choosing-good-data) for the tool to run. It is also where the tool should save any new output files. When the tool is run in the automated test program, its whole world should be contained within the `inputs` folder.


### What happens with a test is run?

JTree will use a testing program to schedule all the tests to be run as a batch in both ArcGIS Pro v3.1 and v3.6. For each test, the _entire_ `inputs` folder is copied to a temporary working folder, the tool is run using the parameters supplied in the config .ini, and the outputs listed in the config .ini are copied to a fresh permanent folder. When both versions of ArcGIS Pro have finished, the listed outputs of both versions will be compared to ensure their data contents are the same. Finally, a report will be generated summarizing what tests passed and failed.

This mechanism allows each tool test to be completely independent of others. It also preserves the input data across multiple runs since the contents of `inputs` is not operated on directly.


## Choosing good data

Good testing data is smallish but representative. The goal is to "exercise" the tool in the way it's most commonly used.

This might be a subset of a "normal" dataset you'd use in production. For example 4 las files from 100. Or perhaps a smaller circuit with a mix of different threat detections. When choosing a subset, it's a good idea to choose adjacent or contiguous pieces.

You might have to remake tile indexes, clipping shapes, or other ancillary inputs to match the subset. That will depend on the tool, as some tools can tolerate "missing" data and others cannot. It's ok if a tool produces a yellow warning when it runs, but the data chosen should allow the tool to run to completion without red error messages (or crashes!).

That data should be copied to the `inputs` folder, and then _not modified_.


## Essential workflow

### Prepare ArcGIS

1. Open ArcGIS Pro v3.1. You may want to create a new project to start fresh.

1. Add the toolboxes from `I:\test\ArcGISPro_VersionTesting\toolboxes\baseline` to your project's Catalog. 

    You can drag-and-drop toolbox folders from the `baseline` folder or use Add Folder Connection in Catalog. This is the same as you'd do normally when using production toolboxes in ArcGIS, but they're already unzipped into their home. You don't need to copy them to your workstation.

    ![folder_conn](img/add_folder_connection.png)

<!--
1. You'll need to see the tool's "alias", which is the tool's internal name that ArcGIS uses. The alias is used to refer to the tool in most subsequent steps.
    1. Right click on the tool and choose Properties.
    2. The alias is shown in the "Name" field of the Properties dialog.

    ![alias1](img/toolproperties_01.png)
    ![alias2](img/toolproperties_02.png)
-->

### Gather input data

1. You will find each [tool's test in a folder](#anatomy-of-a-test) within `I:\test\ArcGISPro_VersionTesting\tests`. It will be named like `toolbox_name.tool_alias.default`. Within that folder will be 2 items: a folder named `inputs` and a config .ini file with a name that matches the test folder.

    ![test_folder](img/test_folder_01_annotated.png)

    !!! tip
        [Tools/Tests index](tool_test_names.md) contains a table of toolboxes, tool display names, and the test folder name.

1. Any input data (GDBs, shapefiles, las, tifs, txt, csv, xml, dxf, npy, ...) should be copied to `inputs`. You can organize files within `inputs` as you like.

    !!! success ""
        Think of `inputs` as a snapshot of all the things you need to run this particular tool _just_ before you press the Run button.

    ![inputs_folder](img/test_folder_02.png)
    ![inputs_folder](img/test_folder_02a.png)


### Setup tool test configuration

1. Open the config .ini file for the test. Notepad++ has colored text for .ini, but any text editor will work.

#### [test] section

1. If the tool input data **must** exist on the I: (notably, for condor tools), then change `run_local` from its default of `false` to `true`.

1. You can optionally add a short `description` about this specific tool test setup.

    ![config_test_section](img/03_param_tweaks_blast2dem_testsection_annotated.png)

#### [parameters] section

1. When the data is setup in `inputs`, open the tool in ArcPro and adjust the tool's parameters as if you were going to run it on the data in `inputs`.

    !!! info
        If you _do_ want to run the tool once to make sure the parameters are correct, please make a **temporary copy** of `inputs` and use that to avoid accidently modifying anything in `inputs`.

    ![get_params](img/01_arc_tool_params_blast2dem_annotated.png)

1. Any newly created outputs files should _also_ be saved to the `inputs` folder.

    ![get_params](img/01_arc_tool_params_blast2dem_outputfolder.png)

1. Click the ⌄ menu on the Run button and choose _Copy Python Command_ from the menu. This will place a small amount of python code in your clipboard.
    
    ![get_params](img/01a_arc_tool_params_blast2dem.png)

1. Paste this into a blank Notepad++ or somewhere else temporarily.

    You'll notice that the text from _Copy Python Command_ has a list of parameters for the tool that match the list in the `[parameters]` section of the config .ini.

    ![get_params](img/02_python_to_ini_blast2dem_vsplit_annotated.png)

    !!! tip
        The comments in config .ini above each parameter show the parameter's display name in ArcGIS and its type.

1. Copy the parameter values from the python code into the matching item in the config .ini.

    1. Don't include any `r` prefix on the parameter values from the python code.
    1. You may include the quotes ( " or ' ) around the parameter values from the python code, though it's ideal to remove them and copy only the value.
    1. The config .ini will start filled with the tool's default values, if present. Don't forget to change these if you modified the default parameters when setting up the tool in ArcGIS.
    1. Any of the files from `inputs` should be shortened to start with `inputs\`. For example, `I:\test\ArcGISPro_VersionTesting\tests\htcondor_tools.blast2demrasters.default\inputs\tileindex.gdb\tileindex` would become `inputs\tileindex.gdb\tileindex`.
    1. Parameters with values `None`, `""`, or `"#"` in the python can be ignored and left blank in the config .ini.

    ![get_params](img/02_python_to_ini_blast2dem_vsplit_a_annotated.png)
    ![get_params](img/03_param_tweaks_blast2dem_annotated.png)



#### [outputs] section

1. Any newly created output files or modified inputs that are important must be listed one per line . Format the lines as you did for parameters.

    !!! success ""
        What does the tool do that I really care about?

    1. If the item is something in a Geodatabase (eg feature class), list only the geodatabase. For example: `inputs\outputdata.gdb` instead of `inputs\outputdata.gdb\output_polygons`.
    1. If the item is something that is a "file" comprised of multiple files, you'll have to list them all. **Shapefile** is the most common culprit.
    1. You may list folders (see example in image).
    1. If a tool produces some extra files that really aren't important, you can omit those.
    1. If the tool doesn't produce anything or modify anything, this section can be left empty.

    ![config_outputs_section](img/04_outputs_blast2dem_annotated.png)

!!! success
    That's it!   Don't forget to save your changes to the config .ini. 😊

### Tools that run in sequence

Some tools are meant to run in sequence as part of a workflow, and they often modify one or more feature classes at each step. When setting up these tools, you may want to start with a single smallish test input dataset for the first tool of the series in some separate temporary working folder. Make a copy of this working folder for `inputs` just before you're ready to press the Run button in ArcGIS. The contents of each tool's `inputs` should be a snapshot at that point in the sequence.

## Advanced configurations

As alluded to in [Anatomy of a test](#anatomy-of-a-test), the same tool can be tested multiple times with:

1. Different input data -- a test _variant_.
2. The same input data but different parameters -- a test _subtest_.

The test folder name and config .ini file within it have a particular name schema that identifies the tool test. The folder and file names contain 3+ parts separated by `.` (period). The first two parts identify the toolbox and tool, respectively. The third part identifies the test _variant_ and an optional fourth parts identifies a _subtest_.

![folder_breakdown](img/test_id_name_breakdown_folder.png)
![config_breakdown](img/test_id_name_breakdown_config.png)

All the tests are given a variant ID of `default` and no subtests when an empty template is created. You can use this unless you want to create additional variants or subtests.

The recommended way of **creating a new variant** is to make a copy of one of the tool's test folders (such as `default`), then rename the variant portion of _both_ the folder and config .ini filenames, and setup test inputs and parameters as normal.

The recommended way of **creating a new subtest** is to configure the config .ini for a test first. Then copy the config .ini, rename the subtest portion of the copy's filename, and modify its parameters as necessary.

!!! note
    When naming variants and subtests, please choose lowercase letters and numbers. An underscore can be used, but no other punctuation or other special characters please.

Using the `htcondor_tools.blast2demrasters` example again, a new variant was created in `htcondor_tools.blast2demrasters.grounds`. The las input for `default` has thinned mkps instead of true grounds, so a bare earth and slope rasters cannot be run on it. The las for the `grounds` variant has grounds (and is from a different project). In addition, the `grounds` test variant has 3 subtests: `bareearth`, `highesthit`, and `slope`.

![grounds_folder](img/test_folder_02_variant_subtests_a.png)
![grounds_catalog](img/test_folder_02_variant_subtests_b.png)

The 3 config .ini files with differences highlighted are shown below. `inputs\raster` was used as to save the output rasters in these 3 subtests, but it would also possible for each subtests to save outputs to separate folders (ex `inputs\out_be` and `inputs\slope`). However, when run each subtest gets its own copy of the entire `inputs` folder, so this isn't necessary.

![grounds_subtests](img/subtests_sidebyside_annotated.png)


## Known limitations

- The automated test running system can only accept Feature Classes, not Feature _Layers_. As such, tools that **require** a selection of features will not work.


## Examples

Fully setup examples can be found in the following test folders:

- I:\test\ArcGISPro_VersionTesting\tests\htcondor_tools.blast2demrasters.default
- I:\test\ArcGISPro_VersionTesting\tests\htcondor_tools.blast2demrasters.grounds
- I:\test\ArcGISPro_VersionTesting\tests\nv5_toolbox.prjforlas.default


## Glossary

| term | detail |
| ---  | --- |
| baseline | anything related to the _current_ version of ArcGIS. |
| target | anything related to the _new_ version of ArcGIS. |
| toolbox | a collection of geoprocessing tools, usually contained in a folder with an atbx or tbx file, scripts, and other additional files. |
| tool | a single item within a toolbox, usually corresponding to a script. |
| alias | a tool's internal name |
| test | a folder containing an `inputs` folder and config .ini file (`toolbox.tool.default.ini`) for an individual tool. | |
| configuration file | aka config .ini, is a text file specifying vital information for a tool test such as parameter values and expected outputs. |
| variant | a test with a set of input data. Different variants for the same tool test have different input data. |
| subtest | multiple test configuration files for the same input data but different parameters |
| inputs | data files required to run a tool |
| outputs | data files produced or modified by a tool |

## Questions?

If you have questions, please message **Ben Stabley** on the JTree team.

Thank you