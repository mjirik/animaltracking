echo "prefix"
echo %PREFIX%
dir %PREFIX%
echo "recipe dir"
echo %RECIPE_DIR%
dir %RECIPE_DIR%

echo %PREFIX% >> scaffan_build_vystup.txt
echo %RECIPE_DIR% >> scaffan_build_vystup.txt
dir %PREFIX% >> scaffan_build_vystup.txt
dir %RECIPE_DIR% >> scaffan_build_vystup.txt
copy scaffan_build_vystup.txt "%HOMEDRIVE%%HOMEPATH"\
copy scaffan_build_vystup.txt "%PREFIX%"\

"%PYTHON%" setup.py install
if errorlevel 1 exit 1

mkdir -p "$PREFIX%"\scaffan
echo "copy "%RECIPE_DIR%"\scaffan\scaffan_icon512.png "%PREFIX%"\scaffan\"
