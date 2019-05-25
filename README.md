# About

This project is a plugin for QGIS 2 and 3 to perform interactive raster georeferencing. The plugin was originally made to replace a workflow where digitizers would use Google Earth to interactively georeference a raster and the tools (move, rotate, scale...) found in that software have been reimplemented. Compared to the standard raster georeferencer tool of QGIS, which needs control points and an export, this plugin allows the visualization of the result immediately, on top of the other layers of the map. 

# Install

## From the QGIS plugin registry

In QGIS, open the "Plugins" > "Manage and install plugin" dialog. Install the "Freehand raster georeferencer" plugin.

## From Github

For QGIS 3 use the master branch. For QGIS 2, use the qgis2 branch.

1. Download a ZIP of the repository or clone it using "git clone"
2. The folder with the Python files should be directly under the directory with all the QGIS plugins (for example, ~/.qgis2/python/plugins/FreehandRasterGeoreferencer)
3. Compile the assets and UI: 
    - On Windows, launch the OSGeo4W Shell. On Unix, launch a command line and make sure the PyQT tools (pyuic4/5 and pyrcc4/5) are on the PATH
    - Go to the plugin directory
    - Launch "build.bat" or "build.sh"
4. The next time QGIS is opened, the plugin should be listed in the "Plugins" > "Manage and install plugin" dialog

**Note that the QGIS 2 branch is considered legacy and no further development is planned at this point.**

# Documentation

See http://gvellut.github.io/FreehandRasterGeoreferencer/

# Issues

Report issues at https://github.com/gvellut/FreehandRasterGeoreferencer/issues

# Limitations

- The plugin uses Qt to read and and manipulate a raster and is therefore limited to the formats supported by that library. That means almost none of the GDAL raster formats are supported and very large rasters should be avoided. Currently BMP, JPEG, PNG, TIFF can be loaded.
- There is limited support for changing CRS: If the CRS of the map changes, you will have to adjust georeferencing of the layer in the new CRS.
- The raster layer added by this plugin does not have all the capabilities of a normal QGIS raster layer: It is limited to visualization and modification using the provided tools. However, a normal QGIS raster file, along with georerencing information, can be easily exported by the plugin and can be reloaded using the standard "Add Raster" functionality.
