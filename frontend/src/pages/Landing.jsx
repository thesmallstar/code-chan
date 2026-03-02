import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import StatusBadge from '../components/StatusBadge'

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

function ReviewRow({ review, onClick }) {
  const pr = review.pull_request
  const date = review.created_at
    ? new Date(review.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : ''

  return (
    <button
      onClick={onClick}
      className="w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors border-b border-gray-100 last:border-0 group"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            {pr && (
              <span className="text-xs mono text-gray-400 shrink-0">
                {pr.owner}/{pr.repo} #{pr.pr_number}
              </span>
            )}
            <StatusBadge status={review.status} />
          </div>
          <p className="text-sm font-medium text-gray-800 truncate">
            {pr?.title || '(untitled PR)'}
          </p>
          {pr?.author && (
            <p className="text-xs text-gray-400 mt-0.5">by {pr.author}</p>
          )}
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

export default function Landing() {
  const navigate = useNavigate()
  const [ghStatus, setGhStatus] = useState({ state: 'checking', username: null })
  const [prUrl, setPrUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [reviews, setReviews] = useState([])

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

  useEffect(() => {
    checkGitHub()
    loadReviews()
  }, [])

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

        {/* Right: recent reviews */}
        <div className="flex-1 overflow-y-auto">
          <div className="px-8 py-12">
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
              <div className="text-center py-16 text-gray-400">
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
