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

from PyQt5.QtWidgets import QDialog, QFileDialog, QMessageBox
from qgis.core import QgsProject

from .ui_freehandrastergeoreferencer import Ui_FreehandRasterGeoreferencer
from . import utils


class FreehandRasterGeoreferencerDialog(QDialog,
                                        Ui_FreehandRasterGeoreferencer):

    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)
        self.pushButtonAdd.clicked.connect(self.accept)
        self.pushButtonCancel.clicked.connect(self.reject)
        self.pushButtonBrowse.clicked.connect(self.showBrowserDialog)
        self.pushButtonReplace.clicked.connect(self.replaceImage)

    def clear(self, layer):
        self.layer = layer
        if layer is None:
            imagepath = ""
        else:
            imagepath = layer.filepath

        self.lineEditImagePath.setText(imagepath)

    def showBrowserDialog(self):
        bDir, found = QgsProject.instance().readEntry(
            utils.SETTINGS_KEY, utils.SETTING_BROWSER_RASTER_DIR, None)
        if not found:
            bDir = os.path.expanduser("~")

        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select image", bDir, "Images (*.png *.bmp *.jpg *.tif *.pdf)")

        if filepath:
            self.lineEditImagePath.setText(filepath)
            bDir, _ = os.path.split(filepath)
            QgsProject.instance().writeEntry(utils.SETTINGS_KEY,
                                             utils.SETTING_BROWSER_RASTER_DIR,
                                             bDir)

    def replaceImage(self):
        imagepath = self.lineEditImagePath.text()
        imagename, _ = os.path.splitext(os.path.basename(imagepath))
        self.layer.replaceImage(imagepath, imagename)
        self.close()

    def accept(self):
        result, message, details = self.validate()
        if result:
            self.done(QDialog.Accepted)
        else:
            msgBox = QMessageBox()
            msgBox.setWindowTitle("Error")
            msgBox.setText(message)
            msgBox.setDetailedText(details)
            msgBox.setStandardButtons(QMessageBox.Ok)
            msgBox.exec_()

    def validate(self):
        result = True
        message = ""
        details = ""

        self.imagePath = self.lineEditImagePath.text()
        _, extension = os.path.splitext(self.imagePath)
        extension = extension.lower()
        if not os.path.isfile(self.imagePath) or \
                (extension not in [".jpg", ".bmp", ".png", ".tif", ".pdf"]):
            result = False
            if len(details) > 0:
                details += "\n"
            details += "The path must be an image file"

        if not result:
            message = "There were errors in the form"

        return result, message, details
