export const COMMENT_LABELS = [
  { value: 'nit',           bg: 'bg-gray-100',   text: 'text-gray-600'   },
  { value: 'suggestion',    bg: 'bg-blue-100',   text: 'text-blue-700'   },
  { value: 'question',      bg: 'bg-purple-100', text: 'text-purple-700' },
  { value: 'bug',           bg: 'bg-orange-100', text: 'text-orange-700' },
  { value: 'critical bug',  bg: 'bg-red-100',    text: 'text-red-700'    },
]

export function labelClasses(value) {
  const found = COMMENT_LABELS.find((l) => l.value === value)
  return found ? `${found.bg} ${found.text}` : 'bg-gray-100 text-gray-600'
}
