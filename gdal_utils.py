import numpy as np
from osgeo import gdal


def format(filepath):
    dataset = gdal.Open(filepath, gdal.GA_ReadOnly)
    cols = dataset.RasterXSize
    rows = dataset.RasterYSize
    bands = dataset.RasterCount
    if bands == 0:
        return None
    band = dataset.GetRasterBand(1)
    bandtype = gdal.GetDataTypeName(band.DataType)

    return bands, bandtype, cols, rows


def byte_pixels_band1(filepath):
    dataset = gdal.Open(filepath, gdal.GA_ReadOnly)
    cols = dataset.RasterXSize
    rows = dataset.RasterYSize

    # to grayscale 8
    band = dataset.GetRasterBand(1)
    data = band.ReadAsArray(0, 0, cols, rows)
    min_ = np.min(data)
    max_ = np.max(data)
    data = band.ReadAsArray(0, 0, cols, rows)
    data = (255 - 0) * ((data - min_) / (max_ - min_))
    data = data.astype(np.uint8)
    return data
