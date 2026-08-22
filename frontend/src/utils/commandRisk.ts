import type { RiskConfigItem } from '@/api/modules/command'

export type CommandRiskLevel = RiskConfigItem['risk_level']

export function canSelectRiskLevel(config: Pick<RiskConfigItem, 'minimum_risk'>, level: CommandRiskLevel) {
  return config.minimum_risk !== 'critical' || level === 'critical'
}
