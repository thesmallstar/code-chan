import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { api } from '../lib/api'
import StatusBadge from '../components/StatusBadge'
import ChunkList from '../components/ChunkList'
import DiffView from '../components/DiffView'
import ChatPanel from '../components/ChatPanel'
import DraftComments from '../components/DraftComments'
import ThreadsPanel from '../components/ThreadsPanel'

const POLLING_INTERVAL = 3000
const ACTIVE_STATUSES = ['PENDING', 'SYNCING', 'SUMMARIZING', 'CHUNKING', 'AI_RUNNING']

// ── Top bar ──────────────────────────────────────────────────────────────────
function TopBar({ review, onSync, navigate }) {
  const pr = review?.pull_request
  return (
    <header className="border-b border-gray-200 bg-white px-4 py-2.5 flex items-center gap-4 shrink-0">
      <button
        onClick={() => navigate('/')}
        className="text-sm text-gray-400 hover:text-gray-600 mono"
      >
        ← code-chan
      </button>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          {pr && (
            <a
              href={pr.url || '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-gray-900 hover:underline truncate max-w-md"
            >
              {pr.owner}/{pr.repo} #{pr.pr_number}
              {pr.title ? ` · ${pr.title}` : ''}
            </a>
          )}
          {review && <StatusBadge status={review.status} />}
        </div>
        {pr?.author && (
          <span className="text-xs text-gray-400">by {pr.author}</span>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={onSync}
          className="text-xs px-2.5 py-1 border border-gray-300 rounded-md hover:bg-gray-50 text-gray-600"
        >
          re-run chan
        </button>
      </div>
    </header>
  )
}

// ── Overview tab ─────────────────────────────────────────────────────────────
function OverviewPanel({ review }) {
  if (!review?.summary_md && !['READY', 'AI_RUNNING'].includes(review?.status)) {
    return (
      <div className="flex items-center justify-center h-40">
        <p className="text-sm text-gray-400 animate-pulse">chan is writing the summary…</p>
      </div>
    )
  }
  return (
    <div className="p-6 max-w-3xl">
      {review?.pull_request?.body && (
        <div className="mb-6">
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            PR Description
          </h2>
          <div className="prose text-sm text-gray-700">
            <ReactMarkdown>{review.pull_request.body}</ReactMarkdown>
          </div>
        </div>
      )}
      {review?.summary_md && (
        <div>
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            chan's take
          </h2>
          <div className="prose text-sm">
            <ReactMarkdown>{review.summary_md}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Section label ────────────────────────────────────────────────────────────
function SectionLabel({ children }) {
  return (
    <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3 mt-6 first:mt-0">
      {children}
    </h3>
  )
}

// ── Chunk detail tab ──────────────────────────────────────────────────────────
function ChunkPanel({ chunkSummary, totalChunks, draftTrigger, onDraftTrigger }) {
  const [chunk, setChunk] = useState(null)
  const [loading, setLoading] = useState(false)
  const [runningAI, setRunningAI] = useState(false)
  const [addingComment, setAddingComment] = useState(null)
  const [newCommentBody, setNewCommentBody] = useState('')

  useEffect(() => {
    if (!chunkSummary) return
    setLoading(true)
    api.getChunk(chunkSummary.id)
      .then(setChunk)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [chunkSummary?.id])

  const handleRunAI = async () => {
    setRunningAI(true)
    try {
      const updated = await api.runAI(chunkSummary.id)
      setChunk(updated)
    } catch (e) {
      console.error(e)
    } finally {
      setRunningAI(false)
    }
  }

  const handleAddCommentFromDiff = (path, line) => {
    setAddingComment({ path, line: line.newLine, side: 'RIGHT' })
    setNewCommentBody('')
  }

  const handleSaveDraft = async () => {
    if (!newCommentBody.trim() || !addingComment) return
    try {
      await api.createDraft(chunk.id, {
        path: addingComment.path,
        line: addingComment.line,
        side: addingComment.side,
        body_md: newCommentBody.trim(),
      })
      onDraftTrigger()
      setAddingComment(null)
      setNewCommentBody('')
    } catch (e) {
      console.error(e)
    }
  }

  if (!chunkSummary) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-400">
        pick a chunk and chan will walk you through it
      </div>
    )
  }
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-400 animate-pulse">
        chan is fetching this chunk…
      </div>
    )
  }
  if (!chunk) return null

  const num = (chunk.order_index ?? 0) + 1
  // Render diffs in chan's suggested reading order
  const orderedDiffContent = {}
  const reviewOrder = chunk.review_order?.length ? chunk.review_order : chunk.file_paths
  for (const path of reviewOrder) {
    if (chunk.diff_content?.[path] !== undefined) orderedDiffContent[path] = chunk.diff_content[path]
  }
  // any remaining files not in review_order
  for (const path of (chunk.file_paths || [])) {
    if (!orderedDiffContent[path] && chunk.diff_content?.[path] !== undefined) {
      orderedDiffContent[path] = chunk.diff_content[path]
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      {/* Sticky header */}
      <div className="sticky top-0 bg-white border-b border-gray-200 z-10 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xs mono text-gray-400 font-semibold">
            chunk {num}/{totalChunks}
          </span>
          <h2 className="text-sm font-semibold text-gray-900">{chunk.title}</h2>
          <StatusBadge status={chunk.status} />
        </div>
        <div className="flex items-center gap-2">
          {chunk.status !== 'AI_DONE' && (
            <button
              onClick={handleRunAI}
              disabled={runningAI}
              className="text-xs px-2.5 py-1 bg-gray-900 text-white rounded hover:bg-gray-800 disabled:opacity-50"
            >
              {runningAI ? 'chan is thinking…' : 'ask chan'}
            </button>
          )}
        </div>
      </div>

      <div className="px-6 py-5 max-w-4xl">

        {/* ── What this chunk is about ── */}
        {chunk.purpose && (
          <div className="mb-6 p-4 rounded-xl border border-gray-200 bg-gray-50">
            <p className="text-sm text-gray-700 leading-relaxed">{chunk.purpose}</p>
          </div>
        )}

        {/* ── How to review ── */}
        {chunk.walkthrough && (
          <>
            <SectionLabel>how to review this</SectionLabel>
            <div className="mb-5 p-4 rounded-xl bg-amber-50 border border-amber-100">
              <p className="text-sm text-amber-900 leading-relaxed">{chunk.walkthrough}</p>
            </div>
          </>
        )}

        {/* ── What changed ── */}
        {chunk.chunk_summary && (
          <>
            <SectionLabel>what changed</SectionLabel>
            <div className="mb-5 prose text-sm">
              <ReactMarkdown>{chunk.chunk_summary}</ReactMarkdown>
            </div>
          </>
        )}

        {/* ── Chan's inline comment suggestions ── */}
        {chunk.ai_suggestions_md && (
          <>
            <SectionLabel>chan's notes</SectionLabel>
            <div className="mb-5 p-4 bg-blue-50 border border-blue-100 rounded-xl">
              <div className="prose text-sm text-blue-900">
                <ReactMarkdown>{chunk.ai_suggestions_md}</ReactMarkdown>
              </div>
            </div>
          </>
        )}

        {/* ── Diff (in suggested reading order) ── */}
        <SectionLabel>
          diff
          {chunk.review_order?.length > 0 && (
            <span className="ml-1 normal-case font-normal text-gray-400">(in chan's suggested reading order)</span>
          )}
        </SectionLabel>
        <DiffView
          diffContent={orderedDiffContent}
          lineMap={chunk.line_map}
          onAddComment={handleAddCommentFromDiff}
        />

        {/* Inline comment composer */}
        {addingComment && (
          <div className="mt-4 p-4 border border-gray-300 rounded-lg bg-white shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs mono text-gray-500">
                Comment on {addingComment.path}:{addingComment.line}
              </span>
              <button
                onClick={() => setAddingComment(null)}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>
            <textarea
              value={newCommentBody}
              onChange={(e) => setNewCommentBody(e.target.value)}
              placeholder="Write your review comment…"
              rows={4}
              autoFocus
              className="w-full text-sm px-3 py-2 border border-gray-300 rounded resize-y
                focus:outline-none focus:ring-2 focus:ring-gray-900"
            />
            <div className="flex gap-2 mt-2">
              <button
                onClick={handleSaveDraft}
                disabled={!newCommentBody.trim()}
                className="text-xs px-3 py-1.5 bg-gray-900 text-white rounded hover:bg-gray-800 disabled:opacity-50"
              >
                Save as Draft
              </button>
              <button
                onClick={() => setAddingComment(null)}
                className="text-xs px-3 py-1.5 border border-gray-300 rounded hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function ReviewInstance() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [review, setReview] = useState(null)
  const [threads, setThreads] = useState([])
  const [tab, setTab] = useState('overview')   // 'overview' | 'chunk' | 'threads'
  const [selectedChunk, setSelectedChunk] = useState(null)
  const [draftTrigger, setDraftTrigger] = useState(0)
  const [error, setError] = useState(null)
  const [doneChunks, setDoneChunks] = useState(new Set())

  const handleToggleDone = useCallback(async (chunkId) => {
    // Optimistic update
    setDoneChunks((prev) => {
      const next = new Set(prev)
      if (next.has(chunkId)) next.delete(chunkId)
      else next.add(chunkId)
      return next
    })
    try {
      const updated = await api.toggleChunkDone(chunkId)
      setDoneChunks((prev) => {
        const next = new Set(prev)
        if (updated.human_done) next.add(chunkId)
        else next.delete(chunkId)
        return next
      })
    } catch (e) {
      console.error('Failed to save done state:', e)
      // Revert optimistic update
      setDoneChunks((prev) => {
        const next = new Set(prev)
        if (next.has(chunkId)) next.delete(chunkId)
        else next.add(chunkId)
        return next
      })
    }
  }, [])

  const loadReview = useCallback(() => {
    api.getReview(id)
      .then((data) => {
        setReview(data)
        setDoneChunks(new Set(data.chunks.filter(c => c.human_done).map(c => c.id)))
        setError(null)
      })
      .catch((err) => setError(err.message))
  }, [id])

  const loadThreads = useCallback(() => {
    api.getThreads(id).then(setThreads).catch(console.error)
  }, [id])

  // Initial load
  useEffect(() => {
    loadReview()
    loadThreads()
  }, [loadReview, loadThreads])

  // Poll while processing
  useEffect(() => {
    if (!review) return
    if (!ACTIVE_STATUSES.includes(review.status)) return
    const timer = setInterval(loadReview, POLLING_INTERVAL)
    return () => clearInterval(timer)
  }, [review, loadReview])

  const handleChunkSelect = (chunk) => {
    setSelectedChunk(chunk)
    setTab('chunk')
  }

  const handleSync = async () => {
    try {
      await api.syncReview(id)
      loadReview()
    } catch (e) {
      console.error(e)
    }
  }

  const handleReplyToThread = async (threadId, body) => {
    await api.replyToThread(threadId, body)
    loadThreads()
  }

  if (error) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 mb-4">{error}</p>
          <button onClick={() => navigate('/')} className="text-sm text-gray-500 underline">
            Back to home
          </button>
        </div>
      </div>
    )
  }

  if (!review) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <p className="text-sm text-gray-400 animate-pulse">chan is loading your review…</p>
      </div>
    )
  }

  const isActive = ACTIVE_STATUSES.includes(review.status)

  return (
    <div className="h-screen flex flex-col bg-gray-50 overflow-hidden">
      <TopBar review={review} onSync={handleSync} navigate={navigate} />

      {/* Status progress banner while processing */}
      {isActive && (
        <div className="bg-blue-50 border-b border-blue-100 px-4 py-2 text-xs text-blue-700 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
          chan is on it — this takes a minute. updates automatically.
        </div>
      )}

      {review.status === 'ERROR' && (
        <div className="bg-red-50 border-b border-red-100 px-4 py-2 text-xs text-red-600">
          Error: {review.error_message}
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <aside className="w-64 bg-white border-r border-gray-200 flex flex-col overflow-hidden shrink-0">
          <div className="px-3 pt-3 pb-2">
            <div className="flex items-center justify-between px-1 mb-2">
              <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Review Chunks
              </h2>
              <span className="text-xs text-gray-400 mono">
                {doneChunks.size}/{review.chunks?.length ?? 0} done
              </span>
            </div>
            {/* Progress bar */}
            {(review.chunks?.length ?? 0) > 0 && (
              <div className="px-1">
                <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-green-500 rounded-full transition-all duration-300"
                    style={{ width: `${(doneChunks.size / (review.chunks?.length ?? 1)) * 100}%` }}
                  />
                </div>
                <p className="text-xs text-gray-400 mt-1">
                  {(review.chunks?.length ?? 0) - doneChunks.size} chunk{(review.chunks?.length ?? 0) - doneChunks.size !== 1 ? 's' : ''} left
                </p>
              </div>
            )}
          </div>
          <div className="flex-1 overflow-y-auto">
            <ChunkList
              chunks={review.chunks}
              selectedId={selectedChunk?.id}
              onSelect={handleChunkSelect}
              totalChunks={review.chunks?.length ?? 0}
              doneChunks={doneChunks}
              onToggleDone={handleToggleDone}
            />
          </div>
          <div className="border-t border-gray-200 p-2">
            <button
              onClick={() => setTab('threads')}
              className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors
                ${tab === 'threads'
                  ? 'bg-gray-900 text-white'
                  : 'hover:bg-gray-100 text-gray-700'
                }`}
            >
              Threads
              {threads.length > 0 && (
                <span className="ml-2 text-xs bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded-full">
                  {threads.length}
                </span>
              )}
            </button>
            <button
              onClick={() => setTab('overview')}
              className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors mt-0.5
                ${tab === 'overview'
                  ? 'bg-gray-900 text-white'
                  : 'hover:bg-gray-100 text-gray-700'
                }`}
            >
              Overview
            </button>
          </div>
        </aside>

        {/* Main content + right panel */}
        <div className="flex-1 flex overflow-hidden">
          {/* Center: diff / overview / threads */}
          <div className="flex-1 overflow-y-auto">
            {tab === 'overview' && <OverviewPanel review={review} />}
            {tab === 'threads' && (
              <ThreadsPanel
                threads={threads}
                onReply={handleReplyToThread}
                onRefresh={loadThreads}
              />
            )}
            {tab === 'chunk' && (
              <ChunkPanel
                chunkSummary={selectedChunk}
                totalChunks={review.chunks?.length ?? 0}
                draftTrigger={draftTrigger}
                onDraftTrigger={() => setDraftTrigger((n) => n + 1)}
              />
            )}
          </div>

          {/* Right panel: Chat + Drafts (only when a chunk is selected) */}
          {tab === 'chunk' && selectedChunk && (
            <div className="w-80 border-l border-gray-200 flex flex-col bg-white overflow-hidden shrink-0">
              <div className="flex-1 overflow-hidden flex flex-col" style={{ maxHeight: '55%' }}>
                <ChatPanel chunkId={selectedChunk.id} />
              </div>
              <div className="border-t border-gray-200 overflow-y-auto" style={{ maxHeight: '45%' }}>
                <DraftComments
                  chunkId={selectedChunk.id}
                  trigger={draftTrigger}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
