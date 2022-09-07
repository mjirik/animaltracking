#!/bin/bash
echo "======build.sh================="
echo "build.sh" > ~/conda_build_log.txt
date >> ~/conda_build_log.txt
echo "===== recipe dir $RECIPE_DIR" >> ~/conda_build_log.txt
ls -R $RECIPE_DIR >> ~/conda_build_log.txt
echo "===== prefix $PREFIX ======" >> ~/conda_build_log.txt
ls -R $PREFIX >> ~/scaffan.txt

$PYTHON setup.py install

