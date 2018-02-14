# -*- coding: utf-8 -*-
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

import os.path

from PyQt4.QtCore import QObject, SIGNAL
from PyQt4.QtGui import QAction, QIcon
from qgis.core import QgsMapLayerRegistry, QgsPluginLayerRegistry, QgsMapLayer

from freehandrastergeoreferencer_commands import ExportAsRasterCommand
from freehandrastergeoreferencer_layer import \
    FreehandRasterGeoreferencerLayerType, FreehandRasterGeoreferencerLayer
from freehandrastergeoreferencer_maptools import MoveRasterMapTool,\
    RotateRasterMapTool, ScaleRasterMapTool, AdjustRasterMapTool
from freehandrastergeoreferencerdialog import FreehandRasterGeoreferencerDialog
import utils


class FreehandRasterGeoreferencer(object):

    PLUGIN_MENU = u"&Freehand Raster Georeferencer"

    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        self.layers = {}
        QObject.connect(QgsMapLayerRegistry.instance(), SIGNAL(
            "layerRemoved(QString)"), self.layerRemoved)
        # new pyqt4 connection style: old style (like above) does not work...
        self.iface.legendInterface().currentLayerChanged.connect(
            self.currentLayerChanged)

    def initGui(self):
        # Create actions
        self.actionAddLayer = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconAdd.png"),
            u"Add raster for interactive georeferencing",
            self.iface.mainWindow())
        self.actionAddLayer.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_AddLayer")
        self.actionAddLayer.triggered.connect(self.addLayer)

        self.actionMoveRaster = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconMove.png"),
            u"Move raster",
            self.iface.mainWindow())
        self.actionMoveRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_MoveRaster")
        self.actionMoveRaster.triggered.connect(self.moveRaster)
        self.actionMoveRaster.setCheckable(True)

        self.actionRotateRaster = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconRotate.png"),
            u"Rotate raster", self.iface.mainWindow())
        self.actionRotateRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_RotateRaster")
        self.actionRotateRaster.triggered.connect(self.rotateRaster)
        self.actionRotateRaster.setCheckable(True)

        self.actionScaleRaster = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconScale.png"),
            u"Scale raster", self.iface.mainWindow())
        self.actionScaleRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_ScaleRaster")
        self.actionScaleRaster.triggered.connect(self.scaleRaster)
        self.actionScaleRaster.setCheckable(True)

        self.actionAdjustRaster = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconAdjust.png"),
            u"Adjust sides of raster", self.iface.mainWindow())
        self.actionAdjustRaster.setObjectName(
            "FreehandRasterGeoreferencingLayerPlugin_AdjustRaster")
        self.actionAdjustRaster.triggered.connect(self.adjustRaster)
        self.actionAdjustRaster.setCheckable(True)

        self.actionIncreaseTransparency = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/"
                  "iconTransparencyIncrease.png"),
            u"Increase transparency", self.iface.mainWindow())
        self.actionIncreaseTransparency.triggered.connect(
            self.increaseTransparency)
        self.actionIncreaseTransparency.setShortcut("Alt+Ctrl+N")

        self.actionDecreaseTransparency = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/"
                  "iconTransparencyDecrease.png"),
            u"Decrease transparency", self.iface.mainWindow())
        self.actionDecreaseTransparency.triggered.connect(
            self.decreaseTransparency)
        self.actionDecreaseTransparency.setShortcut("Alt+Ctrl+B")

        self.actionExport = QAction(
            QIcon(":/plugins/freehandrastergeoreferencer/iconExport.png"),
            u"Export raster with world file", self.iface.mainWindow())
        self.actionExport.triggered.connect(self.exportAsRaster)

        # Add toolbar button and menu item for AddLayer
        self.iface.layerToolBar().addAction(self.actionAddLayer)
        self.iface.insertAddLayerAction(self.actionAddLayer)
        self.iface.addPluginToMenu(
            FreehandRasterGeoreferencer.PLUGIN_MENU, self.actionAddLayer)

        # create toolbar for this plugin
        self.toolbar = self.iface.addToolBar("Freehand raster georeferencing")
        self.toolbar.addAction(self.actionAddLayer)
        self.toolbar.addAction(self.actionMoveRaster)
        self.toolbar.addAction(self.actionRotateRaster)
        self.toolbar.addAction(self.actionScaleRaster)
        self.toolbar.addAction(self.actionAdjustRaster)
        self.toolbar.addAction(self.actionDecreaseTransparency)
        self.toolbar.addAction(self.actionIncreaseTransparency)
        self.toolbar.addAction(self.actionExport)

        # Register plugin layer type
        self.layerType = FreehandRasterGeoreferencerLayerType(self)
        QgsPluginLayerRegistry.instance().addPluginLayerType(self.layerType)

        self.dialogAddLayer = FreehandRasterGeoreferencerDialog()

        self.moveTool = MoveRasterMapTool(self.iface)
        self.moveTool.setAction(self.actionMoveRaster)
        self.rotateTool = RotateRasterMapTool(self.iface)
        self.rotateTool.setAction(self.actionRotateRaster)
        self.scaleTool = ScaleRasterMapTool(self.iface)
        self.scaleTool.setAction(self.actionScaleRaster)
        self.adjustTool = AdjustRasterMapTool(self.iface)
        self.adjustTool.setAction(self.actionAdjustRaster)
        self.currentTool = None

        # default state for toolbar
        self.checkCurrentLayerIsPluginLayer()

    def unload(self):
        # Remove the plugin menu item and icon
        self.iface.layerToolBar().removeAction(self.actionAddLayer)
        self.iface.removeAddLayerAction(self.actionAddLayer)
        self.iface.removePluginMenu(
            FreehandRasterGeoreferencer.PLUGIN_MENU, self.actionAddLayer)

        # Unregister plugin layer type
        QgsPluginLayerRegistry.instance().removePluginLayerType(
            FreehandRasterGeoreferencerLayer.LAYER_TYPE)

        QObject.disconnect(QgsMapLayerRegistry.instance(), SIGNAL(
            "layerRemoved(QString)"), self.layerRemoved)
        self.iface.legendInterface().currentLayerChanged.disconnect(
            self.currentLayerChanged)

        del self.toolbar

    def layerRemoved(self, layerId):
        if layerId in self.layers:
            del self.layers[layerId]
            self.checkCurrentLayerIsPluginLayer()

    def currentLayerChanged(self, layer):
        self.checkCurrentLayerIsPluginLayer()

    def checkCurrentLayerIsPluginLayer(self):
        layer = self.iface.legendInterface().currentLayer()
        if (layer and
            layer.type() == QgsMapLayer.PluginLayer and
                layer.pluginLayerType() ==
                FreehandRasterGeoreferencerLayer.LAYER_TYPE):
            self.actionMoveRaster.setEnabled(True)
            self.actionRotateRaster.setEnabled(True)
            self.actionScaleRaster.setEnabled(True)
            self.actionAdjustRaster.setEnabled(True)
            self.actionDecreaseTransparency.setEnabled(True)
            self.actionIncreaseTransparency.setEnabled(True)
            self.actionExport.setEnabled(True)

            if self.currentTool:
                self.currentTool.reset()
                self.currentTool.setLayer(layer)
        else:
            self.actionMoveRaster.setEnabled(False)
            self.actionRotateRaster.setEnabled(False)
            self.actionScaleRaster.setEnabled(False)
            self.actionAdjustRaster.setEnabled(False)
            self.actionDecreaseTransparency.setEnabled(False)
            self.actionIncreaseTransparency.setEnabled(False)
            self.actionExport.setEnabled(False)

            if self.currentTool:
                self.currentTool.reset()
                self.currentTool.setLayer(None)
                self.iface.mapCanvas().unsetMapTool(self.currentTool)
                self.iface.actionPan().trigger()
                self.currentTool = None

    def addLayer(self):
        self.dialogAddLayer.clear()
        self.dialogAddLayer.show()
        result = self.dialogAddLayer.exec_()
        if result == 1:
            self.createFreehandRasterGeoreferencerLayer()

    def createFreehandRasterGeoreferencerLayer(self):
        imagePath = self.dialogAddLayer.lineEditImagePath.text()
        imagePath = utils.toRelativeToQGS(imagePath)

        imageName = os.path.basename(imagePath)
        imageName, _ = os.path.splitext(imageName)

        screenExtent = self.iface.mapCanvas().extent()

        layer = FreehandRasterGeoreferencerLayer(
            self, imagePath, imageName, screenExtent)
        if layer.isValid():
            QgsMapLayerRegistry.instance().addMapLayer(layer)
            self.layers[layer.id()] = layer
            self.iface.legendInterface().setCurrentLayer(layer)

    def moveRaster(self):
        self.currentTool = self.moveTool
        layer = self.iface.legendInterface().currentLayer()
        self.moveTool.setLayer(layer)
        self.iface.mapCanvas().setMapTool(self.moveTool)

    def rotateRaster(self):
        self.currentTool = self.rotateTool
        layer = self.iface.legendInterface().currentLayer()
        self.rotateTool.setLayer(layer)
        self.iface.mapCanvas().setMapTool(self.rotateTool)

    def scaleRaster(self):
        self.currentTool = self.scaleTool
        layer = self.iface.legendInterface().currentLayer()
        self.scaleTool.setLayer(layer)
        self.iface.mapCanvas().setMapTool(self.scaleTool)

    def adjustRaster(self):
        self.currentTool = self.adjustTool
        layer = self.iface.legendInterface().currentLayer()
        self.adjustTool.setLayer(layer)
        self.iface.mapCanvas().setMapTool(self.adjustTool)

    def increaseTransparency(self):
        layer = self.iface.legendInterface().currentLayer()
        # clamp to 100
        tr = min(layer.transparency + 10, 100)
        layer.transparencyChanged(tr)

    def decreaseTransparency(self):
        layer = self.iface.legendInterface().currentLayer()
        # clamp to 0
        tr = max(layer.transparency - 10, 0)
        layer.transparencyChanged(tr)

    def exportAsRaster(self):
        layer = self.iface.legendInterface().currentLayer()
        exportCommand = ExportAsRasterCommand(self.iface)
        exportCommand.exportAsRaster(layer)
