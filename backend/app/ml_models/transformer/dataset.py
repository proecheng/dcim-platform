"""
负荷时序数据集

用于时序Transformer模型的训练和推理
- 采集目标设备或回路的历史负荷时序数据
- 时间粒度为15分钟
- 历史长度至少包含30天的完整数据
"""

import torch
import numpy as np
from torch.utils.data import Dataset
from typing import Dict, Optional, Tuple


class LoadTimeSeriesDataset(Dataset):
    """
    负荷时序数据集 (S2-TF-a)

    构建输入序列 X = [x1, x2, ..., xT]
    每个时刻的特征向量 xt 包含:
    - 功率值 (kW)
    - 时段类型标签 (尖峰/高峰/平段/低谷/深谷)
    - 是否工作日标签 (0/1)
    - 环境温度
    """

    def __init__(
        self,
        power_data: np.ndarray,  # (N, T) 功率时序
        period_types: np.ndarray,  # (N, T) 时段类型
        is_weekday: np.ndarray,  # (N, T) 工作日标志
        temperature: np.ndarray,  # (N, T) 温度
        labels: Optional[Dict[str, np.ndarray]] = None,
        max_seq_len: int = 2880,
        normalize: bool = True,
    ):
        """
        Args:
            power_data: 功率数据 shape (num_samples, seq_len)
            period_types: 时段类型索引 shape (num_samples, seq_len)
            is_weekday: 工作日标志 shape (num_samples, seq_len)
            temperature: 温度数据 shape (num_samples, seq_len)
            labels: 标签字典，包含 transferability, capacity, period_labels
            max_seq_len: 最大序列长度
            normalize: 是否归一化连续特征
        """
        self.max_seq_len = max_seq_len
        self.normalize = normalize

        # 截断或填充至max_seq_len
        self.power = self._pad_or_truncate(power_data)
        self.period_types = self._pad_or_truncate(period_types, pad_value=0)
        self.is_weekday = self._pad_or_truncate(is_weekday, pad_value=0)
        self.temperature = self._pad_or_truncate(temperature)

        # 生成有效位置掩码
        actual_lens = np.minimum(
            np.array([p.shape[-1] for p in [power_data]] * len(power_data))
            if power_data.ndim == 1
            else np.full(len(power_data), power_data.shape[-1]),
            max_seq_len,
        )
        self.masks = np.zeros((len(power_data), max_seq_len), dtype=bool)
        for i, length in enumerate(actual_lens):
            self.masks[i, length:] = True  # True表示被mask的位置

        # 归一化
        if normalize:
            self.power_mean = self.power[~self.masks].mean() if (~self.masks).any() else 0
            self.power_std = self.power[~self.masks].std() if (~self.masks).any() else 1
            self.temp_mean = self.temperature[~self.masks].mean() if (~self.masks).any() else 0
            self.temp_std = self.temperature[~self.masks].std() if (~self.masks).any() else 1

            self.power_std = max(self.power_std, 1e-6)
            self.temp_std = max(self.temp_std, 1e-6)

        # 标签
        self.labels = labels

    def _pad_or_truncate(self, data: np.ndarray, pad_value: float = 0.0) -> np.ndarray:
        """填充或截断序列至max_seq_len"""
        if data.ndim == 1:
            data = data.reshape(1, -1)

        n, t = data.shape
        if t >= self.max_seq_len:
            return data[:, : self.max_seq_len]
        else:
            padded = np.full((n, self.max_seq_len), pad_value, dtype=data.dtype)
            padded[:, :t] = data
            return padded

    def __len__(self) -> int:
        return len(self.power)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        # 功率（归一化）
        power = self.power[idx].astype(np.float32)
        if self.normalize:
            power = (power - self.power_mean) / self.power_std

        # 温度（归一化）
        temp = self.temperature[idx].astype(np.float32)
        if self.normalize:
            temp = (temp - self.temp_mean) / self.temp_std

        item = {
            "power": torch.from_numpy(power),
            "period_type": torch.from_numpy(self.period_types[idx].astype(np.int64)),
            "is_weekday": torch.from_numpy(self.is_weekday[idx].astype(np.int64)),
            "temperature": torch.from_numpy(temp),
            "mask": torch.from_numpy(self.masks[idx]),
        }

        if self.labels is not None:
            item["transferability"] = torch.tensor(self.labels["transferability"][idx], dtype=torch.float32).unsqueeze(
                0
            )
            item["capacity"] = torch.tensor(self.labels["capacity"][idx], dtype=torch.float32).unsqueeze(0)
            item["period_labels"] = torch.tensor(self.labels["period_labels"][idx], dtype=torch.long)

        return item


def generate_synthetic_dataset(
    num_samples: int = 200,
    seq_len: int = 672,  # 7天 * 96个15分钟
    seed: int = 42,
) -> Tuple[LoadTimeSeriesDataset, LoadTimeSeriesDataset]:
    """
    生成合成训练数据集 (用于模型初始训练)

    模拟不同类型的负荷模式：
    - 可转移负荷：有明显的峰谷特征，如空调、水泵
    - 不可转移负荷：关键生产设备，无法移动

    Returns:
        (train_dataset, val_dataset) 训练集和验证集
    """
    rng = np.random.RandomState(seed)

    power_data = np.zeros((num_samples, seq_len), dtype=np.float32)
    period_types = np.zeros((num_samples, seq_len), dtype=np.int64)
    is_weekday_data = np.zeros((num_samples, seq_len), dtype=np.int64)
    temperature_data = np.zeros((num_samples, seq_len), dtype=np.float32)

    transferability_labels = np.zeros(num_samples, dtype=np.float32)
    capacity_labels = np.zeros(num_samples, dtype=np.float32)
    period_labels = np.zeros(num_samples, dtype=np.int64)

    for i in range(num_samples):
        # 基础负荷
        base_power = rng.uniform(50, 500)

        # 时段类型分配 (每天96个点)
        for day in range(seq_len // 96):
            day_start = day * 96
            for t in range(96):
                hour = t * 0.25
                # 时段划分: 0=尖峰 1=高峰 2=平段 3=低谷 4=深谷
                if 10 <= hour < 12 or 14 <= hour < 16:
                    period_types[i, day_start + t] = 0  # 尖峰
                elif 8 <= hour < 10 or 12 <= hour < 14 or 16 <= hour < 18:
                    period_types[i, day_start + t] = 1  # 高峰
                elif 6 <= hour < 8 or 18 <= hour < 22:
                    period_types[i, day_start + t] = 2  # 平段
                elif 22 <= hour or hour < 4:
                    period_types[i, day_start + t] = 3  # 低谷
                else:
                    period_types[i, day_start + t] = 4  # 深谷

                # 工作日
                is_weekday_data[i, day_start + t] = 1 if day % 7 < 5 else 0

                # 温度模式
                temperature_data[i, day_start + t] = 25 + 5 * np.sin(2 * np.pi * hour / 24) + rng.normal(0, 1)

        # 生成负荷模式
        is_transferable = rng.random() > 0.4  # 60%可转移

        if is_transferable:
            # 可转移负荷：高峰时段功率高，有明显波动
            for t in range(seq_len):
                pt = period_types[i, t]
                if pt in [0, 1]:  # 尖峰/高峰
                    power_data[i, t] = base_power * (1.2 + 0.3 * rng.random())
                elif pt == 2:  # 平段
                    power_data[i, t] = base_power * (0.8 + 0.2 * rng.random())
                else:  # 低谷/深谷
                    power_data[i, t] = base_power * (0.3 + 0.2 * rng.random())
                power_data[i, t] += rng.normal(0, base_power * 0.05)

            transferability_labels[i] = 1.0
            capacity_labels[i] = base_power * rng.uniform(0.2, 0.5)
            period_labels[i] = rng.choice([3, 4])  # 建议转到低谷/深谷
        else:
            # 不可转移负荷：相对平稳
            for t in range(seq_len):
                power_data[i, t] = base_power * (0.9 + 0.2 * rng.random())
                power_data[i, t] += rng.normal(0, base_power * 0.03)

            transferability_labels[i] = 0.0
            capacity_labels[i] = 0.0
            period_labels[i] = 2  # 平段（无需转移）

    # 确保功率非负
    power_data = np.maximum(power_data, 0)

    # 分割训练/验证集
    split_idx = int(num_samples * 0.8)

    labels_train = {
        "transferability": transferability_labels[:split_idx],
        "capacity": capacity_labels[:split_idx],
        "period_labels": period_labels[:split_idx],
    }
    labels_val = {
        "transferability": transferability_labels[split_idx:],
        "capacity": capacity_labels[split_idx:],
        "period_labels": period_labels[split_idx:],
    }

    train_dataset = LoadTimeSeriesDataset(
        power_data[:split_idx],
        period_types[:split_idx],
        is_weekday_data[:split_idx],
        temperature_data[:split_idx],
        labels=labels_train,
        max_seq_len=seq_len,
    )

    val_dataset = LoadTimeSeriesDataset(
        power_data[split_idx:],
        period_types[split_idx:],
        is_weekday_data[split_idx:],
        temperature_data[split_idx:],
        labels=labels_val,
        max_seq_len=seq_len,
    )

    return train_dataset, val_dataset
