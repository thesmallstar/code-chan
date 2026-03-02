import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import { api } from '../lib/api'

function Message({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 text-sm
          ${isUser
            ? 'bg-gray-900 text-white'
            : 'bg-white border border-gray-200 text-gray-800'
          }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{msg.content}</p>
        ) : (
          <div className="prose text-sm">
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  )
}

export default function ChatPanel({ chunkId, onDraftFromChat }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    if (!chunkId) return
    api.getChat(chunkId)
      .then(setMessages)
      .catch(() => setMessages([]))
  }, [chunkId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    if (!input.trim() || sending) return
    const text = input.trim()
    setInput('')
    setSending(true)
    setError(null)

    setMessages((prev) => [...prev, { id: Date.now(), role: 'user', content: text }])

    try {
      const reply = await api.sendChat(chunkId, text)
      setMessages((prev) => [...prev.slice(0, -1), { id: Date.now() - 1, role: 'user', content: text }, reply])
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  if (!chunkId) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-400 italic">
        select a chunk to chat with chan
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-gray-200">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">chat with chan</h3>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3 bg-gray-50">
        {messages.length === 0 ? (
          <p className="text-xs text-gray-400 text-center italic mt-4">
            ask chan to explain a change, flag an issue, or help write a comment.
          </p>
        ) : (
          messages.map((m, i) => <Message key={m.id ?? i} msg={m} />)
        )}
        {sending && (
          <div className="flex justify-start mb-3">
            <div className="bg-white border border-gray-200 rounded-lg px-3 py-2">
              <span className="text-xs text-gray-400 animate-pulse">chan is thinking…</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {error && (
        <p className="px-3 py-1 text-xs text-red-500 bg-red-50 border-t border-red-100">{error}</p>
      )}

      <div className="border-t border-gray-200 p-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="ask chan anything about this chunk… (Enter to send)"
          rows={3}
          className="w-full text-sm px-3 py-2 border border-gray-300 rounded-lg resize-none
            focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
        />
        <button
          onClick={send}
          disabled={sending || !input.trim()}
          className="mt-1.5 w-full py-1.5 bg-gray-900 text-white text-xs font-medium rounded-lg
            hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  )
}
