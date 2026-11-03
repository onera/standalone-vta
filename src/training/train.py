import logging
import os
import torch
import torch.optim as optim
from tqdm.contrib.logging import logging_redirect_tqdm

from src.training.config import parse_args, TrainingConfig
from src.training.data import get_data_loaders
from src.training.modeling import get_model

from src.training.quantization import prepare_qat_model, convert_quantized_model
from src.training.engine import train_model
from src.training.solver.loss import FlattenCrossEntropyLoss
from src.training.onnx_utils import convert_qdq_to_qlinear_onnx, verify_onnx
from src.training.vta import compile_and_run_vta
from src.training.utils import set_seed, select_device
from src.training.logging_utils import configure_logging

# Keep the package logger when invoked with ``python -m src.training.train``.
logger = logging.getLogger("src.training.train")

def main() -> None:
    """Runs training, quantization, ONNX export, comparison and optional VTA execution.

    Raises:
        SystemExit: If VTA compilation or execution fails.
    """
    # 0. Parse Configuration & Set Seed
    cfg: TrainingConfig = parse_args()
    configure_logging()
    set_seed(cfg.seed)
    device = select_device(cfg.device)

    model_dir: str = cfg.get_output_dir()
    os.makedirs(model_dir, exist_ok=True)

    logger.info(
        f"[setup] Model={cfg.model_name} dataset={cfg.dataset_name} "
        f"device={device} seed={cfg.seed} epochs={cfg.n_epochs}"
    )
    logger.info(
        f"[setup] Batch size={cfg.batch_size}; maximum batches per phase="
        f"{cfg.max_steps_per_epoch if cfg.max_steps_per_epoch is not None else 'unlimited'}"
    )
    cfg.save_yaml(os.path.join(model_dir, "config.yaml"))

    # 1. Setup Data Loaders
    loaders = get_data_loaders(
        dataset_name=cfg.dataset_name, 
        batch_size=cfg.batch_size, 
        image_size=cfg.image_size
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
        image_size=cfg.image_size
    )

    criterion = FlattenCrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=cfg.learning_rate)

    # 4. Prepare Model for QAT (PT2E)
    example_inputs = next(iter(loaders['train']))[0]
    qat_model = prepare_qat_model(model, example_inputs, min_batch=1, max_batch=cfg.batch_size)

    # 5. Train Model
    with logging_redirect_tqdm(loggers=[logging.getLogger("src.training")]):
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
    logger.info(f"[export] Saved quantized model state: {state_dict_path}")
    
    # 7. Export Model to ONNX Format (QDQ)
    onnx_path = os.path.join(model_dir, "vta_cnn_qdq.onnx")
    logger.info("[export] Exporting QDQ model to ONNX")
    with torch.no_grad():
        torch.onnx.export(
            q_model,
            example_inputs[0:1],
            onnx_path,
            dynamo=True,
            verbose=False,
            opset_version=18
        )
    logger.info(f"[export] Saved QDQ model: {onnx_path}")

    # 8. Convert QDQ ONNX to QLinear ONNX to be compatible with the standard VTA compiler
    qlinear_onnx_path = os.path.join(model_dir, "vta_cnn_qlinear.onnx")
    convert_qdq_to_qlinear_onnx(onnx_path, qlinear_onnx_path)

    # 9. Verify ONNX Model Accuracy & Output Match
    if not cfg.skip_onnx_verify:
        verify_onnx(q_model, onnx_path, qlinear_onnx_path, loaders, num_samples=20)
    else:
        logger.info("[verify] Skipped by configuration")

    # 10. Compile and Run Model on VTA Simulator
    if not cfg.skip_vta:
        if not compile_and_run_vta(qlinear_onnx_path):
            raise SystemExit(1)
    else:
        logger.info("[vta] Skipped by configuration")
    logger.info("[pipeline] Completed requested stages")

if __name__ == "__main__":
    main()
