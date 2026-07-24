import os
from typing import Dict, Optional, Tuple, Union
from torchvision import datasets, transforms
from torch.utils.data import DataLoader, random_split, Dataset

def get_data_loaders(
    dataset_name: str = "FashionMNIST",
    batch_size: int = 32,
    val_split: float = 0.2,
    image_size: Optional[Union[int, Tuple[int, int]]] = None
) -> Dict[str, DataLoader]:
    """Prepares training, validation, and test DataLoaders for the selected dataset.

    Args:
        dataset_name: The name of the dataset to load ("FashionMNIST", "MNIST", or "ImageNet").
        batch_size: The batch size for DataLoader.
        val_split: Fraction of training dataset to use as validation set.
        image_size: Optional (height, width) tuple or single integer to resize inputs.

    Returns:
        A dictionary containing "train", "valid", and "test" DataLoaders.
        
    Raises:
        ValueError: If the dataset name is not recognized.
    """
    # Define transforms
    transform_list = []
    if image_size is not None:
        if isinstance(image_size, int):
            resize_dim = (image_size, image_size)
        else:
            resize_dim = tuple(image_size)
        transform_list.append(transforms.Resize(resize_dim))
    transform_list.append(transforms.ToTensor())
    transform = transforms.Compose(transform_list)


    if dataset_name == "FashionMNIST":
        full_train_data: Dataset = datasets.FashionMNIST(
            download=True,
            root="datasets",
            train=True,
            transform=transform
        )
        test_data: Dataset = datasets.FashionMNIST(
            download=True,
            root="datasets",
            train=False,
            transform=transform
        )
    elif dataset_name == "MNIST":
        full_train_data = datasets.MNIST(
            download=True,
            root="datasets",
            train=True,
            transform=transform
        )
        test_data = datasets.MNIST(
            download=True,
            root="datasets",
            train=False,
            transform=transform
        )
    elif dataset_name == "ImageNet":
        imagenet_root: str = "datasets/imagenet"
        transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        
        if os.path.exists(imagenet_root) and any(os.path.exists(os.path.join(imagenet_root, s)) for s in ["train", "val"]):
            full_train_data = datasets.ImageNet(
                root=imagenet_root,
                split='train',
                transform=transform
            )
            test_data = datasets.ImageNet(
                root=imagenet_root,
                split='val',
                transform=transform
            )
        else:
            print("⚠️ ImageNet directory not found at datasets/imagenet or empty. Falling back to synthetic FakeData for testing.")
            full_train_data = datasets.FakeData(
                size=200,
                image_size=(3, 224, 224),
                num_classes=1000,
                transform=transform
            )
            test_data = datasets.FakeData(
                size=100,
                image_size=(3, 224, 224),
                num_classes=1000,
                transform=transform
            )
    else:
        raise ValueError(f"Unrecognized dataset_name: {dataset_name}. Must be 'FashionMNIST', 'MNIST', or 'ImageNet'.")

    val_size: int = int(len(full_train_data) * val_split)
    train_size: int = len(full_train_data) - val_size
    train_data, val_data = random_split(full_train_data, [train_size, val_size])

    train_loader = DataLoader(train_data, batch_size=batch_size, shuffle=True)
    valid_loader = DataLoader(val_data, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_data, batch_size=batch_size, shuffle=False)

    data_loaders: Dict[str, DataLoader] = {
        "train": train_loader,
        "valid": valid_loader,
        "test": test_loader
    }
    
    return data_loaders
