# pythontemplate


## Install requirements

Install build packages and setup automatic upload after build.

```commandline
conda install -c conda-forge bump2version conda-build anaconda-client
anaconda login
conda config --set anaconda_upload yes
```

## Initial package setup

1) Select package name (`pythonpackage`)
    * one long word with no underscores and no dashes

2) Rename directory `pythontemplate` to `pythonpackage`
   
3) Find and replace:
   * `pythontemplate` -> Your package name - `pythonpackage`
   
4) Optional Find and replace     
   
   * `{{name_and_surname}}` - Full name used in project description
   * `{{githublogin}}` - Your login to github where is stored the repository
   * `{{email}}` - Email used in project description
   
5) Final touch 
   * Edit file `setup.py`
   * Edit file `conda-recipe/meta.yaml`

## Increase version 

```commandline
git pull
bumpversion path .
git push
git push --tags
```

## Build and upload to PyPI

```commandline
python setup.py sdist bdist_wheel
twine check dist/*
twine upload dist/*
```
## Build and upload to conda

```commandline
conda build . -c conda-forge
```