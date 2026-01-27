// frontend/src/composables/bigscreen/useBuildingModel.ts
import { ref, shallowRef } from 'vue'
import * as THREE from 'three'
import { CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js'

export interface BuildingFloor {
  name: string
  label: string
  group: THREE.Group
  visible: boolean
}

export interface UseBuildingModelOptions {
  scene: THREE.Scene
  floorHeight?: number
  buildingWidth?: number
  buildingDepth?: number
}

export interface FloorEquipmentInfo {
  cabinets: number
  ups: number
  ac: number
  chillers?: number
  coolingTowers?: number
  pumps?: number
}

// Floor specifications based on the plan
const FLOOR_SPECS: Record<string, FloorEquipmentInfo> = {
  B1: { cabinets: 0, ups: 0, ac: 0, chillers: 2, coolingTowers: 2, pumps: 4 },
  F1: { cabinets: 20, ups: 2, ac: 4 },
  F2: { cabinets: 15, ups: 2, ac: 4 },
  F3: { cabinets: 8, ups: 1, ac: 2 }
}

export function useBuildingModel(options: UseBuildingModelOptions) {
  const { scene, floorHeight = 4, buildingWidth = 40, buildingDepth = 25 } = options

  const buildingGroup = shallowRef<THREE.Group | null>(null)
  const floors = ref<BuildingFloor[]>([])
  const currentFloor = ref<string>('all')
  const highlightedFloor = ref<string | null>(null)

  // Store original materials for highlight/restore
  const originalMaterials = new Map<THREE.Mesh, THREE.Material | THREE.Material[]>()

  // Materials with proper typing
  const materials = {
    floor: new THREE.MeshStandardMaterial({
      color: 0x1a2a4a,
      metalness: 0.3,
      roughness: 0.7
    }),
    wall: new THREE.MeshStandardMaterial({
      color: 0x2a3a5a,
      metalness: 0.2,
      roughness: 0.8,
      transparent: true,
      opacity: 0.3
    }),
    cabinet: new THREE.MeshStandardMaterial({
      color: 0x409eff,
      metalness: 0.5,
      roughness: 0.4
    }),
    cabinetActive: new THREE.MeshStandardMaterial({
      color: 0x67c23a,
      metalness: 0.5,
      roughness: 0.4,
      emissive: 0x67c23a,
      emissiveIntensity: 0.2
    }),
    cabinetWarning: new THREE.MeshStandardMaterial({
      color: 0xe6a23c,
      metalness: 0.5,
      roughness: 0.4,
      emissive: 0xe6a23c,
      emissiveIntensity: 0.3
    }),
    cabinetError: new THREE.MeshStandardMaterial({
      color: 0xf56c6c,
      metalness: 0.5,
      roughness: 0.4,
      emissive: 0xf56c6c,
      emissiveIntensity: 0.4
    }),
    ups: new THREE.MeshStandardMaterial({
      color: 0xe6a23c,
      metalness: 0.4,
      roughness: 0.5
    }),
    ac: new THREE.MeshStandardMaterial({
      color: 0x67c23a,
      metalness: 0.3,
      roughness: 0.6
    }),
    chiller: new THREE.MeshStandardMaterial({
      color: 0x2a5a8a,
      metalness: 0.4,
      roughness: 0.5
    }),
    coolingTower: new THREE.MeshStandardMaterial({
      color: 0x4a7a9a,
      metalness: 0.3,
      roughness: 0.6
    }),
    pump: new THREE.MeshStandardMaterial({
      color: 0x5a8a5a,
      metalness: 0.4,
      roughness: 0.5
    }),
    glass: new THREE.MeshStandardMaterial({
      color: 0x88ccff,
      metalness: 0.9,
      roughness: 0.1,
      transparent: true,
      opacity: 0.2
    }),
    highlight: new THREE.MeshStandardMaterial({
      color: 0xffff00,
      metalness: 0.3,
      roughness: 0.5,
      emissive: 0xffff00,
      emissiveIntensity: 0.3
    }),
    office: new THREE.MeshStandardMaterial({
      color: 0x6a7a8a,
      metalness: 0.2,
      roughness: 0.7,
      transparent: true,
      opacity: 0.4
    })
  }

  /**
   * Create the complete building with all floors
   */
  function createBuilding(): THREE.Group {
    const building = new THREE.Group()
    building.name = 'datacenter-building'

    // Create each floor
    const b1 = createFloorB1(-floorHeight) // Underground
    const f1 = createFloorF1(0)
    const f2 = createFloorF2(floorHeight)
    const f3 = createFloorF3(floorHeight * 2)

    floors.value = [
      { name: 'B1', label: 'B1 制冷机房', group: b1, visible: true },
      { name: 'F1', label: 'F1 机房区A', group: f1, visible: true },
      { name: 'F2', label: 'F2 机房区B', group: f2, visible: true },
      { name: 'F3', label: 'F3 办公监控', group: f3, visible: true }
    ]

    building.add(b1, f1, f2, f3)

    // Add outer building shell/glass
    addBuildingShell(building)

    // Add ground plane
    addGroundPlane(building)

    buildingGroup.value = building
    scene.add(building)

    return building
  }

  /**
   * Create B1 floor - Underground cooling equipment area (500 sqm)
   */
  function createFloorB1(yOffset: number): THREE.Group {
    const floor = new THREE.Group()
    floor.name = 'floor-B1'
    floor.position.y = yOffset
    floor.userData = { floorName: 'B1', specs: FLOOR_SPECS.B1 }

    // Floor slab (smaller for B1 - underground)
    const floorWidth = buildingWidth * 0.7
    const floorDepth = buildingDepth * 0.8
    const floorGeom = new THREE.BoxGeometry(floorWidth, 0.3, floorDepth)
    const floorMesh = new THREE.Mesh(floorGeom, materials.floor)
    floorMesh.position.y = 0
    floorMesh.receiveShadow = true
    floorMesh.name = 'floor-slab-B1'
    floor.add(floorMesh)

    // Ceiling
    const ceilingMesh = new THREE.Mesh(floorGeom, materials.floor.clone())
    ceilingMesh.position.y = floorHeight - 0.15
    ceilingMesh.name = 'ceiling-B1'
    floor.add(ceilingMesh)

    // Chillers (2 units) - Large cooling machines
    for (let i = 0; i < 2; i++) {
      const chiller = createEquipment(6, 2.5, 3, materials.chiller, 'chiller')
      chiller.position.set(-8 + i * 12, 1.25, -4)
      chiller.name = `B1-CH-${i + 1}`
      chiller.userData = { type: 'chiller', id: `CH-${i + 1}`, floor: 'B1' }
      floor.add(chiller)
      addLabel(chiller, `冷水机组${i + 1}`)
    }

    // Cooling towers (2 units)
    for (let i = 0; i < 2; i++) {
      const tower = createEquipment(4, 3, 4, materials.coolingTower, 'coolingTower')
      tower.position.set(-6 + i * 10, 1.5, 6)
      tower.name = `B1-CT-${i + 1}`
      tower.userData = { type: 'coolingTower', id: `CT-${i + 1}`, floor: 'B1' }
      floor.add(tower)
      addLabel(tower, `冷却塔${i + 1}`)
    }

    // Chilled water pumps (2 units)
    for (let i = 0; i < 2; i++) {
      const pump = createEquipment(2, 1.5, 2, materials.pump, 'pump')
      pump.position.set(8 + i * 4, 0.75, -4)
      pump.name = `B1-CHWP-${i + 1}`
      pump.userData = { type: 'pump', id: `CHWP-${i + 1}`, floor: 'B1' }
      floor.add(pump)
      addLabel(pump, `冷冻水泵${i + 1}`)
    }

    // Cooling water pumps (2 units)
    for (let i = 0; i < 2; i++) {
      const pump = createEquipment(2, 1.5, 2, materials.pump, 'pump')
      pump.position.set(8 + i * 4, 0.75, 2)
      pump.name = `B1-CWP-${i + 1}`
      pump.userData = { type: 'pump', id: `CWP-${i + 1}`, floor: 'B1' }
      floor.add(pump)
      addLabel(pump, `冷却水泵${i + 1}`)
    }

    // Piping visualization (simplified)
    addPipingVisualization(floor)

    return floor
  }

  /**
   * Create F1 floor - Main server room A (1000 sqm, 20 cabinets)
   */
  function createFloorF1(yOffset: number): THREE.Group {
    const floor = new THREE.Group()
    floor.name = 'floor-F1'
    floor.position.y = yOffset
    floor.userData = { floorName: 'F1', specs: FLOOR_SPECS.F1 }

    // Floor slab
    const floorGeom = new THREE.BoxGeometry(buildingWidth, 0.3, buildingDepth)
    const floorMesh = new THREE.Mesh(floorGeom, materials.floor)
    floorMesh.receiveShadow = true
    floorMesh.name = 'floor-slab-F1'
    floor.add(floorMesh)

    // Raised floor visualization
    addRaisedFloor(floor, buildingWidth * 0.8, buildingDepth * 0.6, -2, -2)

    // 20 cabinets in 4 rows of 5
    createCabinetGrid(floor, 20, 4, 5, -14, -6, 'F1')

    // UPS units (2) - on the side
    for (let i = 0; i < 2; i++) {
      const ups = createEquipment(3, 2.5, 2, materials.ups, 'ups')
      ups.position.set(-16 + i * 6, 1.25, 10)
      ups.name = `F1-UPS-${i + 1}`
      ups.userData = { type: 'ups', id: `UPS-${i + 1}`, floor: 'F1' }
      floor.add(ups)
      addLabel(ups, `UPS-${i + 1}`)
    }

    // CRAC units (4) - precision air conditioning
    for (let i = 0; i < 4; i++) {
      const ac = createEquipment(2, 2.5, 1.5, materials.ac, 'ac')
      ac.position.set(-14 + i * 9, 1.25, -10)
      ac.name = `F1-CRAC-${i + 1}`
      ac.userData = { type: 'ac', id: `CRAC-${i + 1}`, floor: 'F1' }
      floor.add(ac)
      addLabel(ac, `精密空调${i + 1}`)
    }

    // PDU (Power Distribution Units)
    for (let i = 0; i < 2; i++) {
      const pdu = createEquipment(1, 2, 0.8, materials.ups, 'pdu')
      pdu.position.set(15, 1, -6 + i * 6)
      pdu.name = `F1-PDU-${i + 1}`
      pdu.userData = { type: 'pdu', id: `PDU-${i + 1}`, floor: 'F1' }
      floor.add(pdu)
    }

    return floor
  }

  /**
   * Create F2 floor - Server room B (1000 sqm, 15 cabinets)
   */
  function createFloorF2(yOffset: number): THREE.Group {
    const floor = new THREE.Group()
    floor.name = 'floor-F2'
    floor.position.y = yOffset
    floor.userData = { floorName: 'F2', specs: FLOOR_SPECS.F2 }

    // Floor slab
    const floorGeom = new THREE.BoxGeometry(buildingWidth, 0.3, buildingDepth)
    const floorMesh = new THREE.Mesh(floorGeom, materials.floor)
    floorMesh.receiveShadow = true
    floorMesh.name = 'floor-slab-F2'
    floor.add(floorMesh)

    // Raised floor
    addRaisedFloor(floor, buildingWidth * 0.7, buildingDepth * 0.5, -2, -2)

    // 15 cabinets in 3 rows of 5
    createCabinetGrid(floor, 15, 3, 5, -14, -4, 'F2')

    // UPS units (2)
    for (let i = 0; i < 2; i++) {
      const ups = createEquipment(3, 2.5, 2, materials.ups, 'ups')
      ups.position.set(-16 + i * 6, 1.25, 10)
      ups.name = `F2-UPS-${i + 1}`
      ups.userData = { type: 'ups', id: `UPS-${i + 1}`, floor: 'F2' }
      floor.add(ups)
      addLabel(ups, `UPS-${i + 1}`)
    }

    // CRAC units (4)
    for (let i = 0; i < 4; i++) {
      const ac = createEquipment(2, 2.5, 1.5, materials.ac, 'ac')
      ac.position.set(-14 + i * 9, 1.25, -10)
      ac.name = `F2-CRAC-${i + 1}`
      ac.userData = { type: 'ac', id: `CRAC-${i + 1}`, floor: 'F2' }
      floor.add(ac)
    }

    // Battery room
    const batteryRoom = createEquipment(8, 2.5, 5, materials.office, 'room')
    batteryRoom.position.set(12, 1.25, 6)
    batteryRoom.name = 'F2-BatteryRoom'
    batteryRoom.userData = { type: 'room', id: 'BatteryRoom', floor: 'F2' }
    floor.add(batteryRoom)
    addLabel(batteryRoom, '电池室')

    return floor
  }

  /**
   * Create F3 floor - Office and NOC area (1000 sqm, 8 cabinets)
   */
  function createFloorF3(yOffset: number): THREE.Group {
    const floor = new THREE.Group()
    floor.name = 'floor-F3'
    floor.position.y = yOffset
    floor.userData = { floorName: 'F3', specs: FLOOR_SPECS.F3 }

    // Floor slab
    const floorGeom = new THREE.BoxGeometry(buildingWidth, 0.3, buildingDepth)
    const floorMesh = new THREE.Mesh(floorGeom, materials.floor)
    floorMesh.receiveShadow = true
    floorMesh.name = 'floor-slab-F3'
    floor.add(floorMesh)

    // 8 cabinets in 2 rows of 4 (network/core equipment)
    createCabinetGrid(floor, 8, 2, 4, -8, -8, 'F3')

    // NOC/Monitoring center - large glass-walled room
    const noc = createEquipment(14, 2.5, 8, materials.glass, 'room')
    noc.position.set(-6, 1.25, 6)
    noc.name = 'F3-NOC'
    noc.userData = { type: 'room', id: 'NOC', floor: 'F3' }
    floor.add(noc)
    addLabel(noc, '网络运维中心 (NOC)')

    // Add monitoring desks inside NOC
    for (let i = 0; i < 3; i++) {
      const desk = createEquipment(3, 0.8, 1.5, materials.floor, 'furniture')
      desk.position.set(-10 + i * 4, 0.4, 6)
      desk.name = `F3-Desk-${i + 1}`
      floor.add(desk)
    }

    // Meeting room
    const meeting = createEquipment(8, 2.5, 6, materials.glass, 'room')
    meeting.position.set(12, 1.25, 6)
    meeting.name = 'F3-Meeting'
    meeting.userData = { type: 'room', id: 'Meeting', floor: 'F3' }
    floor.add(meeting)
    addLabel(meeting, '会议室')

    // Office area
    const office = createEquipment(10, 2.5, 5, materials.office, 'room')
    office.position.set(10, 1.25, -6)
    office.name = 'F3-Office'
    office.userData = { type: 'room', id: 'Office', floor: 'F3' }
    floor.add(office)
    addLabel(office, '办公区')

    // Single UPS for this floor
    const ups = createEquipment(3, 2.5, 2, materials.ups, 'ups')
    ups.position.set(-16, 1.25, -8)
    ups.name = 'F3-UPS-1'
    ups.userData = { type: 'ups', id: 'UPS-1', floor: 'F3' }
    floor.add(ups)
    addLabel(ups, 'UPS-1')

    // AC units (2)
    for (let i = 0; i < 2; i++) {
      const ac = createEquipment(2, 2.5, 1.5, materials.ac, 'ac')
      ac.position.set(-14 + i * 28, 1.25, -10)
      ac.name = `F3-AC-${i + 1}`
      ac.userData = { type: 'ac', id: `AC-${i + 1}`, floor: 'F3' }
      floor.add(ac)
    }

    return floor
  }

  /**
   * Create a grid of server cabinets
   */
  function createCabinetGrid(
    floor: THREE.Group,
    total: number,
    rows: number,
    cols: number,
    startX: number,
    startZ: number,
    floorName: string
  ): void {
    const cabinetWidth = 0.6 // Standard 600mm
    const cabinetHeight = 2.0 // ~42U rack
    const cabinetDepth = 1.0 // Standard 1000mm
    const spacingX = 2.2 // Hot/cold aisle spacing
    const spacingZ = 2.5 // Row spacing

    for (let i = 0; i < total; i++) {
      const row = Math.floor(i / cols)
      const col = i % cols

      // Alternate cabinet orientation for hot/cold aisle
      const cabinet = createEquipment(cabinetWidth, cabinetHeight, cabinetDepth, materials.cabinet, 'cabinet')
      cabinet.position.set(startX + col * spacingX, cabinetHeight / 2, startZ + row * spacingZ)

      // Rotate every other row for hot/cold aisle containment
      if (row % 2 === 1) {
        cabinet.rotation.y = Math.PI
      }

      const cabinetId = String(i + 1).padStart(2, '0')
      cabinet.name = `${floorName}-Cabinet-${cabinetId}`
      cabinet.userData = {
        type: 'cabinet',
        id: `Cabinet-${cabinetId}`,
        floor: floorName,
        row: row + 1,
        position: col + 1
      }
      cabinet.castShadow = true
      floor.add(cabinet)

      // Add status indicator on top
      addCabinetStatusIndicator(cabinet)
    }
  }

  /**
   * Create equipment mesh with edges for better visibility
   */
  function createEquipment(
    width: number,
    height: number,
    depth: number,
    material: THREE.Material,
    type: string
  ): THREE.Mesh {
    const geom = new THREE.BoxGeometry(width, height, depth)
    const mesh = new THREE.Mesh(geom, material)
    mesh.castShadow = true
    mesh.receiveShadow = true
    mesh.userData.equipmentType = type

    // Add edges for better visibility
    const edgesGeometry = new THREE.EdgesGeometry(geom)
    const edgesMaterial = new THREE.LineBasicMaterial({ color: 0x4a5a6a, transparent: true, opacity: 0.5 })
    const edges = new THREE.LineSegments(edgesGeometry, edgesMaterial)
    edges.name = 'edges'
    mesh.add(edges)

    return mesh
  }

  /**
   * Add status indicator light on top of cabinet
   */
  function addCabinetStatusIndicator(cabinet: THREE.Mesh): void {
    const indicatorGeom = new THREE.CylinderGeometry(0.1, 0.1, 0.05, 8)
    const indicatorMat = new THREE.MeshBasicMaterial({ color: 0x00ff00 })
    const indicator = new THREE.Mesh(indicatorGeom, indicatorMat)
    indicator.position.y = 1.05 // On top of cabinet
    indicator.name = 'status-indicator'
    indicator.userData.isIndicator = true
    cabinet.add(indicator)
  }

  /**
   * Add piping visualization for B1 cooling system
   */
  function addPipingVisualization(floor: THREE.Group): void {
    const pipeMaterial = new THREE.MeshStandardMaterial({
      color: 0x4488ff,
      metalness: 0.6,
      roughness: 0.3
    })

    // Main supply pipe
    const pipeGeom = new THREE.CylinderGeometry(0.15, 0.15, 20, 8)
    pipeGeom.rotateZ(Math.PI / 2)
    const mainPipe = new THREE.Mesh(pipeGeom, pipeMaterial)
    mainPipe.position.set(0, 0.5, 0)
    mainPipe.name = 'main-supply-pipe'
    floor.add(mainPipe)

    // Return pipe (orange/red)
    const returnPipeMat = new THREE.MeshStandardMaterial({
      color: 0xff6644,
      metalness: 0.6,
      roughness: 0.3
    })
    const returnPipe = new THREE.Mesh(pipeGeom.clone(), returnPipeMat)
    returnPipe.position.set(0, 0.5, 2)
    returnPipe.name = 'main-return-pipe'
    floor.add(returnPipe)
  }

  /**
   * Add raised floor visualization
   */
  function addRaisedFloor(
    floor: THREE.Group,
    width: number,
    depth: number,
    offsetX: number,
    offsetZ: number
  ): void {
    const raisedFloorMat = new THREE.MeshStandardMaterial({
      color: 0x3a4a5a,
      metalness: 0.2,
      roughness: 0.8,
      transparent: true,
      opacity: 0.6
    })

    const raisedFloorGeom = new THREE.BoxGeometry(width, 0.1, depth)
    const raisedFloor = new THREE.Mesh(raisedFloorGeom, raisedFloorMat)
    raisedFloor.position.set(offsetX, 0.2, offsetZ)
    raisedFloor.name = 'raised-floor'
    floor.add(raisedFloor)

    // Add floor tile grid pattern
    const gridHelper = new THREE.GridHelper(Math.max(width, depth), Math.floor(Math.max(width, depth) / 0.6), 0x5a6a7a, 0x4a5a6a)
    gridHelper.position.set(offsetX, 0.26, offsetZ)
    gridHelper.name = 'floor-grid'
    floor.add(gridHelper)
  }

  /**
   * Add outer building shell/glass facade
   */
  function addBuildingShell(building: THREE.Group): void {
    // Glass exterior shell
    const shellHeight = floorHeight * 3.2
    const shellGeom = new THREE.BoxGeometry(buildingWidth + 1, shellHeight, buildingDepth + 1)

    // Create glass material with better transparency
    const glassMaterial = new THREE.MeshStandardMaterial({
      color: 0x88ccff,
      metalness: 0.9,
      roughness: 0.1,
      transparent: true,
      opacity: 0.15,
      side: THREE.DoubleSide
    })

    const shellMesh = new THREE.Mesh(shellGeom, glassMaterial)
    shellMesh.position.y = floorHeight * 1.1
    shellMesh.name = 'building-shell'
    building.add(shellMesh)

    // Add building edges for better definition
    const shellEdges = new THREE.EdgesGeometry(shellGeom)
    const shellEdgesMat = new THREE.LineBasicMaterial({ color: 0x4488aa, transparent: true, opacity: 0.6 })
    const shellEdgesLine = new THREE.LineSegments(shellEdges, shellEdgesMat)
    shellEdgesLine.position.copy(shellMesh.position)
    shellEdgesLine.name = 'building-shell-edges'
    building.add(shellEdgesLine)

    // Roof
    const roofGeom = new THREE.BoxGeometry(buildingWidth + 2, 0.5, buildingDepth + 2)
    const roofMat = new THREE.MeshStandardMaterial({
      color: 0x2a3a4a,
      metalness: 0.3,
      roughness: 0.7
    })
    const roof = new THREE.Mesh(roofGeom, roofMat)
    roof.position.y = floorHeight * 2.75
    roof.name = 'building-roof'
    roof.receiveShadow = true
    building.add(roof)

    // Roof equipment (HVAC units)
    for (let i = 0; i < 4; i++) {
      const hvac = createEquipment(3, 1.5, 2, materials.ac, 'hvac')
      hvac.position.set(-12 + i * 8, floorHeight * 2.75 + 1, 0)
      hvac.name = `roof-HVAC-${i + 1}`
      building.add(hvac)
    }
  }

  /**
   * Add ground plane around the building
   */
  function addGroundPlane(building: THREE.Group): void {
    const groundGeom = new THREE.PlaneGeometry(buildingWidth * 2.5, buildingDepth * 2.5)
    const groundMat = new THREE.MeshStandardMaterial({
      color: 0x1a1a2a,
      metalness: 0.1,
      roughness: 0.9
    })
    const ground = new THREE.Mesh(groundGeom, groundMat)
    ground.rotation.x = -Math.PI / 2
    ground.position.y = -floorHeight - 0.1
    ground.receiveShadow = true
    ground.name = 'ground-plane'
    building.add(ground)

    // Add grid on ground
    const gridHelper = new THREE.GridHelper(buildingWidth * 2, 40, 0x2a3a4a, 0x1a2a3a)
    gridHelper.position.y = -floorHeight
    gridHelper.name = 'ground-grid'
    building.add(gridHelper)
  }

  /**
   * Add CSS2D label to an object
   */
  function addLabel(object: THREE.Object3D, text: string): CSS2DObject {
    const div = document.createElement('div')
    div.className = 'building-label'
    div.textContent = text
    div.style.cssText = `
      color: #fff;
      font-size: 10px;
      background: rgba(0, 20, 40, 0.75);
      padding: 2px 8px;
      border-radius: 3px;
      white-space: nowrap;
      pointer-events: none;
      border: 1px solid rgba(64, 158, 255, 0.3);
    `
    const label = new CSS2DObject(div)
    label.position.set(0, 2, 0)
    label.name = 'label'
    object.add(label)
    return label
  }

  // ==================== Floor Visibility Control ====================

  /**
   * Set visibility of a specific floor
   */
  function setFloorVisibility(floorName: string, visible: boolean): void {
    const floor = floors.value.find((f) => f.name === floorName)
    if (floor) {
      floor.group.visible = visible
      floor.visible = visible
    }
  }

  /**
   * Show all floors
   */
  function showAllFloors(): void {
    floors.value.forEach((f) => {
      f.group.visible = true
      f.visible = true
    })
    currentFloor.value = 'all'
  }

  /**
   * Show only a single floor (hide others)
   */
  function showSingleFloor(floorName: string): void {
    floors.value.forEach((f) => {
      const show = f.name === floorName
      f.group.visible = show
      f.visible = show
    })
    currentFloor.value = floorName

    // Also hide the building shell when viewing single floor
    if (buildingGroup.value) {
      const shell = buildingGroup.value.getObjectByName('building-shell')
      const shellEdges = buildingGroup.value.getObjectByName('building-shell-edges')
      const roof = buildingGroup.value.getObjectByName('building-roof')
      if (shell) shell.visible = false
      if (shellEdges) shellEdges.visible = false
      if (roof) roof.visible = floorName === 'F3'
    }
  }

  /**
   * Toggle floor visibility
   */
  function toggleFloorVisibility(floorName: string): boolean {
    const floor = floors.value.find((f) => f.name === floorName)
    if (floor) {
      const newState = !floor.visible
      setFloorVisibility(floorName, newState)
      return newState
    }
    return false
  }

  // ==================== Highlight Control ====================

  /**
   * Highlight a specific floor
   */
  function highlightFloor(floorName: string): void {
    // Clear previous highlight
    clearHighlight()

    const floor = floors.value.find((f) => f.name === floorName)
    if (!floor) return

    highlightedFloor.value = floorName

    floor.group.traverse((obj) => {
      if (obj instanceof THREE.Mesh && obj.material && !obj.userData.isIndicator) {
        // Store original material
        originalMaterials.set(obj, obj.material)

        // Create highlighted version
        const origMat = obj.material as THREE.MeshStandardMaterial
        if (origMat.isMeshStandardMaterial) {
          const highlightMat = origMat.clone()
          highlightMat.emissive = new THREE.Color(0x4488ff)
          highlightMat.emissiveIntensity = 0.2
          obj.material = highlightMat
        }
      }
    })
  }

  /**
   * Highlight a specific equipment by name
   */
  function highlightEquipment(equipmentName: string): void {
    if (!buildingGroup.value) return

    const equipment = buildingGroup.value.getObjectByName(equipmentName)
    if (equipment instanceof THREE.Mesh) {
      originalMaterials.set(equipment, equipment.material)
      equipment.material = materials.highlight.clone()
    }
  }

  /**
   * Clear all highlights
   */
  function clearHighlight(): void {
    // Restore original materials
    originalMaterials.forEach((material, mesh) => {
      mesh.material = material
    })
    originalMaterials.clear()
    highlightedFloor.value = null
  }

  // ==================== Equipment Status ====================

  /**
   * Update cabinet status indicator color
   */
  function updateCabinetStatus(cabinetName: string, status: 'normal' | 'warning' | 'error' | 'offline'): void {
    if (!buildingGroup.value) return

    const cabinet = buildingGroup.value.getObjectByName(cabinetName)
    if (!cabinet) return

    const indicator = cabinet.getObjectByName('status-indicator') as THREE.Mesh | undefined
    if (indicator && indicator.material instanceof THREE.MeshBasicMaterial) {
      const colors = {
        normal: 0x00ff00,
        warning: 0xffaa00,
        error: 0xff0000,
        offline: 0x666666
      }
      indicator.material.color.setHex(colors[status])
    }
  }

  /**
   * Update multiple cabinet statuses at once
   */
  function updateCabinetStatuses(statuses: Record<string, 'normal' | 'warning' | 'error' | 'offline'>): void {
    Object.entries(statuses).forEach(([name, status]) => {
      updateCabinetStatus(name, status)
    })
  }

  // ==================== Query Functions ====================

  /**
   * Get all equipment on a specific floor
   */
  function getFloorEquipment(floorName: string): THREE.Object3D[] {
    const floor = floors.value.find((f) => f.name === floorName)
    if (!floor) return []

    const equipment: THREE.Object3D[] = []
    floor.group.traverse((obj) => {
      if (obj.userData.type) {
        equipment.push(obj)
      }
    })
    return equipment
  }

  /**
   * Get equipment by type across all floors
   */
  function getEquipmentByType(type: string): THREE.Object3D[] {
    if (!buildingGroup.value) return []

    const equipment: THREE.Object3D[] = []
    buildingGroup.value.traverse((obj) => {
      if (obj.userData.type === type) {
        equipment.push(obj)
      }
    })
    return equipment
  }

  /**
   * Get all cabinets
   */
  function getAllCabinets(): THREE.Object3D[] {
    return getEquipmentByType('cabinet')
  }

  /**
   * Find equipment by name
   */
  function findEquipment(name: string): THREE.Object3D | undefined {
    return buildingGroup.value?.getObjectByName(name) ?? undefined
  }

  // ==================== Disposal ====================

  /**
   * Dispose of all resources
   */
  function dispose(): void {
    clearHighlight()

    if (buildingGroup.value) {
      buildingGroup.value.traverse((obj) => {
        if (obj instanceof THREE.Mesh) {
          obj.geometry.dispose()
          if (Array.isArray(obj.material)) {
            obj.material.forEach((m) => m.dispose())
          } else if (obj.material) {
            obj.material.dispose()
          }
        }
        if (obj instanceof THREE.LineSegments) {
          obj.geometry.dispose()
          if (obj.material instanceof THREE.Material) {
            obj.material.dispose()
          }
        }
      })
      scene.remove(buildingGroup.value)
      buildingGroup.value = null
    }

    // Dispose materials
    Object.values(materials).forEach((m) => {
      if (m instanceof THREE.Material) {
        m.dispose()
      }
    })

    floors.value = []
    originalMaterials.clear()
  }

  return {
    // State
    buildingGroup,
    floors,
    currentFloor,
    highlightedFloor,

    // Building creation
    createBuilding,

    // Floor visibility
    setFloorVisibility,
    showAllFloors,
    showSingleFloor,
    toggleFloorVisibility,

    // Highlighting
    highlightFloor,
    highlightEquipment,
    clearHighlight,

    // Status updates
    updateCabinetStatus,
    updateCabinetStatuses,

    // Query functions
    getFloorEquipment,
    getEquipmentByType,
    getAllCabinets,
    findEquipment,

    // Disposal
    dispose
  }
}
