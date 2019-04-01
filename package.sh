rm -f fhrgr.zip
cd ..
zip -r FreehandRasterGeoreferencer/fhrgr.zip FreehandRasterGeoreferencer -x ".*" -x "*/.*" -x "*.pyc" -x "*/__pycache__/*" -x "*.sh" -x "*.bat"
cd FreehandRasterGeoreferencer