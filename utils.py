# -*- coding: utf-8 -*-

from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import QgsProject
import os.path

# constants for saving data inside QGS
SETTINGS_KEY = "FreehandRasterGeoreferencer"
SETTING_BROWSER_RASTER_DIR = "browseRasterDir"

def toRelativeToQGS(imagePath):
    if os.path.isabs(imagePath):
        # Make it relative to current project if image below QGS
        imageFolder,imageName = os.path.split(imagePath)
        qgsPath = QgsProject.instance().fileName()
        qgsFolder,_ = os.path.split(qgsPath)
        imageFolder = os.path.abspath(imageFolder)
        qgsFolder = os.path.abspath(qgsFolder)
        
        if imageFolder.startswith(qgsFolder):
            # relative
            imageFolderRelPath = os.path.relpath(imageFolder, qgsFolder)
            imagePath = os.path.join(imageFolderRelPath, imageName)
            qDebug(imagePath.encode('utf8'))
            
    return imagePath
