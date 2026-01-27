/**
 * 大屏布局 API
 */
import request from '@/utils/request'
import type { DataCenterLayout } from '@/types/bigscreen'

/**
 * 获取机房布局配置
 */
export function getDataCenterLayout(): Promise<DataCenterLayout> {
  return request.get('/v1/bigscreen/layout')
}

/**
 * 保存机房布局配置 (管理员)
 */
export function saveDataCenterLayout(layout: DataCenterLayout): Promise<void> {
  return request.post('/v1/bigscreen/layout', layout)
}

/**
 * 获取默认布局模板
 */
export function getDefaultLayout(): Promise<DataCenterLayout> {
  // 返回默认布局配置
  return Promise.resolve({
    name: '默认机房布局',
    dimensions: { width: 40, length: 30, height: 4 },
    modules: [
      {
        id: 'module-A',
        name: 'A区机柜',
        position: { x: -10, z: 0 },
        rotation: 0,
        cabinets: [
          { id: 'A-01', name: 'A区1号柜', position: { x: 0, y: 0, z: 0 }, size: { width: 0.6, height: 2, depth: 1 }, status: 'normal' },
          { id: 'A-02', name: 'A区2号柜', position: { x: 1.2, y: 0, z: 0 }, size: { width: 0.6, height: 2, depth: 1 }, status: 'normal' },
          { id: 'A-03', name: 'A区3号柜', position: { x: 2.4, y: 0, z: 0 }, size: { width: 0.6, height: 2, depth: 1 }, status: 'normal' },
          { id: 'A-04', name: 'A区4号柜', position: { x: 3.6, y: 0, z: 0 }, size: { width: 0.6, height: 2, depth: 1 }, status: 'normal' }
        ],
        coolingUnits: [
          { id: 'AC-A-01', position: { x: -2, z: 0 } }
        ]
      },
      {
        id: 'module-B',
        name: 'B区机柜',
        position: { x: 10, z: 0 },
        rotation: 0,
        cabinets: [
          { id: 'B-01', name: 'B区1号柜', position: { x: 0, y: 0, z: 0 }, size: { width: 0.6, height: 2, depth: 1 }, status: 'normal' },
          { id: 'B-02', name: 'B区2号柜', position: { x: 1.2, y: 0, z: 0 }, size: { width: 0.6, height: 2, depth: 1 }, status: 'normal' },
          { id: 'B-03', name: 'B区3号柜', position: { x: 2.4, y: 0, z: 0 }, size: { width: 0.6, height: 2, depth: 1 }, status: 'normal' },
          { id: 'B-04', name: 'B区4号柜', position: { x: 3.6, y: 0, z: 0 }, size: { width: 0.6, height: 2, depth: 1 }, status: 'normal' }
        ],
        coolingUnits: [
          { id: 'AC-B-01', position: { x: 6, z: 0 } }
        ]
      }
    ],
    infrastructure: {
      upsRoom: { position: { x: 0, z: -12 }, size: { width: 6, length: 4 } },
      powerRoom: { position: { x: 0, z: 12 }, size: { width: 6, length: 4 } }
    }
  })
}
