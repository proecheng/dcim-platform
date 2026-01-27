// frontend/src/config/themes/tech-blue.ts
import type { BigscreenTheme } from '@/types/theme'

/**
 * 科技蓝主题 (默认)
 * 深蓝背景 + 霓虹蓝光效
 */
export const techBlueTheme: BigscreenTheme = {
  name: 'tech-blue',
  displayName: '科技蓝',

  scene: {
    backgroundColor: 0x0a0a1a,
    fogColor: 0x0a0a1a,
    fogDensity: 0.015,
    gridColor: 0x004466,
    gridOpacity: 0.3,
    ambientLightColor: 0x88aacc,
    ambientLightIntensity: 0.4
  },

  materials: {
    cabinetBody: {
      color: 0x1a2a3a,
      metalness: 0.8,
      roughness: 0.3,
      envMapIntensity: 1.0,
      emissive: 0x001122,
      emissiveIntensity: 0.1
    },
    cabinetFrame: {
      color: 0x2a3a4a,
      metalness: 0.9,
      roughness: 0.2
    },
    floor: {
      color: 0x0a1520,
      metalness: 0.9,
      roughness: 0.1,
      opacity: 0.95
    }
  },

  ui: {
    primaryColor: '#00ccff',
    secondaryColor: '#0088ff',
    successColor: '#00ff88',
    warningColor: '#ffaa00',
    dangerColor: '#ff4d4f',
    backgroundColor: 'rgba(10, 15, 30, 0.85)',
    borderColor: 'rgba(0, 136, 255, 0.4)',
    textColor: '#ffffff',
    textColorSecondary: '#8899aa',
    panelOpacity: 0.85,
    borderStyle: 'glow'
  },

  effects: {
    bloom: true,
    bloomStrength: 0.5,
    outline: true,
    outlineColor: 0x00ccff,
    particles: true,
    flowLines: true
  }
}
