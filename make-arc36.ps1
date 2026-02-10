Write-Host "==== Removing existing arc36-prod ===="
conda deactivate
conda env remove -y -n arc36-prod

Write-Host
Write-Host "==== Cloning standard environment ===="
# conda create -n arc36-prod --clone arcgispro-py3
conda create -n arc36-prod --clone C:\ArcGIS_360\ArcGIS\Pro\bin\Python\envs\arcgispro-py3
Write-Host
Write-Host "==== Activating ===="
conda activate arc36-prod
Write-Host
Write-Host "==== Adding packages from esri channel ===="
conda install -y -c esri geopandas,laspy,lazrs-python,rasterio,pyproj,fiona,scikit-learn,humanize,pyfakefs
Write-Host
Write-Host "==== Adding packages from conda-forge channel ===="
conda install -y -c conda-forge ezdxf,polars,xlsxwriter,dask-geopandas,momepy,tabulate,memory_profiler
# conda install -y -c conda-forge scikit-learn,scikit-learn-intelex
Write-Host
Write-Host "==== Adding packages from pip ===="
pip install laszip # scikit-learn-intelex tbb4py
Write-Host
Write-Host "==== Adding inhouse packages from pip ===="
pip install I:\test\ARC_PRO_CONDA\packages\pyvoronoi-1.2.7a0-cp313-cp313-win_amd64.whl
pip install I:\test\ARC_PRO_CONDA\packages\condorize-5.1.1a0-py3-none-any.whl