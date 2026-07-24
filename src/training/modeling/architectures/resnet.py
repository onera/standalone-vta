from typing import Tuple, Union
import torch
import torch.nn as nn
from src.training.modeling.common import ConvBnAct

class BasicBlock(nn.Module):
    """Basic residual block used in ResNet-18 and ResNet-34 architectures.

    This block implements a two-layer residual function using 3x3 convolutions 
    interspersed with Batch Normalization and ReLU activations. 

    Dimensionality adjustment follows Option B as described in the original paper:
    "Deep Residual Learning for Image Recognition" (He et al., 2015).
    Ref: https://arxiv.org/pdf/1512.03385 (Section 3.3, "Residual Network" paragraph).

    If the spatial dimensions or channel counts between input and output mismatch, 
    the identity shortcut is replaced by a projection shortcut consisting of a 
    1x1 convolution followed by a Batch Normalization layer.

    Structural Topology:
        x ---> Conv3x3 ---> BN ---> ReLU ---> Conv3x3 ---> BN ---> (+) ---> ReLU ---> out
        |                                                           ^
        +--------> [ Optional: Conv1x1 (stride=2) ---> BN ] --------+

    Args:
        in_channels (int): Number of channels in the input tensor.
        out_channels (int): Number of channels produced by the block.
        stride (int, optional): Stride for the first spatial convolution. 
            A stride of 2 downsamples the input spatial dimensions by half. 
            Defaults to 1.
    """
    def __init__(self, in_channels: int, out_channels: int, stride: int = 1) -> None:
        super().__init__()
        # First layer: handles optional spatial downsampling via stride
        self.conv1 = ConvBnAct(
            in_channels=in_channels, 
            out_channels=out_channels, 
            kernel_size=3, 
            stride=stride, 
            padding=1, 
            batchnorm=True, 
            activation=True
        )
        # Second layer: maintains spatial dimensions and channel depth
        self.conv2 = ConvBnAct(
            in_channels=out_channels, 
            out_channels=out_channels, 
            kernel_size=3, 
            stride=1, 
            padding=1, 
            batchnorm=True, 
            activation=False  # Activation is applied AFTER the residual addition
        )
        
        # Identity or Projection Shortcut (Option B)
        self.shortcut = nn.Sequential()
        if stride != 1 or in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(out_channels)
            )
        self.relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Performs the forward pass of the BasicBlock.

        Args:
            x (torch.Tensor): Input feature map of shape (N, C_in, H, W).

        Returns:
            torch.Tensor: Output feature map of shape (N, C_out, H/stride, W/stride).
        """
        out = self.conv1(x)
        out = self.conv2(out)
        out = out + self.shortcut(x)
        out = self.relu(out)
        return out


class ResNet18(nn.Module):
    """ResNet-18 adapted for Standalone-VTA compiler constraints.

    This model implements the ResNet-18 architecture from He et al.'s original 
    paper "Deep Residual Learning for Image Recognition" (https://arxiv.org/abs/1512.03385),
    with adaptations for VTA hardware:
        1. Fully Convolutional Classifier: Replaces the global average pooling and 
           fully connected layer with a final `nn.Conv2d` layer. The kernel size of 
           this layer dynamically matches the remaining spatial resolution of the 
           feature maps after all pooling and residual stages.
        2. VTA-Compliant Downsampling: Shortcut projections (1x1 convolutions) are 
           used in residual paths when downsampling or changing channel dimensions.
    """
    def __init__(
        self, 
        in_channels: int = 3, 
        num_classes: int = 1000, 
        image_size: Union[int, Tuple[int, int]] = (224, 224)
    ) -> None:
        """Initializes the ResNet18 model.

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
        
        # Initial layer
        self.conv1 = ConvBnAct(
            in_channels=in_channels, 
            out_channels=64, 
            kernel_size=7, 
            stride=2, 
            padding=3, 
            batchnorm=True, 
            activation=True
        )
        current_h = (current_h - 7 + 2 * 3) // 2 + 1
        current_w = (current_w - 7 + 2 * 3) // 2 + 1
        
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        current_h = (current_h - 3 + 2 * 1) // 2 + 1
        current_w = (current_w - 3 + 2 * 1) // 2 + 1
        
        # Group 1 (layer 1)
        self.layer1 = nn.Sequential(
            BasicBlock(64, 64, stride=1),
            BasicBlock(64, 64, stride=1)
        )
        
        # Group 2 (layer 2)
        self.layer2 = nn.Sequential(
            BasicBlock(64, 128, stride=2),
            BasicBlock(128, 128, stride=1)
        )
        current_h = (current_h - 3 + 2 * 1) // 2 + 1
        current_w = (current_w - 3 + 2 * 1) // 2 + 1
        
        # Group 3 (layer 3)
        self.layer3 = nn.Sequential(
            BasicBlock(128, 256, stride=2),
            BasicBlock(256, 256, stride=1)
        )
        current_h = (current_h - 3 + 2 * 1) // 2 + 1
        current_w = (current_w - 3 + 2 * 1) // 2 + 1
        
        # Group 4 (layer 4)
        self.layer4 = nn.Sequential(
            BasicBlock(256, 512, stride=2),
            BasicBlock(512, 512, stride=1)
        )
        current_h = (current_h - 3 + 2 * 1) // 2 + 1
        current_w = (current_w - 3 + 2 * 1) // 2 + 1
        
        # Fully Convolutional Head
        self.classifier = nn.Conv2d(512, num_classes, kernel_size=(current_h, current_w), stride=1, padding=0)


    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Performs the forward pass of the ResNet18 model.

        Args:
            x: Input image tensor of shape [Batch, in_channels, height, width].

        Returns:
            Output logits tensor of shape [Batch, num_classes, 1, 1].
        """
        x = self.conv1(x)
        x = self.maxpool(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        x = self.classifier(x)
        return x
