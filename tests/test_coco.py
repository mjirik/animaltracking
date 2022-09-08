import pytest
from pathlib import Path
from ctcodedetector import coco_dataset



def test_coco_split():
    cocod = coco_dataset.CocoDataset(Path("coco_test.json"), Path("images_test"))
    cocod.train_test_split("cctr.json", "ccte.json")


