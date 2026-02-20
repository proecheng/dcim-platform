"""
时序Transformer模型

基于专利 S2-TF 步骤实现:
- S2-TF-a: 多维特征输入序列构建
- S2-TF-b: 位置编码和特征嵌入
- S2-TF-c: 多层Transformer编码器
- S2-TF-d: 三个预测头（可转移性/时段/容量）
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Optional
from ..config import TransformerConfig


class PositionalEncoding(nn.Module):
    """
    正弦余弦位置编码 (S2-TF-b)

    PE(pos, 2i) = sin(pos / 10000^(2i/d_model))
    PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))
    """

    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # (1, max_len, d_model)

        self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.pe[:, : x.size(1)]
        return self.dropout(x)


class FeatureEmbedding(nn.Module):
    """
    特征嵌入层 (S2-TF-b)

    将多维时序特征映射至d_model维向量空间
    - 功率值 (连续): 线性变换
    - 时段类型 (离散): Embedding
    - 工作日标签 (二值): Embedding
    - 环境温度 (连续): 线性变换
    """

    def __init__(self, config: TransformerConfig):
        super().__init__()
        self.config = config

        # 连续特征投影（功率 + 温度）
        self.continuous_proj = nn.Linear(2, config.d_model // 2)

        # 离散特征嵌入
        self.period_embedding = nn.Embedding(config.num_period_types, config.d_model // 4)
        self.weekday_embedding = nn.Embedding(2, config.d_model // 4)

        # 最终投影到d_model
        self.output_proj = nn.Linear(config.d_model, config.d_model)
        self.layer_norm = nn.LayerNorm(config.d_model)

    def forward(
        self, power: torch.Tensor, period_type: torch.Tensor, is_weekday: torch.Tensor, temperature: torch.Tensor
    ) -> torch.Tensor:
        # 连续特征 (batch, seq_len, 2)
        continuous = torch.stack([power, temperature], dim=-1)
        cont_embed = self.continuous_proj(continuous)

        # 离散特征
        period_embed = self.period_embedding(period_type)
        weekday_embed = self.weekday_embedding(is_weekday)

        # 拼接所有特征
        combined = torch.cat([cont_embed, period_embed, weekday_embed], dim=-1)

        # 投影并归一化
        output = self.output_proj(combined)
        output = self.layer_norm(output)

        return output


class TransferabilityClassificationHead(nn.Module):
    """可转移性分类头 (S2-TF-d) - 输出二分类概率"""

    def __init__(self, d_model: int, dropout: float = 0.1):
        super().__init__()
        self.classifier = nn.Sequential(
            nn.Linear(d_model, d_model // 2), nn.ReLU(), nn.Dropout(dropout), nn.Linear(d_model // 2, 1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.classifier(x))


class PeriodPredictionHead(nn.Module):
    """转移时段预测头 (S2-TF-d) - 输出各时段概率分布"""

    def __init__(self, d_model: int, num_periods: int, dropout: float = 0.1):
        super().__init__()
        self.predictor = nn.Sequential(
            nn.Linear(d_model, d_model // 2), nn.ReLU(), nn.Dropout(dropout), nn.Linear(d_model // 2, num_periods)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.softmax(self.predictor(x), dim=-1)


class CapacityRegressionHead(nn.Module):
    """转移容量回归头 (S2-TF-d) - 输出可转移功率量"""

    def __init__(self, d_model: int, dropout: float = 0.1):
        super().__init__()
        self.regressor = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, 1),
            nn.ReLU(),  # 功率量必须非负
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.regressor(x)


class LoadTransferabilityTransformer(nn.Module):
    """
    负荷可转移性时序Transformer模型

    完整实现专利 S2-TF 步骤:
    1. 特征嵌入 + 位置编码
    2. 多层Transformer编码器
    3. 三个预测头输出
    """

    def __init__(self, config: Optional[TransformerConfig] = None):
        super().__init__()
        if config is None:
            config = TransformerConfig()
        self.config = config

        # S2-TF-b: 特征嵌入
        self.feature_embedding = FeatureEmbedding(config)

        # S2-TF-b: 位置编码
        self.positional_encoding = PositionalEncoding(
            d_model=config.d_model, max_len=config.max_seq_len, dropout=config.dropout
        )

        # S2-TF-c: Transformer编码器
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.d_model,
            nhead=config.n_heads,
            dim_feedforward=config.d_ff,
            dropout=config.dropout,
            batch_first=True,
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=config.n_layers)

        # S2-TF-d: 三个预测头
        self.transferability_head = TransferabilityClassificationHead(config.d_model, config.dropout)
        self.period_head = PeriodPredictionHead(config.d_model, config.num_period_outputs, config.dropout)
        self.capacity_head = CapacityRegressionHead(config.d_model, config.dropout)

    def forward(
        self,
        power: torch.Tensor,
        period_type: torch.Tensor,
        is_weekday: torch.Tensor,
        temperature: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        前向传播

        Args:
            power: (batch, seq_len) 功率时序
            period_type: (batch, seq_len) 时段类型
            is_weekday: (batch, seq_len) 工作日标志
            temperature: (batch, seq_len) 温度
            mask: (batch, seq_len) 可选的填充掩码
        """
        # S2-TF-b: 嵌入编码
        embedded = self.feature_embedding(power, period_type, is_weekday, temperature)
        encoded = self.positional_encoding(embedded)

        # S2-TF-c: Transformer编码
        if mask is not None:
            transformer_out = self.transformer_encoder(encoded, src_key_padding_mask=mask)
        else:
            transformer_out = self.transformer_encoder(encoded)

        # 全局平均池化获取序列级表示
        if mask is not None:
            mask_expanded = (~mask).unsqueeze(-1).float()
            global_feat = (transformer_out * mask_expanded).sum(dim=1) / mask_expanded.sum(dim=1).clamp(min=1)
        else:
            global_feat = transformer_out.mean(dim=1)

        # S2-TF-d: 三个预测头
        transferability = self.transferability_head(global_feat)
        period_probs = self.period_head(global_feat)
        capacity = self.capacity_head(global_feat)

        return {"transferability": transferability, "period_probs": period_probs, "capacity": capacity}

    def compute_loss(
        self,
        predictions: Dict[str, torch.Tensor],
        targets: Dict[str, torch.Tensor],
        alpha: float = 1.0,
        beta: float = 0.5,
        gamma: float = 0.5,
    ) -> Dict[str, torch.Tensor]:
        """
        计算多任务损失函数 (S2-TF-e)

        L = alpha * L_cls + beta * L_reg + gamma * L_period
        """
        loss_cls = F.binary_cross_entropy(predictions["transferability"], targets["transferability"])

        loss_reg = F.mse_loss(predictions["capacity"], targets["capacity"])

        loss_period = F.cross_entropy(predictions["period_probs"], targets["period_labels"])

        total_loss = alpha * loss_cls + beta * loss_reg + gamma * loss_period

        return {"total": total_loss, "classification": loss_cls, "regression": loss_reg, "period": loss_period}
