import type { ComponentName } from '../types/provider'
import type { ParserUsed, Priority, SortOption } from '../types/search'

export const PRIORITY_LABELS: Record<Priority, string> = {
  balanced: 'Balanced',
  quality: 'Quality',
  cost: 'Cost',
  experience: 'Experience',
  distance: 'Distance',
}

export const SORT_LABELS: Record<SortOption, string> = {
  match: 'Best match',
  quality: 'Quality',
  experience: 'Experience',
  distance: 'Distance',
  cost: 'Cost',
}

export const COMPONENT_LABELS: Record<ComponentName, string> = {
  quality: 'Quality',
  experience: 'Experience',
  cost: 'Cost',
  volume: 'Volume',
  distance: 'Distance',
}

export const PARSER_LABELS: Record<ParserUsed, string> = {
  llm: 'AI',
  rule_based: 'keyword matching',
}
