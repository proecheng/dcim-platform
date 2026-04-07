# -*- coding: utf-8 -*-
"""
Shift Device Service
负荷转移设备服务

Device management and shift potential calculation
设备管理和转移潜力计算
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from ...models.energy import DeviceShiftConfig, PowerDevice
from ...models.load_shift import ShiftExecution, DeviceLifespanImpact
from ...schemas.load_shift import DeviceShiftPotentialResponse

logger = logging.getLogger(__name__)


class ShiftDeviceService:
    """Shift device service - device management and potential calculation"""

    @staticmethod
    async def get_shiftable_devices(
        db: AsyncSession,
        device_type: Optional[str] = None,
        min_power: Optional[float] = None,
        max_power: Optional[float] = None,
        is_critical: Optional[bool] = None,
    ) -> List[DeviceShiftPotentialResponse]:
        """
        Get shiftable devices with shift potential
        获取可转移设备及转移潜力

        Args:
            db: Database session
            device_type: Filter by device type (e.g., "空调", "UPS", "服务器")
            min_power: Minimum rated power (kW)
            max_power: Maximum rated power (kW)
            is_critical: Filter by critical device flag

        Returns:
            List of DeviceShiftPotentialResponse with shift potential
        """
        logger.info(
            f"Querying shiftable devices: type={device_type}, power={min_power}-{max_power}kW, critical={is_critical}"
        )

        # Build query
        query = (
            select(DeviceShiftConfig, PowerDevice)
            .join(PowerDevice, DeviceShiftConfig.device_id == PowerDevice.id)
            .where(DeviceShiftConfig.is_shiftable == True)
        )

        # Apply filters
        if device_type:
            query = query.where(PowerDevice.device_type == device_type)

        if min_power is not None:
            query = query.where(DeviceShiftConfig.rated_power >= min_power)

        if max_power is not None:
            query = query.where(DeviceShiftConfig.rated_power <= max_power)

        if is_critical is not None:
            query = query.where(PowerDevice.is_critical == is_critical)

        # Execute query
        result = await db.execute(query)
        rows = result.all()

        # Calculate shift potential for each device
        devices = []
        for config, device in rows:
            potential = await ShiftDeviceService._calculate_shift_potential(
                db=db,
                config=config,
                device=device,
            )
            devices.append(potential)

        logger.info(f"Found {len(devices)} shiftable devices")
        return devices

    @staticmethod
    async def get_device_potential(
        db: AsyncSession,
        device_id: int,
    ) -> DeviceShiftPotentialResponse:
        """
        Get shift potential for a specific device
        获取指定设备的转移潜力

        Args:
            db: Database session
            device_id: Device ID

        Returns:
            DeviceShiftPotentialResponse
        """
        logger.info(f"Calculating shift potential for device {device_id}")

        # Query device and config
        query = (
            select(DeviceShiftConfig, PowerDevice)
            .join(PowerDevice, DeviceShiftConfig.device_id == PowerDevice.id)
            .where(DeviceShiftConfig.device_id == device_id)
        )
        result = await db.execute(query)
        row = result.first()

        if not row:
            raise ValueError(f"Device {device_id} not found or not shiftable")

        config, device = row
        potential = await ShiftDeviceService._calculate_shift_potential(
            db=db,
            config=config,
            device=device,
        )

        return potential

    @staticmethod
    async def _calculate_shift_potential(
        db: AsyncSession,
        config: DeviceShiftConfig,
        device: PowerDevice,
    ) -> DeviceShiftPotentialResponse:
        """
        Calculate shift potential for a device
        计算设备转移潜力

        Considers:
        - Device rated power and current load
        - Historical shift success rate (last 90 days)
        - Device availability (uptime)
        - Recent shift frequency (lifespan impact)
        - Maintenance schedule

        Args:
            db: Database session
            config: DeviceShiftConfig
            device: PowerDevice

        Returns:
            DeviceShiftPotentialResponse with calculated potential
        """
        device_id = config.device_id
        rated_power = config.rated_power

        # Factor 1: Base potential (rated power * safety factor)
        safety_factor = 0.85  # Conservative approach
        base_potential = rated_power * safety_factor

        # Factor 2: Historical success rate (last 90 days)
        ninety_days_ago = datetime.now() - timedelta(days=90)

        # Count total and successful shifts for this device
        query = select(
            func.count(ShiftExecution.id).label("total"),
            func.sum(func.case((ShiftExecution.status == "completed", 1), else_=0)).label("successful"),
        ).where(
            ShiftExecution.created_at >= ninety_days_ago,
            # Note: ShiftExecution doesn't have device_id directly
            # In real implementation, need to join through plan -> devices
            # For now, use all executions as proxy
        )
        result = await db.execute(query)
        row = result.first()

        success_rate = 1.0  # Default 100%
        if row and row.total and row.total > 0:
            success_rate = (row.successful or 0) / row.total

        # Factor 3: Recent shift frequency (lifespan impact)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        query = select(func.count(DeviceLifespanImpact.id)).where(
            DeviceLifespanImpact.device_id == device_id,
            DeviceLifespanImpact.impact_date >= thirty_days_ago,
        )
        result = await db.execute(query)
        recent_shift_count = result.scalar() or 0

        # Reduce potential if device shifted too frequently
        # Frequent starts reduce lifespan 15-25%
        frequency_penalty = 1.0
        if recent_shift_count > 60:  # > 2 shifts/day
            frequency_penalty = 0.7  # 30% penalty
        elif recent_shift_count > 30:  # > 1 shift/day
            frequency_penalty = 0.85  # 15% penalty

        # Factor 4: Device availability (uptime)
        # Assume 99% uptime if device is not critical, 99.9% if critical
        availability = 0.999 if device.is_critical else 0.99

        # Calculate final shift potential
        shift_potential_kw = base_potential * success_rate * frequency_penalty * availability

        # Calculate confidence score (0-1)
        # Based on historical data availability and success rate
        confidence_score = 0.5  # Base confidence
        if row and row.total:
            # More historical data = higher confidence
            data_confidence = min(row.total / 30, 1.0)  # Max at 30 shifts
            confidence_score = 0.3 + (0.7 * data_confidence * success_rate)

        # Adjust confidence based on frequency penalty
        confidence_score *= frequency_penalty

        # Build response
        potential_response = DeviceShiftPotentialResponse(
            device_id=device_id,
            device_name=device.device_name,
            device_type=device.device_type,
            rated_power=rated_power,
            shift_potential_kw=round(shift_potential_kw, 2),
            confidence_score=round(confidence_score, 2),
            is_critical=device.is_critical,
            recent_shift_count=recent_shift_count,
            success_rate=round(success_rate, 2),
            availability=round(availability, 3),
            last_shift_date=None,  # TODO: Query from DeviceLifespanImpact
            next_maintenance_date=None,  # TODO: Query from maintenance schedule
            notes=ShiftDeviceService._generate_potential_notes(
                success_rate=success_rate,
                recent_shift_count=recent_shift_count,
                frequency_penalty=frequency_penalty,
            ),
        )

        logger.debug(f"Device {device_id} potential: {shift_potential_kw:.2f}kW (confidence={confidence_score:.2f})")

        return potential_response

    @staticmethod
    def _generate_potential_notes(
        success_rate: float,
        recent_shift_count: int,
        frequency_penalty: float,
    ) -> str:
        """
        Generate notes about shift potential
        生成转移潜力说明

        Args:
            success_rate: Historical success rate
            recent_shift_count: Recent shift count (30 days)
            frequency_penalty: Frequency penalty factor

        Returns:
            Notes string
        """
        notes = []

        # Success rate notes
        if success_rate < 0.8:
            notes.append(f"历史成功率较低({success_rate * 100:.0f}%)，建议谨慎使用")
        elif success_rate >= 0.95:
            notes.append(f"历史成功率高({success_rate * 100:.0f}%)，可靠性好")

        # Frequency notes
        if recent_shift_count > 60:
            notes.append(f"近30天已转移{recent_shift_count}次，频繁启停可能影响设备寿命")
        elif recent_shift_count > 30:
            notes.append(f"近30天已转移{recent_shift_count}次，建议适当降低频率")
        elif recent_shift_count == 0:
            notes.append("近期未执行转移，可优先考虑")

        # Penalty notes
        if frequency_penalty < 0.8:
            notes.append("由于频繁转移，潜力已降低30%")
        elif frequency_penalty < 0.9:
            notes.append("由于频繁转移，潜力已降低15%")

        return "; ".join(notes) if notes else "设备状态良好，可正常转移"

    @staticmethod
    async def get_device_shift_history(
        db: AsyncSession,
        device_id: int,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get device shift history
        获取设备转移历史

        Args:
            db: Database session
            device_id: Device ID
            days: Number of days to look back

        Returns:
            List of shift history records
        """
        logger.info(f"Querying shift history for device {device_id} (last {days} days)")

        start_date = datetime.now() - timedelta(days=days)

        query = (
            select(DeviceLifespanImpact)
            .where(
                DeviceLifespanImpact.device_id == device_id,
                DeviceLifespanImpact.impact_date >= start_date,
            )
            .order_by(DeviceLifespanImpact.impact_date.desc())
        )

        result = await db.execute(query)
        impacts = result.scalars().all()

        history = []
        for impact in impacts:
            history.append(
                {
                    "date": impact.impact_date.isoformat(),
                    "shift_count": impact.shift_count,
                    "total_runtime_hours": impact.total_runtime_hours,
                    "estimated_lifespan_loss_days": impact.estimated_lifespan_loss_days,
                    "notes": impact.notes,
                }
            )

        logger.info(f"Found {len(history)} shift history records")
        return history

    @staticmethod
    async def update_device_lifespan_impact(
        db: AsyncSession,
        device_id: int,
        plan_id: int,
        shift_count: int,
        runtime_hours: float,
    ) -> None:
        """
        Update device lifespan impact after shift execution
        转移执行后更新设备寿命影响

        Args:
            db: Database session
            device_id: Device ID
            plan_id: Shift plan ID
            shift_count: Number of shifts (start/stop cycles)
            runtime_hours: Total runtime hours
        """
        logger.info(f"Updating lifespan impact for device {device_id}: shifts={shift_count}, runtime={runtime_hours}h")

        # Calculate estimated lifespan loss
        # Frequent starts reduce lifespan 15-25%
        # Assume: 1 start/stop cycle = 0.5 days lifespan loss
        # Assume: 1 hour runtime = 0.04 days lifespan loss (1 day / 24 hours)
        lifespan_loss_from_shifts = shift_count * 0.5
        lifespan_loss_from_runtime = runtime_hours * 0.04
        total_lifespan_loss = lifespan_loss_from_shifts + lifespan_loss_from_runtime

        # Check if record exists for today
        today = datetime.now().date()
        query = select(DeviceLifespanImpact).where(
            DeviceLifespanImpact.device_id == device_id,
            DeviceLifespanImpact.impact_date == today,
        )
        result = await db.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing record
            existing.shift_count += shift_count
            existing.total_runtime_hours += runtime_hours
            existing.estimated_lifespan_loss_days += total_lifespan_loss
            existing.updated_at = datetime.now()
            logger.debug(f"Updated existing lifespan impact record: id={existing.id}")
        else:
            # Create new record
            impact = DeviceLifespanImpact(
                device_id=device_id,
                plan_id=plan_id,
                impact_date=today,
                shift_count=shift_count,
                total_runtime_hours=runtime_hours,
                estimated_lifespan_loss_days=total_lifespan_loss,
                notes=f"转移{shift_count}次，运行{runtime_hours:.1f}小时",
            )
            db.add(impact)
            logger.debug("Created new lifespan impact record")

        await db.commit()
        logger.info(f"Lifespan impact updated: loss={total_lifespan_loss:.2f} days")
