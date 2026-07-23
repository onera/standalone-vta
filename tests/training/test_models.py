import pytest
import torch
from src.training.modeling import MODEL_REGISTRY, get_model

@pytest.mark.parametrize("model_name", list(MODEL_REGISTRY.keys()))
def test_model_instantiation_and_forward(model_name: str):
    num_classes = 10
    in_channels = 1 if model_name == "LeNet5" else 3
    input_res = 28 if model_name == "LeNet5" else 224


    model = get_model(
        model_name=model_name, 
        num_classes=num_classes, 
        in_channels=in_channels, 
        input_res=input_res
    )
    model.eval()

    dummy_input = torch.randn(1, in_channels, input_res, input_res)
    with torch.no_grad():
        output = model(dummy_input)

    # Check output shape [Batch, num_classes, 1, 1]
    assert output.ndim == 4
    assert output.shape[0] == 1
    assert output.shape[1] == num_classes
    assert output.shape[2] == 1
    assert output.shape[3] == 1

def test_unknown_model_raises_error():
    with pytest.raises(ValueError, match="Unknown model_name"):
        get_model("NonExistentModel")
