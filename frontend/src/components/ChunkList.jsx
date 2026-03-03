import StatusBadge from './StatusBadge'

export default function ChunkList({ chunks, selectedId, onSelect, totalChunks, doneChunks, onToggleDone }) {
  if (!chunks || chunks.length === 0) {
    return (
      <div className="px-4 py-6 text-xs text-gray-400 text-center italic">
        chan hasn't planned the review yet
      </div>
    )
  }

  return (
    <div className="space-y-px py-1">
      {chunks.map((chunk, i) => {
        const isSelected = selectedId === chunk.id
        const isDone = doneChunks?.has(chunk.id)
        const num = (chunk.order_index ?? i) + 1
        return (
          <div key={chunk.id} className="relative group/item">
            <button
              onClick={() => onSelect(chunk)}
              className={`w-full text-left px-3 py-3 pr-9 transition-colors
                ${isSelected
                  ? 'bg-gray-900 text-white'
                  : isDone
                    ? 'bg-green-50 hover:bg-green-100 text-gray-500'
                    : 'hover:bg-gray-50 text-gray-700'
                }`}
            >
              {/* chunk number + status */}
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className={`text-xs font-mono font-semibold ${isSelected ? 'text-gray-400' : 'text-gray-400'}`}>
                  {num} / {totalChunks ?? chunks.length}
                </span>
                <StatusBadge status={chunk.status} />
              </div>

              {/* title */}
              <p className={`text-sm font-semibold leading-snug mb-1
                ${isSelected ? 'text-white' : isDone ? 'text-gray-400 line-through' : 'text-gray-800'}`}>
                {chunk.title || `Chunk ${num}`}
              </p>

              {/* purpose — one line preview */}
              {chunk.purpose && (
                <p className={`text-xs leading-relaxed line-clamp-2
                  ${isSelected ? 'text-gray-300' : isDone ? 'text-gray-400' : 'text-gray-500'}`}>
                  {chunk.purpose}
                </p>
              )}

              {/* file count */}
              <p className={`text-xs mt-1.5 ${isSelected ? 'text-gray-400' : 'text-gray-400'}`}>
                {(chunk.file_paths || []).length} file{(chunk.file_paths || []).length !== 1 ? 's' : ''}
              </p>
            </button>

            {/* Mark as done button */}
            <button
              onClick={(e) => { e.stopPropagation(); onToggleDone?.(chunk.id) }}
              title={isDone ? 'Mark as not done' : 'Mark as done'}
              className={`absolute right-2 top-3 w-5 h-5 rounded flex items-center justify-center transition-colors
                ${isDone
                  ? 'bg-green-500 text-white'
                  : 'border border-gray-300 text-transparent hover:border-gray-400 hover:text-gray-300 bg-white'
                }`}
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M1.5 5l2.5 2.5 4.5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>
        )
      })}
    </div>
  )
}
