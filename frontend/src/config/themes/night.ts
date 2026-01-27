// frontend/src/config/themes/night.ts
import type { BigscreenTheme } from '@/types/theme'

/**
 * 暗夜模式主题
 * 纯黑背景 + 最小化UI + 低亮度护眼
 */
export const nightTheme: BigscreenTheme = {
  name: 'night',
  displayName: '暗夜模式',

  scene: {
    backgroundColor: 0x000000,
    fogColor: 0x000000,
    fogDensity: 0.025,
    gridColor: 0x111111,
    gridOpacity: 0.1,
    ambientLightColor: 0x334455,
    ambientLightIntensity: 0.2
  },

  materials: {
    cabinetBody: {
      color: 0x0a0a0a,
      metalness: 0.5,
      roughness: 0.5,
      envMapIntensity: 0.3,
      emissive: 0x000511,
      emissiveIntensity: 0.05
    },
    cabinetFrame: {
      color: 0x151515,
      metalness: 0.6,
      roughness: 0.4
    },
    floor: {
      color: 0x000000,
      metalness: 0.2,
      roughness: 0.8,
      opacity: 0.9
    }
  },

  ui: {
    primaryColor: '#336688',
    secondaryColor: '#224466',
    successColor: '#2a6a3a',
    warningColor: '#8a6a2a',
    dangerColor: '#8a3a3a',
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    borderColor: 'rgba(50, 50, 70, 0.4)',
    textColor: '#888888',
    textColorSecondary: '#555555',
    panelOpacity: 0.8,
    borderStyle: 'solid'
  },

  effects: {
    bloom: false,
    bloomStrength: 0.2,
    outline: true,
    outlineColor: 0x336688,
    particles: false,
    flowLines: false
  }
}
