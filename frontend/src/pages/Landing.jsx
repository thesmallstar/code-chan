import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import StatusBadge from '../components/StatusBadge'

const SYNC_CACHE_KEY = 'reviewRequestsLastSync'
const ONE_HOUR_MS = 60 * 60 * 1000

function isStale() {
  const stored = localStorage.getItem(SYNC_CACHE_KEY)
  if (!stored) return true
  return Date.now() - Number(stored) > ONE_HOUR_MS
}

function saveLastSync() {
  localStorage.setItem(SYNC_CACHE_KEY, String(Date.now()))
}

function formatLastSync(ts) {
  if (!ts) return null
  // ts comes from the server as a naive UTC datetime string (no Z suffix).
  // Appending 'Z' tells the browser to parse it as UTC so local time is correct.
  const raw = ts.endsWith('Z') || ts.includes('+') ? ts : ts + 'Z'
  const ms = Date.now() - new Date(raw).getTime()
  if (ms < 0) return 'just now'
  const mins = Math.floor(ms / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  return `${Math.floor(mins / 60)}h ago`
}

function GitHubStatus({ status, username }) {
  if (status === 'checking') {
    return (
      <span className="inline-flex items-center gap-1.5 text-sm text-gray-500">
        <span className="w-2 h-2 rounded-full bg-gray-300 animate-pulse" />
        Checking GitHub…
      </span>
    )
  }
  if (status === 'ok') {
    return (
      <span className="inline-flex items-center gap-1.5 text-sm text-green-700">
        <span className="w-2 h-2 rounded-full bg-green-500" />
        GitHub connected · <span className="font-medium">{username}</span>
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-red-600">
      <span className="w-2 h-2 rounded-full bg-red-500" />
      GitHub not connected
    </span>
  )
}

const PR_STATE_BADGE = {
  merged:  { label: 'merged',  cls: 'bg-purple-100 text-purple-700' },
  closed:  { label: 'closed',  cls: 'bg-gray-100 text-gray-500' },
  open:    { label: 'open',    cls: 'bg-green-100 text-green-700' },
}

const REVIEW_DECISION_BADGE = {
  APPROVED:           { label: 'approved',          cls: 'bg-green-100 text-green-700' },
  CHANGES_REQUESTED:  { label: 'changes requested', cls: 'bg-red-100 text-red-600' },
  REVIEW_REQUIRED:    { label: 'review required',   cls: 'bg-yellow-100 text-yellow-700' },
}

function ReviewRow({ review, onClick }) {
  const pr = review.pull_request
  const date = review.created_at
    ? new Date(review.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : ''
  const syncedAt = pr?.last_synced_at
    ? new Date(pr.last_synced_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : null
  const prStateBadge = pr?.pr_state ? PR_STATE_BADGE[pr.pr_state] : null
  const decisionBadge = pr?.review_decision ? REVIEW_DECISION_BADGE[pr.review_decision] : null

  return (
    <button
      onClick={onClick}
      className="w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors border-b border-gray-100 last:border-0 group"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5 flex-wrap">
            {pr && (
              <span className="text-xs mono text-gray-400 shrink-0">
                {pr.owner}/{pr.repo} #{pr.pr_number}
              </span>
            )}
            <StatusBadge status={review.status} />
            {prStateBadge && (
              <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${prStateBadge.cls}`}>
                {prStateBadge.label}
              </span>
            )}
            {decisionBadge && (
              <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${decisionBadge.cls}`}>
                {decisionBadge.label}
              </span>
            )}
          </div>
          <p className="text-sm font-medium text-gray-800 truncate">
            {pr?.title || '(untitled PR)'}
          </p>
          <div className="flex items-center gap-3 mt-0.5">
            {pr?.author && (
              <p className="text-xs text-gray-400">by {pr.author}</p>
            )}
            {syncedAt && (
              <p className="text-xs text-gray-300">synced {syncedAt}</p>
            )}
          </div>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-xs text-gray-400">{date}</p>
          <p className="text-xs text-gray-300 mt-1 group-hover:text-gray-500 transition-colors">
            Open →
          </p>
        </div>
      </div>
    </button>
  )
}

const DAY_OPTIONS = [
  { label: '7d',  value: 7  },
  { label: '14d', value: 14 },
  { label: '30d', value: 30 },
  { label: 'all', value: 0  },
]

function ReviewRequestRow({ item, onStart, starting }) {
  const updated = item.updated_at
    ? new Date(item.updated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    : ''

  return (
    <div className="px-4 py-3 border-b border-gray-100 last:border-0 flex items-center justify-between gap-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5 flex-wrap">
          <span className="text-xs mono text-gray-400 shrink-0">
            {item.repo_full_name} #{item.pr_number}
          </span>
          {item.labels.map((l) => (
            <span key={l} className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded-full">{l}</span>
          ))}
        </div>
        <p className="text-sm font-medium text-gray-800 truncate">{item.title}</p>
        <p className="text-xs text-gray-400 mt-0.5">by {item.author} · updated {updated}</p>
      </div>
      <button
        onClick={() => onStart(item.pr_url)}
        disabled={starting === item.pr_url}
        className="shrink-0 text-xs px-3 py-1.5 bg-gray-900 text-white rounded-md hover:bg-gray-800
          disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
      >
        {starting === item.pr_url ? 'starting…' : 'let chan review it'}
      </button>
    </div>
  )
}

export default function Landing() {
  const navigate = useNavigate()
  const [ghStatus, setGhStatus] = useState({ state: 'checking', username: null })
  const [prUrl, setPrUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [reviews, setReviews] = useState([])
  const [reviewRequests, setReviewRequests] = useState([])
  const [lastSyncedAt, setLastSyncedAt] = useState(null)
  const [requestDays, setRequestDays] = useState(14)
  const [requestsLoading, setRequestsLoading] = useState(false)
  const [startingUrl, setStartingUrl] = useState(null)
  const syncIntervalRef = useRef(null)

  const checkGitHub = () => {
    setGhStatus({ state: 'checking', username: null })
    api.verifyGitHub()
      .then((data) => {
        if (data.ok) setGhStatus({ state: 'ok', username: data.username })
        else setGhStatus({ state: 'error', username: null, error: data.error })
      })
      .catch(() => setGhStatus({ state: 'error', username: null, error: 'Cannot reach backend' }))
  }

  const loadReviews = () => {
    api.listReviews().then(setReviews).catch(() => {})
  }

  const applyRequestsResponse = ({ items, last_synced_at }) => {
    setReviewRequests(items)
    if (last_synced_at) setLastSyncedAt(last_synced_at)
  }

  const loadReviewRequests = (days) => {
    setRequestsLoading(true)
    api.getReviewRequests(days)
      .then(applyRequestsResponse)
      .catch(() => setReviewRequests([]))
      .finally(() => setRequestsLoading(false))
  }

  const syncReviewRequests = (days) => {
    setRequestsLoading(true)
    api.syncReviewRequests(days)
      .then((data) => { applyRequestsResponse(data); saveLastSync() })
      .catch(() => setReviewRequests([]))
      .finally(() => setRequestsLoading(false))
  }

  useEffect(() => {
    checkGitHub()
    loadReviews()
    if (isStale()) {
      syncReviewRequests(requestDays)
    } else {
      loadReviewRequests(requestDays)
    }

    syncIntervalRef.current = setInterval(() => syncReviewRequests(requestDays), ONE_HOUR_MS)
    return () => clearInterval(syncIntervalRef.current)
  }, [])

  const handleDaysChange = (days) => {
    setRequestDays(days)
    loadReviewRequests(days)
  }

  const handleManualRefresh = () => {
    syncReviewRequests(requestDays)
  }

  const handleStartReview = async (url) => {
    setStartingUrl(url)
    try {
      const { review_id } = await api.createReview(url, 'claude')
      const newReview = await api.getReview(review_id)
      setReviewRequests((prev) => prev.filter((r) => r.pr_url !== url))
      setReviews((prev) => [...prev, newReview])
    } catch {
      // leave the item in place on error
    } finally {
      setStartingUrl(null)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!prUrl.trim()) return
    setLoading(true)
    setError(null)
    try {
      const { review_id } = await api.createReview(prUrl.trim(), 'claude')
      navigate(`/review/${review_id}`)
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold text-gray-900 mono">code-chan</span>
          <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">v0 · your ai reviewer</span>
        </div>
        <div className="flex items-center gap-3">
          <GitHubStatus state={ghStatus.state} username={ghStatus.username} status={ghStatus.state} />
          <button onClick={checkGitHub} className="text-xs text-gray-400 hover:text-gray-600 underline">
            re-check
          </button>
        </div>
      </header>

      <div className="flex-1 flex">
        {/* Left: new review form */}
        <div className="w-full max-w-md px-10 py-12 border-r border-gray-100 shrink-0">
          <h1 className="text-2xl font-semibold text-gray-900 mb-1">hey, I'm chan 👋</h1>
          <p className="text-gray-500 mb-8 text-sm leading-relaxed">
            drop a PR link and I'll read through it, group the changes, and leave you
            inline comments to discuss and post to GitHub.
          </p>

          {ghStatus.state === 'error' && (
            <div className="mb-5 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              <strong>GitHub not available:</strong> {ghStatus.error}
              <br />
              <span className="text-red-500 text-xs mt-1 block">
                Run <code className="bg-red-100 px-1 rounded">gh auth login</code> or set{' '}
                <code className="bg-red-100 px-1 rounded">GITHUB_TOKEN</code>
              </span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                GitHub PR URL
              </label>
              <input
                type="url"
                value={prUrl}
                onChange={(e) => setPrUrl(e.target.value)}
                placeholder="https://github.com/owner/repo/pull/123"
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm mono
                  focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent
                  placeholder:text-gray-400 placeholder:font-sans"
                required
              />
            </div>

            <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg">
              <span className="text-xs text-gray-500">powered by</span>
              <span className="text-xs font-semibold text-gray-700 mono">claude code</span>
              <span className="ml-auto text-xs text-gray-400">
                make sure <code className="bg-gray-100 px-1 rounded">claude</code> CLI is authenticated
              </span>
            </div>

            {error && <p className="text-sm text-red-600">{error}</p>}

            <button
              type="submit"
              disabled={loading || !prUrl.trim()}
              className="w-full py-2.5 bg-gray-900 text-white text-sm font-medium rounded-lg
                hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? 'chan is waking up…' : 'let chan review it'}
            </button>
          </form>
        </div>

        {/* Right: review requests + recent reviews */}
        <div className="flex-1 overflow-y-auto">
          {/* ── Review requests ── */}
          <div className="px-8 pt-10 pb-6 border-b border-gray-100">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Requested Reviews</h2>
                {lastSyncedAt && (
                  <p className="text-xs text-gray-400 mt-0.5">
                    synced {formatLastSync(lastSyncedAt)}
                    {' · '}
                    <button
                      onClick={handleManualRefresh}
                      disabled={requestsLoading}
                      className="underline hover:text-gray-600 disabled:opacity-50"
                    >
                      refresh
                    </button>
                  </p>
                )}
              </div>
              <div className="flex items-center gap-1">
                {DAY_OPTIONS.map(({ label, value }) => (
                  <button
                    key={value}
                    onClick={() => handleDaysChange(value)}
                    className={`text-xs px-2.5 py-1 rounded-md border transition-colors
                      ${requestDays === value
                        ? 'bg-gray-900 text-white border-gray-900'
                        : 'border-gray-200 text-gray-500 hover:bg-gray-50'
                      }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {requestsLoading ? (
              <p className="text-sm text-gray-400 animate-pulse py-4">fetching review requests…</p>
            ) : reviewRequests.length === 0 ? (
              <p className="text-sm text-gray-400 py-4">no pending review requests found.</p>
            ) : (
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                {reviewRequests.map((item) => (
                  <ReviewRequestRow
                    key={`${item.repo_full_name}-${item.pr_number}`}
                    item={item}
                    onStart={handleStartReview}
                    starting={startingUrl}
                  />
                ))}
              </div>
            )}
          </div>

          {/* ── Recent reviews ── */}
          <div className="px-8 py-8">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Recent Reviews</h2>
              <button
                onClick={loadReviews}
                className="text-xs text-gray-400 hover:text-gray-600 underline"
              >
                Refresh
              </button>
            </div>

            {reviews.length === 0 ? (
              <div className="text-center py-10 text-gray-400">
                <p className="text-sm">chan hasn't reviewed anything yet.</p>
                <p className="text-xs mt-1">drop a PR link on the left to get started.</p>
              </div>
            ) : (
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                {reviews.map((r) => (
                  <ReviewRow
                    key={r.id}
                    review={r}
                    onClick={() => navigate(`/review/${r.id}`)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
