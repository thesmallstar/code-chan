import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { api } from '../lib/api'
import { COMMENT_LABELS, labelClasses } from '../lib/labels'
import StatusBadge from '../components/StatusBadge'
import ChunkList from '../components/ChunkList'
import DiffView from '../components/DiffView'
import ChatPanel from '../components/ChatPanel'
import DraftComments from '../components/DraftComments'
import ThreadsPanel from '../components/ThreadsPanel'

const POLLING_INTERVAL = 3000
const ACTIVE_STATUSES = ['PENDING', 'SYNCING', 'SUMMARIZING', 'CHUNKING', 'AI_RUNNING']

const REVIEW_ACTIONS = [
  { event: 'COMMENT',         label: 'Comment',         cls: 'border-gray-300 text-gray-700 hover:bg-gray-50' },
  { event: 'APPROVE',         label: 'Approve',         cls: 'border-green-400 text-green-700 hover:bg-green-50' },
  { event: 'REQUEST_CHANGES', label: 'Request Changes', cls: 'border-red-400 text-red-600 hover:bg-red-50' },
]

// ── Submit review panel ───────────────────────────────────────────────────────
function SubmitReviewPanel({ reviewId }) {
  const [event, setEvent] = useState('COMMENT')
  const [body, setBody] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(null)
  const [error, setError] = useState(null)

  const handleSubmit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      const res = await api.submitReview(reviewId, event, body)
      setSubmitted(res)
      setBody('')
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (submitted) {
    return (
      <div className="px-3 py-2.5 bg-green-50 border-b border-green-200 text-xs text-green-700 flex items-center gap-2">
        <span>Review submitted — {submitted.state?.toLowerCase()}</span>
        {submitted.html_url && (
          <a href={submitted.html_url} target="_blank" rel="noopener noreferrer" className="underline">view on GitHub</a>
        )}
        <button onClick={() => setSubmitted(null)} className="ml-auto text-green-500 hover:text-green-700">✕</button>
      </div>
    )
  }

  return (
    <div className="px-3 py-3 border-b border-gray-200 space-y-2">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Submit Review</h3>
      <div className="flex gap-1.5 flex-wrap">
        {REVIEW_ACTIONS.map(({ event: e, label, cls }) => (
          <button
            key={e}
            onClick={() => setEvent(e)}
            className={`text-xs px-2.5 py-1 rounded border font-medium transition-colors ${cls}
              ${event === e ? 'ring-2 ring-offset-1 ring-gray-400' : ''}`}
          >
            {label}
          </button>
        ))}
      </div>
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder={event === 'REQUEST_CHANGES' ? 'Describe required changes… (required)' : 'Overall comment (optional)'}
        rows={3}
        className="w-full text-xs px-2 py-1.5 border border-gray-300 rounded resize-none
          focus:outline-none focus:ring-1 focus:ring-gray-900"
      />
      {error && <p className="text-xs text-red-500">{error}</p>}
      <button
        onClick={handleSubmit}
        disabled={submitting || (event === 'REQUEST_CHANGES' && !body.trim())}
        className="w-full text-xs py-1.5 bg-gray-900 text-white rounded hover:bg-gray-800
          disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? 'Submitting…' : `Submit ${event === 'APPROVE' ? 'Approval' : event === 'REQUEST_CHANGES' ? 'Request' : 'Comment'}`}
      </button>
    </div>
  )
}

// ── Top bar ──────────────────────────────────────────────────────────────────
function TopBar({ review, onSync, navigate }) {
  const pr = review?.pull_request
  return (
    <header className="border-b border-gray-200 bg-white px-4 py-2.5 flex items-center gap-4 shrink-0">
      <button
        onClick={() => navigate('/')}
        className="text-sm text-gray-400 hover:text-gray-600 mono flex items-center gap-2"
      >
        <img src="/logo.png" alt="chan" className="w-6 h-6" />
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
          {review?.model_provider && (
            <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium
              ${review.model_provider === 'codex'
                ? 'bg-emerald-50 text-emerald-700'
                : 'bg-orange-50 text-orange-700'
              }`}>
              {review.model_provider === 'codex' ? 'codex' : 'claude'}
            </span>
          )}
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
  const [selectedLabel, setSelectedLabel] = useState(null)

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
        label: selectedLabel,
      })
      onDraftTrigger()
      setAddingComment(null)
      setNewCommentBody('')
      setSelectedLabel(null)
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
            {/* Label picker */}
            <div className="flex items-center gap-1.5 flex-wrap mb-2">
              {COMMENT_LABELS.map(({ value }) => (
                <button
                  key={value}
                  onClick={() => setSelectedLabel(selectedLabel === value ? null : value)}
                  className={`text-xs px-2 py-0.5 rounded-full border transition-colors
                    ${selectedLabel === value
                      ? `${labelClasses(value)} border-transparent ring-1 ring-gray-400`
                      : 'border-gray-200 text-gray-400 hover:bg-gray-50'
                    }`}
                >
                  {value}
                </button>
              ))}
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

// ── Re-review components ──────────────────────────────────────────────────────
function ThreadOpinionCard({ op }) {
  const resolve = op.should_resolve
  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden mb-3 bg-white">
      {op.path && (
        <div className="px-3 py-1.5 bg-gray-50 border-b border-gray-100 flex items-center gap-2">
          <span className="text-xs mono text-gray-500 truncate">
            {op.path}{op.line ? `:${op.line}` : ''}
          </span>
          {op.author && <span className="text-xs text-gray-400 shrink-0">{op.author}</span>}
        </div>
      )}
      <div className="px-3 py-3">
        {op.body_preview && (
          <p className="text-sm text-gray-700 mb-2 italic">"{op.body_preview}{op.body_preview?.length >= 120 ? '…' : ''}"</p>
        )}
        <div className="flex items-start gap-2">
          <span className={`shrink-0 text-xs px-2 py-0.5 rounded-full font-medium ${
            resolve ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
          }`}>
            {resolve ? '✓ can resolve' : '↩ respond first'}
          </span>
          {op.reason && (
            <p className="text-xs text-gray-500 leading-relaxed">{op.reason}</p>
          )}
        </div>
      </div>
    </div>
  )
}

const REREVIEW_ACTIVE = ['PENDING', 'RUNNING']

function ReReviewPanel({ reviewId }) {
  const [reReviewId, setReReviewId] = useState(null)
  const [rr, setRr] = useState(null)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState(null)

  const loadRr = useCallback(() => {
    if (!reReviewId) return
    api.getReReview(reReviewId)
      .then(setRr)
      .catch((e) => setError(e.message))
  }, [reReviewId])

  useEffect(() => { if (reReviewId) loadRr() }, [reReviewId, loadRr])

  useEffect(() => {
    if (!rr || !REREVIEW_ACTIVE.includes(rr.status)) return
    const t = setInterval(loadRr, 3000)
    return () => clearInterval(t)
  }, [rr, loadRr])

  const startReReview = async () => {
    setStarting(true)
    setError(null)
    try {
      const { re_review_id } = await api.createReReview(reviewId)
      setReReviewId(re_review_id)
    } catch (e) {
      setError(e.message)
    } finally {
      setStarting(false)
    }
  }

  if (!reReviewId) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 px-8 text-center">
        <p className="text-sm text-gray-500">
          Get a summary of what's changed since the last review and chan's opinion on open threads.
        </p>
        {error && <p className="text-xs text-red-500">{error}</p>}
        <button
          onClick={startReReview}
          disabled={starting}
          className="text-sm px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 disabled:opacity-50"
        >
          {starting ? 'starting…' : 'run re-review'}
        </button>
      </div>
    )
  }

  const isActive = rr && REREVIEW_ACTIVE.includes(rr.status)
  const noNewCommits = rr?.old_head_sha && rr?.new_head_sha && rr.old_head_sha === rr.new_head_sha

  return (
    <div className="h-full overflow-y-auto">
      <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-3 z-10">
        <h2 className="text-sm font-semibold text-gray-900">Re-review</h2>
        {rr?.old_head_sha && rr?.new_head_sha && (
          <span className="text-xs mono text-gray-400">
            {noNewCommits
              ? `at ${rr.old_head_sha.slice(0, 7)} (no new commits)`
              : `${rr.old_head_sha.slice(0, 7)} → ${rr.new_head_sha.slice(0, 7)}`}
          </span>
        )}
        {rr && (
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            rr.status === 'DONE' ? 'bg-green-100 text-green-700' :
            rr.status === 'ERROR' ? 'bg-red-100 text-red-600' :
            'bg-gray-100 text-gray-500'
          }`}>
            {rr.status === 'PENDING' ? 'queued' :
             rr.status === 'RUNNING' ? 'analysing…' :
             rr.status === 'DONE' ? 'done' : 'error'}
          </span>
        )}
      </div>

      <div className="px-6 py-6 max-w-3xl">
        {isActive && (
          <div className="flex items-center gap-3 py-10 justify-center">
            <span className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
            <p className="text-sm text-gray-500">chan is analysing changes and reviewing threads…</p>
          </div>
        )}

        {rr?.status === 'ERROR' && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
            {rr.error_message || 'Something went wrong.'}
          </div>
        )}

        {rr?.status === 'DONE' && (
          <>
            <section className="mb-8">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">
                {noNewCommits ? 'No new commits' : 'Changes since last review'}
              </h3>
              {rr.changes_summary_md ? (
                <div className="prose prose-sm text-gray-700 max-w-none">
                  <ReactMarkdown>{rr.changes_summary_md}</ReactMarkdown>
                </div>
              ) : (
                <p className="text-sm text-gray-400 italic">No summary generated.</p>
              )}
            </section>

            <section>
              <h3 className="text-sm font-semibold text-gray-900 mb-3">
                Open Threads
                {rr.thread_opinions.length > 0 && (
                  <span className="ml-2 text-sm font-normal text-gray-400">
                    ({rr.thread_opinions.filter(o => !o.should_resolve).length} need response ·{' '}
                    {rr.thread_opinions.filter(o => o.should_resolve).length} can resolve)
                  </span>
                )}
              </h3>
              {rr.thread_opinions.length === 0 ? (
                <p className="text-sm text-gray-400 italic">No open threads.</p>
              ) : (
                <>
                  {rr.thread_opinions.filter(o => !o.should_resolve).map((op, i) => (
                    <ThreadOpinionCard key={i} op={op} />
                  ))}
                  {rr.thread_opinions.filter(o => o.should_resolve).map((op, i) => (
                    <ThreadOpinionCard key={i} op={op} />
                  ))}
                </>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function ReviewInstance() {
  const { id } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [review, setReview] = useState(null)
  const [threads, setThreads] = useState([])
  const [tab, setTab] = useState(location.state?.tab || 'overview')   // 'overview' | 'chunk' | 'threads' | 're-review'
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
          {!isActive && review.status !== 'ERROR' && (
            <SubmitReviewPanel reviewId={id} />
          )}
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
              onClick={() => setTab('re-review')}
              className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors mt-0.5
                ${tab === 're-review'
                  ? 'bg-gray-900 text-white'
                  : 'hover:bg-gray-100 text-gray-700'
                }`}
            >
              Re-review
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
            {tab === 're-review' && <ReReviewPanel reviewId={id} />}
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
