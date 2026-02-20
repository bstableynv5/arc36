# ArcGIS Pro 3.6 PDX Python Production Environment

## Purpose

The "production environment" (aka prod-env) is a customized version of the base ArcGIS Pro python environment. It contains additional packages that are used in the PDX production tools. ArcGIS Pro uses [conda](https://docs.conda.io/en/latest/) to manage its python environment and packages.

## Installation

1. Goto `I:\test\ARC_PRO_CONDA\arc36_environment\`. Right click on `prod_env_installer.ps1` and select "Run with powershell". The exact menu item may look different depending on Windows 10 or 11.
    
    ![win10](./img/run_with_powershell_win10.png)
    ![win11](./img/run_with_powershell_win11.png)

    A console window will appear and you may see 2 security related confirmation prompts.
    - For _Execution Policy Change_, enter **N** or press Enter.
    - For _Security warning_, enter **R**.

    ![security](./img/security_warnings.png)

    Then the installation script will run and you will see a console like this:
    ![normal_install](./img/normal.png)

2. The installer will **automatically activate** the production environment as the default active environment within ArcGIS Pro. You can confirm by going to _Settings > Package Manager_ within ArcGIS. If the production environment is not active, you can activate it by selecting it from the drop-down on the right.
![package_manager](./img/arc_package_manager.png)
