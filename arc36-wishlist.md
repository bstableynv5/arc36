included
--------
scipy
networkx
pyarrow (for parquet support)


esri
----
geopandas,1.1.0
laspy,2.5.4
lazrs-python,0.6.2
rasterio,1.4.3
scikit-learn,1.6.1
pyproj,3.7.2
fiona,1.10.1


conda-forge
-----------
scikit-learn-intelex(py313),2025.10.0 -- can't solve environment?
ezdxf,1.4.2
polars(what python version?),1.36.1
xlsxwriter,3.2.9

default
-------
~~scikit-learn-intelex(py311),2023.1.1~~

internal
--------
pyvoronly
condorize


possible extras?
----------------
conda-forge::python-duckdb,1.4.3
conda-forge::memory_profiler(what python version?),0.61.0 -- project not maintained

don't need
----------
pygeos -- it is part of shapely since 2.0 (2023)

pip?
----
laszip
scikit-learn-intelex