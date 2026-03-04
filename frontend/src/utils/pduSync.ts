const POWER_ENTITY_SYNC_EVENT = 'power-entity-changed'

export type PowerEntityType = 'pdu' | 'panel' | 'battery'
type PowerEntitySource = 'pdu' | 'topology' | 'cabinet' | 'battery' | 'ups'
type PowerEntityAction = 'create' | 'update' | 'delete'

interface PowerEntitySyncDetail {
  entity: PowerEntityType
  source: PowerEntitySource
  action: PowerEntityAction
  timestamp: number
}

export function notifyPowerEntityChanged(entity: PowerEntityType, source: PowerEntitySource, action: PowerEntityAction) {
  const detail: PowerEntitySyncDetail = {
    entity,
    source,
    action,
    timestamp: Date.now()
  }

  window.dispatchEvent(new CustomEvent<PowerEntitySyncDetail>(POWER_ENTITY_SYNC_EVENT, { detail }))
}

export function subscribePowerEntityChanged(entity: PowerEntityType, handler: () => void): () => void {
  const listener = (event: Event) => {
    const customEvent = event as CustomEvent<PowerEntitySyncDetail>
    if (customEvent.detail?.entity === entity) {
      handler()
    }
  }

  window.addEventListener(POWER_ENTITY_SYNC_EVENT, listener)
  return () => window.removeEventListener(POWER_ENTITY_SYNC_EVENT, listener)
}

export function notifyPduTopologyChanged(source: 'pdu' | 'topology', action: PowerEntityAction) {
  notifyPowerEntityChanged('pdu', source, action)
}

export function subscribePduTopologyChanged(handler: () => void): () => void {
  return subscribePowerEntityChanged('pdu', handler)
}

export function notifyPanelTopologyChanged(source: 'cabinet' | 'topology', action: PowerEntityAction) {
  notifyPowerEntityChanged('panel', source, action)
}

export function subscribePanelTopologyChanged(handler: () => void): () => void {
  return subscribePowerEntityChanged('panel', handler)
}

export function notifyBatteryChanged(action: PowerEntityAction) {
  notifyPowerEntityChanged('battery', 'battery', action)
}

export function subscribeBatteryChanged(handler: () => void): () => void {
  return subscribePowerEntityChanged('battery', handler)
}
