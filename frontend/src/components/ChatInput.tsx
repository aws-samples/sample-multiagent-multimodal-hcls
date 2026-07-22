import { useState, KeyboardEvent } from 'react'
import { Send, Mic } from 'lucide-react'
import { Button } from './ui/button'
import { cn } from '../utils'

interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
  placeholder?: string
}

export function ChatInput({
  onSend,
  disabled = false,
  placeholder = "Ask about clinical research, treatments, or drug information...",
}: ChatInputProps) {
  const [input, setInput] = useState('')

  const handleSend = () => {
    const trimmed = input.trim()
    if (trimmed && !disabled) {
      onSend(trimmed)
      setInput('')
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex gap-3 items-end">
          <div className="flex-1 relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={disabled}
              rows={1}
              className={cn(
                "w-full bg-white border border-gray-300 rounded-xl px-4 py-3 pr-12",
                "placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-[#667eea] focus:border-transparent",
                "resize-none max-h-32 overflow-y-auto text-gray-900",
                "shadow-sm transition-all duration-200",
                disabled && "opacity-50 cursor-not-allowed bg-gray-50"
              )}
              style={{
                minHeight: '48px',
                lineHeight: '1.5'
              }}
            />
            {/* Character count or status indicator */}
            <div className="absolute bottom-2 right-3 text-xs text-gray-400">
              {input.length > 0 && `${input.length} chars`}
            </div>
          </div>
          
          <Button
            onClick={handleSend}
            disabled={disabled || !input.trim()}
            className={cn(
              "bg-gradient-to-r from-[#667eea] to-[#764ba2] hover:from-[#5a6fd8] hover:to-[#6a4190]",
              "text-white px-4 py-3 rounded-xl transition-all duration-200 shadow-sm",
              "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:from-[#667eea] disabled:hover:to-[#764ba2]",
              "h-12 min-w-[48px] flex items-center justify-center"
            )}
          >
            <Send className="w-5 h-5" />
          </Button>
        </div>
        
        {/* Quick action suggestions */}
        <div className="flex flex-wrap gap-2 mt-4">
          <button
            onClick={() => setInput("Find recent studies on diabetes treatment")}
            disabled={disabled}
            className="px-3 py-1.5 text-sm bg-blue-50 text-blue-700 rounded-full hover:bg-blue-100 transition-colors disabled:opacity-50"
          >
            📚 Research diabetes
          </button>
          <button
            onClick={() => setInput("What are the side effects of metformin?")}
            disabled={disabled}
            className="px-3 py-1.5 text-sm bg-green-50 text-green-700 rounded-full hover:bg-green-100 transition-colors disabled:opacity-50"
          >
            💊 Drug information
          </button>
          <button
            onClick={() => setInput("Show me clinical trials for cancer treatment")}
            disabled={disabled}
            className="px-3 py-1.5 text-sm bg-purple-50 text-purple-700 rounded-full hover:bg-purple-100 transition-colors disabled:opacity-50"
          >
            🧪 Clinical trials
          </button>
        </div>
      </div>
    </div>
  )
}
