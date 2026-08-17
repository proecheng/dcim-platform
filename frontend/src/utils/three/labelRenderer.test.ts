import { describe, expect, it } from 'vitest'

import { createPowerLabel, createTemperatureLabel, updateLabelContent } from './labelRenderer'


describe('Three.js labels', () => {
  it('renders device names as text', () => {
    const label = createPowerLabel(12.5, '<img src=x onerror=alert(1)>')

    expect(label.element.querySelector('img')).toBeNull()
    expect(label.element.textContent).toContain('<img src=x onerror=alert(1)>')
  })

  it('updates label content as text', () => {
    const label = createTemperatureLabel(25)

    updateLabelContent(label, '<svg onload=alert(1)>')

    expect(label.element.querySelector('svg')).toBeNull()
    expect(label.element.textContent).toBe('<svg onload=alert(1)>')
  })
})
