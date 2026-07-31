export type OrderTypeOption = {
  value: string
  label: string
}

export type ClassificationScore = {
  label: string
  probability: number
  percentage: number
}

export type ClassificationResult = {
  specimen: string
  order_type: string
  order_type_label: string
  scores: ClassificationScore[]
}

export type HandsfreeState = {
  enabled: boolean
  output_target: string
  status: 'disabled' | 'ready' | 'queued' | 'analyzing' | 'result' | 'error'
  revision: number
  settings_revision: number
  settings: {
    specimen: string
    order_type: string
  }
  available: {
    specimens: string[]
    order_types: OrderTypeOption[]
  }
  result: ClassificationResult | null
  error: {
    code: string
    message: string
  } | null
}

export function displaySpecimen(specimen: string): string {
  return specimen.toUpperCase()
}

export function getEffectiveOrderType(state: HandsfreeState): string {
  const supportedValues = state.available.order_types.map((option) => option.value)
  if (supportedValues.includes(state.settings.order_type)) {
    return state.settings.order_type
  }
  if (supportedValues.includes('System')) return 'System'
  return supportedValues[0] ?? 'System'
}

export function getOrderTypeLabel(state: HandsfreeState, value: string): string {
  return state.available.order_types.find((option) => option.value === value)?.label ?? value
}

export function compactScore(score: ClassificationScore): string {
  const readableLabel = score.label.replaceAll('_', ' ')
  const label = readableLabel.length > 42
    ? `${readableLabel.slice(0, 39)}...`
    : readableLabel
  return `${label}  ${score.percentage.toFixed(1)}%`
}
