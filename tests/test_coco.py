import pytest
from pathlib import Path
from animaltracking import coco_dataset
import os

CI = os.getenv("CARNIVOREID_DATASET_BASEDIR", r"H:\biology\orig\CarnivoreID")
print(type(CI))
print(CI)

def test_coco_split():
    fnin = Path("instances_default.json")
    fntest = Path("test.json")
    fntrain = Path("train.json")
    fnval = Path("val.json")
    fntmp = Path("tmp.json")
    cocod = coco_dataset.CocoDataset(fnin, Path("images_test"))
    cocod.train_test_split(fntrain, fntmp)

    cocod = coco_dataset.CocoDataset(fntmp, Path("images_test"))
    cocod.train_test_split(fntest, fnval, 0.5)


@pytest.mark.skipif(CI, "This is not possible on CI")
def test_skip():
    assert False