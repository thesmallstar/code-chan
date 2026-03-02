import { useState } from 'react'

/**
 * Parse a GitHub unified diff patch string into line objects.
 */
function parsePatch(patch) {
  if (!patch) return []
  const lines = []
  let oldLine = 0
  let newLine = 0

  for (const raw of patch.split('\n')) {
    const hunkMatch = raw.match(/^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)/)
    if (hunkMatch) {
      oldLine = parseInt(hunkMatch[1], 10)
      newLine = parseInt(hunkMatch[2], 10)
      lines.push({ type: 'hunk', content: raw, oldLine: null, newLine: null })
      continue
    }
    if (raw.startsWith('+') && !raw.startsWith('+++')) {
      lines.push({ type: 'addition', content: raw.slice(1), oldLine: null, newLine: newLine++ })
    } else if (raw.startsWith('-') && !raw.startsWith('---')) {
      lines.push({ type: 'deletion', content: raw.slice(1), oldLine: oldLine++, newLine: null })
    } else {
      const content = raw.startsWith(' ') ? raw.slice(1) : raw
      lines.push({ type: 'context', content, oldLine: oldLine++, newLine: newLine++ })
    }
  }
  return lines
}

function DiffLineRow({ line, commentableLine, onCommentClick }) {
  const isCommentable = commentableLine && line.newLine !== null
  return (
    <tr
      className={`group ${
        line.type === 'addition' ? 'diff-addition' :
        line.type === 'deletion' ? 'diff-deletion' :
        line.type === 'hunk'     ? 'diff-hunk' :
        'diff-context'
      }`}
    >
      <td className="select-none px-3 text-right w-12 border-r border-gray-200 text-gray-400 text-xs mono">
        {line.oldLine ?? ''}
      </td>
      <td className="select-none px-3 text-right w-12 border-r border-gray-200 text-gray-400 text-xs mono">
        {line.newLine ?? ''}
      </td>
      <td className="px-1 w-5 select-none text-center">
        {line.type === 'addition' ? '+' : line.type === 'deletion' ? '−' : ''}
      </td>
      <td className="px-3 py-0.5 text-xs mono whitespace-pre w-full">
        {line.content}
      </td>
      {onCommentClick && isCommentable && (
        <td className="pr-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={() => onCommentClick(line)}
            title="Add comment on this line"
            className="text-xs text-gray-400 hover:text-gray-600 px-1"
          >
            +
          </button>
        </td>
      )}
    </tr>
  )
}

function FileDiff({ path, patch, lineMap, onAddComment }) {
  const [collapsed, setCollapsed] = useState(false)
  const lines = parsePatch(patch)
  const commentableSet = new Set(lineMap || [])

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden mb-3">
      <div
        className="flex items-center justify-between px-3 py-2 bg-gray-50 cursor-pointer hover:bg-gray-100"
        onClick={() => setCollapsed(!collapsed)}
      >
        <span className="text-sm mono text-gray-700 font-medium">{path}</span>
        <span className="text-xs text-gray-400">{collapsed ? '▶' : '▼'}</span>
      </div>
      {!collapsed && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-xs">
            <tbody>
              {lines.map((line, i) => (
                <DiffLineRow
                  key={i}
                  line={line}
                  commentableLine={commentableSet.has(line.newLine)}
                  onCommentClick={onAddComment ? (l) => onAddComment(path, l) : null}
                />
              ))}
            </tbody>
          </table>
          {lines.length === 0 && (
            <p className="text-xs text-gray-400 px-4 py-3 italic">No diff available for this file.</p>
          )}
        </div>
      )}
    </div>
  )
}

export default function DiffView({ diffContent, lineMap, onAddComment }) {
  const entries = Object.entries(diffContent || {})
  if (!entries.length) {
    return <p className="text-sm text-gray-400 italic">No diff content available.</p>
  }
  return (
    <div>
      {entries.map(([path, patch]) => (
        <FileDiff
          key={path}
          path={path}
          patch={patch}
          lineMap={lineMap?.[path]}
          onAddComment={onAddComment}
        />
      ))}
    </div>
  )
}
