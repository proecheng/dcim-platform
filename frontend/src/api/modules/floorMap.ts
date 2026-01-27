import request from '@/utils/request'
import type { ResponseModel } from './types'

export interface FloorInfo {
  floor_code: string
  floor_name: string
  map_types: string[]
}

export interface FloorListResponse {
  floors: FloorInfo[]
}

export interface MapElement2D {
  type: string
  id: string
  name: string
  x: number
  y: number
  width: number
  height: number
  color?: string
  status?: string
  deviceType?: string
  row?: number
  col?: number
}

export interface MapData2D {
  floor: string
  name: string
  dimensions: {
    width: number
    height: number
  }
  background: string
  elements: MapElement2D[]
}

export interface MapObject3D {
  type: string
  id?: string
  name?: string
  position: [number, number, number]
  size: [number, number, number]
  color: string
  equipmentType?: string
  row?: number
  col?: number
  opacity?: number
  path?: [number, number, number][]
  radius?: number
}

export interface MapData3D {
  floor: string
  name: string
  scene: {
    width: number
    depth: number
    height: number
  }
  camera: {
    position: [number, number, number]
    target: [number, number, number]
  }
  objects: MapObject3D[]
}

export interface FloorMapData {
  id: number
  floor_code: string
  floor_name: string
  map_type: '2d' | '3d'
  map_data: MapData2D | MapData3D
  thumbnail?: string
  is_default: boolean
}

// 获取楼层列表
export function getFloors() {
  return request.get<ResponseModel<FloorListResponse>>('/v1/floor-map/floors')
}

// 获取楼层图数据
export function getFloorMap(floorCode: string, mapType: '2d' | '3d') {
  return request.get<ResponseModel<FloorMapData>>(`/v1/floor-map/${floorCode}/${mapType}`)
}

// 获取默认楼层图
export function getDefaultFloorMap(mapType: '2d' | '3d' = '3d') {
  return request.get<ResponseModel<FloorMapData>>(`/v1/floor-map/default?map_type=${mapType}`)
}
