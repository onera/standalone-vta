from typing import Tuple, Union
import torch
import torch.nn as nn

class LeNet5(nn.Module):
    """LeNet-5 adapted for the Standalone-VTA compiler constraints.

    This architecture modifies the classic LeNet-5 model (LeCun et al.) to comply
    with the hardware constraints of the VTA (Versatile Tensor Accelerator) 
    standalone compiler (https://github.com/onera/standalone-vta).

    Key Adaptations for VTA Compatibility:
        1. Fully Convolutional Classifier: Replaces traditional fully connected (linear)
           layers with `nn.Conv2d` layers to avoid flattening and reshaping operators 
           (e.g., `nn.Flatten`, `view`, or `reshape`), which are not supported by the VTA compiler.
        2. Spatial Dimension Reduction: The first classifier layer uses a kernel size 
           equal to the incoming spatial dimension (5x5) to reduce the feature map to 
           1x1 spatially.
        3. 1x1 Convolutions: Subsequent classifier layers use 1x1 convolutions.
        4. Max Pooling & ReLU: Replaces average pooling with max pooling and tanh 
           activations with ReLU, aligned with VTA hardware operation support.

    Target Dataset:
        Designed for 28x28 single-channel grayscale image datasets, such as MNIST 
        and FashionMNIST.
    """
    def __init__(
        self, 
        num_classes: int = 10, 
        image_size: Union[int, Tuple[int, int]] = (28, 28)
    ) -> None:
        """Initializes the LeNet5 model layers and validates input spatial resolution.

        Args:
            num_classes: The number of target classification categories. 
                Defaults to 10.
            image_size: Spatial resolution of input images as a single integer or (H, W) tuple.
                Defaults to (28, 28).

        Raises:
            ValueError: If image_size is not (28, 28).
        """
        super().__init__()

        if isinstance(image_size, int):
            image_size = (image_size, image_size)
            
        if image_size != (28, 28):
            raise ValueError(
                f"LeNet5 requires an input image_size of (28, 28), but got {image_size}. "
                "The fully convolutional head kernel sizes are fixed for 28x28 inputs."
            )
        
        self.image_size = image_size
        
        self.features = nn.Sequential(
            nn.Conv2d(1, 6, kernel_size=5, stride=1, padding=2),  # Output shape: [Batch, 6, 28, 28]
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),                # Output shape: [Batch, 6, 14, 14]
            
            nn.Conv2d(6, 16, kernel_size=5, stride=1, padding=0),  # Output shape: [Batch, 16, 10, 10]
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2)                 # Output shape: [Batch, 16, 5, 5]
        )
        
        self.classifier_conv = nn.Sequential(
            # The input tensor spatial size is 5x5.
            # A 5x5 kernel convolution reduces the spatial size to 1x1.
            nn.Conv2d(16, 120, kernel_size=5, stride=1), # Output shape: [Batch, 120, 1, 1]
            nn.ReLU(),
            
            # Subsequent Fully Connected layers are represented as 1x1 convolutions
            nn.Conv2d(120, 84, kernel_size=1, stride=1), # Output shape: [Batch, 84, 1, 1]
            nn.ReLU(),
            
            nn.Conv2d(84, num_classes, kernel_size=1, stride=1) # Output shape: [Batch, num_classes, 1, 1]
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Performs the forward pass of the LeNet5 model.

        Args:
            x: Input image tensor of shape [Batch, 1, 28, 28].

        Returns:
            Output logits tensor of shape [Batch, num_classes, 1, 1].
        """
        x = self.features(x)
        x = self.classifier_conv(x)
        return x
