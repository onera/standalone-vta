import torch
import torch.nn as nn
import torchao
from tqdm import tqdm
from typing import Dict, Union, Optional
from torch.utils.data import DataLoader
from src.training.utils import RunningAverage

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
    batch_size: int = next(iter(dataloaders['train']))[0].size(0)
    print(f"Batch Size: {batch_size}")
    model = model.to(device)
    best_model = None
    best_accuracy: float = 0.0
    
    for epoch in range(num_epochs):
        for phase in ['train', 'valid']:
            if phase not in dataloaders:
                continue

            if phase == 'train':
                torchao.quantization.pt2e.move_exported_model_to_train(model)
            else:
                torchao.quantization.pt2e.move_exported_model_to_eval(model)
            
            metrics = RunningAverage(keys=('loss', 'accuracy'))
            pbar = tqdm(
                dataloaders[phase], 
                desc=f"{phase.capitalize()} Epoch {epoch+1}/{num_epochs}", 
                bar_format='{l_bar}{bar:10}{r_bar}{bar:-10b}', 
                ncols=120
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

            current_accuracy = metrics.get('accuracy')
            if phase == 'valid' and current_accuracy > best_accuracy:
                best_accuracy = current_accuracy
                best_model = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    if best_model is not None:
        model.load_state_dict(best_model)
        print(f"\nBest Validation Accuracy: {best_accuracy:.2f}%")
    else:
        print("\nTraining completed or interrupted early. Returning current trained weights.")
    return model

