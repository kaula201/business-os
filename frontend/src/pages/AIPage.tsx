import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { aiApi } from '../services/api'
import { Send, Bot, Sparkles, RefreshCw, AlertCircle, TrendingUp, Clock, Package } from 'lucide-react'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

function renderMarkdown(text: string): React.ReactNode[] {
  return text.split('\n').map((line, lineIdx) => {
    const parts: React.ReactNode[] = []
    // Process inline markdown: **bold**, `code`, emojis stay as-is
    const regex = /\*\*(.+?)\*\*|`(.+?)`|---/g
    let lastIndex = 0
    let match: RegExpExecArray | null

    while ((match = regex.exec(line)) !== null) {
      if (match.index > lastIndex) {
        parts.push(line.slice(lastIndex, match.index))
      }
    if (match[0] === '---') {
      parts.push(<hr key={`hr-${lineIdx}-${match.index}`} className="my-2 border-gray-300 dark:border-dark-50" />)
    } else if (match[1]) {
      parts.push(<b key={`b-${lineIdx}-${match.index}`} className="font-semibold">{match[1]}</b>)
    } else if (match[2]) {
      parts.push(<code key={`c-${lineIdx}-${match.index}`} className="bg-gray-200 text-gray-700 dark:text-gray-300 px-1 py-0.5 rounded text-xs">{match[2]}</code>)
    }
    lastIndex = match.index + match[0].length
    }
    if (lastIndex < line.length) {
      parts.push(line.slice(lastIndex))
    }

    return (
      <span key={lineIdx}>
        {lineIdx > 0 && <br />}
        {parts.length > 0 ? parts : line}
      </span>
    )
  })
}

export default function AIPage() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: 'მოგესალმებით! 👋 მე ვარ Business OS AI ასისტენტი. დამისვით შეკითხვა თქვენი ბიზნეს მონაცემების შესახებ — შემოსავლები, კლიენტები, შეკვეთები, ნაშთები ან დავალებები.' }
  ])
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const chatMutation = useMutation({
    mutationFn: (message: string) => aiApi.chat(message),
    onSuccess: (res) => {
      setMessages(prev => [...prev, { role: 'assistant', content: res.data.data?.message || 'პასუხი ვერ მოიძებნა' }])
    },
    onError: () => {
      setMessages(prev => [...prev, { role: 'assistant', content: 'შეცდომა AI-სთან დაკავშირებისას. გთხოვთ სცადოთ თავიდან.' }])
    },
  })

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = () => {
    if (!input.trim() || chatMutation.isPending) return
    const userMsg = input.trim()
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setInput('')
    chatMutation.mutate(userMsg)
  }

  const quickActions = [
    { id: 'daily_summary', label: '📊 დღის შეჯამება', prompt: 'მომაწოდე დღის შეჯამება — შემოსავალი, ახალი შეკვეთები, დავალებები' },
    { id: 'critical', label: '🚨 კრიტიკული საკითხები', prompt: 'რა არის კრიტიკული საკითხები? დაბალი ნაშთები, დაგვიანებული დავალებები' },
    { id: 'stock', label: '📦 დაბალი ნაშთები', prompt: 'რომელ პროდუქტებს აქვთ დაბალი ნაშთი?' },
    { id: 'overdue', label: '⏰ დაგვიანებული დავალებები', prompt: 'რა დავალებებია დაგვიანებული?' },
  ]

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col">
      <div className="flex items-center gap-3 mb-4">
        <Bot size={28} className="text-primary-600" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">AI ასისტენტი</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Business OS ინტელექტუალური თანაშემწე</p>
        </div>
      </div>

      <div className="flex-1 flex gap-4 min-h-0">
        {/* Chat */}
        <div className="flex-1 card flex flex-col">
          <div className="flex-1 overflow-y-auto space-y-4 p-4">
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-primary-600 text-white rounded-br-md'
                    : 'bg-gray-100 dark:bg-dark-100 text-gray-800 rounded-bl-md'
                }`}>
                  {msg.role === 'user' ? msg.content : renderMarkdown(msg.content)}
                </div>
              </div>
            ))}
            {chatMutation.isPending && (
              <div className="flex justify-start">
                <div className="bg-gray-100 dark:bg-dark-100 px-4 py-3 rounded-2xl text-gray-500 dark:text-gray-400 text-sm flex items-center gap-2">
                  <RefreshCw size={14} className="animate-spin" />
                  ფიქრობს...
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="border-t border-gray-200 dark:border-dark-50 p-4">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                placeholder="დასვით შეკითხვა..."
                className="input flex-1"
                disabled={chatMutation.isPending}
              />
              <button onClick={handleSend} className="btn-primary px-4" disabled={!input.trim() || chatMutation.isPending}>
                <Send size={18} />
              </button>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="w-64 card hidden lg:flex flex-col">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2">
            <Sparkles size={16} className="text-yellow-500" />
            სწრაფი ქმედებები
          </h3>
          <div className="space-y-2 flex-1">
            {quickActions.map(a => (
              <button
                key={a.id}
                onClick={() => {
                  setInput(a.prompt)
                }}
                className="w-full text-left px-3 py-2.5 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-100 dark:bg-dark-100 text-sm transition-colors border border-gray-100 dark:border-dark-50 hover:border-gray-200 dark:border-dark-50"
              >
                {a.label}
              </button>
            ))}
          </div>
          <div className="mt-4 pt-4 border-t border-gray-200 dark:border-dark-50">
            <div className="text-xs text-gray-400 space-y-2">
              <p className="flex items-center gap-1"><TrendingUp size={12} /> შემოსავლების ანალიზი</p>
              <p className="flex items-center gap-1"><Package size={12} /> ნაშთების მართვა</p>
              <p className="flex items-center gap-1"><Clock size={12} /> დავალებების ტრეკინგი</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
