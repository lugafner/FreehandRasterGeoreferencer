set -x

rm -f fhrgr.zip
rsync -a . FreehandRasterGeoreferencer --exclude "FreehandRasterGeoreferencer" --exclude ".*"  --exclude "*.pyc"  --exclude "**/__pycache__"  --exclude "*.sh"  --exclude "*.bat"  --exclude "azure-pipelines.yml"
zip -r fhrgr.zip FreehandRasterGeoreferencer