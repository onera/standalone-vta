import logging
import sys
import torch
import torch.nn as nn
import torchao
from tqdm import tqdm
from typing import Dict, Union, Optional
from torch.utils.data import DataLoader
from src.training.utils import RunningAverage

logger = logging.getLogger(__name__)

def train_model(
    model: nn.Module,
    dataloaders: Dict[str, DataLoader],
    loss_fn: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: Union[torch.device, str],
    num_epochs: int = 5,
    max_steps_per_epoch: Optional[int] = None
) -> nn.Module:
    """Trains and validates a PyTorch neural network model (supporting PT2E QAT).

    Observers update quantization parameters during training and are disabled
    during validation. Fake quantization remains active in both phases.
    This phase policy does not implement a permanent observer or BatchNorm
    statistics freeze after a fixed number of epochs.

    Args:
        model: The PyTorch neural network model or exported QAT module.
        dataloaders: Dictionary containing "train" and "valid" DataLoaders.
        loss_fn: Loss function module.
        optimizer: Optimization algorithm optimizer.
        device: CPU or CUDA device to perform computation.
        num_epochs: Number of epochs to train.
        max_steps_per_epoch: Maximum number of batches to process per epoch phase.

    Returns:
        The trained model with best validation weights loaded if available.
    """
    logger.info(f"[train] Starting training: epochs={num_epochs}")
    model = model.to(device)
    best_model = None
    best_accuracy: float = 0.0
    
    for epoch in range(num_epochs):
        epoch_metrics: Dict[str, float] = {}
        for phase in ['train', 'valid']:
            if phase not in dataloaders:
                continue

            if phase == 'train':
                torchao.quantization.pt2e.move_exported_model_to_train(model)
                model.apply(torchao.quantization.pt2e.enable_observer)
            else:
                torchao.quantization.pt2e.move_exported_model_to_eval(model)
                # Evaluation mode alone does not stop quantization statistics updates.
                model.apply(torchao.quantization.pt2e.disable_observer)
            
            metrics = RunningAverage(keys=('loss', 'accuracy'))
            pbar = tqdm(
                dataloaders[phase], 
                desc=f"{phase.capitalize()} Epoch {epoch+1}/{num_epochs}",
                total=min(len(dataloaders[phase]), max_steps_per_epoch)
                if max_steps_per_epoch is not None else len(dataloaders[phase]),
                disable=not sys.stderr.isatty(),
                dynamic_ncols=True,
                leave=False,
            )
            
            step_count: int = 0
            for images, labels in pbar:
                images, labels = images.to(device), labels.to(device)
                curr_batch_size = images.size(0)
                outputs = model(images)
                
                loss_val = 0.0
                if phase == 'train':
                    loss = loss_fn(outputs, labels)
                    optimizer.zero_grad()
                    loss.backward()
                    optimizer.step()
                    loss_val = loss.item()
                
                # Flatten outputs if they are in [B, C, 1, 1] format
                if outputs.ndim == 4 and outputs.size(2) == 1 and outputs.size(3) == 1:
                    outputs = outputs.view(outputs.size(0), -1)

                _, predicted = torch.max(outputs.data, 1)
                batch_correct = (predicted == labels).sum().item()
                batch_acc = 100.0 * batch_correct / curr_batch_size

                metrics.update({'loss': loss_val, 'accuracy': batch_acc}, batch_size=curr_batch_size)
                
                pbar.set_postfix(accuracy=f"{metrics.get('accuracy'):.2f}%")
                
                step_count += 1
                if max_steps_per_epoch is not None and step_count >= max_steps_per_epoch:
                    break

            pbar.close()
            current_accuracy = metrics.get('accuracy')
            epoch_metrics[f"{phase}_accuracy"] = current_accuracy
            if phase == 'train':
                epoch_metrics['train_loss'] = metrics.get('loss')
            if phase == 'valid' and current_accuracy > best_accuracy:
                best_accuracy = current_accuracy
                best_model = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        summary = " ".join(
            f"{key}={value:.4f}" if key.endswith('loss') else f"{key}={value:.2f}%"
            for key, value in epoch_metrics.items()
        )
        logger.info(f"[train] Epoch {epoch + 1}/{num_epochs}: {summary}")

    if best_model is not None:
        model.load_state_dict(best_model)
        logger.info(f"[train] Restored best validation state: accuracy={best_accuracy:.2f}%")
    else:
        logger.info("[train] No best validation state selected; returning current weights")
    return model

