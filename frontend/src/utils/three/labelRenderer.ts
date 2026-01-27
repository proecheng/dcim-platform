// frontend/src/utils/three/labelRenderer.ts
import * as THREE from 'three'
import { CSS2DRenderer, CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js'

// 创建 CSS2D 渲染器
export function createLabelRenderer(container: HTMLElement): CSS2DRenderer {
  const labelRenderer = new CSS2DRenderer()
  labelRenderer.setSize(container.clientWidth, container.clientHeight)
  labelRenderer.domElement.style.position = 'absolute'
  labelRenderer.domElement.style.top = '0'
  labelRenderer.domElement.style.left = '0'
  labelRenderer.domElement.style.pointerEvents = 'none'
  container.appendChild(labelRenderer.domElement)
  return labelRenderer
}

// 创建功率标签
export function createPowerLabel(power: number, name: string): CSS2DObject {
  const div = document.createElement('div')
  div.className = 'power-label'
  div.innerHTML = `
    <div class="label-name">${name}</div>
    <div class="label-value">${power.toFixed(1)} kW</div>
  `
  div.style.cssText = `
    background: rgba(0, 20, 40, 0.85);
    border: 1px solid rgba(0, 136, 255, 0.5);
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
    color: #fff;
    white-space: nowrap;
    pointer-events: none;
  `

  const label = new CSS2DObject(div)
  label.name = 'power-label'
  return label
}

// 创建温度标签
export function createTemperatureLabel(temp: number): CSS2DObject {
  const div = document.createElement('div')
  div.className = 'temp-label'

  // 根据温度设置颜色
  let color = '#00ff88' // 正常
  if (temp > 30) color = '#ff3300' // 过热
  else if (temp > 26) color = '#ffcc00' // 偏热
  else if (temp < 18) color = '#0066ff' // 过冷

  div.innerHTML = `<span style="color: ${color}">${temp.toFixed(1)}°C</span>`
  div.style.cssText = `
    background: rgba(0, 0, 0, 0.7);
    border-radius: 3px;
    padding: 2px 6px;
    font-size: 10px;
    font-weight: bold;
    pointer-events: none;
  `

  const label = new CSS2DObject(div)
  label.name = 'temp-label'
  return label
}

// 更新标签内容
export function updateLabelContent(label: CSS2DObject, content: string): void {
  const div = label.element as HTMLDivElement
  if (div) {
    div.innerHTML = content
  }
}

// 设置标签可见性
export function setLabelVisibility(label: CSS2DObject, visible: boolean): void {
  label.visible = visible
  const div = label.element as HTMLDivElement
  if (div) {
    div.style.display = visible ? 'block' : 'none'
  }
}
