import { useState } from 'react'
import Sidebar from './Sidebar'
import Header from './Header'
import Breadcrumbs from './Breadcrumbs'
import ChatBotWidget from '../chat/ChatBotWidget'

export default function Layout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)

  return (
    <div className="flex h-screen bg-[#f7f8f8] dark:bg-dark-300">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} onChatToggle={() => setChatOpen(true)} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Breadcrumbs />
          {children}
        </main>
      </div>
      <ChatBotWidget open={chatOpen} onToggle={setChatOpen} />
    </div>
  )
}