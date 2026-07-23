import torch
import torch.nn as nn
from typing import Optional

class ConvBnAct(nn.Sequential):
    """A sequential block consisting of a Conv2d, optional BatchNorm2d, and optional ReLU activation."""
    def __init__(
        self,
        in_channels: int = 1,
        out_channels: int = 1,
        kernel_size: int = 3,
        stride: int = 1,
        padding: Optional[int] = None,
        dilation: int = 1,
        groups: int = 1,
        bias: bool = False,
        batchnorm: bool = True,
        activation: bool = True
    ) -> None:
        """Initializes the ConvBnAct block.

        Args:
            in_channels: Number of channels in the input image.
            out_channels: Number of channels produced by the convolution.
            kernel_size: Size of the convolving kernel.
            stride: Stride of the convolution.
            padding: Padding added to all four sides of the input.
            dilation: Spacing between kernel elements.
            groups: Number of blocked connections from input channels to output channels.
            bias: If True, adds a learnable bias to the output.
            batchnorm: If True, adds a batch normalization layer.
            activation: If True, adds a ReLU activation layer.
        """
        if padding is None:
            padding = (kernel_size - 1) // 2 * dilation

        layers = [nn.Conv2d(in_channels, out_channels, kernel_size, stride, padding, dilation, groups, bias)]

        if batchnorm:
            layers.append(nn.BatchNorm2d(num_features=out_channels))

        if activation:
            layers.append(nn.ReLU())

        super(ConvBnAct, self).__init__(*layers)
