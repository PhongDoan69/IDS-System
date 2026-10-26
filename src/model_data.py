from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np


@dataclass
class PreparedArrays:
    """Các array cùng thứ tự sample được sinh ở Phase 2."""

    features: np.ndarray
    binary_labels: np.ndarray
    attack_label_ids: np.ndarray
    split_ids: np.ndarray
    row_hashes: np.ndarray

    def close(self):
        """Windows giữ khóa file khi memmap còn sống; đóng rõ ràng khi hết dùng."""
        for value in self.__dict__.values():
            if isinstance(value, np.memmap) and not value._mmap.closed:
                value._mmap.close()


def load_prepared_arrays(processed_dir: Path, representation_path: Path | None = None) -> PreparedArrays:
    feature_path = representation_path or processed_dir / "features_scaled.npy"
    required = [
        feature_path,
        processed_dir / "binary_labels.npy",
        processed_dir / "attack_label_ids.npy",
        processed_dir / "split_ids.npy",
        processed_dir / "row_hashes.npy",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Thiếu artifacts Phase 2/representation: {missing}")
    arrays = PreparedArrays(
        features=np.load(feature_path, mmap_mode="r"),
        binary_labels=np.load(processed_dir / "binary_labels.npy", mmap_mode="r"),
        attack_label_ids=np.load(processed_dir / "attack_label_ids.npy", mmap_mode="r"),
        split_ids=np.load(processed_dir / "split_ids.npy", mmap_mode="r"),
        row_hashes=np.load(processed_dir / "row_hashes.npy", mmap_mode="r"),
    )
    lengths = {len(array) for array in arrays.__dict__.values()}
    if len(lengths) != 1:
        raise ValueError("Các array Phase 2 không cùng số sample")
    if arrays.features.ndim != 2 or not arrays.features.shape[0] or not arrays.features.shape[1]:
        raise ValueError('Features phải là ma trận không rỗng')
    for name in ['binary_labels', 'attack_label_ids', 'split_ids', 'row_hashes']:
        value = getattr(arrays, name)
        if value.ndim != 1 or not np.issubdtype(value.dtype, np.integer):
            raise ValueError(f'{name} phải là vector integer')
    if not np.isin(arrays.split_ids, [0, 1, 2]).all() or np.any(arrays.attack_label_ids < 0):
        raise ValueError('Split/label ID không hợp lệ')
    if not np.array_equal(arrays.binary_labels, np.asarray(arrays.attack_label_ids) != 0):
        raise ValueError('Binary target không khớp giả định BENIGN=0')
    for start in range(0, len(arrays.features), 100000):
        if not np.isfinite(arrays.features[start:start + 100000]).all():
            raise ValueError('Representation chứa NaN/Inf')
    return arrays


def validate_held_out_label(labels: np.ndarray, label_id: int | None) -> None:
    """LOACO chỉ hợp lệ với một lớp tấn công có thật; BENIGN ID 0 không được held-out."""
    if label_id is None:
        return
    if int(label_id) <= 0:
        raise ValueError("held_out_label_id=0 là BENIGN; LOACO phải giữ lại một lớp tấn công.")
    if not np.any(np.asarray(labels) == int(label_id)):
        raise ValueError(f"held_out_label_id={label_id} không tồn tại trong Phase 2.")


def split_indices(split_ids: np.ndarray, split_id: int, exclude_label_id: int | None = None, labels=None) -> np.ndarray:
    mask = np.asarray(split_ids) == split_id
    if exclude_label_id is not None:
        if labels is None:
            raise ValueError("Cần labels khi exclude_label_id được đặt")
        mask &= np.asarray(labels) != exclude_label_id
    return np.flatnonzero(mask)


def iter_index_batches(
    indices: np.ndarray,
    batch_size: int,
    *,
    shuffle: bool,
    random_state: int,
) -> Iterator[np.ndarray]:
    order = np.asarray(indices, dtype=np.int64)
    if shuffle:
        order = np.random.default_rng(random_state).permutation(order)
    for start in range(0, len(order), batch_size):
        yield order[start : start + batch_size]


def torch_batch(features: np.ndarray, indices: np.ndarray, device, pin_memory: bool = True):
    """Copy một batch liên tục từ memmap rồi mới chuyển GPU để không nạp toàn bộ dữ liệu vào VRAM."""
    import torch

    host = torch.from_numpy(np.asarray(features[indices], dtype=np.float32))
    if pin_memory and device.type == "cuda":
        host = host.pin_memory()
    return host.to(device, non_blocking=device.type == "cuda")


def numpy_batches(features: np.ndarray, indices: np.ndarray, batch_size: int) -> Iterator[np.ndarray]:
    for start in range(0, len(indices), batch_size):
        batch_indices = indices[start : start + batch_size]
        yield np.asarray(features[batch_indices], dtype=np.float32)

