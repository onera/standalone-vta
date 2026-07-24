import os
import tempfile
import pytest
from src.training.config import TrainingConfig

def test_config_defaults():
    cfg = TrainingConfig()
    assert cfg.model_name == "LeNet5"
    assert cfg.dataset_name == "FashionMNIST"
    assert cfg.batch_size == 64

def test_config_yaml_save_and_load():
    cfg = TrainingConfig(
        dataset_name="MNIST",
        model_name="ResNet18",
        batch_size=32,
        seed=100
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        yaml_path = os.path.join(tmp_dir, "test_config.yaml")
        cfg.save_yaml(yaml_path)
        assert os.path.exists(yaml_path)

        loaded_cfg = TrainingConfig.from_yaml(yaml_path)
        assert loaded_cfg.dataset_name == "MNIST"
        assert loaded_cfg.model_name == "ResNet18"
        assert loaded_cfg.batch_size == 32
        assert loaded_cfg.seed == 100

def test_image_size_formatting():
    cfg_int = TrainingConfig(image_size=28)
    assert cfg_int.image_size == (28, 28)

    cfg_tuple = TrainingConfig(image_size=(128, 256))
    assert cfg_tuple.image_size == (128, 256)

