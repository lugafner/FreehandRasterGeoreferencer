from qgis.core import *
from qgis.gui import *
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import math
import os.path

class ExportAsRasterCommand(object):
    
    def __init__(self, iface):
        self.iface = iface
        
    def exportAsRaster(self, layer):
        rasterPath = self.getRasterPath(layer.filepath)
        if not rasterPath:
            # cancelled
            return
        
        rasterFormat = rasterPath[-3:]
        if rasterFormat not in ["jpg","bmp","png","tif"]:
            widget = QgsMessageBar.createMessage("Export as raster", "Unsupported file format: %s" % format)
            self.iface.messageBar().pushWidget(widget,  QgsMessageBar.WARNING, 5)
            return
        
        try:
            
            originalWidth = layer.image.width()
            originalHeight = layer.image.height()
            
            # maintain at least the original resolution of the raster
            ratio = layer.xScale / layer.yScale
            if ratio > 1:
                # increase x
                scaleX = ratio
                scaleY = 1
            else:
                # increase y
                scaleX = 1
                scaleY = 1. / ratio
                
            radRotation = layer.rotation * math.pi / 180
            
            width = abs(scaleX * originalWidth * math.cos(radRotation )) + abs(scaleY * originalHeight * math.sin(radRotation)) 
            height = abs(scaleX * originalWidth * math.sin(radRotation)) + abs(scaleY * originalHeight * math.cos(radRotation))
            
            qDebug("wh %f,%f" % (width, height))
            
            img = QImage(QSize(math.ceil(width), math.ceil(height)), QImage.Format_ARGB32)
            # transparent background
            img.fill(QColor(0,0,0,0))
            
            painter = QPainter(img)
            painter.setRenderHint(QPainter.Antialiasing, True)
            
            rect = QRectF(QPointF(-layer.image.width() / 2.0, 
                                -layer.image.height() / 2.0 ), 
                         QPointF(layer.image.width() / 2.0 , 
                                layer.image.height() / 2.0 ))
            
            painter.translate(QPointF(width/2.0, height/2.0))
            painter.rotate(layer.rotation)
            painter.scale(scaleX, scaleY)
            painter.drawImage(rect, layer.image)
            painter.end()
            
            img.save(rasterPath, rasterFormat)
            
            extent = layer.extent()
            a = extent.width() / width
            e = -extent.height() / height
            # 2nd term because (0,0) of world file is on center of upper left pixel
            # instead of upper left corner of that pixel
            c = extent.xMinimum() + a/2
            f = extent.yMaximum() + e/2
            b = d = 0.0
            worldFilePath = rasterPath[:-3]
            if rasterFormat == "jpg":
                worldFilePath += "jpw"
            elif rasterFormat == "png":
                worldFilePath += "pgw"
            elif rasterFormat == "bmp":
                worldFilePath += "bpw"
            elif rasterFormat == "tif":
                worldFilePath += "tfw"
                
            with open(worldFilePath, "w") as writer:
                writer.write("%.13f\n%.13f\n%.13f\n%.13f\n%.13f\n%.13f" % (a,b,d,e,c,f))
                
            crsFilePath = rasterPath + ".aux.xml"
            with open(crsFilePath, "w") as writer:
                writer.write(self.auxContent(self.iface.mapCanvas().mapSettings().destinationCrs())) 
            
                
            widget = QgsMessageBar.createMessage("Raster Geoferencer", "Raster exported successfully.")
            self.iface.messageBar().pushWidget(widget,  QgsMessageBar.INFO, 2)
        except Exception as ex:
            QgsMessageLog.logMessage(repr(ex))
            widget = QgsMessageBar.createMessage("Raster Geoferencer", "There was an error performing this command. See QGIS Message log for details.")
            self.iface.messageBar().pushWidget(widget,  QgsMessageBar.CRITICAL, 5)
            return
        
            
    def getRasterPath(self, originalPath):
        filepath,_ = os.path.splitext(originalPath)
        filepath += "_georeferenced.png" 
        filepath = u"%s"%(QFileDialog.getSaveFileName(None, "Export as raster", filepath, "Images (*.png *.bmp *.jpg *.tif)"))
        return filepath
    
    def auxContent(self, crs):
        content = """<PAMDataset>
  <Metadata domain="xml:ESRI" format="xml">
    <GeodataXform xsi:type="typens:IdentityXform" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:typens="http://www.esri.com/schemas/ArcGIS/9.2">
      <SpatialReference xsi:type="typens:%sCoordinateSystem">
        <WKT>%s</WKT>
      </SpatialReference>
    </GeodataXform>
  </Metadata>
</PAMDataset>"""
        geogOrProj = "Geographic" if crs.geographicFlag() else "Projected"
        return content % (geogOrProj, crs.toWkt())
