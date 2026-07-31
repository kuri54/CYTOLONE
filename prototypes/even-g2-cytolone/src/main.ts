import {
  CreateStartUpPageContainer,
  ListContainerProperty,
  ListItemContainerProperty,
  OsEventTypeList,
  RebuildPageContainer,
  TextContainerProperty,
  waitForEvenAppBridge,
  type EvenAppBridge,
  type EvenHubEvent,
} from '@evenrealities/even_hub_sdk'
import {
  compactScore,
  displaySpecimen,
  getEffectiveOrderType,
  getOrderTypeLabel,
  type HandsfreeState,
} from './workflow'

const API_URL = 'http://127.0.0.1:8765'
const POLL_INTERVAL_MS = 400
const RECONNECT_INTERVAL_MS = 1000

let bridge: EvenAppBridge | null = null
let startupRendered = false
let eventLoopRegistered = false
let remoteState: HandsfreeState | null = null
let menuView: 'main' | 'specimen' | 'mode' = 'main'
let selectedMenuIndex = 0
let renderSignature = ''

async function requestJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers ?? {}),
    },
  })
  const payload = await response.json()
  if (!response.ok) {
    const message = typeof payload?.message === 'string' ? payload.message : `HTTP ${response.status}`
    throw new Error(message)
  }
  return payload as T
}

function pageConfiguration() {
  let title = 'CYTOLONE | MAC OFFLINE'
  let detail = 'Start CYTOLONE on this Mac'
  let items = ['RETRY']
  let selectionBorder = 0

  if (remoteState && !remoteState.enabled) {
    title = 'CYTOLONE | G2 DISABLED'
    detail = 'Mac: External output -> Even G2'
    items = ['WAITING FOR ENABLE']
  } else if (remoteState?.status === 'queued' || remoteState?.status === 'analyzing') {
    title = 'CYTOLONE | ANALYZING'
    detail = `${displaySpecimen(remoteState.settings.specimen)} | ${getOrderTypeLabel(remoteState, getEffectiveOrderType(remoteState))}`
    items = ['ANALYZING | PLEASE WAIT']
  } else if (remoteState?.status === 'error') {
    title = `CYTOLONE | ${remoteState.error?.code ?? 'ERROR'}`
    detail = (remoteState.error?.message ?? 'Inference failed').slice(0, 90)
    items = ['Double click: Back']
  } else if (remoteState?.status === 'result' && remoteState.result) {
    title = `${displaySpecimen(remoteState.result.specimen)} | ${remoteState.result.order_type_label}`
    detail = 'ALL LABELS + % | Dbl: Back'
    items = remoteState.result.scores.map(compactScore)
    selectionBorder = 1
  } else if (remoteState && menuView === 'specimen') {
    title = 'CYTOLONE | SELECT SPECIMEN'
    detail = `Current: ${displaySpecimen(remoteState.settings.specimen)} | Click: Confirm | Dbl: Cancel`
    items = remoteState.available.specimens.map(displaySpecimen)
    selectionBorder = 1
  } else if (remoteState && menuView === 'mode') {
    title = 'CYTOLONE | SELECT MODE'
    detail = `Current: ${getOrderTypeLabel(remoteState, getEffectiveOrderType(remoteState))} | Click: Confirm | Dbl: Cancel`
    items = remoteState.available.order_types.map((option) => option.label.toUpperCase())
    selectionBorder = 1
  } else if (remoteState) {
    const mode = getEffectiveOrderType(remoteState)
    title = 'CYTOLONE | READY'
    detail = 'Up/Down: Select | Click: Action'
    items = [
      'ANALYZE',
      `SPECIMEN: ${displaySpecimen(remoteState.settings.specimen)}`,
      `MODE: ${getOrderTypeLabel(remoteState, mode).toUpperCase()}`,
    ]
    selectionBorder = 1
  }

  const titleText = new TextContainerProperty({
    containerID: 1,
    containerName: 'cytolone-title',
    content: title,
    xPosition: 8,
    yPosition: 8,
    width: 560,
    height: 48,
    isEventCapture: 0,
  })
  const detailText = new TextContainerProperty({
    containerID: 2,
    containerName: 'cytolone-detail',
    content: detail,
    xPosition: 8,
    yPosition: 58,
    width: 560,
    height: 46,
    isEventCapture: 0,
  })
  const actionList = new ListContainerProperty({
    containerID: 3,
    containerName: 'cytolone-actions',
    itemContainer: new ListItemContainerProperty({
      itemCount: items.length,
      itemWidth: 544,
      isItemSelectBorderEn: selectionBorder,
      itemName: items,
    }),
    isEventCapture: 1,
    xPosition: 8,
    yPosition: 110,
    width: 560,
    height: 170,
  })
  return {
    containerTotalNum: 3,
    textObject: [titleText, detailText],
    listObject: [actionList],
  }
}

async function renderGlasses(force = false): Promise<void> {
  if (!bridge) return
  const nextSignature = JSON.stringify({
    revision: remoteState?.revision ?? -1,
    menuView,
    online: Boolean(remoteState),
  })
  if (!force && renderSignature === nextSignature) return

  const config = pageConfiguration()
  if (!startupRendered) {
    await bridge.createStartUpPageContainer(new CreateStartUpPageContainer(config))
    startupRendered = true
  } else {
    await bridge.rebuildPageContainer(new RebuildPageContainer(config))
  }
  renderSignature = nextSignature
}

async function pollMac(): Promise<void> {
  try {
    remoteState = await requestJson<HandsfreeState>('/api/state')
  } catch {
    remoteState = null
  }
  await renderGlasses()
}

async function requestAnalyze(): Promise<void> {
  if (!remoteState) return
  const orderType = getEffectiveOrderType(remoteState)
  try {
    await requestJson('/api/analyze', {
      method: 'POST',
      body: JSON.stringify({
        specimen: remoteState.settings.specimen,
        order_type: orderType,
      }),
    })
    await pollMac()
  } catch (error) {
    console.error('Analyze rejected', error)
  }
}

async function updateSettings(specimen: string, orderType: string): Promise<void> {
  try {
    remoteState = await requestJson<HandsfreeState>('/api/settings', {
      method: 'POST',
      body: JSON.stringify({ specimen, order_type: orderType }),
    })
    await renderGlasses(true)
  } catch (error) {
    console.error('Settings rejected', error)
  }
}

async function dismissResult(): Promise<void> {
  try {
    remoteState = await requestJson<HandsfreeState>('/api/dismiss', {
      method: 'POST',
      body: '{}',
    })
    menuView = 'main'
    selectedMenuIndex = 0
    await renderGlasses(true)
  } catch (error) {
    console.error('Dismiss failed', error)
  }
}

function openCandidateMenu(view: 'specimen' | 'mode'): void {
  if (!remoteState) return
  menuView = view
  selectedMenuIndex = 0
  void renderGlasses(true)
}

function cancelCandidateMenu(): void {
  menuView = 'main'
  selectedMenuIndex = 0
  void renderGlasses(true)
}

function currentMenuItemCount(): number {
  if (!remoteState) return 0
  if (menuView === 'specimen') return remoteState.available.specimens.length
  if (menuView === 'mode') return remoteState.available.order_types.length
  return 3
}

function rawEventType(event: EvenHubEvent): unknown {
  const raw = (event.jsonData ?? {}) as Record<string, unknown>
  return event.listEvent?.eventType
    ?? event.textEvent?.eventType
    ?? event.sysEvent?.eventType
    ?? raw.eventType
    ?? raw.event_type
}

function normalizeEventType(event: EvenHubEvent): OsEventTypeList | undefined {
  const raw = rawEventType(event)
  if (typeof raw === 'number') {
    if (raw === 0) return OsEventTypeList.CLICK_EVENT
    if (raw === 1) return OsEventTypeList.SCROLL_TOP_EVENT
    if (raw === 2) return OsEventTypeList.SCROLL_BOTTOM_EVENT
    if (raw === 3) return OsEventTypeList.DOUBLE_CLICK_EVENT
  }
  if (typeof raw === 'string') {
    const value = raw.toUpperCase()
    if (value.includes('DOUBLE')) return OsEventTypeList.DOUBLE_CLICK_EVENT
    if (value.includes('CLICK')) return OsEventTypeList.CLICK_EVENT
    if (value.includes('SCROLL_TOP') || value.includes('UP')) return OsEventTypeList.SCROLL_TOP_EVENT
    if (value.includes('SCROLL_BOTTOM') || value.includes('DOWN')) return OsEventTypeList.SCROLL_BOTTOM_EVENT
  }
  if (event.listEvent) return OsEventTypeList.CLICK_EVENT
  return undefined
}

function incomingListIndex(event: EvenHubEvent): number | null {
  const value = event.listEvent?.currentSelectItemIndex
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10)
    return Number.isNaN(parsed) ? null : parsed
  }
  return null
}

function registerEventLoop(): void {
  if (!bridge || eventLoopRegistered) return
  bridge.onEvenHubEvent((event) => {
    const eventType = normalizeEventType(event)
    if (eventType === OsEventTypeList.DOUBLE_CLICK_EVENT) {
      if (remoteState?.status === 'result' || remoteState?.status === 'error') void dismissResult()
      else if (menuView !== 'main') cancelCandidateMenu()
      return
    }
    if (!remoteState?.enabled || remoteState.status !== 'ready') return

    const incomingIndex = incomingListIndex(event)
    if (incomingIndex !== null && incomingIndex !== selectedMenuIndex) {
      selectedMenuIndex = Math.max(0, Math.min(currentMenuItemCount() - 1, incomingIndex))
      return
    }
    if (eventType !== OsEventTypeList.CLICK_EVENT) return

    if (menuView === 'specimen') {
      const specimen = remoteState.available.specimens[selectedMenuIndex]
      if (!specimen) return
      menuView = 'main'
      selectedMenuIndex = 0
      void updateSettings(specimen, getEffectiveOrderType(remoteState))
    } else if (menuView === 'mode') {
      const orderType = remoteState.available.order_types[selectedMenuIndex]?.value
      if (!orderType) return
      menuView = 'main'
      selectedMenuIndex = 0
      void updateSettings(remoteState.settings.specimen, orderType)
    } else if (selectedMenuIndex === 0) {
      void requestAnalyze()
    } else if (selectedMenuIndex === 1) {
      openCandidateMenu('specimen')
    } else {
      openCandidateMenu('mode')
    }
  })
  eventLoopRegistered = true
}

async function connectSimulator(): Promise<void> {
  if (bridge) return
  try {
    bridge = await Promise.race([
      waitForEvenAppBridge(),
      new Promise<never>((_, reject) => window.setTimeout(() => reject(new Error('Bridge timeout')), 5000)),
    ])
    registerEventLoop()
    await renderGlasses(true)
  } catch {
    window.setTimeout(() => void connectSimulator(), RECONNECT_INTERVAL_MS)
  }
}

window.setInterval(() => void pollMac(), POLL_INTERVAL_MS)
void pollMac()
void connectSimulator()
