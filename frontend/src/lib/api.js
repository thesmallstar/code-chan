const BASE = ''

async function req(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body !== undefined) opts.body = JSON.stringify(body)
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  health: () => req('GET', '/api/health'),
  getProviders: () => req('GET', '/api/providers'),

  // GitHub
  verifyGitHub: () => req('POST', '/api/github/verify'),
  getReviewRequests: (days = 14) => req('GET', `/api/github/review-requests?days=${days}`),
  syncReviewRequests: (days = 14) => req('POST', `/api/github/review-requests/sync?days=${days}`),

  // Reviews
  listReviews: () => req('GET', '/api/reviews'),
  createReview: (prUrl, modelProvider) =>
    req('POST', '/api/reviews', { pr_url: prUrl, model_provider: modelProvider }),
  getReview: (id) => req('GET', `/api/reviews/${id}`),
  syncReview: (id) => req('POST', `/api/reviews/${id}/sync`),
  submitReview: (id, event, body = '') => req('POST', `/api/reviews/${id}/submit`, { event, body }),
  getThreads: (reviewId) => req('GET', `/api/reviews/${reviewId}/threads`),

  // Chunks
  getChunk: (id) => req('GET', `/api/chunks/${id}`),
  toggleChunkDone: (chunkId) => req('PATCH', `/api/chunks/${chunkId}/done`),
  runAI: (chunkId) => req('POST', `/api/chunks/${chunkId}/run-ai`),
  getChat: (chunkId) => req('GET', `/api/chunks/${chunkId}/chat`),
  sendChat: (chunkId, message) => req('POST', `/api/chunks/${chunkId}/chat`, { message }),
  getDrafts: (chunkId) => req('GET', `/api/chunks/${chunkId}/drafts`),
  createDraft: (chunkId, draft) => req('POST', `/api/chunks/${chunkId}/drafts`, draft),
  updateDraft: (draftId, data) => req('PUT', `/api/chunks/drafts/${draftId}`, data),
  deleteDraft: (draftId) => req('DELETE', `/api/chunks/drafts/${draftId}`),
  sendDraft: (draftId) => req('POST', `/api/chunks/drafts/${draftId}/send`),

  // Threads
  replyToThread: (threadId, bodyMd) =>
    req('POST', `/api/threads/${threadId}/reply`, { body_md: bodyMd }),
  discussThread: (threadId, message, history = []) =>
    req('POST', `/api/threads/${threadId}/discuss`, { message, history }),
  resolveThread: (threadId) => req('PATCH', `/api/threads/${threadId}/resolve`),

  // Re-review
  createReReview: (reviewId) => req('POST', `/api/reviews/${reviewId}/re-review`),
  getReReview: (id) => req('GET', `/api/re-reviews/${id}`),
}
