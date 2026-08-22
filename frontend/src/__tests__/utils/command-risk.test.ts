import { describe, expect, it } from 'vitest'
import { canSelectRiskLevel } from '@/utils/commandRisk'

describe('command risk policy', () => {
  it('prevents protected commands from being downgraded', () => {
    expect(canSelectRiskLevel({ minimum_risk: 'critical' }, 'normal')).toBe(false)
    expect(canSelectRiskLevel({ minimum_risk: 'critical' }, 'critical')).toBe(true)
  })

  it('allows normal commands to be promoted and restored', () => {
    expect(canSelectRiskLevel({ minimum_risk: 'normal' }, 'normal')).toBe(true)
    expect(canSelectRiskLevel({ minimum_risk: 'normal' }, 'critical')).toBe(true)
  })
})
