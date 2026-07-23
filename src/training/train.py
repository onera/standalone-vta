import os
import sys
import torch
import torch.optim as optim

from src.training.config import parse_args, TrainingConfig
from src.training.data import get_data_loaders
from src.training.modeling import get_model

from src.training.quantization import prepare_qat_model, convert_quantized_model
from src.training.engine import train_model
from src.training.solver.loss import FlattenCrossEntropyLoss
from src.training.onnx_utils import convert_qdq_to_qlinear_onnx, verify_onnx
from src.training.vta import compile_and_run_vta
from src.training.utils import set_seed, select_device

def main() -> None:
    # 0. Parse Configuration & Set Seed
    cfg: TrainingConfig = parse_args()
    set_seed(cfg.seed)
    device = select_device(cfg.device)

    model_dir: str = cfg.get_output_dir()
    os.makedirs(model_dir, exist_ok=True)
    cfg.save_yaml(os.path.join(model_dir, "config.yaml"))

    print(f"🚀 Starting Pipeline: Model='{cfg.model_name}', Dataset='{cfg.dataset_name}', Epochs={cfg.n_epochs}")


    # 1. Setup Data Loaders
    loaders = get_data_loaders(
        dataset_name=cfg.dataset_name, 
        batch_size=cfg.batch_size, 
        resize=cfg.input_res
    )

    # 2. Determine Channels and Class Count
    if cfg.dataset_name == "ImageNet":
        in_channels = 3
        num_classes = 1000
    else:
        in_channels = 1
        num_classes = 10

    # 3. Instantiate Model & Loss/Optimizer
    model = get_model(
        model_name=cfg.model_name, 
        num_classes=num_classes, 
        in_channels=in_channels, 
        input_res=cfg.input_res
    )
    criterion = FlattenCrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=cfg.learning_rate)

    # 4. Prepare Model for QAT (PT2E)
    example_inputs = next(iter(loaders['train']))[0]
    qat_model = prepare_qat_model(model, example_inputs, min_batch=1, max_batch=cfg.batch_size)

    # 5. Train Model
    qat_model = train_model(
        qat_model,
        loaders,
        criterion,
        optimizer,
        device=device,
        num_epochs=cfg.n_epochs,
        max_steps_per_epoch=cfg.max_steps_per_epoch
    )

    # 6. Convert to Quantized Model & Save State Dict
    q_model = convert_quantized_model(qat_model)
    state_dict_path = os.path.join(model_dir, "q_model_state_dict.pth")
    torch.save(q_model.state_dict(), state_dict_path)
    print(f"💾 Saved Quantized Model State Dict to: {state_dict_path}")

    # 7. Export Model to ONNX Format (QDQ)
    onnx_path = os.path.join(model_dir, "vta_cnn_qdq.onnx")
    with torch.no_grad():
        torch.onnx.export(
            q_model,
            example_inputs[0:1],
            onnx_path,
            dynamo=True,
            opset_version=18
        )
    print(f"📦 Exported ONNX QDQ Model to: {onnx_path}")

    # 8. Convert QDQ ONNX to QLinear ONNX to be compatible with the standard VTA compiler
    qlinear_onnx_path = os.path.join(model_dir, "vta_cnn_qlinear.onnx")
    convert_qdq_to_qlinear_onnx(onnx_path, qlinear_onnx_path)

    # 9. Verify ONNX Model Accuracy & Output Match
    if not cfg.skip_onnx_verify:
        verify_onnx(q_model, onnx_path, qlinear_onnx_path, loaders, num_samples=20)
    else:
        print("⏭️ Skipping ONNX Runtime Verification.")

    # 10. Compile and Run Model on VTA Simulator
    if not cfg.skip_vta:
        compile_and_run_vta(qlinear_onnx_path)
    else:
        print("⏭️ Skipping VTA Execution.")

if __name__ == "__main__":
    main()
