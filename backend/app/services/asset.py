"""
资产管理服务
Asset Management Service

提供资产、机柜、维护、盘点等管理功能
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from ..models.asset import (
    Asset, Cabinet, AssetLifecycle, MaintenanceRecord,
    AssetInventory, AssetInventoryItem, AssetStatus, AssetType
)
from ..schemas.asset import (
    CabinetCreate, CabinetUpdate,
    AssetCreate, AssetUpdate,
    MaintenanceCreate,
    InventoryCreate, InventoryItemUpdate,
    AssetStatistics
)


class AssetService:
    """资产管理服务"""

    def __init__(self, db: Session):
        """
        初始化资产服务

        Args:
            db: SQLAlchemy 数据库会话
        """
        self.db = db

    # ==================== 机柜管理 ====================

    def get_cabinets(self, skip: int = 0, limit: int = 100) -> List[Cabinet]:
        """
        获取机柜列表

        Args:
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            机柜列表
        """
        return self.db.query(Cabinet).offset(skip).limit(limit).all()

    def get_cabinet(self, cabinet_id: int) -> Optional[Cabinet]:
        """
        根据ID获取机柜

        Args:
            cabinet_id: 机柜ID

        Returns:
            机柜对象或None
        """
        return self.db.query(Cabinet).filter(Cabinet.id == cabinet_id).first()

    def get_cabinet_by_code(self, cabinet_code: str) -> Optional[Cabinet]:
        """
        根据编码获取机柜

        Args:
            cabinet_code: 机柜编码

        Returns:
            机柜对象或None
        """
        return self.db.query(Cabinet).filter(Cabinet.cabinet_code == cabinet_code).first()

    def create_cabinet(self, data: CabinetCreate) -> Cabinet:
        """
        创建机柜

        Args:
            data: 机柜创建数据

        Returns:
            创建的机柜对象
        """
        cabinet = Cabinet(**data.model_dump())
        self.db.add(cabinet)
        self.db.commit()
        self.db.refresh(cabinet)
        return cabinet

    def update_cabinet(self, cabinet_id: int, data: CabinetUpdate) -> Optional[Cabinet]:
        """
        更新机柜

        Args:
            cabinet_id: 机柜ID
            data: 机柜更新数据

        Returns:
            更新后的机柜对象或None
        """
        cabinet = self.get_cabinet(cabinet_id)
        if not cabinet:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(cabinet, key, value)

        cabinet.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(cabinet)
        return cabinet

    def delete_cabinet(self, cabinet_id: int) -> bool:
        """
        删除机柜

        Args:
            cabinet_id: 机柜ID

        Returns:
            是否删除成功
        """
        cabinet = self.get_cabinet(cabinet_id)
        if not cabinet:
            return False

        # 检查是否有关联资产
        asset_count = self.db.query(func.count(Asset.id)).filter(
            Asset.cabinet_id == cabinet_id
        ).scalar()
        if asset_count > 0:
            return False

        self.db.delete(cabinet)
        self.db.commit()
        return True

    def get_cabinet_u_usage(self, cabinet_id: int) -> Dict[str, Any]:
        """
        获取机柜U位使用情况

        Args:
            cabinet_id: 机柜ID

        Returns:
            包含total_u, used_u, available_u, usage_rate, u_map的字典
        """
        cabinet = self.get_cabinet(cabinet_id)
        if not cabinet:
            return {
                "total_u": 0,
                "used_u": 0,
                "available_u": 0,
                "usage_rate": 0,
                "u_map": {}
            }

        total_u = cabinet.total_u or 42

        # 获取该机柜中所有资产
        assets = self.db.query(Asset).filter(
            Asset.cabinet_id == cabinet_id,
            Asset.u_position.isnot(None),
            Asset.u_height.isnot(None)
        ).all()

        # 构建U位映射表
        u_map = {}
        used_u = 0

        for asset in assets:
            if asset.u_position and asset.u_height:
                for u in range(asset.u_position, asset.u_position + asset.u_height):
                    if u <= total_u:
                        u_map[u] = {
                            "asset_id": asset.id,
                            "asset_code": asset.asset_code,
                            "asset_name": asset.asset_name,
                            "asset_type": asset.asset_type.value if asset.asset_type else None
                        }
                used_u += asset.u_height

        available_u = total_u - used_u
        usage_rate = round((used_u / total_u * 100), 2) if total_u > 0 else 0

        return {
            "total_u": total_u,
            "used_u": used_u,
            "available_u": available_u,
            "usage_rate": usage_rate,
            "u_map": u_map
        }

    # ==================== 资产管理 ====================

    def get_assets(
        self,
        skip: int = 0,
        limit: int = 100,
        asset_type: Optional[AssetType] = None,
        status: Optional[AssetStatus] = None,
        cabinet_id: Optional[int] = None,
        keyword: Optional[str] = None
    ) -> List[Asset]:
        """
        获取资产列表

        Args:
            skip: 跳过记录数
            limit: 返回记录数
            asset_type: 资产类型筛选
            status: 状态筛选
            cabinet_id: 机柜ID筛选
            keyword: 关键词搜索(资产编码、名称、品牌、型号)

        Returns:
            资产列表
        """
        query = self.db.query(Asset)

        conditions = []
        if asset_type:
            conditions.append(Asset.asset_type == asset_type)
        if status:
            conditions.append(Asset.status == status)
        if cabinet_id:
            conditions.append(Asset.cabinet_id == cabinet_id)
        if keyword:
            keyword_filter = or_(
                Asset.asset_code.contains(keyword),
                Asset.asset_name.contains(keyword),
                Asset.brand.contains(keyword),
                Asset.model.contains(keyword)
            )
            conditions.append(keyword_filter)

        if conditions:
            query = query.filter(and_(*conditions))

        return query.order_by(Asset.created_at.desc()).offset(skip).limit(limit).all()

    def get_asset(self, asset_id: int) -> Optional[Asset]:
        """
        根据ID获取资产

        Args:
            asset_id: 资产ID

        Returns:
            资产对象或None
        """
        return self.db.query(Asset).filter(Asset.id == asset_id).first()

    def get_asset_by_code(self, asset_code: str) -> Optional[Asset]:
        """
        根据编码获取资产

        Args:
            asset_code: 资产编码

        Returns:
            资产对象或None
        """
        return self.db.query(Asset).filter(Asset.asset_code == asset_code).first()

    def create_asset(self, data: AssetCreate, operator: Optional[str] = None) -> Asset:
        """
        创建资产

        Args:
            data: 资产创建数据
            operator: 操作人

        Returns:
            创建的资产对象
        """
        asset = Asset(**data.model_dump())
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)

        # 添加生命周期记录
        to_location = None
        if asset.cabinet_id:
            cabinet = self.get_cabinet(asset.cabinet_id)
            if cabinet:
                to_location = f"{cabinet.cabinet_name} U{asset.u_position}" if asset.u_position else cabinet.cabinet_name

        self._add_lifecycle(
            asset_id=asset.id,
            action="purchase",
            operator=operator,
            from_location=None,
            to_location=to_location,
            remark="资产创建入库"
        )

        return asset

    def update_asset(
        self,
        asset_id: int,
        data: AssetUpdate,
        operator: Optional[str] = None
    ) -> Optional[Asset]:
        """
        更新资产

        Args:
            asset_id: 资产ID
            data: 资产更新数据
            operator: 操作人

        Returns:
            更新后的资产对象或None
        """
        asset = self.get_asset(asset_id)
        if not asset:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # 记录位置变更
        old_cabinet_id = asset.cabinet_id
        old_u_position = asset.u_position
        new_cabinet_id = update_data.get("cabinet_id", old_cabinet_id)
        new_u_position = update_data.get("u_position", old_u_position)

        location_changed = (old_cabinet_id != new_cabinet_id) or (old_u_position != new_u_position)

        # 记录状态变更
        old_status = asset.status
        new_status = update_data.get("status", old_status)
        status_changed = old_status != new_status

        # 更新资产属性
        for key, value in update_data.items():
            if value is not None:
                setattr(asset, key, value)

        asset.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(asset)

        # 添加位置变更生命周期记录
        if location_changed:
            from_location = None
            to_location = None

            if old_cabinet_id:
                old_cabinet = self.get_cabinet(old_cabinet_id)
                if old_cabinet:
                    from_location = f"{old_cabinet.cabinet_name} U{old_u_position}" if old_u_position else old_cabinet.cabinet_name

            if new_cabinet_id:
                new_cabinet = self.get_cabinet(new_cabinet_id)
                if new_cabinet:
                    to_location = f"{new_cabinet.cabinet_name} U{new_u_position}" if new_u_position else new_cabinet.cabinet_name

            self._add_lifecycle(
                asset_id=asset_id,
                action="move",
                operator=operator,
                from_location=from_location,
                to_location=to_location,
                remark="资产位置变更"
            )

        # 添加状态变更生命周期记录
        if status_changed:
            action = "status_change"
            remark = f"状态变更: {old_status.value if old_status else 'None'} -> {new_status.value if new_status else 'None'}"

            if new_status == AssetStatus.scrapped:
                action = "scrap"
                remark = "资产报废"
            elif new_status == AssetStatus.maintenance:
                action = "maintain"
                remark = "资产送修"
            elif new_status == AssetStatus.in_use:
                action = "deploy"
                remark = "资产部署上线"

            self._add_lifecycle(
                asset_id=asset_id,
                action=action,
                operator=operator,
                from_location=None,
                to_location=None,
                remark=remark
            )

        return asset

    def delete_asset(self, asset_id: int) -> bool:
        """
        删除资产

        Args:
            asset_id: 资产ID

        Returns:
            是否删除成功
        """
        asset = self.get_asset(asset_id)
        if not asset:
            return False

        # 删除关联的生命周期记录
        self.db.query(AssetLifecycle).filter(AssetLifecycle.asset_id == asset_id).delete()

        # 删除关联的维护记录
        self.db.query(MaintenanceRecord).filter(MaintenanceRecord.asset_id == asset_id).delete()

        # 删除关联的盘点明细
        self.db.query(AssetInventoryItem).filter(AssetInventoryItem.asset_id == asset_id).delete()

        self.db.delete(asset)
        self.db.commit()
        return True

    def get_asset_lifecycle(self, asset_id: int) -> List[AssetLifecycle]:
        """
        获取资产生命周期记录

        Args:
            asset_id: 资产ID

        Returns:
            生命周期记录列表
        """
        return self.db.query(AssetLifecycle).filter(
            AssetLifecycle.asset_id == asset_id
        ).order_by(AssetLifecycle.action_date.desc()).all()

    def _add_lifecycle(
        self,
        asset_id: int,
        action: str,
        operator: Optional[str] = None,
        from_location: Optional[str] = None,
        to_location: Optional[str] = None,
        remark: Optional[str] = None
    ) -> AssetLifecycle:
        """
        添加生命周期记录（私有方法）

        Args:
            asset_id: 资产ID
            action: 操作类型
            operator: 操作人
            from_location: 原位置
            to_location: 新位置
            remark: 备注

        Returns:
            创建的生命周期记录
        """
        lifecycle = AssetLifecycle(
            asset_id=asset_id,
            action=action,
            action_date=datetime.now(),
            operator=operator,
            from_location=from_location,
            to_location=to_location,
            remark=remark
        )
        self.db.add(lifecycle)
        self.db.commit()
        self.db.refresh(lifecycle)
        return lifecycle

    # ==================== 维护管理 ====================

    def create_maintenance(self, data: MaintenanceCreate) -> MaintenanceRecord:
        """
        创建维护记录

        Args:
            data: 维护记录创建数据

        Returns:
            创建的维护记录
        """
        # 创建维护记录
        record = MaintenanceRecord(**data.model_dump())
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        # 更新资产状态为维护中
        asset = self.get_asset(data.asset_id)
        if asset:
            asset.status = AssetStatus.maintenance
            asset.updated_at = datetime.now()
            self.db.commit()

            # 添加生命周期记录
            self._add_lifecycle(
                asset_id=asset.id,
                action="maintain",
                operator=data.technician,
                from_location=None,
                to_location=None,
                remark=f"开始维护: {data.maintenance_type} - {data.description or ''}"
            )

        return record

    def complete_maintenance(
        self,
        record_id: int,
        result: Optional[str] = None
    ) -> Optional[MaintenanceRecord]:
        """
        完成维护

        Args:
            record_id: 维护记录ID
            result: 维护结果

        Returns:
            更新后的维护记录或None
        """
        record = self.db.query(MaintenanceRecord).filter(
            MaintenanceRecord.id == record_id
        ).first()

        if not record:
            return None

        # 更新维护记录
        record.end_time = datetime.now()
        if result:
            record.result = result
        self.db.commit()
        self.db.refresh(record)

        # 恢复资产状态为使用中
        asset = self.get_asset(record.asset_id)
        if asset:
            asset.status = AssetStatus.in_use
            asset.updated_at = datetime.now()
            self.db.commit()

            # 添加生命周期记录
            self._add_lifecycle(
                asset_id=asset.id,
                action="deploy",
                operator=record.technician,
                from_location=None,
                to_location=None,
                remark=f"维护完成: {result or '正常'}"
            )

        return record

    def get_maintenance_records(
        self,
        asset_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[MaintenanceRecord]:
        """
        获取维护记录列表

        Args:
            asset_id: 资产ID（可选）
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            维护记录列表
        """
        query = self.db.query(MaintenanceRecord)

        if asset_id:
            query = query.filter(MaintenanceRecord.asset_id == asset_id)

        return query.order_by(MaintenanceRecord.start_time.desc()).offset(skip).limit(limit).all()

    # ==================== 盘点管理 ====================

    def create_inventory(self, data: InventoryCreate) -> AssetInventory:
        """
        创建资产盘点

        Args:
            data: 盘点创建数据

        Returns:
            创建的盘点记录
        """
        # 创建盘点主记录
        inventory = AssetInventory(**data.model_dump())
        inventory.status = "pending"
        self.db.add(inventory)
        self.db.commit()
        self.db.refresh(inventory)

        # 获取所有在用和借出的资产，创建盘点明细
        assets = self.db.query(Asset).filter(
            Asset.status.in_([AssetStatus.in_use, AssetStatus.borrowed])
        ).all()

        for asset in assets:
            expected_location = None
            if asset.cabinet_id:
                cabinet = self.get_cabinet(asset.cabinet_id)
                if cabinet:
                    expected_location = f"{cabinet.cabinet_name} U{asset.u_position}" if asset.u_position else cabinet.cabinet_name

            item = AssetInventoryItem(
                inventory_id=inventory.id,
                asset_id=asset.id,
                expected_location=expected_location,
                is_matched=False
            )
            self.db.add(item)

        self.db.commit()

        # 更新统计信息
        self._update_inventory_stats(inventory.id)

        self.db.refresh(inventory)
        return inventory

    def update_inventory_item(
        self,
        item_id: int,
        data: InventoryItemUpdate
    ) -> Optional[AssetInventoryItem]:
        """
        更新盘点明细

        Args:
            item_id: 盘点明细ID
            data: 更新数据

        Returns:
            更新后的盘点明细或None
        """
        item = self.db.query(AssetInventoryItem).filter(
            AssetInventoryItem.id == item_id
        ).first()

        if not item:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(item, key, value)

        if not item.check_time:
            item.check_time = datetime.now()

        self.db.commit()
        self.db.refresh(item)

        # 更新盘点统计信息
        self._update_inventory_stats(item.inventory_id)

        return item

    def get_inventory_list(self, skip: int = 0, limit: int = 100) -> List[AssetInventory]:
        """
        获取盘点列表

        Args:
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            盘点列表
        """
        return self.db.query(AssetInventory).order_by(
            AssetInventory.created_at.desc()
        ).offset(skip).limit(limit).all()

    def get_inventory_items(self, inventory_id: int) -> List[AssetInventoryItem]:
        """
        获取盘点明细列表

        Args:
            inventory_id: 盘点ID

        Returns:
            盘点明细列表
        """
        return self.db.query(AssetInventoryItem).filter(
            AssetInventoryItem.inventory_id == inventory_id
        ).all()

    def _update_inventory_stats(self, inventory_id: int) -> None:
        """
        更新盘点统计信息（私有方法）

        Args:
            inventory_id: 盘点ID
        """
        inventory = self.db.query(AssetInventory).filter(
            AssetInventory.id == inventory_id
        ).first()

        if not inventory:
            return

        items = self.get_inventory_items(inventory_id)

        total_count = len(items)
        checked_count = sum(1 for item in items if item.check_time is not None)
        matched_count = sum(1 for item in items if item.is_matched)
        unmatched_count = sum(1 for item in items if item.check_time is not None and not item.is_matched)

        inventory.total_count = total_count
        inventory.checked_count = checked_count
        inventory.matched_count = matched_count
        inventory.unmatched_count = unmatched_count

        # 更新盘点状态
        if checked_count == 0:
            inventory.status = "pending"
        elif checked_count < total_count:
            inventory.status = "in_progress"
        else:
            inventory.status = "completed"
            inventory.completed_at = datetime.now()

        self.db.commit()

    # ==================== 统计分析 ====================

    def get_statistics(self) -> AssetStatistics:
        """
        获取资产统计信息

        Returns:
            资产统计信息
        """
        # 资产总数
        total_count = self.db.query(func.count(Asset.id)).scalar() or 0

        # 按状态统计
        status_counts = self.db.query(
            Asset.status,
            func.count(Asset.id)
        ).group_by(Asset.status).all()
        by_status = {status.value if status else "unknown": count for status, count in status_counts}

        # 按类型统计
        type_counts = self.db.query(
            Asset.asset_type,
            func.count(Asset.id)
        ).group_by(Asset.asset_type).all()
        by_type = {asset_type.value if asset_type else "unknown": count for asset_type, count in type_counts}

        # 按部门统计
        dept_counts = self.db.query(
            Asset.department,
            func.count(Asset.id)
        ).filter(Asset.department.isnot(None)).group_by(Asset.department).all()
        by_department = {dept or "未分配": count for dept, count in dept_counts}

        # 资产总价值
        total_value = self.db.query(func.sum(Asset.purchase_price)).scalar() or 0

        # 保修即将到期数量（30天内）
        expiring_date = date.today() + timedelta(days=30)
        warranty_expiring_count = self.db.query(func.count(Asset.id)).filter(
            Asset.warranty_end.isnot(None),
            Asset.warranty_end <= expiring_date,
            Asset.warranty_end >= date.today(),
            Asset.status != AssetStatus.scrapped
        ).scalar() or 0

        return AssetStatistics(
            total_count=total_count,
            by_status=by_status,
            by_type=by_type,
            by_department=by_department,
            total_value=float(total_value),
            warranty_expiring_count=warranty_expiring_count
        )

    def get_warranty_expiring_assets(self, days: int = 30) -> List[Asset]:
        """
        获取保修即将到期的资产

        Args:
            days: 天数范围（默认30天）

        Returns:
            保修即将到期的资产列表
        """
        expiring_date = date.today() + timedelta(days=days)
        return self.db.query(Asset).filter(
            Asset.warranty_end.isnot(None),
            Asset.warranty_end <= expiring_date,
            Asset.warranty_end >= date.today(),
            Asset.status != AssetStatus.scrapped
        ).order_by(Asset.warranty_end.asc()).all()


# 辅助函数：创建服务实例
def get_asset_service(db: Session) -> AssetService:
    """
    获取资产服务实例

    Args:
        db: 数据库会话

    Returns:
        AssetService实例
    """
    return AssetService(db)
