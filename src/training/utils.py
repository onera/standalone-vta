"""
Copyright (c) 2024 Julien Posso
"""

import os
import random
import string
import shutil
from typing import Dict, Optional, Tuple, Any

import numpy as np
import torch


class RunningAverage:
    """Class to compute and store running averages of values"""

    def __init__(self, keys: Tuple[str, ...] = ('loss', 'accuracy')):
        """
        Initialize the RunningAverage object.

        Args:
            keys (tuple, optional): Tuple of keys for values to be tracked. Defaults to ('loss', 'accuracy').
        """
        self.running = {x: AverageMeter() for x in keys}

    def update(self, values: Dict[str, float], batch_size: int = 1) -> None:
        """
        Update the running average values with new values.

        Args:
            values (dict): Dictionary of key-value pairs to update the running averages.
            batch_size (int, optional): Batch size for weight adjustment. Defaults to 1.
        """
        for key, value in values.items():
            self.running[key].update(value, batch_size)

    def get_multiple(self, keys: Tuple[str, ...] = ('loss', 'accuracy')) -> Dict[str, float]:
        """
        Get the running average values for multiple keys.

        Args:
            keys (tuple, optional): Tuple of keys to retrieve the running averages. Defaults to ('loss', 'accuracy').

        Returns:
            dict: Dictionary of key-value pairs containing the running averages.
        """
        avg = {x: self.running[x].get_avg() for x in keys}
        return avg

    def get(self, key: str) -> float:
        """
        Get the running average value for a specific key.

        Args:
            key (str): Key to retrieve the running average value.

        Returns:
            float: Running average value for the specified key.

        Raises:
            AssertionError: If the specified key does not exist in the running averages dictionary.
        """
        assert key in self.running.keys(), f"Error: '{key}' not found in {self.running.keys()}"
        return self.running[key].get_avg()


class AverageMeter:
    """Class to compute and store the average and current value"""
    def __init__(self):
        self.val = 0.0
        self.avg = 0.0
        self.sum = 0.0
        self.count = 0

    def reset(self) -> None:
        """Reset the average meter values."""
        self.val = 0.0
        self.avg = 0.0
        self.sum = 0.0
        self.count = 0

    def update(self, val: float, n: int = 1) -> None:
        """
        Update the average meter with a new value.

        Args:
            val (float): New value to update the average meter.
            n (int, optional): Weight for the value. Defaults to 1.
        """
        self.val = float(val)
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count if self.count > 0 else 0.0

    def get_avg(self) -> float:
        """
        Get the current average value.

        Returns:
            float: Current average value.
        """
        return self.avg


def select_device(device_str: Optional[str] = None) -> torch.device:
    """
    Select and return the appropriate device (GPU or CPU) for computation.

    Args:
        device_str (str, optional): Optional explicit device string override (e.g. 'cuda:0', 'cpu').

    Returns:
        torch.device: Selected device for computation.
    """
    if device_str is not None:
        device = torch.device(device_str)
        print(f"Device specified: {device}\n")
        return device

    if torch.cuda.is_available():
        if torch.cuda.device_count() > 1:
            gpu_nb = input("Select GPU number:")
            device = torch.device(f"cuda:{gpu_nb}")
        else:
            device = torch.device("cuda:0")
            print(f"Device used: {device}\n")
    else:
        device = torch.device("cpu")
        print(f"Device used: {device}\n")
    return device


def set_seed(seed: int = 1) -> None:
    """
    Set manual seeds for reproducibility.

    Args:
        seed (int): The seed value to set. Defaults to 1.

    See Also:
        - PyTorch documentation on reproducibility: https://pytorch.org/docs/stable/notes/randomness.html#reproducibility
    """
    torch.manual_seed(seed)
    random.seed(seed)  # Python random module.
    np.random.seed(seed)  # Numpy module.
    torch.use_deterministic_algorithms(False)

    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)  # if you are using multi-GPU.
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = False
