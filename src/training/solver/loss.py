import torch
import torch.nn as nn
from typing import Any

class FlattenCrossEntropyLoss(nn.Module):
    """Computes CrossEntropyLoss on flattened spatial logits of shape [Batch, NumClasses, 1, 1]."""
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes the FlattenCrossEntropyLoss class.

        Args:
            *args: Positional arguments forwarded to nn.CrossEntropyLoss.
            **kwargs: Keyword arguments forwarded to nn.CrossEntropyLoss.
        """
        super().__init__()
        # Forward all arguments (weight, ignore_index, reduction, etc.) to the base class
        self.ce = nn.CrossEntropyLoss(*args, **kwargs)

    def forward(self, preds: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Forward pass to compute cross entropy loss.

        Args:
            preds: Tensor of shape [Batch, NumClasses, 1, 1] (Output from the final Conv2d layer)
            targets: Tensor of shape [Batch] containing the ground truth labels

        Returns:
            Computed cross entropy loss.
        """
        # Flatten spatial dimensions: [B, C, 1, 1] -> [B, C]
        preds_flat = preds.view(preds.size(0), -1)
        
        # Compute standard CrossEntropyLoss on the 2D tensor
        return self.ce(preds_flat, targets)
