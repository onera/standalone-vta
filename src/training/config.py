import argparse
from dataclasses import dataclass, asdict, fields
from typing import Optional, Dict, Any
import os
import yaml

@dataclass
class TrainingConfig:
    """Configuration class for training and ONNX export pipeline."""
    dataset_name: str = "FashionMNIST"
    model_name: str = "LeNet5"
    batch_size: int = 64
    n_epochs: int = 1
    max_steps_per_epoch: Optional[int] = 3
    input_res: int = 28
    learning_rate: float = 0.001
    seed: int = 42
    device: Optional[str] = None
    output_dir: Optional[str] = None
    skip_vta: bool = False
    skip_onnx_verify: bool = False

    def get_output_dir(self) -> str:
        """Returns default or configured output directory path."""
        if self.output_dir:
            return self.output_dir
        return f"training_output/{self.model_name}"

    def save_yaml(self, filepath: str) -> None:
        """Saves current configuration to a YAML file for experiment traceability."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        data = asdict(self)
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        print(f"📄 Saved configuration YAML to: {filepath}")

    @classmethod
    def from_yaml(cls, filepath: str) -> "TrainingConfig":
        """Loads configuration from a YAML file."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Configuration YAML file not found at: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        valid_fields = {field.name for field in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)

def parse_args() -> TrainingConfig:
    """Parses command line arguments into a TrainingConfig object, supporting YAML config loading and CLI overrides."""
    parser = argparse.ArgumentParser(
        description="Standalone-VTA Training, Quantization (PT2E), ONNX Conversion & VTA Simulation Pipeline."
    )
    parser.add_argument(
        "--config", type=str, default=None,
        help="Path to input YAML configuration file (e.g. configs/lenet.yaml)"
    )
    parser.add_argument(
        "--dataset", type=str, default=None,
        choices=["FashionMNIST", "MNIST", "ImageNet"],
        help="Dataset to use for training/verification (default: FashionMNIST)"
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Model architecture name (default: LeNet5). Supported: LeNet5, GoogLeNet, VGG16, ResNet18"
    )
    parser.add_argument(
        "--batch-size", type=int, default=None,
        help="Batch size for training and testing (default: 64)"
    )
    parser.add_argument(
        "--epochs", type=int, default=None,
        help="Number of training epochs (default: 1)"
    )
    parser.add_argument(
        "--max-steps-per-epoch", type=int, default=None,
        help="Maximum steps per epoch for fast debugging/testing (default: 3, set to 0 or negative for full epoch)"
    )
    parser.add_argument(
        "--input-res", type=int, default=None,
        help="Input resolution for images (default: 28)"
    )
    parser.add_argument(
        "--lr", type=float, default=None,
        help="Learning rate for optimizer (default: 0.001)"
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducibility (default: 42)"
    )
    parser.add_argument(
        "--device", type=str, default=None,
        help="Device to use for computation (e.g. 'cuda:0', 'cpu', default: auto-select)"
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="Custom output directory to save models and ONNX artifacts"
    )
    parser.add_argument(
        "--skip-vta", action=argparse.BooleanOptionalAction, default=None,
        help="Skip compilation and execution on VTA simulator"
    )
    parser.add_argument(
        "--skip-onnx-verify", action=argparse.BooleanOptionalAction, default=None,
        help="Skip ONNX Runtime verification step"
    )

    args = parser.parse_args()

    # Load base config from YAML if provided, else default dataclass instance
    if args.config:
        cfg = TrainingConfig.from_yaml(args.config)
    else:
        cfg = TrainingConfig()

    # Apply CLI overrides for any explicitly passed parameters
    if args.dataset is not None:
        cfg.dataset_name = args.dataset
    if args.model is not None:
        cfg.model_name = args.model
    if args.batch_size is not None:
        cfg.batch_size = args.batch_size
    if args.epochs is not None:
        cfg.n_epochs = args.epochs
    if args.max_steps_per_epoch is not None:
        cfg.max_steps_per_epoch = args.max_steps_per_epoch if args.max_steps_per_epoch > 0 else None
    if args.input_res is not None:
        cfg.input_res = args.input_res
    if args.lr is not None:
        cfg.learning_rate = args.lr
    if args.seed is not None:
        cfg.seed = args.seed
    if args.device is not None:
        cfg.device = args.device
    if args.output_dir is not None:
        cfg.output_dir = args.output_dir
    if args.skip_vta is not None:
        cfg.skip_vta = args.skip_vta
    if args.skip_onnx_verify is not None:
        cfg.skip_onnx_verify = args.skip_onnx_verify

    return cfg
