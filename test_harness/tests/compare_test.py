from pathlib import Path
from typing import Any

import arcpy
import geopandas as gp
import pandas as pd
import laspy
import numpy as np
import pyproj
import pytest
import rasterio as rio
from rasterio.transform import Affine
from shapely.geometry import Point

from compare import compare, compare_featureclass, compare_gdb, compare_hash

# file types to test
# text: txt, csv
# images: tiff
# las: las/laz
# shapefile: shp
# geodatabase: gdb (folder)
# excel: xlsx


def test_always_pass():
    assert True


def test_compare_hash_two_files(tmp_path: Path):
    file_a = tmp_path / "a.txt"
    file_a.write_text("some text")
    file_b = tmp_path / "b.txt"
    file_b.write_text("different text")

    assert compare_hash(file_a, file_a)
    assert not compare_hash(file_a, file_b)


def test_compare_hash_two_dirs(tmp_path: Path):
    dir_a = tmp_path / "a"
    dir_a.mkdir()
    (dir_a / "a.txt").write_text("some text")
    dir_a_sub = dir_a / "sub"
    dir_a_sub.mkdir()
    (dir_a_sub / "sub.txt").write_text("some text")

    dir_b = tmp_path / "b"
    dir_b.mkdir()
    (dir_b / "b.txt").write_text("some text")
    dir_b_sub = dir_b / "sub"
    dir_b_sub.mkdir()
    (dir_b_sub / "sub.txt").write_text("some other text")

    assert compare_hash(dir_a, dir_a)
    assert not compare_hash(dir_a, dir_b)


def test_compare_text_files(tmp_path: Path):
    # two text files with identical data
    file_a = tmp_path / "a.txt"
    file_a.write_text("some text")

    file_aa = tmp_path / "aa.txt"
    file_aa.write_text("some text")

    # different text file
    file_b = tmp_path / "b.txt"
    file_b.write_text("different text")

    assert compare(file_a, file_a)
    assert compare(file_a, file_aa)
    assert not compare(file_a, file_b)


def _write_tiff(p: Path, data: np.ndarray):
    res = 1  # degree per px
    nw_corner = (0, 0)  #  lon, lat
    offset = nw_corner[0] - res / 2, nw_corner[1] + res / 2
    transform = Affine.translation(*offset) * Affine.scale(res, -res)
    with rio.open(
        p,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=data.dtype,
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(data, 1)


def test_compare_tiff_files(tmp_path: Path):
    # 2 tifs with identical data
    file_a = tmp_path / "image_a.tiff"
    data_a = np.array([0, 1, 2, 3]).reshape((2, 2))
    _write_tiff(file_a, data_a)

    file_aa = tmp_path / "image_aa.tiff"
    _write_tiff(file_aa, data_a)

    # different tif
    file_b = tmp_path / "image_b.tiff"
    data_b = np.array([3, 2, 1, 0]).reshape((2, 2))
    _write_tiff(file_b, data_b)

    assert compare(file_a, file_a)
    assert compare(file_a, file_aa)
    assert not compare(file_a, file_b)


def _write_las(p: Path, data: np.ndarray):
    # 1. Create a new header
    header = laspy.LasHeader(point_format=6, version="1.4")
    header.offsets = np.min(data, axis=0)
    header.scales = np.array([0.1, 0.1, 0.1])
    header.add_crs(pyproj.CRS.from_epsg(4326))

    # 2. Create a Las
    las = laspy.LasData(header)
    las.x = data[:, 0]
    las.y = data[:, 1]
    las.z = data[:, 2]

    las.write(str(p))


def test_compare_las_files(tmp_path: Path):
    # 2 las with identical data
    file_a = tmp_path / "las_a.las"
    data_a = np.array([[0, 0, 0], [0, 0, 1], [0, 0, 2]])
    _write_las(file_a, data_a)

    file_aa = tmp_path / "las_aa.las"
    _write_las(file_aa, data_a)

    # different las
    file_b = tmp_path / "las_b.las"
    data_b = np.array([[0, 0, 1], [0, 0, 2], [0, 0, 3]])
    _write_las(file_b, data_b)

    assert compare(file_a, file_a)
    assert compare(file_a, file_aa)
    assert not compare(file_a, file_b)


def _write_3_shapefiles(tmp_path: Path) -> tuple[Path, Path, Path]:
    # 2 shapefiles that are the same
    file_a = tmp_path / "data_a.shp"
    data_a = {"A": [1, 2], "B": ["a", "b"], "geometry": [Point(0, 0), Point(0, 1)]}
    gp.GeoDataFrame(data_a, geometry="geometry", crs=4326).to_file(file_a)

    file_aa = tmp_path / "data_aa.shp"
    gp.GeoDataFrame(data_a, geometry="geometry", crs=4326).to_file(file_aa)

    # different shapefile
    file_b = tmp_path / "data_b.shp"
    data_b = {"A": [1, 2], "B": ["a", "b"], "geometry": [Point(0, 0), Point(1, 1)]}
    gp.GeoDataFrame(data_b, geometry="geometry", crs=4326).to_file(file_b)

    return (file_a, file_aa, file_b)


def test_compare_shapefile(tmp_path: Path):
    file_a, file_aa, file_b = _write_3_shapefiles(tmp_path)

    # make sure glob finds something. all() and any() behavior does not cause
    # failed test when no shp is made.
    assert len(list(file_a.parent.glob(file_a.with_suffix(".*").name))) > 0

    # shapefile compares with itself
    assert all(compare(a, a) for a in file_a.parent.glob(file_a.with_suffix(".*").name))

    # shapefiles with exact same data compare (ie timestamp or something doesn't trigger difference)
    assert all(
        compare(a, aa)
        for a, aa in zip(
            file_a.parent.glob(file_a.with_suffix(".*").name),
            file_aa.parent.glob(file_aa.with_suffix(".*").name),
        )
    )

    # different shapefiles do not compare
    assert any(
        not compare(a, b)
        for a, b in zip(
            file_a.parent.glob(file_a.with_suffix(".*").name),
            file_b.parent.glob(file_b.with_suffix(".*").name),
        )
    )


def _convert_shp_to_fc(*shapefiles: Path) -> list[Path]:
    # convert shp to gdb feature classes
    FC_NAME = "feature_class"
    gdb_fcs = []
    for shp in shapefiles:
        gdb = shp.with_suffix(".gdb")  # dir/data.shp -> dir/data.gdb
        arcpy.CreateFileGDB_management(str(gdb.parent), gdb.name)
        arcpy.FeatureClassToFeatureClass_conversion(str(shp), str(gdb), FC_NAME)
        gdb_fcs.append(gdb / FC_NAME)
    return gdb_fcs


def test_compare_geodatabase(tmp_path: Path):
    file_a, file_aa, file_b = _convert_shp_to_fc(*_write_3_shapefiles(tmp_path))

    assert compare(file_a.parent, file_a.parent)
    assert compare(file_a.parent, file_aa.parent)
    assert not compare(file_a.parent, file_b.parent)


def test_compare_specialization_featureclass(tmp_path: Path):
    file_a, file_aa, file_b = _convert_shp_to_fc(*_write_3_shapefiles(tmp_path))

    assert compare_featureclass(file_a, file_a)
    assert compare_featureclass(file_a, file_aa)
    assert not compare_featureclass(file_a, file_b)


def test_compare_specialization_geodatabase(tmp_path: Path):
    file_a, file_aa, file_b = _convert_shp_to_fc(*_write_3_shapefiles(tmp_path))

    assert compare_gdb(file_a.parent, file_a.parent)
    assert compare_gdb(file_a.parent, file_aa.parent)
    assert not compare_gdb(file_a.parent, file_b.parent)

    # add an additional feature class, which should make a and aa differ
    arcpy.CreateFeatureclass_management(str(file_aa.parent), "extra_fc", "POINT")
    assert not compare_gdb(file_a.parent, file_aa.parent)


def _write_xlsx(p: Path, data: dict[str, list[Any]]):
    df = pd.DataFrame(data)
    df.to_excel(p)


def test_compare_excel(tmp_path: Path):
    # 2 excel sheets with identical data
    file_a = tmp_path / "sheet_a.xlsx"
    data_a = {"A": [1, 2, 3], "B": ["x", "y", "z"]}
    _write_xlsx(file_a, data_a)

    file_aa = tmp_path / "sheet_aa.xlsx"
    _write_xlsx(file_aa, data_a)

    # 1 sheet with different data
    file_b = tmp_path / "sheet_b.xlsx"
    data_b = {"A": [0, 2, 3], "B": ["x", "y", "z"]}
    _write_xlsx(file_b, data_b)

    assert compare(file_a, file_a)
    assert compare(file_a, file_aa)
    assert not compare(file_a, file_b)
