import pytest
from pathlib import Path
from animaltracking import coco_dataset, filetools
import os

CI = os.getenv("CI", False)
print(type(CI))
print(CI)


def test_coco_split():
    filetools.wget(
        "https://github.com/Tony607/detectron2_instance_segmentation_demo/releases/download/V0.1/data.zip",
        "data.zip",
    )
    filetools.unzip("data.zip", ".")

    # fnin = Path("instances_default.json")
    fnin = Path("data/trainval.json")
    fntest = Path("test.json")
    fntrain = Path("train.json")
    fnval = Path("val.json")
    fntmp = Path("tmp.json")
    cocod = coco_dataset.CocoDataset(fnin, Path("images_test"))
    cocod.train_test_split(fntrain, fntmp)

    cocod = coco_dataset.CocoDataset(fntmp, Path("images_test"))
    cocod.train_test_split(fntest, fnval, 0.5)


@pytest.mark.skipif(CI, reason="This is not possible on CI")
def test_skip():
    assert False
