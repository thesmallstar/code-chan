import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { api } from '../lib/api'

// Group flat thread list into {root, replies[]} structures
function groupThreads(threads) {
  const byGithubId = {}
  for (const t of threads) {
    byGithubId[t.github_id] = t
  }
  const roots = []
  const replyMap = {}
  for (const t of threads) {
    if (t.in_reply_to_id) {
      ;(replyMap[t.in_reply_to_id] = replyMap[t.in_reply_to_id] || []).push(t)
    } else {
      roots.push(t)
    }
  }
  return roots.map((r) => ({ root: r, replies: replyMap[r.github_id] || [] }))
}

function Comment({ comment, isReply }) {
  const date = comment.created_at
    ? new Date(comment.created_at).toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
      })
    : ''
  return (
    <div className={`${isReply ? 'ml-6 border-l-2 border-gray-100 pl-3' : ''}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs font-semibold text-gray-700">{comment.author || 'unknown'}</span>
        <span className="text-xs text-gray-400">{date}</span>
      </div>
      <div className="prose prose-sm text-sm text-gray-800">
        <ReactMarkdown>{comment.body || ''}</ReactMarkdown>
      </div>
    </div>
  )
}

function ChanMessage({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-2`}>
      <div className={`max-w-[90%] rounded-lg px-3 py-2 text-xs
        ${isUser ? 'bg-gray-900 text-white' : 'bg-white border border-gray-200 text-gray-800'}`}>
        {isUser ? (
          <p className="whitespace-pre-wrap">{msg.content}</p>
        ) : (
          <div className="prose prose-sm">
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  )
}

function ThreadCard({ group, onPostReply }) {
  const { root, replies } = group
  const [replyOpen, setReplyOpen] = useState(false)
  const [replyText, setReplyText] = useState('')
  const [postingSending, setPostingSending] = useState(false)

  // Chan discussion state (ephemeral — lives in component memory)
  const [chanOpen, setChanOpen] = useState(false)
  const [chanHistory, setChanHistory] = useState([])
  const [chanInput, setChanInput] = useState('')
  const [chanLoading, setChanLoading] = useState(false)
  const [chanError, setChanError] = useState(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chanHistory, chanLoading])

  const isInline = root.type === 'REVIEW_COMMENT'

  const askChan = async () => {
    if (!chanInput.trim() || chanLoading) return
    const msg = chanInput.trim()
    setChanInput('')
    setChanLoading(true)
    setChanError(null)
    const newHistory = [...chanHistory, { role: 'user', content: msg }]
    setChanHistory(newHistory)
    try {
      const { reply } = await api.discussThread(root.id, msg, chanHistory)
      setChanHistory([...newHistory, { role: 'assistant', content: reply }])
    } catch (e) {
      setChanError(e.message)
    } finally {
      setChanLoading(false)
    }
  }

  const handleChanKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); askChan() }
  }

  const postReply = async () => {
    if (!replyText.trim()) return
    setPostingSending(true)
    try {
      await onPostReply(root.id, replyText.trim())
      setReplyText('')
      setReplyOpen(false)
    } finally {
      setPostingSending(false)
    }
  }

  return (
    <div className="border border-gray-200 rounded-xl mb-3 overflow-hidden bg-white">
      {/* File + line header */}
      {isInline && root.path && (
        <div className="px-3 py-1.5 bg-gray-50 border-b border-gray-100 flex items-center gap-2">
          <span className="text-xs mono text-gray-500 truncate">
            {root.path}{root.line ? `:${root.line}` : ''}
          </span>
          <span className="text-xs text-gray-400 uppercase tracking-wide shrink-0">
            {root.type === 'REVIEW_COMMENT' ? 'inline' : 'pr comment'}
          </span>
        </div>
      )}

      {/* Diff hunk */}
      {root.diff_hunk && (
        <pre className="px-3 py-2 text-xs bg-gray-50 border-b border-gray-100 overflow-x-auto mono text-gray-600 max-h-28">
          {root.diff_hunk}
        </pre>
      )}

      {/* Root comment + replies */}
      <div className="px-3 py-3 space-y-3">
        <Comment comment={root} isReply={false} />
        {replies.map((r) => (
          <Comment key={r.id} comment={r} isReply />
        ))}
      </div>

      {/* Actions */}
      <div className="px-3 pb-3 flex items-center gap-2">
        <button
          onClick={() => { setChanOpen(!chanOpen); if (!chanOpen && chanHistory.length === 0) setChanHistory([]) }}
          className={`text-xs px-2.5 py-1 rounded-md border transition-colors
            ${chanOpen ? 'bg-gray-900 text-white border-gray-900' : 'border-gray-200 text-gray-500 hover:border-gray-400 hover:text-gray-700'}`}
        >
          {chanOpen ? 'close chan' : 'ask chan'}
        </button>
        <button
          onClick={() => setReplyOpen(!replyOpen)}
          className="text-xs px-2.5 py-1 rounded-md border border-gray-200 text-gray-500 hover:border-gray-400 hover:text-gray-700 transition-colors"
        >
          reply on GitHub
        </button>
      </div>

      {/* Reply on GitHub */}
      {replyOpen && (
        <div className="px-3 pb-3 border-t border-gray-100 pt-2">
          <textarea
            value={replyText}
            onChange={(e) => setReplyText(e.target.value)}
            placeholder="Write a reply to post on GitHub…"
            rows={3}
            className="w-full text-xs px-2 py-1.5 border border-gray-300 rounded-lg resize-y
              focus:outline-none focus:ring-1 focus:ring-gray-900"
          />
          <div className="flex gap-2 mt-1.5">
            <button
              onClick={postReply}
              disabled={postingSending || !replyText.trim()}
              className="text-xs px-3 py-1 bg-gray-900 text-white rounded-md hover:bg-gray-800 disabled:opacity-50"
            >
              {postingSending ? 'posting…' : 'post reply'}
            </button>
            <button
              onClick={() => { setReplyOpen(false); setReplyText('') }}
              className="text-xs px-3 py-1 border border-gray-200 rounded-md hover:bg-gray-50"
            >
              cancel
            </button>
          </div>
        </div>
      )}

      {/* Chan discussion */}
      {chanOpen && (
        <div className="border-t border-gray-100 bg-gray-50">
          <div className="px-3 pt-2 pb-1">
            <p className="text-xs text-gray-400 italic">
              chan has full context of this thread — ask anything.
            </p>
          </div>
          <div className="px-3 py-2 max-h-64 overflow-y-auto">
            {chanHistory.length === 0 && !chanLoading && (
              <p className="text-xs text-gray-400 text-center italic py-2">
                e.g. "is this concern valid?", "how should i address this?", "what does line 703 actually do?"
              </p>
            )}
            {chanHistory.map((m, i) => <ChanMessage key={i} msg={m} />)}
            {chanLoading && (
              <div className="flex justify-start mb-2">
                <div className="bg-white border border-gray-200 rounded-lg px-3 py-2">
                  <span className="text-xs text-gray-400 animate-pulse">chan is thinking…</span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
          {chanError && (
            <p className="px-3 pb-1 text-xs text-red-500">{chanError}</p>
          )}
          <div className="px-3 pb-3 pt-1">
            <textarea
              value={chanInput}
              onChange={(e) => setChanInput(e.target.value)}
              onKeyDown={handleChanKey}
              placeholder="ask chan about this thread… (Enter to send)"
              rows={2}
              className="w-full text-xs px-2 py-1.5 border border-gray-300 rounded-lg resize-none
                focus:outline-none focus:ring-1 focus:ring-gray-900"
            />
            <button
              onClick={askChan}
              disabled={chanLoading || !chanInput.trim()}
              className="mt-1 w-full py-1 bg-gray-900 text-white text-xs rounded-lg
                hover:bg-gray-800 disabled:opacity-40 transition-colors"
            >
              send
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function ThreadsPanel({ threads, onReply, onRefresh }) {
  const [error, setError] = useState(null)

  const handleReply = async (threadId, body) => {
    setError(null)
    try {
      await onReply(threadId, body)
    } catch (err) {
      setError(err.message)
    }
  }

  const grouped = groupThreads(threads || [])
  const reviewGroups = grouped.filter((g) => g.root.type === 'REVIEW_COMMENT')
  const issueGroups = grouped.filter((g) => g.root.type === 'ISSUE_COMMENT')

  return (
    <div className="h-full overflow-y-auto">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 sticky top-0 bg-white z-10">
        <h2 className="text-sm font-semibold text-gray-900">
          Threads ({grouped.length})
        </h2>
        <button onClick={onRefresh} className="text-xs text-gray-400 hover:text-gray-600 underline">
          refresh
        </button>
      </div>

      {error && <p className="mx-4 mt-3 text-xs text-red-500">{error}</p>}

      <div className="p-4">
        {grouped.length === 0 && (
          <p className="text-sm text-gray-400 italic text-center py-8">no comments on this PR yet.</p>
        )}

        {issueGroups.length > 0 && (
          <div className="mb-4">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">PR comments</p>
            {issueGroups.map((g) => (
              <ThreadCard key={g.root.id} group={g} onPostReply={handleReply} />
            ))}
          </div>
        )}

        {reviewGroups.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">inline review comments</p>
            {reviewGroups.map((g) => (
              <ThreadCard key={g.root.id} group={g} onPostReply={handleReply} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
