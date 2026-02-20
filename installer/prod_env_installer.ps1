<# 
 .SYNOPSIS
 Installs the "production python environment" for ArcGIS Pro.
 
 .DESCRIPTION
 This script does 3 things.
 1. Uses conda to create a new environment from a .yaml specification.
 2. Uses proswap to set this environment to the default for ArcGIS Pro.
 3. Removes old environment-related paths from USER's path and adds new ones.

 We want to set the paths so that "python" is available to users and that it's
 the one they're probably going to expect and want. For people with python2
 scripts, they'll have to update their own code. We also add env/Scripts to the
 path so commands from python programs (such as condorize) are available on
 any command line, which is what users are expecting. We have been advising
 folks to add env/Scripts to path recently, so this is making it "official".

 Note that on versions of ArcGIS Pro prior to v3.6, the ESRI-supplied
 "conda" may not have the "env" subcommand. Or it may have been jacked-up
 by ESRI. This installer script is intended for v3.6 and possibly above.

 PRECONDITIONS:
 1. ArcGISPro 3.6 is installed on the machine in the standard location.
 2. The user has access to the I: drive.
 3. An environment named $PROD_ENV does not already exist.

 POSTCONDITIONS:
 1. A new environment named $PROD_ENV is created.
 2. This environment is activated in Arc (set in Settings>PackageManager).
 3. The environment's python is the default "python" on the cmd line.
#>
# Set-StrictMode -Version Latest

$PROD_ENV = "arc36-prod-v1.0"
$PROD_ENV_YAML = "I:\test\ARC_PRO_CONDA\arc36_environment\$PROD_ENV.yaml"
$CONDA_EXE = "C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\conda.exe"
$CONDA_ACTIVATE = "C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\activate.bat"

# funcs for colored output
function BLUE([string]$str) {
    Write-Host "[96m" $str "[0m" # bright cyan
}
function GREEN([string]$str) {
    Write-Host "[32m" $str "[0m"
}
function RED([string]$str) {
    Write-Host "[31m" $str "[0m"
}

################################################################################
Write-Host
BLUE "(1) Installing $PROD_ENV environment into ArcGIS Pro."
Write-Host

& $CONDA_EXE env create -n $PROD_ENV -f $PROD_ENV_YAML
if (!$?) {
    RED "ERROR: Could not find ArcGIS Pro conda or could not create environment."
    RED "ERROR: Is ArcGIS Pro installed? Does an env named $PROD_ENV already exist?"
    Read-Host -Prompt "Press ENTER to close..."
    exit 1
}

################################################################################
# (2026-02-11) set the default env in arcgis for the user.
# using the "direct" method because proswap.bat also activates
# "python command line" with proenv.bat. this made my cmd line get "stuck"
# in the python command line.
Write-Host
BLUE "(2) Setting $PROD_ENV as your default environment in ArcGIS Pro."
Write-Host
& $CONDA_EXE proswap -q -n $PROD_ENV
# & $CONDA_ACTIVATE $PROD_ENV

################################################################################
Write-Host
BLUE "(3) Setting system paths."
Write-Host

function remove_from_path {
    # Removes paths starting with any string in `remove_list` from the PATH
    # for `scope`. Returns an array of the remaining paths.
    param(
        [string[]]$remove_list, 
        [string]$scope
    ) 
    # read and split PATH into array
    $original_path = [Environment]::GetEnvironmentVariable("Path", $scope)
    $original_paths = $original_path.Split(";")
    # filter and keep ok paths
    $keep_paths = @()
    foreach ($p in $original_paths) {
        $ok = $true
        foreach ($rm_path in $remove_list) {
            if ($p.StartsWith($rm_path)) {
                $ok = $false
                # Write-Host "Remove: " $p
            }
        }
        if ($ok) {
            $keep_paths += $p
        }
    }
    return $keep_paths
}
function set_paths {
    # Sets/Overwrites PATH for `scope` with all the paths in `paths`.
    param(
        [string[]]$paths, 
        [string]$scope
    )

    $final_string = $paths -join ";"
    [Environment]::SetEnvironmentVariable("Path", $final_string, $scope)
}

$remove_paths = @(
    "C:\Python27\ArcGIS", # eradicate this garbage
    "C:\Program Files\ArcGIS\Pro\bin\Python\Library\bin",
    "C:\Program Files\ArcGIS\Pro\bin\Python\Scripts",
    "C:\Program Files\ArcGIS\Pro\bin\Python\condabin",
    "$HOME\AppData\Local\ESRI\conda\envs" # will get any existing previous env path
)

$add_paths = @(
    "$HOME\AppData\Local\ESRI\conda\envs\$PROD_ENV", # for python.exe
    "$HOME\AppData\Local\ESRI\conda\envs\$PROD_ENV\Scripts", # for other python commands (condorize)
    "C:\Program Files\ArcGIS\Pro\bin\Python\Scripts", # for conda, etc
    "C:\Program Files\ArcGIS\Pro\bin\Python\Library\bin",
    "C:\Program Files\ArcGIS\Pro\bin\Python\condabin"
)

# 1. "func()" syntax concatenates all params into array, so can't use it here.
# 2. using strings for scope because the normal enums just refused to work.
$filtered_paths = remove_from_path -remove_list $remove_paths -scope "User"
set_paths -paths ($add_paths + $filtered_paths) -scope "User"
# gave up on machine paths. admin prompt can't access I:.
# $filtered_paths = remove_from_path -remove_list $remove_paths -scope "Machine"
# set_paths -paths ($add_paths + $filtered_paths) -scope "Machine"

################################################################################
# should see DONE if successful
Write-Host
GREEN "DONE"
Read-Host -Prompt "Please restart any open command prompts. Press ENTER to close..."

# NOTE: Digital signature will appear below. **Any** changes above,
# even whitespace, will invalidate the signature. Resign after any edit.
