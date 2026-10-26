"""Kiểm tra nội dung trước khi dùng artifact; không sửa, clip hay chuẩn hóa dữ liệu lỗi."""
from __future__ import annotations

import numpy as np


def finite_vector(values, name: str, length: int | None = None) -> np.ndarray:
    array = np.asarray(values)
    if array.ndim != 1 or (length is not None and len(array) != length):
        raise ValueError(f'{name}: cần vector một chiều đúng số dòng')
    if not np.issubdtype(array.dtype, np.number) or not np.isfinite(array).all():
        raise ValueError(f'{name}: chứa NaN/Inf hoặc không phải số')
    return array


def probability_vector(values, name='P_attack', length=None):
    array = finite_vector(values, name, length)
    if np.any((array < 0) | (array > 1)):
        raise ValueError(f'{name}: xác suất phải thuộc [0,1]')
    return array


def probability_matrix(values, class_ids, length=None, held_out=None):
    classes = finite_vector(class_ids, 'class_ids')
    if not np.issubdtype(classes.dtype, np.integer) or not len(classes):
        raise ValueError('class_ids phải là vector số nguyên không rỗng')
    if len(np.unique(classes)) != len(classes) or np.any(classes <= 0):
        raise ValueError('Stage 2 phải có ID attack duy nhất, không BENIGN/UNKNOWN')
    if held_out is not None and held_out in classes:
        raise ValueError('Stage 2 còn held-out class')
    array = np.asarray(values)
    if array.ndim != 2 or array.shape[1] != len(classes) or (length is not None and len(array) != length):
        raise ValueError('Stage 2 probability shape không khớp rows/class_ids')
    if not np.isfinite(array).all() or np.any((array < 0) | (array > 1)):
        raise ValueError('Stage 2 probability chứa NaN/Inf hoặc ngoài [0,1]')
    if not np.allclose(array.sum(axis=1), 1, atol=1e-5, rtol=0):
        raise ValueError('Tổng xác suất Stage 2 mỗi hàng khác 1')
    return array


def exact_indices(actual, expected, name='indices'):
    actual = np.asarray(actual)
    if actual.ndim != 1 or not np.issubdtype(actual.dtype, np.integer) or not np.array_equal(actual, expected):
        raise ValueError(f'{name}: không khớp index/order của split được phép')


def assert_new_outputs(*paths):
    """Từ chối cả output dở dang. Không xóa hoặc resume ngầm một run."""
    from pathlib import Path
    candidates = [Path(p) for p in paths]
    # Một file đã mất nhưng sidecar còn lại vẫn là lịch sử của run cũ.
    candidates += [p.with_name(p.name + '.contract.json') for p in candidates]
    existing = sorted({str(p) for p in candidates if p.exists()})
    if existing:
        raise FileExistsError(f'Không ghi đè artifact; chọn run-id/output mới: {existing}')
