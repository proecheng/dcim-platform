// frontend/src/config/themes/wireframe.ts
import type { BigscreenTheme } from '@/types/theme'

/**
 * 科技线框主题
 * 纯黑背景 + 透明线框机柜
 */
export const wireframeTheme: BigscreenTheme = {
  name: 'wireframe',
  displayName: '科技线框',

  scene: {
    backgroundColor: 0x000000,
    fogColor: 0x000000,
    fogDensity: 0.005,
    gridColor: 0x003344,
    gridOpacity: 0.5,
    ambientLightColor: 0x446688,
    ambientLightIntensity: 0.3
  },

  materials: {
    cabinetBody: {
      color: 0x003355,
      metalness: 0.1,
      roughness: 0.9,
      envMapIntensity: 0.2,
      emissive: 0x001133,
      emissiveIntensity: 0.3
    },
    cabinetFrame: {
      color: 0x00ccff,
      metalness: 0.0,
      roughness: 1.0
    },
    floor: {
      color: 0x000000,
      metalness: 0.0,
      roughness: 1.0,
      opacity: 0.5
    }
  },

  ui: {
    primaryColor: '#00ffff',
    secondaryColor: '#00ccff',
    successColor: '#00ff88',
    warningColor: '#ffff00',
    dangerColor: '#ff0055',
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    borderColor: 'rgba(0, 255, 255, 0.6)',
    textColor: '#00ffff',
    textColorSecondary: '#006688',
    panelOpacity: 0.7,
    borderStyle: 'solid'
  },

  effects: {
    bloom: true,
    bloomStrength: 0.8,
    outline: true,
    outlineColor: 0x00ffff,
    particles: false,
    flowLines: true
  }
}
