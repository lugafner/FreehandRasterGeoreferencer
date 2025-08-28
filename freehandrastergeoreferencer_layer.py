"""
/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import math
import os

import numpy as np
from osgeo import gdal
from PyQt5.QtCore import (
    pyqtSignal,
    qDebug,
    QFileInfo,
    QPointF,
    QRectF,
    QSettings,
    QSize,
    Qt,
)
from PyQt5.QtGui import QColor, QImage, QImageReader, QPainter, QPen
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDataProvider,
    QgsMapLayerRenderer,
    QgsMessageLog,
    QgsPluginLayer,
    QgsPluginLayerType,
    QgsPointXY,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
)

from . import gdal_utils, utils
from .loaderrordialog import LoadErrorDialog


class LayerDefaultSettings:
    TRANSPARENCY = 30
    BLEND_MODE = "SourceOver"


class FreehandRasterGeoreferencerLayer(QgsPluginLayer):

    LAYER_TYPE = "FreehandRasterGeoreferencerLayer"
    transformParametersChanged = pyqtSignal(tuple)

    def __init__(self, plugin, filepath, title, screenExtent):
        QgsPluginLayer.__init__(
            self, FreehandRasterGeoreferencerLayer.LAYER_TYPE, title
        )
        self.plugin = plugin
        self.iface = plugin.iface

        self.title = title
        self.filepath = filepath
        self.screenExtent = screenExtent
        self.history = []
        # set custom properties
        self.setCustomProperty("title", title)
        self.setCustomProperty("filepath", self.filepath)

        self.setValid(True)

        self.setTransparency(LayerDefaultSettings.TRANSPARENCY)
        self.setBlendModeByName(LayerDefaultSettings.BLEND_MODE)

        # dummy data: real init is done in intializeLayer
        self.center = QgsPointXY(0, 0)
        self.rotation = 0.0
        self.xScale = 1.0
        self.yScale = 1.0

        self.error = False
        self.initializing = False
        self.initialized = False
        self.initializeLayer(screenExtent)
        self._extent = None

        self.provider = FreehandRasterGeoreferencerLayerProvider(self)

    def dataProvider(self):
        # issue with DBManager if the dataProvider of the QgsLayerPlugin
        # returns None
        return self.provider

    def setScale(self, xScale, yScale):
        self.xScale = xScale
        self.yScale = yScale

    def setRotation(self, rotation):
        # 3 decimals ought to be enough for everybody
        rotation = round(rotation, 3)
        # keep in -180,180 interval
        if rotation < -180:
            rotation += 360
        if rotation > 180:
            rotation -= 360
        self.rotation = rotation

    def setCenter(self, center):
        self.center = center

    def commitTransformParameters(self):
        QgsProject.instance().setDirty(True)
        self._extent = None
        self.setCustomProperty("xScale", self.xScale)
        self.setCustomProperty("yScale", self.yScale)
        self.setCustomProperty("rotation", self.rotation)
        self.setCustomProperty("xCenter", self.center.x())
        self.setCustomProperty("yCenter", self.center.y())
        self.transformParametersChanged.emit(
            (self.xScale, self.yScale, self.rotation, self.center)
        )

    def reprojectTransformParameters(self, oldCrs, newCrs):
        transform = QgsCoordinateTransform(oldCrs, newCrs, QgsProject.instance())

        newCenter = transform.transform(self.center)
        newExtent = transform.transform(self.extent())

        # transform the parameters except rotation
        # TODO rotation could be better handled (maybe check rotation between
        # old and new extent)
        # but not really worth the effort ?
        self.setCrs(newCrs)
        self.setCenter(newCenter)
        self.resetScale(newExtent.width(), newExtent.height())

    def resetTransformParametersToNewCrs(self):
        """
        Attempts to keep the layer on the same region of the map when
        the map CRS is changed
        """
        oldCrs = self.crs()
        newCrs = self.iface.mapCanvas().mapSettings().destinationCrs()
        self.reprojectTransformParameters(oldCrs, newCrs)
        self.commitTransformParameters()

    def setupCrsEvents(self):
        layerId = self.id()

        def removeCrsChangeHandler(layerIds):
            if layerId in layerIds:
                try:
                    self.iface.mapCanvas().destinationCrsChanged.disconnect(
                        self.resetTransformParametersToNewCrs
                    )
                except Exception:
                    pass
                try:
                    QgsProject.instance().disconnect(removeCrsChangeHandler)
                except Exception:
                    pass

        self.iface.mapCanvas().destinationCrsChanged.connect(
            self.resetTransformParametersToNewCrs
        )
        QgsProject.instance().layersRemoved.connect(removeCrsChangeHandler)

    def setupCrs(self):
        mapCrs = self.iface.mapCanvas().mapSettings().destinationCrs()
        self.setCrs(mapCrs)

        self.setupCrsEvents()

    def repaint(self):
        self.repaintRequested.emit()

    def transformParameters(self):
        return (self.center, self.rotation, self.xScale, self.yScale)

    def initializeLayer(self, screenExtent=None):
        if self.error or self.initialized or self.initializing:
            return

        if self.filepath is not None:
            # not safe...
            self.initializing = True
            absPath = self.getAbsoluteFilepath()

            if not os.path.exists(absPath):
                # TODO integrate with BadLayerHandler ?
                loadErrorDialog = LoadErrorDialog(absPath)
                result = loadErrorDialog.exec_()
                if result == 1:
                    # absolute
                    absPath = loadErrorDialog.lineEditImagePath.text()
                    # to relative if needed
                    self.filepath = utils.toRelativeToQGS(absPath)
                    self.setCustomProperty("filepath", self.filepath)
                    QgsProject.instance().setDirty(True)
                else:
                    self.error = True

                del loadErrorDialog

            imageFormat = utils.imageFormat(absPath)
            if imageFormat == "pdf":
                s = QSettings()
                oldValidation = s.value("/Projections/defaultBehavior")
                s.setValue(
                    "/Projections/defaultBehavior", "useGlobal"
                )  # for not asking about crs
                layer = QgsRasterLayer(absPath, os.path.basename(absPath))
                self.image = layer.previewAsImage(QSize(layer.width(), layer.height()))
                s.setValue("/Projections/defaultBehavior", oldValidation)
            else:
                has_corrected = False
                if imageFormat == "tif":
                    # other than TIFF => assumes can be loaded by Qt
                    has_corrected = self.preCheckImage(absPath)
                if has_corrected:
                    # image already loaded by preCheckImage
                    self.showBarMessage(
                        "Raster changed",
                        "Raster content has been transformed for display in the "
                        "plugin. "
                        "When exporting, select the 'Only export world file' checkbox.",
                        Qgis.Warning,
                        10,
                    )
                else:
                    reader = QImageReader(absPath)
                    self.image = reader.read()

            self.initialized = True
            self.initializing = False

            self.setupCrs()

            if screenExtent:
                # constructor called from AddLayer action
                # if not, layer loaded from QGS project file

                # check if image already has georef info
                # use GDAL
                dataset = gdal.Open(absPath, gdal.GA_ReadOnly)
                georef = None
                if dataset:
                    georef = dataset.GetGeoTransform()

                if georef and not self.is_default_geotransform(georef):
                    self.initializeExistingGeoreferencing(dataset, georef)
                else:
                    # init to default params
                    self.setCenter(screenExtent.center())
                    self.setRotation(0.0)

                    sw = screenExtent.width()
                    sh = screenExtent.height()

                    self.resetScale(sw, sh)

                    self.commitTransformParameters()

    def preCheckImage(self, filepath):
        nbands, datatype, width, height = gdal_utils.format(filepath)

        pixels = None
        if nbands not in (1, 3):
            pixels = gdal_utils.pixels(filepath)
            if nbands > 3:
                # first 3
                pixels = pixels[:3]
                nbands = 3

            if nbands == 2:
                # remove band 2
                pixels = pixels[0][np.newaxis, ...]
                nbands = 1

        if datatype != "Byte":
            pixels = pixels if pixels is not None else gdal_utils.pixels(filepath)

            bands = np.empty(np.shape(pixels), dtype=np.uint8)
            for i in range(nbands):
                band_pixels = pixels[i]
                bands[i] = gdal_utils.to_byte(band_pixels)
            pixels = bands

        if pixels is not None:
            # some transformation done# band at the end
            pixels = np.transpose(pixels, [1, 2, 0])
            pixels = pixels.ravel()

            if nbands == 1:
                # monochrome
                format = QImage.Format_Grayscale8
                bytesPerLine = width
            else:
                format = QImage.Format_RGB888
                bytesPerLine = 3 * width

            # Byte
            qImg = QImage(pixels, width, height, bytesPerLine, format)
            self.image = qImg

            return True

        return False

    def initializeExistingGeoreferencing(self, dataset, georef):
        # georef can have scaling, rotation or translation
        rotation = 180 / math.pi * -math.atan2(georef[4], georef[1])
        sx = math.sqrt(georef[1] ** 2 + georef[4] ** 2)
        sy = math.sqrt(georef[2] ** 2 + georef[5] ** 2)
        i_center_x = self.image.width() / 2
        i_center_y = self.image.height() / 2
        center = QgsPointXY(
            georef[0] + georef[1] * i_center_x + georef[2] * i_center_y,
            georef[3] + georef[4] * i_center_x + georef[5] * i_center_y,
        )

        qDebug(repr(rotation) + " " + repr((sx, sy)) + " " + repr(center))

        self.setRotation(rotation)
        self.setCenter(center)
        # keep yScale positive
        self.setScale(sx, sy)
        self.commitTransformParameters()

        crs_wkt = dataset.GetProjection()
        message_shown = False
        if crs_wkt:
            qcrs = QgsCoordinateReferenceSystem(crs_wkt)
            # TODO check change
            if qcrs.description() != self.crs().description():
                # reproject
                try:
                    self.reprojectTransformParameters(qcrs, self.crs())
                    self.commitTransformParameters()
                    self.showBarMessage(
                        "Transform parameters changed: ",
                        "Found existing georeferencing in raster but "
                        "its CRS does not match the CRS of the map. "
                        "Reprojected the extent.",
                        Qgis.Warning,
                        25,
                    )
                    message_shown = True
                except Exception as ex:
                    QgsMessageLog.logMessage(repr(ex))
                    self.showBarMessage(
                        "CRS does not match",
                        "Found existing georeferencing in raster but "
                        "its CRS does not match the CRS of the map. "
                        "Unable to reproject.",
                        Qgis.Warning,
                        5,
                    )
                    message_shown = True
        # if no projection info, assume it is the same CRS
        # as the map and no warning
        if not message_shown:
            self.showBarMessage(
                "Georeferencing loaded",
                "Found existing georeferencing in raster",
                Qgis.Info,
                3,
            )

        # zoom (assume the user wants to work on the image)
        self.iface.mapCanvas().setExtent(self.extent())

    def is_default_geotransform(self, georef):
        """
        Check if there is really a transform or if it is just the default
        made up by GDAL
        """
        return georef[0] == 0 and georef[3] == 0 and georef[1] == 1 and georef[5] == 1

    def resetScale(self, sw, sh):
        iw = self.image.width()
        ih = self.image.height()
        wratio = sw / iw
        hratio = sh / ih

        if wratio > hratio:
            # takes all height of current extent
            self.setScale(hratio, hratio)
        else:
            # all width
            self.setScale(wratio, wratio)

    def replaceImage(self, filepath, title):
        self.title = title
        self.filepath = filepath

        # set custom properties
        self.setCustomProperty("title", title)
        self.setCustomProperty("filepath", self.filepath)
        self.setName(title)

        fileInfo = QFileInfo(filepath)
        ext = fileInfo.suffix()
        if ext == "pdf":
            s = QSettings()
            oldValidation = s.value("/Projections/defaultBehavior")
            s.setValue(
                "/Projections/defaultBehavior", "useGlobal"
            )  # for not asking about crs
            path = fileInfo.filePath()
            baseName = fileInfo.baseName()
            layer = QgsRasterLayer(path, baseName)
            self.image = layer.previewAsImage(QSize(layer.width(), layer.height()))
            s.setValue("/Projections/defaultBehavior", oldValidation)
        else:
            reader = QImageReader(filepath)
            self.image = reader.read()
        self.repaint()

    def clone(self):
        layer = FreehandRasterGeoreferencerLayer(
            self.plugin, self.filepath, self.title, self.screenExtent
        )
        layer.center = self.center
        layer.rotation = self.rotation
        layer.xScale = self.xScale
        layer.yScale = self.yScale
        layer.commitTransformParameters()
        return layer

    def getAbsoluteFilepath(self):
        if not os.path.isabs(self.filepath):
            # relative to QGS file
            qgsPath = QgsProject.instance().fileName()
            qgsFolder, _ = os.path.split(qgsPath)
            filepath = os.path.join(qgsFolder, self.filepath)
        else:
            filepath = self.filepath

        return filepath

    def extent(self):
        self.initializeLayer()
        if not self.initialized:
            qDebug("Not Initialized")
            return QgsRectangle(0, 0, 1, 1)

        if self._extent:
            return self._extent

        topLeft, topRight, bottomRight, bottomLeft = self.cornerCoordinates()

        left = min(topLeft.x(), topRight.x(), bottomRight.x(), bottomLeft.x())
        right = max(topLeft.x(), topRight.x(), bottomRight.x(), bottomLeft.x())
        top = max(topLeft.y(), topRight.y(), bottomRight.y(), bottomLeft.y())
        bottom = min(topLeft.y(), topRight.y(), bottomRight.y(), bottomLeft.y())

        # recenter + create rectangle
        self._extent = QgsRectangle(left, bottom, right, top)
        return self._extent

    def cornerCoordinates(self):
        return self.transformedCornerCoordinates(
            self.center, self.rotation, self.xScale, self.yScale
        )

    def transformedCornerCoordinates(self, center, rotation, xScale, yScale):
        # scale
        topLeft = QgsPointXY(
            -self.image.width() / 2.0 * xScale, self.image.height() / 2.0 * yScale
        )
        topRight = QgsPointXY(
            self.image.width() / 2.0 * xScale, self.image.height() / 2.0 * yScale
        )
        bottomLeft = QgsPointXY(
            -self.image.width() / 2.0 * xScale, -self.image.height() / 2.0 * yScale
        )
        bottomRight = QgsPointXY(
            self.image.width() / 2.0 * xScale, -self.image.height() / 2.0 * yScale
        )

        # rotate
        # minus sign because rotation is CW in this class and Qt)
        rotationRad = -rotation * math.pi / 180
        cosRot = math.cos(rotationRad)
        sinRot = math.sin(rotationRad)

        topLeft = self._rotate(topLeft, cosRot, sinRot)
        topRight = self._rotate(topRight, cosRot, sinRot)
        bottomRight = self._rotate(bottomRight, cosRot, sinRot)
        bottomLeft = self._rotate(bottomLeft, cosRot, sinRot)

        topLeft.set(topLeft.x() + center.x(), topLeft.y() + center.y())
        topRight.set(topRight.x() + center.x(), topRight.y() + center.y())
        bottomRight.set(bottomRight.x() + center.x(), bottomRight.y() + center.y())
        bottomLeft.set(bottomLeft.x() + center.x(), bottomLeft.y() + center.y())

        return (topLeft, topRight, bottomRight, bottomLeft)

    def transformedCornerCoordinatesFromPoint(
        self, startPoint, rotation, xScale, yScale
    ):
        # startPoint is a fixed point for this new movement (rotation and
        # scale)
        # rotation is the global rotation of the image
        # xScale is the new xScale factor to be multiplied by self.xScale
        # idem for yScale
        # Calculate the coordinate of the center in a startPoint origin
        # coordinate system and apply scales
        dX = (self.center.x() - startPoint.x()) * xScale
        dY = (self.center.y() - startPoint.y()) * yScale
        # Half width and half height in the current transformation
        hW = (self.image.width() / 2.0) * self.xScale * xScale
        hH = (self.image.height() / 2.0) * self.yScale * yScale
        # Actual rectangle coordinates :
        pt1 = QgsPointXY(-hW, hH)
        pt2 = QgsPointXY(hW, hH)
        pt3 = QgsPointXY(hW, -hH)
        pt4 = QgsPointXY(-hW, -hH)
        # Actual rotation from the center
        # minus sign because rotation is CW in this class and Qt)
        rotationRad = -self.rotation * math.pi / 180
        cosRot = math.cos(rotationRad)
        sinRot = math.sin(rotationRad)
        pt1 = self._rotate(pt1, cosRot, sinRot)
        pt2 = self._rotate(pt2, cosRot, sinRot)
        pt3 = self._rotate(pt3, cosRot, sinRot)
        pt4 = self._rotate(pt4, cosRot, sinRot)
        # Second transformation
        # displacement of the origin
        pt1 = QgsPointXY(pt1.x() + dX, pt1.y() + dY)
        pt2 = QgsPointXY(pt2.x() + dX, pt2.y() + dY)
        pt3 = QgsPointXY(pt3.x() + dX, pt3.y() + dY)
        pt4 = QgsPointXY(pt4.x() + dX, pt4.y() + dY)
        # Rotation
        # minus sign because rotation is CW in this class and Qt)
        rotationRad = -rotation * math.pi / 180
        cosRot = math.cos(rotationRad)
        sinRot = math.sin(rotationRad)
        pt1 = self._rotate(pt1, cosRot, sinRot)
        pt2 = self._rotate(pt2, cosRot, sinRot)
        pt3 = self._rotate(pt3, cosRot, sinRot)
        pt4 = self._rotate(pt4, cosRot, sinRot)
        # translate to startPoint
        pt1 = QgsPointXY(pt1.x() + startPoint.x(), pt1.y() + startPoint.y())
        pt2 = QgsPointXY(pt2.x() + startPoint.x(), pt2.y() + startPoint.y())
        pt3 = QgsPointXY(pt3.x() + startPoint.x(), pt3.y() + startPoint.y())
        pt4 = QgsPointXY(pt4.x() + startPoint.x(), pt4.y() + startPoint.y())

        return (pt1, pt2, pt3, pt4)

    def moveCenterFromPointRotate(self, startPoint, rotation, xScale, yScale):
        cornerPoints = self.transformedCornerCoordinatesFromPoint(
            startPoint, rotation, xScale, yScale
        )
        self.center = QgsPointXY(
            (cornerPoints[0].x() + cornerPoints[2].x()) / 2,
            (cornerPoints[0].y() + cornerPoints[2].y()) / 2,
        )

    def _rotate(self, point, cosRot, sinRot):
        return QgsPointXY(
            point.x() * cosRot - point.y() * sinRot,
            point.x() * sinRot + point.y() * cosRot,
        )

    def createMapRenderer(self, rendererContext):
        return FreehandRasterGeoreferencerLayerRenderer(self, rendererContext)

    def setBlendModeByName(self, modeName):
        self.blendModeName = modeName
        blendMode = getattr(QPainter, "CompositionMode_" + modeName, 0)
        self.setBlendMode(blendMode)
        self.setCustomProperty("blendMode", modeName)

    def setTransparency(self, transparency):
        self.transparency = transparency
        self.setCustomProperty("transparency", transparency)

    def draw(self, renderContext):
        if renderContext.extent().isEmpty():
            qDebug("Drawing is skipped because map extent is empty.")
            return True

        self.initializeLayer()
        if not self.initialized:
            qDebug("Drawing is skipped because nothing to draw.")
            return True

        painter = renderContext.painter()
        painter.save()
        self.prepareStyle(painter)
        self.drawRaster(renderContext)
        painter.restore()

        return True

    def drawRaster(self, renderContext):
        painter = renderContext.painter()
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        self.map2pixel = renderContext.mapToPixel()

        scaleX = self.xScale / self.map2pixel.mapUnitsPerPixel()
        scaleY = self.yScale / self.map2pixel.mapUnitsPerPixel()

        rect = QRectF(
            QPointF(-self.image.width() / 2.0, -self.image.height() / 2.0),
            QPointF(self.image.width() / 2.0, self.image.height() / 2.0),
        )
        mapCenter = self.map2pixel.transform(self.center)

        # draw the image on the map canvas
        painter.translate(QPointF(mapCenter.x(), mapCenter.y()))
        painter.rotate(self.rotation)
        painter.scale(scaleX, scaleY)
        painter.drawImage(rect, self.image)

        painter.setOpacity(1.0)
        painter.setBrush(Qt.NoBrush)
        pen = QPen()
        pen.setColor(QColor(0, 0, 0))
        pen.setWidth(3)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawRect(rect)

    def prepareStyle(self, painter):
        painter.setOpacity(1.0 - self.transparency / 100.0)

    def readXml(self, node, context):
        self.readCustomProperties(node)
        self.title = self.customProperty("title", "")
        self.filepath = self.customProperty("filepath", "")
        self.xScale = float(self.customProperty("xScale", 1.0))
        self.yScale = float(self.customProperty("yScale", 1.0))
        self.rotation = float(self.customProperty("rotation", 0.0))
        xCenter = float(self.customProperty("xCenter", 0.0))
        yCenter = float(self.customProperty("yCenter", 0.0))
        self.center = QgsPointXY(xCenter, yCenter)
        self.setTransparency(
            int(self.customProperty("transparency", LayerDefaultSettings.TRANSPARENCY))
        )
        self.setBlendModeByName(
            self.customProperty("blendMode", LayerDefaultSettings.BLEND_MODE)
        )
        return True

    def writeXml(self, node, doc, context):
        element = node.toElement()
        self.writeCustomProperties(node, doc)
        element.setAttribute("type", "plugin")
        element.setAttribute("name", FreehandRasterGeoreferencerLayer.LAYER_TYPE)
        return True

    def metadata(self):
        lines = []
        fmt = "%s:\t%s"
        lines.append(fmt % (self.tr("Title"), self.title))
        filepath = self.getAbsoluteFilepath()
        filepath = os.path.normpath(filepath)
        lines.append(fmt % (self.tr("Path"), filepath))
        lines.append(fmt % (self.tr("Image Width"), str(self.image.width())))
        lines.append(fmt % (self.tr("Image Height"), str(self.image.height())))
        lines.append(fmt % (self.tr("Rotation (CW)"), str(self.rotation)))
        lines.append(fmt % (self.tr("X center"), str(self.center.x())))
        lines.append(fmt % (self.tr("Y center"), str(self.center.y())))
        lines.append(fmt % (self.tr("X scale"), str(self.xScale)))
        lines.append(fmt % (self.tr("Y scale"), str(self.yScale)))

        return "\n".join(lines)

    def log(self, msg):
        qDebug(msg)

    def dump(self, detail=False, bbox=None):
        pass

    def showStatusMessage(self, msg, timeout):
        self.iface.mainWindow().statusBar().showMessage(msg, timeout)

    def showBarMessage(self, title, text, level, duration):
        self.iface.messageBar().pushMessage(title, text, level, duration)

    def transparencyChanged(self, val):
        QgsProject.instance().setDirty(True)
        self.setTransparency(val)
        self.repaintRequested.emit()

    def setTransformContext(self, transformContext):
        pass


class FreehandRasterGeoreferencerLayerType(QgsPluginLayerType):
    def __init__(self, plugin):
        QgsPluginLayerType.__init__(self, FreehandRasterGeoreferencerLayer.LAYER_TYPE)
        self.plugin = plugin

    def createLayer(self):
        return FreehandRasterGeoreferencerLayer(self.plugin, None, "", None)

    def showLayerProperties(self, layer):
        from .propertiesdialog import PropertiesDialog

        dialog = PropertiesDialog(layer)
        dialog.horizontalSlider_Transparency.valueChanged.connect(
            layer.transparencyChanged
        )
        dialog.spinBox_Transparency.valueChanged.connect(layer.transparencyChanged)

        dialog.exec_()

        dialog.horizontalSlider_Transparency.valueChanged.disconnect(
            layer.transparencyChanged
        )
        dialog.spinBox_Transparency.valueChanged.disconnect(layer.transparencyChanged)
        return True


class FreehandRasterGeoreferencerLayerProvider(QgsDataProvider):
    def __init__(self, layer):
        QgsDataProvider.__init__(self, "dummyURI")
        self.layer = layer

    def name(self):
        # doesn't matter
        return "FreehandRasterGeoreferencerLayerProvider"
        
    def isValid(self):
        # return is valid true, if layer is valid
        # not necessary for functionality, but prevents a NotImplemented error
        return self.layer.isValid()


class FreehandRasterGeoreferencerLayerRenderer(QgsMapLayerRenderer):
    """
    Custom renderer: in QGIS3 no implementation is provided for
    QgsPluginLayers
    """

    def __init__(self, layer, rendererContext):
        QgsMapLayerRenderer.__init__(self, layer.id())
        self.layer = layer
        self.rendererContext = rendererContext

    def render(self):
        # same implementation as for QGIS2
        return self.layer.draw(self.rendererContext)
