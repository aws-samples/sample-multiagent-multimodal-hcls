import { useEffect, useRef, useState } from 'react'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { useChat } from '../hooks/useChat'
import { fetchAuthSession } from 'aws-amplify/auth'
import { Loader2, Brain, Sparkles } from 'lucide-react'

interface ChatContainerProps {
  user: any
}

export function ChatContainer({ user }: ChatContainerProps) {
  const { messages, sendMessage, isStreaming, isInitialized, initializationError, initializeConversation } = useChat()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const hasInitialized = useRef(false)
  const [accessToken, setAccessToken] = useState<string>('')

  // Fetch access token
  useEffect(() => {
    const getToken = async () => {
      try {
        const session = await fetchAuthSession()
        const token = session.tokens?.accessToken?.toString() || ''
        setAccessToken(token)
      } catch (error) {
        console.error('Error fetching auth session:', error)
      }
    }
    getToken()
  }, [])

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Initialize conversation on first load
  useEffect(() => {
    if (
      isInitialized &&
      !hasInitialized.current &&
      messages.length === 0 &&
      accessToken &&
      user
    ) {
      hasInitialized.current = true
      const email = user.signInDetails?.loginId || user.username
      initializeConversation(
        email,
        accessToken,
        user.username
      )
    }
  }, [isInitialized, messages.length, accessToken, user, initializeConversation])

  const handleSendMessage = async (message: string) => {
    if (!accessToken || !user) return

    await sendMessage(
      message,
      accessToken,
      user.username
    )
  }

  if (initializationError) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center bg-red-50 border border-red-200 rounded-xl p-6 max-w-md">
          <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-red-600 text-xl">⚠️</span>
          </div>
          <h3 className="text-lg font-semibold text-red-800 mb-2">Connection Error</h3>
          <p className="text-red-600 mb-2">{initializationError}</p>
          <p className="text-red-500 text-sm">Please check your CloudFormation stack configuration</p>
        </div>
      </div>
    )
  }

  if (!isInitialized) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center">
          <div className="w-16 h-16 bg-gradient-to-r from-[#667eea] to-[#764ba2] rounded-full flex items-center justify-center mx-auto mb-4">
            <Brain className="w-8 h-8 text-white animate-pulse" />
          </div>
          <h3 className="text-lg font-semibold text-gray-700 mb-2">Initializing AI Agent</h3>
          <p className="text-gray-500">Connecting to clinical intelligence systems...</p>
          <div className="flex items-center justify-center gap-1 mt-4">
            <div className="w-2 h-2 bg-[#667eea] rounded-full animate-bounce"></div>
            <div className="w-2 h-2 bg-[#667eea] rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
            <div className="w-2 h-2 bg-[#667eea] rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Welcome Header */}
      {messages.length === 0 && (
        <div className="p-8 text-center border-b border-gray-100">
          <div className="w-16 h-16 bg-gradient-to-r from-[#667eea] to-[#764ba2] rounded-full flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Welcome to Clinical Decision Support</h2>
          <p className="text-gray-600 max-w-2xl mx-auto">
            Ask questions about medical literature, clinical trials, treatment protocols, or drug information. 
            Our AI agents will search PubMed and clinical databases to provide evidence-based responses.
          </p>
          <div className="flex flex-wrap justify-center gap-2 mt-6">
            <span className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm">PubMed Research</span>
            <span className="px-3 py-1 bg-green-50 text-green-700 rounded-full text-sm">Clinical Trials</span>
            <span className="px-3 py-1 bg-purple-50 text-purple-700 rounded-full text-sm">Drug Information</span>
            <span className="px-3 py-1 bg-orange-50 text-orange-700 rounded-full text-sm">Treatment Guidelines</span>
          </div>
        </div>
      )}

      {/* Scrollable message history */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {messages.map((message, index) => {
            const isLastMessage = index === messages.length - 1
            const isStreamingMessage = isStreaming && isLastMessage && message.role === 'assistant'

            return (
              <ChatMessage
                key={`${message.timestamp}-${index}`}
                message={message}
                isStreaming={isStreamingMessage}
              />
            )
          })}

          {isStreaming && messages[messages.length - 1]?.role === 'user' && (
            <div className="flex justify-start">
              <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl px-4 py-3 max-w-xs">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 bg-gradient-to-r from-[#667eea] to-[#764ba2] rounded-full flex items-center justify-center">
                    <Brain className="w-3 h-3 text-white animate-pulse" />
                  </div>
                  <span className="text-sm text-gray-700">Analyzing clinical data...</span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Fixed chat input at bottom */}
      <div className="border-t border-gray-100 bg-gray-50/50">
        <ChatInput
          onSend={handleSendMessage}
          disabled={isStreaming}
        />
      </div>
    </div>
  )
}
