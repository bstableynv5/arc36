pyfakefs??

# included in base env

1. scipy
1. networkx
1. pyarrow (for parquet support)
1. python-duckdb,1.4.3

# add from channel

## esri
1. geopandas,1.1.0
1. laspy,2.5.4
1. lazrs-python,0.6.2
1. rasterio,1.4.3
1. scikit-learn,1.6.1
1. pyproj,3.7.2
1. fiona,1.10.1
1. humanize,4.14.0
1. pyfakefs,6.0.0

## conda-forge
1. ezdxf,1.4.2
1. polars(what python version?),1.36.1
1. xlsxwriter,3.2.9
1. dask-geopandas,0.5.0
1. momepy,0.10.0
1. tabulate,0.9.0

## default
1. ~~tbb4py,2022.3.0 -- can't solve environment~~

## internal
1. pyvoronoi, >=1.2.6
1. condorize
1. ~~pyvoronly?~~

## pip?
1. laszip,0.2.4
1. ~~scikit-learn-intelex,2025.10.0 -- removes tbb4py~~
    - daal==2025.10.0
    - tbb==2022.3.0 -- update from 2022.0.0 in base env
    - tcmlib==1.4.1
1. ~~tbb4py==2022.3.0 -- added to match tbb==2022.3.0~~

# possible extras?
1. conda-forge::osmnx,2.0.7
1. conda-forge::memory_profiler(what python version?),0.61.0 -- project not maintained?

# don't need
1. pygeos -- it is part of shapely since 2.0 (2023)
