"""楼层平面图生成服务"""
import json
from typing import Dict, List, Any

# 楼层配置
FLOOR_CONFIG = {
    "B1": {
        "name": "地下制冷机房",
        "width": 40,
        "height": 30,
        "color": "#1a3a5c",
        "devices": ["chiller", "cooling_tower", "pump"]
    },
    "F1": {
        "name": "1楼机房区A",
        "width": 50,
        "height": 40,
        "color": "#1e4d2b",
        "cabinets": 20,
        "rows": 4,
        "cols": 5
    },
    "F2": {
        "name": "2楼机房区B",
        "width": 50,
        "height": 35,
        "color": "#4a1e6b",
        "cabinets": 15,
        "rows": 3,
        "cols": 5
    },
    "F3": {
        "name": "3楼办公监控",
        "width": 45,
        "height": 30,
        "color": "#6b4a1e",
        "cabinets": 8,
        "rows": 2,
        "cols": 4
    }
}


class FloorMapGenerator:
    """楼层图生成器"""

    def generate_2d_map(self, floor_code: str, devices: List[Dict] = None) -> Dict[str, Any]:
        """生成2D平面图数据"""
        config = FLOOR_CONFIG.get(floor_code, {})
        devices = devices or []

        map_data = {
            "floor": floor_code,
            "name": config.get("name", f"Floor {floor_code}"),
            "dimensions": {
                "width": config.get("width", 50),
                "height": config.get("height", 40)
            },
            "background": config.get("color", "#1a1a2e"),
            "elements": []
        }

        # 根据楼层类型生成不同布局
        if floor_code == "B1":
            map_data["elements"] = self._generate_cooling_layout_2d(devices)
        else:
            map_data["elements"] = self._generate_datacenter_layout_2d(floor_code, config, devices)

        return map_data

    def generate_3d_map(self, floor_code: str, devices: List[Dict] = None) -> Dict[str, Any]:
        """生成3D场景数据"""
        config = FLOOR_CONFIG.get(floor_code, {})
        devices = devices or []

        map_data = {
            "floor": floor_code,
            "name": config.get("name", f"Floor {floor_code}"),
            "scene": {
                "width": config.get("width", 50),
                "depth": config.get("height", 40),
                "height": 4  # 层高
            },
            "camera": {
                "position": [25, 20, 35],
                "target": [25, 0, 20]
            },
            "objects": []
        }

        # 生成3D对象
        if floor_code == "B1":
            map_data["objects"] = self._generate_cooling_layout_3d(devices)
        else:
            map_data["objects"] = self._generate_datacenter_layout_3d(floor_code, config, devices)

        return map_data

    def _generate_cooling_layout_2d(self, devices: List[Dict]) -> List[Dict]:
        """生成制冷机房2D布局"""
        elements = []

        # 冷水机组区域
        elements.append({
            "type": "zone",
            "id": "chiller_zone",
            "name": "冷水机组区",
            "x": 2, "y": 2, "width": 15, "height": 12,
            "color": "rgba(0, 102, 204, 0.3)"
        })

        # 冷却塔区域
        elements.append({
            "type": "zone",
            "id": "tower_zone",
            "name": "冷却塔区",
            "x": 20, "y": 2, "width": 15, "height": 12,
            "color": "rgba(0, 170, 102, 0.3)"
        })

        # 水泵区域
        elements.append({
            "type": "zone",
            "id": "pump_zone",
            "name": "水泵区",
            "x": 2, "y": 16, "width": 33, "height": 10,
            "color": "rgba(102, 0, 204, 0.3)"
        })

        # 添加冷水机组设备
        for i in range(3):
            elements.append({
                "type": "device",
                "id": f"B1_CHILLER_{i+1:02d}",
                "name": f"冷水机组{i+1}",
                "deviceType": "chiller",
                "x": 4 + i * 5, "y": 5,
                "width": 4, "height": 6,
                "status": "normal"
            })

        # 添加冷却塔设备
        for i in range(2):
            elements.append({
                "type": "device",
                "id": f"B1_TOWER_{i+1:02d}",
                "name": f"冷却塔{i+1}",
                "deviceType": "cooling_tower",
                "x": 22 + i * 6, "y": 5,
                "width": 5, "height": 6,
                "status": "normal"
            })

        # 添加水泵设备
        for i in range(4):
            elements.append({
                "type": "device",
                "id": f"B1_PUMP_{i+1:02d}",
                "name": f"冷冻水泵{i+1}",
                "deviceType": "pump",
                "x": 4 + i * 8, "y": 18,
                "width": 3, "height": 5,
                "status": "normal"
            })

        return elements

    def _generate_datacenter_layout_2d(self, floor_code: str, config: Dict, devices: List[Dict]) -> List[Dict]:
        """生成数据中心机房2D布局"""
        elements = []
        rows = config.get("rows", 4)
        cols = config.get("cols", 5)
        cabinet_count = config.get("cabinets", 20)
        width = config.get("width", 50)

        cabinet_width = 2.5
        cabinet_height = 4
        aisle_width = 3
        start_x = 5
        start_y = 5

        # 机柜区域
        cabinet_idx = 0
        for row in range(rows):
            for col in range(cols):
                if cabinet_idx >= cabinet_count:
                    break

                x = start_x + col * (cabinet_width + 1)
                y = start_y + row * (cabinet_height + aisle_width)

                elements.append({
                    "type": "cabinet",
                    "id": f"CAB-{floor_code}-{cabinet_idx+1:02d}",
                    "name": f"机柜{cabinet_idx+1}",
                    "x": x, "y": y,
                    "width": cabinet_width, "height": cabinet_height,
                    "status": "normal",
                    "row": row + 1,
                    "col": col + 1
                })
                cabinet_idx += 1

        # UPS区域
        elements.append({
            "type": "zone",
            "id": f"ups_zone_{floor_code}",
            "name": "UPS区",
            "x": width - 10, "y": 2,
            "width": 8, "height": 8,
            "color": "rgba(204, 102, 0, 0.3)"
        })

        # UPS设备
        ups_count = 2 if floor_code != "F3" else 1
        for i in range(ups_count):
            elements.append({
                "type": "device",
                "id": f"{floor_code}_UPS_{i+1:02d}",
                "name": f"UPS主机{i+1}",
                "deviceType": "ups",
                "x": width - 9 + i * 4, "y": 4,
                "width": 3, "height": 4,
                "status": "normal"
            })

        # 空调区域
        elements.append({
            "type": "zone",
            "id": f"ac_zone_{floor_code}",
            "name": "精密空调区",
            "x": width - 10, "y": 12,
            "width": 8, "height": 12,
            "color": "rgba(0, 204, 204, 0.3)"
        })

        # 精密空调设备
        ac_count = 4 if floor_code != "F3" else 2
        for i in range(ac_count):
            row_offset = i // 2
            col_offset = i % 2
            elements.append({
                "type": "device",
                "id": f"{floor_code}_AC_{i+1:02d}",
                "name": f"精密空调{i+1}",
                "deviceType": "ac",
                "x": width - 9 + col_offset * 4, "y": 14 + row_offset * 5,
                "width": 3, "height": 4,
                "status": "normal"
            })

        return elements

    def _generate_cooling_layout_3d(self, devices: List[Dict]) -> List[Dict]:
        """生成制冷机房3D对象"""
        objects = []

        # 地板
        objects.append({
            "type": "floor",
            "position": [20, 0, 15],
            "size": [40, 0.1, 30],
            "color": "#1a3a5c"
        })

        # 冷水机组
        for i in range(3):
            objects.append({
                "type": "equipment",
                "id": f"B1_CHILLER_{i+1:02d}",
                "name": f"冷水机组{i+1}",
                "equipmentType": "chiller",
                "position": [5 + i * 6, 1.5, 8],
                "size": [4, 3, 6],
                "color": "#0066cc"
            })

        # 冷却塔
        for i in range(2):
            objects.append({
                "type": "equipment",
                "id": f"B1_TOWER_{i+1:02d}",
                "name": f"冷却塔{i+1}",
                "equipmentType": "cooling_tower",
                "position": [25 + i * 7, 2, 8],
                "size": [5, 4, 5],
                "color": "#00aa66"
            })

        # 水泵
        for i in range(4):
            objects.append({
                "type": "equipment",
                "id": f"B1_PUMP_{i+1:02d}",
                "name": f"冷冻水泵{i+1}",
                "equipmentType": "pump",
                "position": [5 + i * 8, 0.75, 22],
                "size": [2, 1.5, 3],
                "color": "#6600cc"
            })

        # 管道装饰
        objects.append({
            "type": "pipe",
            "id": "main_pipe",
            "name": "主管道",
            "path": [[5, 2, 15], [35, 2, 15]],
            "radius": 0.3,
            "color": "#3388ff"
        })

        return objects

    def _generate_datacenter_layout_3d(self, floor_code: str, config: Dict, devices: List[Dict]) -> List[Dict]:
        """生成数据中心3D对象"""
        objects = []
        width = config.get("width", 50)
        depth = config.get("height", 40)
        rows = config.get("rows", 4)
        cols = config.get("cols", 5)
        cabinet_count = config.get("cabinets", 20)

        # 地板
        objects.append({
            "type": "floor",
            "position": [width/2, 0, depth/2],
            "size": [width, 0.1, depth],
            "color": config.get("color", "#1e4d2b")
        })

        # 机柜
        cabinet_idx = 0
        for row in range(rows):
            for col in range(cols):
                if cabinet_idx >= cabinet_count:
                    break

                x = 5 + col * 4
                z = 5 + row * 8

                objects.append({
                    "type": "cabinet",
                    "id": f"CAB-{floor_code}-{cabinet_idx+1:02d}",
                    "name": f"机柜{cabinet_idx+1}",
                    "position": [x, 1.1, z],
                    "size": [0.6, 2.2, 1.0],
                    "color": "#333344",
                    "row": row + 1,
                    "col": col + 1
                })
                cabinet_idx += 1

        # UPS设备
        ups_count = 2 if floor_code != "F3" else 1
        for i in range(ups_count):
            objects.append({
                "type": "equipment",
                "id": f"{floor_code}_UPS_{i+1:02d}",
                "name": f"UPS主机{i+1}",
                "equipmentType": "ups",
                "position": [width - 6 + i * 3, 1, 5],
                "size": [2, 2, 1.5],
                "color": "#cc6600"
            })

        # 精密空调
        ac_count = 4 if floor_code != "F3" else 2
        for i in range(ac_count):
            row_offset = i // 2
            col_offset = i % 2
            objects.append({
                "type": "equipment",
                "id": f"{floor_code}_AC_{i+1:02d}",
                "name": f"精密空调{i+1}",
                "equipmentType": "ac",
                "position": [width - 5 + col_offset * 3, 1.5, 15 + row_offset * 5],
                "size": [1.5, 3, 1.2],
                "color": "#00cccc"
            })

        # 冷通道装饰
        for row in range(rows - 1):
            z = 5 + row * 8 + 4
            objects.append({
                "type": "aisle",
                "id": f"cold_aisle_{floor_code}_{row+1}",
                "name": f"冷通道{row+1}",
                "position": [cols * 2 + 2.5, 0.05, z],
                "size": [cols * 4, 0.1, 3],
                "color": "#0066ff",
                "opacity": 0.3
            })

        return objects
