// frontend/src/config/themes/index.ts
import type { BigscreenTheme, ThemeName } from '@/types/theme'
import { techBlueTheme } from './tech-blue'
import { wireframeTheme } from './wireframe'
import { realisticTheme } from './realistic'
import { nightTheme } from './night'

// 所有可用主题
export const themes: Record<ThemeName, BigscreenTheme> = {
  'tech-blue': techBlueTheme,
  'wireframe': wireframeTheme,
  'realistic': realisticTheme,
  'night': nightTheme
}

// 默认主题
export const defaultTheme = techBlueTheme

// 获取主题列表
export function getThemeList(): { name: ThemeName; displayName: string }[] {
  return Object.entries(themes).map(([name, theme]) => ({
    name: name as ThemeName,
    displayName: theme.displayName
  }))
}

// 获取主题
export function getTheme(name: ThemeName): BigscreenTheme {
  return themes[name] || defaultTheme
}

export { techBlueTheme, wireframeTheme, realisticTheme, nightTheme }
