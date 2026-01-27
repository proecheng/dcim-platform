// frontend/src/config/themes/realistic.ts
import type { BigscreenTheme } from '@/types/theme'

/**
 * 写实风格主题
 * 灰色背景 + PBR真实材质
 */
export const realisticTheme: BigscreenTheme = {
  name: 'realistic',
  displayName: '写实风格',

  scene: {
    backgroundColor: 0x1a1a1a,
    fogColor: 0x1a1a1a,
    fogDensity: 0.02,
    gridColor: 0x333333,
    gridOpacity: 0.2,
    ambientLightColor: 0xffffff,
    ambientLightIntensity: 0.6
  },

  materials: {
    cabinetBody: {
      color: 0x2a2a2a,
      metalness: 0.95,
      roughness: 0.15,
      envMapIntensity: 1.5
    },
    cabinetFrame: {
      color: 0x3a3a3a,
      metalness: 0.9,
      roughness: 0.2
    },
    floor: {
      color: 0x252525,
      metalness: 0.3,
      roughness: 0.7,
      opacity: 1.0
    }
  },

  ui: {
    primaryColor: '#4a9eff',
    secondaryColor: '#6eb5ff',
    successColor: '#52c41a',
    warningColor: '#faad14',
    dangerColor: '#ff4d4f',
    backgroundColor: 'rgba(30, 30, 30, 0.95)',
    borderColor: 'rgba(80, 80, 80, 0.6)',
    textColor: '#ffffff',
    textColorSecondary: '#999999',
    panelOpacity: 0.95,
    borderStyle: 'solid'
  },

  effects: {
    bloom: false,
    bloomStrength: 0.3,
    outline: true,
    outlineColor: 0x4a9eff,
    particles: false,
    flowLines: false
  }
}
