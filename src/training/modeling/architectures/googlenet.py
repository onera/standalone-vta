from typing import Tuple, Union
import torch
import torch.nn as nn
from src.training.modeling.common import ConvBnAct

class Inception(nn.Module):
    """Inception block as used in GoogLeNet (Inception v1)."""
    def __init__(
        self,
        in_channels: int,
        ch1x1: int,
        ch3x3red: int,
        ch3x3: int,
        ch5x5red: int,
        ch5x5: int,
        pool_proj: int,
    ) -> None:
        """Initializes the Inception module branches.

        Args:
            in_channels: Number of input channels.
            ch1x1: Output channels for 1x1 convolution branch.
            ch3x3red: Reduction output channels before 3x3 convolution.
            ch3x3: Output channels for 3x3 convolution.
            ch5x5red: Reduction output channels before 5x5 convolution.
            ch5x5: Output channels for 5x5 convolution.
            pool_proj: Output channels after max pooling projection.
        """
        super().__init__()
        
        self.branch1 = ConvBnAct(in_channels, ch1x1, kernel_size=1)
        
        self.branch2 = nn.Sequential(
            ConvBnAct(in_channels, ch3x3red, kernel_size=1),
            ConvBnAct(ch3x3red, ch3x3, kernel_size=3, padding=1)
        )
        
        self.branch3 = nn.Sequential(
            ConvBnAct(in_channels, ch5x5red, kernel_size=1),
            ConvBnAct(ch5x5red, ch5x5, kernel_size=5, padding=2)
        )
        
        self.branch4 = nn.Sequential(
            nn.MaxPool2d(kernel_size=3, stride=1, padding=1),
            ConvBnAct(in_channels, pool_proj, kernel_size=1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Performs the forward pass of the Inception block.

        Args:
            x: Input feature tensor.

        Returns:
            Concatenated output tensor from all 4 branches.
        """
        branch1 = self.branch1(x)
        branch2 = self.branch2(x)
        branch3 = self.branch3(x)
        branch4 = self.branch4(x)
        return torch.cat([branch1, branch2, branch3, branch4], 1)


class GoogLeNet(nn.Module):
    """GoogLeNet (Inception v1) adapted for Standalone-VTA compiler constraints.

    Key Adaptations for VTA Compatibility:
        1. Fully Convolutional Head: Replaces the global average pooling and 
           fully connected layer with a final `nn.Conv2d` layer. The kernel size of 
           this layer dynamically matches the remaining spatial resolution of the 
           feature maps.
        2. No Auxiliary Classifiers: Excluded to simplify the graph for hardware deployment.
        3. Max Pooling and ReLU activations are used throughout.
    """
    def __init__(
        self, 
        in_channels: int = 3, 
        num_classes: int = 1000, 
        image_size: Union[int, Tuple[int, int]] = (224, 224)
    ) -> None:
        """Initializes the GoogLeNet model.

        Args:
            in_channels: Number of input channels.
            num_classes: The number of classification categories.
            image_size: Spatial resolution of input images as a single integer or (H, W) tuple.
                Defaults to (224, 224).
        """
        super().__init__()
        
        if isinstance(image_size, int):
            image_size = (image_size, image_size)
        self.image_size = image_size
        
        current_h, current_w = image_size
        
        # Stem
        self.conv1 = ConvBnAct(in_channels, 64, kernel_size=7, stride=2, padding=3)
        current_h = (current_h - 7 + 2 * 3) // 2 + 1
        current_w = (current_w - 7 + 2 * 3) // 2 + 1
        
        self.maxpool1 = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        current_h = (current_h - 3 + 2 * 1) // 2 + 1
        current_w = (current_w - 3 + 2 * 1) // 2 + 1
        
        self.conv2 = ConvBnAct(64, 64, kernel_size=1, stride=1, padding=0)
        self.conv3 = ConvBnAct(64, 192, kernel_size=3, stride=1, padding=1)
        
        self.maxpool2 = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        current_h = (current_h - 3 + 2 * 1) // 2 + 1
        current_w = (current_w - 3 + 2 * 1) // 2 + 1
        
        # Inception 3
        self.inception3a = Inception(192, 64, 96, 128, 16, 32, 32)
        self.inception3b = Inception(256, 128, 128, 192, 32, 96, 64)
        
        self.maxpool3 = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        current_h = (current_h - 3 + 2 * 1) // 2 + 1
        current_w = (current_w - 3 + 2 * 1) // 2 + 1
        
        # Inception 4
        self.inception4a = Inception(480, 192, 96, 208, 16, 48, 64)
        self.inception4b = Inception(512, 160, 112, 224, 24, 64, 64)
        self.inception4c = Inception(512, 128, 128, 256, 24, 64, 64)
        self.inception4d = Inception(512, 112, 144, 288, 32, 64, 64)
        self.inception4e = Inception(528, 256, 160, 320, 32, 128, 128)
        
        self.maxpool4 = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        current_h = (current_h - 3 + 2 * 1) // 2 + 1
        current_w = (current_w - 3 + 2 * 1) // 2 + 1
        
        # Inception 5
        self.inception5a = Inception(832, 256, 160, 320, 32, 128, 128)
        self.inception5b = Inception(832, 384, 192, 384, 48, 128, 128)
        
        # Fully Convolutional Head
        self.classifier = nn.Conv2d(1024, num_classes, kernel_size=(current_h, current_w), stride=1, padding=0)


    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Performs the forward pass of the GoogLeNet model.

        Args:
            x: Input image tensor of shape [Batch, in_channels, height, width].

        Returns:
            Output logits tensor of shape [Batch, num_classes, 1, 1].
        """
        x = self.conv1(x)
        x = self.maxpool1(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.maxpool2(x)
        
        x = self.inception3a(x)
        x = self.inception3b(x)
        x = self.maxpool3(x)
        
        x = self.inception4a(x)
        x = self.inception4b(x)
        x = self.inception4c(x)
        x = self.inception4d(x)
        x = self.inception4e(x)
        x = self.maxpool4(x)
        
        x = self.inception5a(x)
        x = self.inception5b(x)
        
        x = self.classifier(x)
        return x
