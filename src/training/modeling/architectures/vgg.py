import torch
import torch.nn as nn
from src.training.modeling.common import ConvBnAct

class VGG16(nn.Module):
    """VGG-16 (Configuration C) adapted for Standalone-VTA compiler constraints.

    This model implements the VGG-16 architecture from Simonyan & Zisserman's 
    original paper "Very Deep Convolutional Networks for Large-Scale Image Recognition" 
    (https://arxiv.org/abs/1409.1556), with adaptations for VTA hardware:
        1. Fully Convolutional Classifier: Fully connected (linear) layers are 
           converted to convolutional layers (`nn.Conv2d`) to avoid using unsupported 
           flattening/reshaping operators in the forward pass.
        2. Dynamic Max Pooling: Depending on the input spatial resolution, up to 5 
           max pooling layers (kernel 2x2, stride 2) are dynamically applied to ensure 
           the spatial size is reduced to a valid minimum size (e.g. 7x7 for 224x224 inputs, 
           or 1x1 for 28x28 inputs).
        3. Batch Normalization: `ConvBnAct` blocks (convolution followed by batch 
           normalization and ReLU) are used to stabilize training and facilitate 
           efficient quantization.

    Original Channel Configuration (Config C):
        - Block 1: 2x Conv3-64
        - Block 2: 2x Conv3-128
        - Block 3: 2x Conv3-256, Conv1-256
        - Block 4: 2x Conv3-512, Conv1-512
        - Block 5: 2x Conv3-512, Conv1-512
        - Classifier: Conv (512 -> 4096), Conv (4096 -> 4096), Conv (4096 -> num_classes)
    """
    def __init__(self, in_channels: int = 3, num_classes: int = 1000, input_res: int = 224) -> None:
        """Initializes the VGG16 model.

        Args:
            in_channels: Number of input channels.
            num_classes: The number of classification categories.
            input_res: The spatial resolution of input images (e.g. 28 or 224).
        """
        super().__init__()
        
        current_res = input_res
        
        # Block 1
        self.block1 = nn.Sequential(
            ConvBnAct(in_channels=in_channels, out_channels=64, kernel_size=3, padding=1),
            ConvBnAct(in_channels=64, out_channels=64, kernel_size=3, padding=1),
        )
        if current_res >= 2:
            self.block1.add_module("pool", nn.MaxPool2d(kernel_size=2, stride=2))
            current_res //= 2
        
        # Block 2
        self.block2 = nn.Sequential(
            ConvBnAct(in_channels=64, out_channels=128, kernel_size=3, padding=1),
            ConvBnAct(in_channels=128, out_channels=128, kernel_size=3, padding=1),
        )
        if current_res >= 2:
            self.block2.add_module("pool", nn.MaxPool2d(kernel_size=2, stride=2))
            current_res //= 2
        
        # Block 3
        self.block3 = nn.Sequential(
            ConvBnAct(in_channels=128, out_channels=256, kernel_size=3, padding=1),
            ConvBnAct(in_channels=256, out_channels=256, kernel_size=3, padding=1),
            ConvBnAct(in_channels=256, out_channels=256, kernel_size=1, padding=0),
        )
        if current_res >= 2:
            self.block3.add_module("pool", nn.MaxPool2d(kernel_size=2, stride=2))
            current_res //= 2
        
        # Block 4
        self.block4 = nn.Sequential(
            ConvBnAct(in_channels=256, out_channels=512, kernel_size=3, padding=1),
            ConvBnAct(in_channels=512, out_channels=512, kernel_size=3, padding=1),
            ConvBnAct(in_channels=512, out_channels=512, kernel_size=1, padding=0),
        )
        if current_res >= 2:
            self.block4.add_module("pool", nn.MaxPool2d(kernel_size=2, stride=2))
            current_res //= 2
        
        # Block 5
        self.block5 = nn.Sequential(
            ConvBnAct(in_channels=512, out_channels=512, kernel_size=3, padding=1),
            ConvBnAct(in_channels=512, out_channels=512, kernel_size=3, padding=1),
            ConvBnAct(in_channels=512, out_channels=512, kernel_size=1, padding=0),
        )
        if current_res >= 2:
            self.block5.add_module("pool", nn.MaxPool2d(kernel_size=2, stride=2))
            current_res //= 2
        
        # Fully Convolutional Head (replacing Linear layers)
        # We use a kernel size equal to the remaining feature map spatial dimension (current_res) to reduce to 1x1
        self.classifier = nn.Sequential(
            nn.Conv2d(512, 4096, kernel_size=current_res, stride=1, padding=0),
            nn.ReLU(),
            nn.Conv2d(4096, 4096, kernel_size=1, stride=1, padding=0),
            nn.ReLU(),
            nn.Conv2d(4096, num_classes, kernel_size=1, stride=1, padding=0)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Performs the forward pass of the VGG16 model.

        Args:
            x: Input image tensor of shape [Batch, in_channels, input_res, input_res].

        Returns:
            Output logits tensor of shape [Batch, num_classes, 1, 1].
        """
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)
        x = self.block4(x)
        x = self.block5(x)
        x = self.classifier(x)
        return x
