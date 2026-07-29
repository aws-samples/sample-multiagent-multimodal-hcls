import { useState } from 'react'
import { LogOut, MessageCircle, Users, Stethoscope } from 'lucide-react'
import { ChatContainer } from './ChatContainer'
import { AgentsTab } from './AgentsTab'
import { Button } from './ui/button'
import { cn } from '../utils'

interface ChatPageProps {
  signOut: () => void
  user: any
}

type TabType = 'chat' | 'agents'

export function ChatPage({ signOut, user }: ChatPageProps) {
  const [activeTab, setActiveTab] = useState<TabType>('chat')

  const tabs = [
    { id: 'chat' as TabType, label: 'Clinical Chat', icon: MessageCircle },
    { id: 'agents' as TabType, label: 'Agent Architecture', icon: Users },
  ]

  return (
    <div className="min-h-screen bg-[#f5f7fa] flex flex-col">
      {/* AWS-style Header */}
      <header className="flex-shrink-0 bg-gradient-to-r from-[#667eea] to-[#764ba2] text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
                <Stethoscope className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-semibold">Clinical Decision Support</h1>
                <p className="text-white/80 text-sm">AI-Powered Healthcare Intelligence Platform</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center text-sm font-semibold">
                  {user?.username?.charAt(0)?.toUpperCase() || 'U'}
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium">{user?.username || 'User'}</div>
                  <div className="text-xs text-white/70">Healthcare Professional</div>
                </div>
              </div>
              <Button
                onClick={signOut}
                variant="outline"
                size="sm"
                className="bg-white/10 border-white/20 text-white hover:bg-white/20 hover:text-white"
              >
                <LogOut className="w-4 h-4 mr-2" />
                Sign Out
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <div className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-6">
          <nav className="flex space-x-8">
            {tabs.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors",
                    activeTab === tab.id
                      ? "border-[#667eea] text-[#667eea]"
                      : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                  )}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              )
            })}
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-8">
        {activeTab === 'chat' && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 h-[calc(100vh-280px)]">
            <ChatContainer user={user} />
          </div>
        )}
        {activeTab === 'agents' && <AgentsTab />}
      </main>
    </div>
  )
}
