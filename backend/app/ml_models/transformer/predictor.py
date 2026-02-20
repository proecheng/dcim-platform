"""
时序Transformer预测服务

提供可转移负荷识别的推理和训练接口
集成至峰谷套利模板的收益计算 (S2-TF-f)
"""

import logging
import torch
import numpy as np
from typing import Dict, List, Optional, Any
from torch.utils.data import DataLoader

from .model import LoadTransferabilityTransformer
from .dataset import LoadTimeSeriesDataset, generate_synthetic_dataset
from ..config import MLConfig

logger = logging.getLogger(__name__)


class TransferabilityPredictor:
    """
    可转移负荷预测服务

    功能:
    1. 模型加载/初始化
    2. 负荷可转移性推理
    3. 与收益计算集成
    4. 模型训练（使用合成数据或真实数据）
    """

    def __init__(self, config: Optional[MLConfig] = None):
        if config is None:
            config = MLConfig()
        self.config = config
        self.tf_config = config.transformer
        self.device = torch.device(config.device)

        # 初始化模型
        self.model = LoadTransferabilityTransformer(self.tf_config).to(self.device)
        self.model.eval()

        # 尝试加载预训练权重
        self._load_checkpoint()

        self._is_trained = False

    def _load_checkpoint(self) -> bool:
        """加载模型检查点"""
        ckpt_path = self.config.get_checkpoint_path("transformer")
        if ckpt_path.exists():
            try:
                state_dict = torch.load(ckpt_path, map_location=self.device, weights_only=True)
                self.model.load_state_dict(state_dict)
                self._is_trained = True
                logger.info(f"Transformer模型检查点已加载: {ckpt_path}")
                return True
            except Exception as e:
                logger.warning(f"加载检查点失败: {e}")
        return False

    def _save_checkpoint(self):
        """保存模型检查点"""
        ckpt_path = self.config.get_checkpoint_path("transformer")
        ckpt_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.model.state_dict(), ckpt_path)
        logger.info(f"Transformer模型已保存: {ckpt_path}")

    @torch.no_grad()
    def predict(
        self, power_series: np.ndarray, period_types: np.ndarray, is_weekday: np.ndarray, temperature: np.ndarray
    ) -> Dict[str, Any]:
        """
        预测负荷可转移性 (S2-TF-d)

        Args:
            power_series: (seq_len,) 或 (batch, seq_len) 功率时序
            period_types: 同上, 时段类型
            is_weekday: 同上, 工作日标志
            temperature: 同上, 温度

        Returns:
            Dict包含:
            - transferability: 可转移性概率
            - best_period: 最优转移时段索引
            - period_probs: 各时段概率分布
            - capacity_kw: 预测可转移容量(kW)
        """
        self.model.eval()

        # 确保batch维度
        if power_series.ndim == 1:
            power_series = power_series.reshape(1, -1)
            period_types = period_types.reshape(1, -1)
            is_weekday = is_weekday.reshape(1, -1)
            temperature = temperature.reshape(1, -1)

        # 创建临时数据集用于预处理
        dataset = LoadTimeSeriesDataset(
            power_series,
            period_types,
            is_weekday,
            temperature,
            max_seq_len=min(power_series.shape[1], self.tf_config.max_seq_len),
        )

        results = []
        for i in range(len(dataset)):
            item = dataset[i]

            # 转到设备
            power = item["power"].unsqueeze(0).to(self.device)
            pt = item["period_type"].unsqueeze(0).to(self.device)
            wd = item["is_weekday"].unsqueeze(0).to(self.device)
            temp = item["temperature"].unsqueeze(0).to(self.device)
            mask = item["mask"].unsqueeze(0).to(self.device)

            # 推理
            output = self.model(power, pt, wd, temp, mask)

            transferability = output["transferability"].cpu().numpy()[0, 0]
            period_probs = output["period_probs"].cpu().numpy()[0]
            capacity = output["capacity"].cpu().numpy()[0, 0]

            # 反归一化容量（如果模型归一化了）
            if dataset.normalize:
                capacity = capacity * dataset.power_std + dataset.power_mean
                capacity = max(0, capacity)

            period_names = ["尖峰", "高峰", "平段", "低谷", "深谷"]
            best_period_idx = int(np.argmax(period_probs))

            results.append(
                {
                    "transferability": float(transferability),
                    "is_transferable": bool(transferability > 0.5),
                    "best_period": best_period_idx,
                    "best_period_name": period_names[best_period_idx],
                    "period_probs": {name: float(prob) for name, prob in zip(period_names, period_probs)},
                    "capacity_kw": float(capacity),
                    "confidence": float(max(transferability, 1 - transferability)),
                }
            )

        if len(results) == 1:
            return results[0]
        return {"predictions": results}

    def calculate_peak_valley_saving(
        self, predictions: List[Dict[str, Any]], price_diff: float, shift_hours: float = 2.0, working_days: int = 250
    ) -> Dict[str, Any]:
        """
        峰谷套利收益计算集成 (S2-TF-f)

        修正后的收益公式:
        年节省金额 = sum(p_transferable_i * P_transfer_i * dt_i) * price_diff * N_days

        Args:
            predictions: predict()方法的输出列表
            price_diff: 峰谷电价差 (元/kWh)
            shift_hours: 每日转移时长 (小时)
            working_days: 年工作日数

        Returns:
            收益计算详情
        """
        total_weighted_capacity = 0.0
        transferable_loads = []

        for pred in predictions:
            p_trans = pred["transferability"]
            capacity = pred["capacity_kw"]

            if p_trans > 0.3:  # 最低阈值过滤
                weighted = p_trans * capacity
                total_weighted_capacity += weighted
                transferable_loads.append(
                    {
                        "transferability": p_trans,
                        "capacity_kw": capacity,
                        "weighted_capacity": weighted,
                        "best_period": pred["best_period_name"],
                    }
                )

        # 年节省金额
        daily_energy = total_weighted_capacity * shift_hours  # kWh
        daily_saving = daily_energy * price_diff
        annual_saving = daily_saving * working_days

        return {
            "annual_saving_yuan": round(annual_saving, 2),
            "daily_saving_yuan": round(daily_saving, 2),
            "total_weighted_capacity_kw": round(total_weighted_capacity, 2),
            "transferable_load_count": len(transferable_loads),
            "transferable_loads": transferable_loads,
            "calculation_formula": {
                "formula": "annual_saving = sum(p_i * P_i) * shift_hours * price_diff * working_days",
                "params": {
                    "sum_weighted_capacity": round(total_weighted_capacity, 2),
                    "shift_hours": shift_hours,
                    "price_diff": price_diff,
                    "working_days": working_days,
                },
            },
            "data_trace": {
                "model": "LoadTransferabilityTransformer",
                "model_type": "Time-series Transformer with Multi-head Attention",
                "prediction_source": "deep_learning_inference",
            },
        }

    def train(
        self,
        train_dataset: Optional[LoadTimeSeriesDataset] = None,
        val_dataset: Optional[LoadTimeSeriesDataset] = None,
        epochs: int = 50,
        batch_size: int = 16,
        learning_rate: float = 1e-3,
    ) -> Dict[str, List[float]]:
        """
        训练Transformer模型 (S2-TF-e)

        Args:
            train_dataset: 训练集 (None则使用合成数据)
            val_dataset: 验证集
            epochs: 训练轮数
            batch_size: 批次大小
            learning_rate: 学习率

        Returns:
            训练历史 (各损失值)
        """
        # 使用合成数据集或提供的数据集
        if train_dataset is None:
            logger.info("使用合成数据进行初始训练")
            train_dataset, val_dataset = generate_synthetic_dataset()

        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size) if val_dataset else None

        optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

        history = {"train_loss": [], "val_loss": []}

        self.model.train()
        for epoch in range(epochs):
            epoch_loss = 0.0
            batch_count = 0

            for batch in train_loader:
                # 移到设备
                power = batch["power"].to(self.device)
                period_type = batch["period_type"].to(self.device)
                is_weekday = batch["is_weekday"].to(self.device)
                temperature = batch["temperature"].to(self.device)
                mask = batch["mask"].to(self.device)

                targets = {
                    "transferability": batch["transferability"].to(self.device),
                    "capacity": batch["capacity"].to(self.device),
                    "period_labels": batch["period_labels"].to(self.device),
                }

                # 前向传播
                predictions = self.model(power, period_type, is_weekday, temperature, mask)
                losses = self.model.compute_loss(predictions, targets)

                # 反向传播
                optimizer.zero_grad()
                losses["total"].backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                optimizer.step()

                epoch_loss += losses["total"].item()
                batch_count += 1

            scheduler.step()
            avg_loss = epoch_loss / max(batch_count, 1)
            history["train_loss"].append(avg_loss)

            # 验证
            if val_loader:
                val_loss = self._validate(val_loader)
                history["val_loss"].append(val_loss)

            if (epoch + 1) % 10 == 0:
                msg = f"Epoch {epoch+1}/{epochs}, Train Loss: {avg_loss:.4f}"
                if val_loader:
                    msg += f", Val Loss: {history['val_loss'][-1]:.4f}"
                logger.info(msg)

        self._is_trained = True
        self._save_checkpoint()

        return history

    @torch.no_grad()
    def _validate(self, val_loader: DataLoader) -> float:
        """验证集评估"""
        self.model.eval()
        total_loss = 0.0
        batch_count = 0

        for batch in val_loader:
            power = batch["power"].to(self.device)
            period_type = batch["period_type"].to(self.device)
            is_weekday = batch["is_weekday"].to(self.device)
            temperature = batch["temperature"].to(self.device)
            mask = batch["mask"].to(self.device)

            targets = {
                "transferability": batch["transferability"].to(self.device),
                "capacity": batch["capacity"].to(self.device),
                "period_labels": batch["period_labels"].to(self.device),
            }

            predictions = self.model(power, period_type, is_weekday, temperature, mask)
            losses = self.model.compute_loss(predictions, targets)
            total_loss += losses["total"].item()
            batch_count += 1

        self.model.train()
        return total_loss / max(batch_count, 1)

    @property
    def is_trained(self) -> bool:
        return self._is_trained
