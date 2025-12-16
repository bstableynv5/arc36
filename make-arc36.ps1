Write-Host "==== Cloning standard environment ===="
conda create -n arc36-prod --clone arcgispro-py3
Write-Host
Write-Host "==== Activating ===="
conda activate arc36-prod
Write-Host
Write-Host "==== Adding packages from esri channel ===="
conda install -y -c esri geopandas,laspy,lazrs-python,rasterio,pyproj,fiona,scikit-learn
Write-Host
Write-Host "==== Adding packages from conda-forge channel ===="
conda install -y -c conda-forge ezdxf,polars,xlsxwriter,dask-geopandas,momepy
# conda install -y -c conda-forge scikit-learn,scikit-learn-intelex
Write-Host
Write-Host "==== Adding package from pip ===="
pip install scikit-learn-intelex,tbb4py,laszip