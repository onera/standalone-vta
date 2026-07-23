import torch.nn as nn
from src.training.modeling.architectures import LeNet5, VGG16, ResNet18, GoogLeNet

MODEL_REGISTRY = {
    "LeNet5": LeNet5,
    "VGG16": VGG16,
    "ResNet18": ResNet18,
    "GoogLeNet": GoogLeNet,
}

def get_model(
    model_name: str = "LeNet5",
    num_classes: int = 10,
    in_channels: int = 1,
    input_res: int = 28
) -> nn.Module:
    """Instantiates a model architecture from the model registry.

    Args:
        model_name: Name of the model class (supported: LeNet5, VGG16, ResNet18, GoogLeNet).
        num_classes: Number of target output classes.
        in_channels: Number of input image channels (1 for grayscale, 3 for RGB).
        input_res: Spatial resolution of input images.

    Returns:
        Instantiated PyTorch model nn.Module.

    Raises:
        ValueError: If model_name is not registered.
    """
    if model_name not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model_name: '{model_name}'. Supported models: {list(MODEL_REGISTRY.keys())}")
    
    cls = MODEL_REGISTRY[model_name]
    if model_name == "LeNet5":
        return cls(num_classes=num_classes)
    else:
        return cls(in_channels=in_channels, num_classes=num_classes, input_res=input_res)
