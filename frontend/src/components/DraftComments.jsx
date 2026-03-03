import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { api } from '../lib/api'
import StatusBadge from './StatusBadge'
import { COMMENT_LABELS, labelClasses } from '../lib/labels'

function LabelPicker({ value, onChange }) {
  return (
    <div className="flex items-center gap-1 flex-wrap">
      {COMMENT_LABELS.map(({ value: v }) => (
        <button
          key={v}
          onClick={() => onChange(value === v ? null : v)}
          className={`text-xs px-2 py-0.5 rounded-full border transition-colors
            ${value === v
              ? `${labelClasses(v)} border-transparent ring-1 ring-offset-1 ring-gray-400`
              : 'border-gray-200 text-gray-400 hover:bg-gray-50'
            }`}
        >
          {v}
        </button>
      ))}
    </div>
  )
}

function DraftRow({ draft, onSend, onDelete, onEdit }) {
  const [editing, setEditing] = useState(false)
  const [body, setBody] = useState(draft.body_md || '')
  const [label, setLabel] = useState(draft.label || null)
  const [saving, setSaving] = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      await api.updateDraft(draft.id, { body_md: body, label })
      onEdit({ ...draft, body_md: body, label })
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  const cancel = () => {
    setEditing(false)
    setBody(draft.body_md || '')
    setLabel(draft.label || null)
  }

  return (
    <div className="border border-gray-200 rounded-lg p-3 mb-2 bg-white">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0 space-y-1">
          <span className="text-xs mono text-gray-500 truncate block">
            {draft.path}:{draft.line} ({draft.side})
          </span>
          {draft.label && !editing && (
            <span className={`inline-block text-xs px-2 py-0.5 rounded-full font-medium ${labelClasses(draft.label)}`}>
              {draft.label}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <StatusBadge status={draft.status} />
        </div>
      </div>

      {editing ? (
        <div className="space-y-2">
          <LabelPicker value={label} onChange={setLabel} />
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={4}
            className="w-full text-xs px-2 py-1.5 border border-gray-300 rounded mono resize-y
              focus:outline-none focus:ring-1 focus:ring-gray-900"
          />
          <div className="flex gap-2">
            <button
              onClick={save}
              disabled={saving}
              className="text-xs px-3 py-1 bg-gray-900 text-white rounded hover:bg-gray-800 disabled:opacity-50"
            >
              Save
            </button>
            <button
              onClick={cancel}
              className="text-xs px-3 py-1 border border-gray-300 rounded hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="prose prose-sm text-xs text-gray-700 mb-3">
          <ReactMarkdown>{draft.body_md}</ReactMarkdown>
        </div>
      )}

      {draft.status === 'DRAFT' && !editing && (
        <div className="flex gap-2 mt-2">
          <button
            onClick={() => onSend(draft.id)}
            className="text-xs px-3 py-1 bg-gray-900 text-white rounded hover:bg-gray-800"
          >
            Send to GitHub
          </button>
          <button
            onClick={() => setEditing(true)}
            className="text-xs px-3 py-1 border border-gray-300 rounded hover:bg-gray-50"
          >
            Edit
          </button>
          <button
            onClick={() => onDelete(draft.id)}
            className="text-xs px-3 py-1 border border-red-200 text-red-500 rounded hover:bg-red-50"
          >
            Delete
          </button>
        </div>
      )}
    </div>
  )
}

export default function DraftComments({ chunkId, trigger }) {
  const [drafts, setDrafts] = useState([])
  const [error, setError] = useState(null)
  const [sending, setSending] = useState(null)

  const load = () => {
    if (!chunkId) return
    api.getDrafts(chunkId).then(setDrafts).catch(() => {})
  }

  useEffect(load, [chunkId, trigger])

  const handleSend = async (draftId) => {
    setSending(draftId)
    setError(null)
    try {
      const updated = await api.sendDraft(draftId)
      setDrafts((prev) => prev.map((d) => (d.id === draftId ? updated : d)))
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(null)
    }
  }

  const handleDelete = async (draftId) => {
    try {
      await api.deleteDraft(draftId)
      setDrafts((prev) => prev.filter((d) => d.id !== draftId))
    } catch (err) {
      setError(err.message)
    }
  }

  const handleEdit = (updated) => {
    setDrafts((prev) => prev.map((d) => (d.id === updated.id ? updated : d)))
  }

  if (!chunkId) return null

  return (
    <div>
      <div className="px-3 py-2 border-b border-gray-200">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
          chan's drafts ({drafts.length})
        </h3>
      </div>
      <div className="p-3">
        {error && <p className="text-xs text-red-500 mb-2">{error}</p>}
        {drafts.length === 0 ? (
          <p className="text-xs text-gray-400 italic">
            chan hasn't drafted anything yet — comments will appear here after review.
          </p>
        ) : (
          drafts.map((d) => (
            <DraftRow
              key={d.id}
              draft={d}
              onSend={handleSend}
              onDelete={handleDelete}
              onEdit={handleEdit}
            />
          ))
        )}
      </div>
    </div>
  )
}
