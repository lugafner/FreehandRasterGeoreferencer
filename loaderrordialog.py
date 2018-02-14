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
import string

from PyQt4 import QtGui
from PyQt4.QtCore import qDebug, QObject, SIGNAL, Qt
from PyQt4.QtGui import QApplication, QFileDialog, QMessageBox
from qgis.core import QgsProject

from ui_loaderrordialog import Ui_LoadError
import utils


class LoadErrorDialog(QtGui.QDialog, Ui_LoadError):

    def __init__(self, filepath):
        QtGui.QDialog.__init__(self)
        self.setupUi(self)

        self.lblError.setText(u"File '%s' not found." % filepath)
        QApplication.setOverrideCursor(Qt.ArrowCursor)
        QObject.connect(self.pushButtonBrowse, SIGNAL("clicked()"),
                        self.showBrowserDialog)

    def clear(self):
        self.lineEditImagePath.setText("")

    def showBrowserDialog(self):
        bDir, found = QgsProject.instance().readEntry(
            utils.SETTINGS_KEY,
            utils.SETTING_BROWSER_RASTER_DIR,
            None)

        if not found or not os.path.isdir(bDir):
            bDir = os.path.expanduser("~")

        qDebug(repr(bDir))
        filepath = '%s' % (QFileDialog.getOpenFileName(
            self, "Select image", bDir, "Images (*.png *.bmp *.jpg *.tif)"))
        self.lineEditImagePath.setText(filepath)

        if filepath:
            bDir, _ = os.path.split(filepath)
            QgsProject.instance().writeEntry(utils.SETTINGS_KEY,
                                             utils.SETTING_BROWSER_RASTER_DIR,
                                             bDir)

    def done(self, ack):
        QApplication.restoreOverrideCursor()
        super(LoadErrorDialog, self).done(ack)

    def accept(self):
        result, message, details = self.validate()
        if result:
            self.done(QtGui.QDialog.Accepted)
        else:
            msgBox = QtGui.QMessageBox()
            msgBox.setWindowTitle(u"Error")
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
        extension = string.lower(extension)
        if not os.path.isfile(self.imagePath) or \
                (extension not in [".jpg", ".bmp", ".png", ".tif"]):
            result = False
            if len(details) > 0:
                details += '\n'
            details += u"The path must be an image file"

        if not result:
            message = "There were errors in the form"

        return result, message, details
