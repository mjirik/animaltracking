import pytest
from pathlib import Path
from animaltracking import coco_dataset


def test_coco_split():
    cocod = coco_dataset.CocoDataset(Path("instances_default.json"), Path("images_test"))
    cocod.train_test_split("cctr.json", "ccte.json")
