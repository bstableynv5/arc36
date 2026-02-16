# Arc 3.6

See [arc36-wishlist.md] for specific packages.

## Test machine

PDX-170 - has 3.2, could not connect to update server
PDX-184 - could not connect

per Rob Dolan
PDX-D-377 - has 3.1.2, could not connect to update server
PDX-D-336 - has 3.1.3, update available, could not update on our license

2025-12-08
336 has been updated to Arcpro 3.6 per rob rolan

## 2 Arcs 1 Machine

For testing we require both Arc 3.1 and 3.6 installed on the same machine. Getting Arc 3.6, running it, and creating python environments for it is easy, but there are some extra steps involved in getting `import arcpy` to operate in this weird setup.

1. Zip+copy Arc 3.6 from some machine.
2. Unzip it to another machine, such as `C:\ArcGIS_360`
3. Create new env using the prod env environment file. `conda env create -n arc36-prod -f arc36-prodv2.yaml`
4. Edit `C:\Users\USER\AppData\Local\ESRI\conda\envs\arc36-prod\Lib\site-packages\arcpy_init.py`. Insert `return Path(r"C:\ArcGIS_360\ArcGIS\Pro")` so `product_installer_dir()` always returns the path to Arc 3.6 instead of 3.1 or whatever is officially installed. This function searches various places, such as the registry, to find where Arc is installed. We're telling it directly.
    ```python
    def product_install_dir():
        """Returns the ArcGIS product installation directory as a pathlib.Path."""
        return Path(r"C:\ArcGIS_360\ArcGIS\Pro") # <- add this line
        install_dir = None # ignore this line and everything below it
    ```
5. You should now be able to import arcpy from `arc36-prod`.

## Observered issues in arc36
- `__file__` within atbx (eg validation code) refers to file inside atbx, not the atbx itself. Means we will need to update these to adjust the paths.