from pathlib import Path

import laspy
import numpy as np
import pyproj
import pytest
import rasterio as rio
from rasterio.transform import Affine

from compare import compare, compare_hash


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


# text: txt, csv
# images: tiff
# las: las/laz
# shapefile: shp
# geodatabase: gdb (folder)


def test_compare_text_files(tmp_path: Path):
    file_a = tmp_path / "a.txt"
    file_a.write_text("some text")
    file_b = tmp_path / "b.txt"
    file_b.write_text("different text")

    assert compare(file_a, file_a)
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
    file_a = tmp_path / "image_a.tiff"
    data_a = np.array([0, 1, 2, 3]).reshape((2, 2))
    _write_tiff(file_a, data_a)

    file_b = tmp_path / "image_b.tiff"
    data_b = np.array([3, 2, 1, 0]).reshape((2, 2))
    _write_tiff(file_b, data_b)

    assert compare(file_a, file_a)
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
    file_a = tmp_path / "las_a.las"
    data_a = np.array([[0, 0, 0], [0, 0, 1], [0, 0, 2]])
    _write_las(file_a, data_a)

    file_b = tmp_path / "las_b.las"
    data_b = np.array([[0, 0, 1], [0, 0, 2], [0, 0, 3]])
    _write_las(file_b, data_b)

    assert compare(file_a, file_a)
    assert not compare(file_a, file_b)
