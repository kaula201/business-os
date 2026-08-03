import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { aiApi } from '../../services/api'
import { Bot, X, Send, Sparkles, MessageSquare, Minimize2 } from 'lucide-react'

interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
}

interface Props {
  open: boolean
  onToggle: (v: boolean) => void
}

const suggestions = [
  'რა არის ჩემი მიმდინარე შეკვეთები?',
  'რომელ პროდუქტს აქვს დაბალი ნაშთი?',
  'რამდენი კლიენტი მყავს?',
  'მაჩვენე დაგვიანებული დავალებები',
]

export default function ChatBotWidget({ open, onToggle }: Props) {
  const [messages, setMessages] = useState<ChatMsg[]>([
    { role: 'assistant', content: '👋 გამარჯობა! მე ვარ Business OS AI ასისტენტი. დამისვით შეკითხვა თქვენი ბიზნესის შესახებ.' }
  ])
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open) messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open])

  const chatMutation = useMutation({
    mutationFn: (msg: string) => aiApi.chat(msg),
    onSuccess: (res) => {
      const answer = res.data.data?.message || 'პასუხი ვერ მოიძებნა'
      setMessages(prev => [...prev, { role: 'assistant', content: answer }])
    },
    onError: () => {
      setMessages(prev => [...prev, { role: 'assistant', content: '❌ შეცდომა AI-სთან დაკავშირებისას' }])
    },
  })

  function handleSend() {
    if (!input.trim() || chatMutation.isPending) return
    const msg = input.trim()
    setMessages(prev => [...prev, { role: 'user', content: msg }])
    setInput('')
    chatMutation.mutate(msg)
  }

  return (
    <>
      {!open && (
        <button
          aria-label="AI ასისტენტის გახსნა"
          onClick={() => onToggle(true)}
          className="fixed bottom-6 right-6 z-50 hidden h-14 w-14 items-center justify-center rounded-full bg-primary-600 text-white shadow-lg transition-all hover:scale-105 hover:bg-primary-700 md:flex"
        >
          <MessageSquare size={24} />
        </button>
      )}

      {open && (
        <div className="fixed bottom-6 right-6 z-50 w-96 max-w-[calc(100vw-2rem)] bg-white rounded-2xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden dark:bg-dark-200 dark:border-dark-50"
          style={{ maxHeight: 'min(600px, 80vh)' }}
        >
          <div className="flex items-center justify-between px-4 py-3 bg-primary-600 text-white dark:bg-primary-700">
            <div className="flex items-center gap-2">
              <Bot size={20} />
              <span className="font-medium text-sm">AI ასისტენტი</span>
            </div>
            <button aria-label="AI ასისტენტის ჩაკეცვა" onClick={() => onToggle(false)} className="p-1 hover:bg-primary-500 rounded-lg transition-colors dark:hover:bg-primary-600">
              <Minimize2 size={18} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50 dark:bg-dark-300">
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-primary-600 text-white rounded-br-sm dark:bg-primary-500'
                    : 'bg-white text-gray-800 rounded-bl-sm shadow-sm border border-gray-100 dark:bg-dark-200 dark:text-gray-200 dark:border-dark-50'
                }`}>
                  {msg.content}
                </div>
              </div>
            ))}
            {chatMutation.isPending && (
              <div className="flex justify-start">
                <div className="bg-white px-3.5 py-2.5 rounded-2xl text-sm text-gray-500 shadow-sm border border-gray-100 flex items-center gap-2 dark:bg-dark-200 dark:text-gray-400 dark:border-dark-50">
                  <Sparkles size={14} className="animate-pulse text-primary-500" />
                  ფიქრობს...
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {messages.length <= 1 && (
            <div className="px-4 py-2 border-t border-gray-100 bg-white dark:border-dark-50 dark:bg-dark-200">
              <div className="flex flex-wrap gap-1.5">
                {suggestions.map((s, i) => (
                  <button key={i} onClick={() => setInput(s)}
                    className="text-xs px-2.5 py-1.5 bg-gray-100 hover:bg-primary-50 hover:text-primary-700 rounded-full transition-colors text-gray-600 dark:bg-dark-100 dark:text-gray-400 dark:hover:bg-primary-900/30 dark:hover:text-primary-200"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="p-3 border-t border-gray-200 bg-white dark:border-dark-50 dark:bg-dark-200">
            <div className="flex gap-2">
              <input type="text" value={input} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                placeholder="დაწერეთ შეკითხვა..." className="input text-sm flex-1" disabled={chatMutation.isPending} />
              <button aria-label="შეკითხვის გაგზავნა" onClick={handleSend} disabled={!input.trim() || chatMutation.isPending}
                className="btn-primary px-3 py-0"><Send size={16} /></button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}