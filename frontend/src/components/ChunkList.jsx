import StatusBadge from './StatusBadge'

export default function ChunkList({ chunks, selectedId, onSelect, totalChunks }) {
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
        const num = (chunk.order_index ?? i) + 1
        return (
          <button
            key={chunk.id}
            onClick={() => onSelect(chunk)}
            className={`w-full text-left px-3 py-3 transition-colors group
              ${isSelected
                ? 'bg-gray-900 text-white'
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
            <p className={`text-sm font-semibold leading-snug mb-1 ${isSelected ? 'text-white' : 'text-gray-800'}`}>
              {chunk.title || `Chunk ${num}`}
            </p>

            {/* purpose — one line preview */}
            {chunk.purpose && (
              <p className={`text-xs leading-relaxed line-clamp-2 ${isSelected ? 'text-gray-300' : 'text-gray-500'}`}>
                {chunk.purpose}
              </p>
            )}

            {/* file count */}
            <p className={`text-xs mt-1.5 ${isSelected ? 'text-gray-400' : 'text-gray-400'}`}>
              {(chunk.file_paths || []).length} file{(chunk.file_paths || []).length !== 1 ? 's' : ''}
            </p>
          </button>
        )
      })}
    </div>
  )
}
