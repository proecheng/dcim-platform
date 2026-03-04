# 后端数据模型文档

生成时间: 2026-03-01  
项目版本: V3.2.1  
ORM 框架: SQLAlchemy 2.0 (异步)

## 概述

DCIM 后端使用 SQLAlchemy 2.0 异步 ORM，定义了 29 个数据模型文件，涵盖 100+ 个数据表。所有模型继承自 Base 类，支持异步数据库操作。

数据库: SQLite (开发) / PostgreSQL (生产)  
异步驱动: aiosqlite (SQLite) / asyncpg (PostgreSQL)

## 核心模型总览

| 模型文件 | 表数量 | 核心表 |
|---------|-------|--------|
| user.py | 5 | User, RolePermission, UserSession, UserSite |
| device.py | 1 | Device |
| point.py | 3 | Point, PointRealtime, PointHistory |
| alarm.py | 4 | AlarmThreshold, Alarm, AlarmRule, AlarmShield |
| energy.py | 15 | PowerDevice, EnergyDaily, PUEHistory, Transformer |
| asset.py | 5 | Asset, Cabinet, AssetLifecycle |
| capacity.py | 4 | CapacityMonitor, CapacityTrend |
| operation.py | 6 | WorkOrder, Inspection, Knowledge |

## 数据库关系图

设备 (Device) 1:N 点位 (Point)  
点位 (Point) 1:N 告警阈值 (AlarmThreshold)  
点位 (Point) 1:N 告警记录 (Alarm)  
用电设备 (PowerDevice) 自关联树形结构  
变压器 (Transformer) 1:N 电表 (MeterPoint) 1:N 配电柜 (DistributionPanel) 1:N 回路 (DistributionCircuit)  
机柜 (Cabinet) 1:N 资产 (Asset)  
用户 (User) M:N 站点 (Site) 通过 UserSite

## 更新记录

2026-03-01: 初始版本，涵盖 V3.2.1 所有 29 个模型文件
