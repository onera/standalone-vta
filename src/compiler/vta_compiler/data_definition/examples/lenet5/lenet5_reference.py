import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

class QuantizedLeNet5(nn.Module):
    def __init__(self, L1_tensor, L2_tensor, L3_tensor, L4_tensor, L5_tensor):
        super(QuantizedLeNet5, self).__init__()
        
        # Convert numpy weights to PyTorch tensors
        self.L1_weight = torch.from_numpy(L1_tensor).float()
        self.L2_weight = torch.from_numpy(L2_tensor).float()
        self.L3_weight = torch.from_numpy(L3_tensor).float()
        self.L4_weight = torch.from_numpy(L4_tensor.squeeze()).float()
        self.L5_weight = torch.from_numpy(L5_tensor.squeeze()).float()
        
        # Layers
        self.relu = nn.ReLU()
        self.pool = nn.AvgPool2d(kernel_size=2, stride=2)

    def truncate_to_int8(self, x):
        # Convert to int32 first, then apply bitwise operation, and finally convert to int8
        x_trunc = torch.floor(x)
        return torch.bitwise_and(x_trunc.round().to(torch.int32), 0xFF).to(torch.int8)

    def forward(self, x):
        # Convert input to PyTorch tensor if it's not already
        if isinstance(x, np.ndarray):
            x = torch.from_numpy(x)
        
        # Intermediate output dictionnary
        intermediate_outputs = {}

        # Layer 1
        x = F.conv2d(x.float(), self.L1_weight, None, stride=1, padding=0)
        x = self.relu(x)
        intermediate_outputs['conv1'] = x.clone() # Store intermediate result
        
        x = self.pool(x)
        intermediate_outputs['L1_ACC'] = x.clone() # Store intermediate result
        x = self.truncate_to_int8(x) # Simulate int8 truncation
        intermediate_outputs['L1'] = x.clone() # Store intermediate result
        
        # Layer 2
        x = F.conv2d(x.float(), self.L2_weight, None, stride=1, padding=0)
        x = self.relu(x)
        intermediate_outputs['conv2'] = x.clone() # Store intermediate result

        x = self.pool(x)
        intermediate_outputs['L2_ACC'] = x.clone() # Store intermediate result
        x = self.truncate_to_int8(x) # Simulate int8 truncation
        intermediate_outputs['L2'] = x.clone() # Store intermediate result
        
        # Layer 3
        x = F.conv2d(x.float(), self.L3_weight, None, stride=1, padding=0)
        x = self.relu(x)
        intermediate_outputs['conv3'] = x.clone() # Store intermediate result
        
        x = self.truncate_to_int8(x) # Simulate int8 truncation
        intermediate_outputs['L3'] = x.clone() # Store intermediate result
        
        # Classifier section
        x = x.view(-1, 120)
        
        # Layer 4
        x = F.linear(x.float(), self.L4_weight)
        x = self.relu(x)
        intermediate_outputs['L4_ACC'] = x.clone() # Store intermediate result
        x = self.truncate_to_int8(x) # Simulate int8 truncation
        intermediate_outputs['L4'] = x.clone() # Store intermediate result
        
        # Layer 5
        x = F.linear(x.float(), self.L5_weight)
        intermediate_outputs['L5_ACC'] = x.clone() # Store intermediate result
        x = self.truncate_to_int8(x) # Simulate int8 truncation

        return x, intermediate_outputs

if __name__ == '__main__':
    # Generate input data and weights
    input_tensor = np.random.randint(0, 4, size=(1, 1, 32, 32), dtype=np.int8)
    L1_tensor = np.random.randint(0, 4, size=(6, 1, 5, 5), dtype=np.int8)
    L2_tensor = np.random.randint(0, 4, size=(16, 6, 5, 5), dtype=np.int8)
    L3_tensor = np.random.randint(0, 4, size=(120, 16, 5, 5), dtype=np.int8)
    L4_tensor = np.random.randint(0, 4, size=(84, 120, 1, 1), dtype=np.int8)
    L5_tensor = np.random.randint(0, 4, size=(10, 84, 1, 1), dtype=np.int8)

    # Create the model
    model = QuantizedLeNet5(L1_tensor, L2_tensor, L3_tensor, L4_tensor, L5_tensor)

    # Disable gradients for all parameters (inference mode only)
    for param in model.parameters():
        param.requires_grad = False

    print(f"Input tensor:\n{input_tensor}\n\n")
    print(f"Input shape: {input_tensor.shape}")

    # Set the model to evaluation mode
    model.eval()

    output, _ = model(input_tensor)
    print(f"Output tensor:\n{output}\n\n")
    print(f"Output shape: {output.shape}")
    print(f"Output data type: {output.dtype}")
