// frontend/src/types/theme.ts

/**
 * 大屏主题配置类型
 */
export interface BigscreenTheme {
  name: string
  displayName: string

  // 场景配置
  scene: {
    backgroundColor: number
    fogColor: number
    fogDensity: number
    gridColor: number
    gridOpacity: number
    ambientLightColor: number
    ambientLightIntensity: number
  }

  // 材质配置
  materials: {
    cabinetBody: {
      color: number
      metalness: number
      roughness: number
      envMapIntensity: number
      emissive?: number
      emissiveIntensity?: number
    }
    cabinetFrame: {
      color: number
      metalness: number
      roughness: number
    }
    floor: {
      color: number
      metalness: number
      roughness: number
      opacity: number
    }
  }

  // UI配置
  ui: {
    primaryColor: string
    secondaryColor: string
    successColor: string
    warningColor: string
    dangerColor: string
    backgroundColor: string
    borderColor: string
    textColor: string
    textColorSecondary: string
    panelOpacity: number
    borderStyle: 'glow' | 'solid' | 'gradient'
  }

  // 特效配置
  effects: {
    bloom: boolean
    bloomStrength: number
    outline: boolean
    outlineColor: number
    particles: boolean
    flowLines: boolean
  }
}

export type ThemeName = 'tech-blue' | 'wireframe' | 'realistic' | 'night'
