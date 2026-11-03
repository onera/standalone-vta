import logging
import numpy as np
import onnx
from onnx import numpy_helper
import torch
import torch.nn as nn
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

def verify_onnx(
    py_model: nn.Module,
    qdq_path: str,
    qlinear_path: str,
    loaders: Dict[str, Any],
    num_samples: int = 1000
) -> None:
    """Verifies predictions and calculates differences between PyTorch, ONNX QDQ, and ONNX QLinear models.

    Args:
        py_model: Trained PyTorch model.
        qdq_path: Path to the QDQ ONNX model.
        qlinear_path: Path to the QLinear ONNX model.
        loaders: Data loaders dictionary containing the test set loader.
        num_samples: Number of samples to run verification on.

    Raises:
        ValueError: If the requested sample count is nonpositive or no samples
            are available in the test loader.
    """
    import onnxruntime as ort
    if num_samples <= 0:
        raise ValueError("num_samples must be positive")
    logger.info(f"[verify] Comparing PyTorch, QDQ and QLinear: requested samples={num_samples}")
    
    test_loader = loaders['test']
    ort_sess_qdq = ort.InferenceSession(qdq_path)
    ort_sess_qlinear = ort.InferenceSession(qlinear_path)
    
    # Get QLinear input/output details to handle quantized inputs correctly
    qlinear_input_name: str = ort_sess_qlinear.get_inputs()[0].name
    qlinear_input_type: str = ort_sess_qlinear.get_inputs()[0].type
    
    model_qlinear = onnx.load(qlinear_path)
    
    def get_init_val(name: str) -> Optional[np.ndarray]:
        """Returns an initializer array by name, or None when absent.

        Args:
            name: Initializer name in the QLinear graph.

        Returns:
            Constant array, or None if not found.
        """
        for init in model_qlinear.graph.initializer:
            if init.name == name:
                return numpy_helper.to_array(init)
        return None

    # Get scales and zero points to perform manual quantization and dequantization
    first_node = model_qlinear.graph.node[0]
    last_node = model_qlinear.graph.node[-1]
    
    x_scale = get_init_val(first_node.input[1])
    x_zp = get_init_val(first_node.input[2])
    y_scale = get_init_val(last_node.input[6])
    y_zp = get_init_val(last_node.input[7])

    py_preds: List[int] = []
    qdq_preds: List[int] = []
    qlinear_preds: List[int] = []
    labels_list: List[int] = []
    max_diff_qdq: float = 0.0
    max_diff_qlinear: float = 0.0
    mse_qdq: float = 0.0
    mse_qlinear: float = 0.0
    
    device = next(py_model.parameters()).device
    
    for i, (imgs, labels) in enumerate(test_loader):
        if len(py_preds) >= num_samples:
            break
            
        for b in range(imgs.size(0)):
            if len(py_preds) >= num_samples:
                break
            img = imgs[b:b+1]
            label = labels[b]
            
            with torch.no_grad():
                py_out = py_model(img.to(device)).cpu()
                if py_out.ndim == 4: 
                    py_out = py_out.view(py_out.size(0), -1)
                py_pred = torch.argmax(py_out, dim=1).item()
                py_out_np = py_out.numpy()
                
            qdq_out = ort_sess_qdq.run(None, {ort_sess_qdq.get_inputs()[0].name: img.numpy()})[0]
            if qdq_out.ndim == 4: 
                qdq_out = qdq_out.reshape(qdq_out.shape[0], -1)
            qdq_pred = np.argmax(qdq_out, axis=1)[0]
            
            # Format input for QLinear (perform manual input quantization if input is INT8)
            if "int8" in qlinear_input_type.lower():
                img_q = np.round(img.numpy() / x_scale + x_zp).clip(-128, 127).astype(np.int8)
                qlinear_out_q = ort_sess_qlinear.run(None, {qlinear_input_name: img_q})[0]
                # Manual output dequantization
                qlinear_out = (qlinear_out_q.astype(np.float32) - y_zp) * y_scale
            else:
                qlinear_out = ort_sess_qlinear.run(None, {qlinear_input_name: img.numpy()})[0]

            if qlinear_out.ndim == 4:
                qlinear_out = qlinear_out.reshape(qlinear_out.shape[0], -1)
            qlinear_pred = np.argmax(qlinear_out, axis=1)[0]
            
            diff_qdq = np.abs(py_out_np - qdq_out)
            max_diff_qdq = max(max_diff_qdq, float(np.max(diff_qdq)))
            mse_qdq += float(np.mean(diff_qdq**2))
            
            diff_qlinear = np.abs(py_out_np - qlinear_out)
            max_diff_qlinear = max(max_diff_qlinear, float(np.max(diff_qlinear)))
            mse_qlinear += float(np.mean(diff_qlinear**2))
            
            py_preds.append(py_pred)
            qdq_preds.append(qdq_pred)
            qlinear_preds.append(qlinear_pred)
            labels_list.append(label.item())
        
    actual_samples = len(py_preds)
    if actual_samples == 0:
        raise ValueError("No test samples available for ONNX comparison")
    if actual_samples < num_samples:
        logger.warning(
            f"[verify] Test loader exhausted: requested={num_samples} processed={actual_samples}"
        )
    mse_qdq /= actual_samples
    mse_qlinear /= actual_samples
    labels_np = np.array(labels_list)
    py_acc = np.mean(np.array(py_preds) == labels_np) * 100
    qdq_acc = np.mean(np.array(qdq_preds) == labels_np) * 100
    qlinear_acc = np.mean(np.array(qlinear_preds) == labels_np) * 100
    
    logger.info(f"[verify] Processed samples={actual_samples}")
    logger.info(
        f"[verify] Accuracy: PyTorch={py_acc:.2f}% QDQ={qdq_acc:.2f}% QLinear={qlinear_acc:.2f}%"
    )
    for name, predictions, max_diff, mse in (
        ("QDQ", qdq_preds, max_diff_qdq, mse_qdq),
        ("QLinear", qlinear_preds, max_diff_qlinear, mse_qlinear),
    ):
        match_rate = np.mean(np.array(py_preds) == np.array(predictions)) * 100
        logger.info(
            f"[verify] {name} vs PyTorch: max_abs_diff={max_diff:.6g} "
            f"mse={mse:.6g} prediction_match={match_rate:.2f}%"
        )
    logger.info("[verify] Comparison completed; no numerical acceptance threshold applied")
