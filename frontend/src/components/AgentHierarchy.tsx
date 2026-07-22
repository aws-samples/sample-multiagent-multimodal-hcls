import { Network, Database, Bot } from 'lucide-react'

interface MCPServer {
  name: string
  type: string
}

interface SubAgent {
  name: string
  description: string
  mcpServer: MCPServer
}

interface AgentHierarchyProps {
  orchestrator: {
    name: string
    description: string
  }
  subAgents: SubAgent[]
}

export function AgentHierarchy({ orchestrator, subAgents }: AgentHierarchyProps) {
  return (
    <div className="w-full">
      {/* Orchestrator Agent */}
      <div className="flex justify-center mb-8">
        <div className="bg-gradient-to-br from-[#298dff] to-[#0b2545] border-2 border-[#298dff] rounded-xl p-6 shadow-lg min-w-[300px]">
          <div className="flex items-center gap-3 mb-2">
            <Network className="w-6 h-6 text-white" />
            <h3 className="text-xl font-bold text-white">{orchestrator.name}</h3>
          </div>
          <p className="text-gray-200 text-sm">{orchestrator.description}</p>
        </div>
      </div>

      {/* Connection Lines */}
      <div className="flex justify-center mb-8">
        <div className="relative w-full max-w-4xl">
          <svg className="w-full h-16" style={{ overflow: 'visible' }}>
            {subAgents.map((_, index) => {
              const totalAgents = subAgents.length
              const spacing = 100 / (totalAgents + 1)
              const startX = 50
              const startY = 0
              const endX = spacing * (index + 1)
              const endY = 64
              
              return (
                <line
                  key={index}
                  x1={`${startX}%`}
                  y1={startY}
                  x2={`${endX}%`}
                  y2={endY}
                  stroke="#298dff"
                  strokeWidth="2"
                  strokeDasharray="5,5"
                />
              )
            })}
          </svg>
        </div>
      </div>

      {/* Sub Agents */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {subAgents.map((agent, index) => (
          <div key={index} className="flex flex-col items-center">
            <div className="bg-[#1a1e27] border-2 border-[#4fc3f7] rounded-xl p-5 shadow-md w-full max-w-sm">
              <div className="flex items-center gap-3 mb-2">
                <Bot className="w-5 h-5 text-[#4fc3f7]" />
                <h4 className="text-lg font-semibold text-gray-200">{agent.name}</h4>
              </div>
              <p className="text-gray-400 text-sm mb-4">{agent.description}</p>
              
              {/* Connection to MCP Server */}
              <div className="flex justify-center my-4">
                <div className="w-0.5 h-8 bg-gradient-to-b from-[#4fc3f7] to-[#298dff]"></div>
              </div>
              
              {/* MCP Server */}
              <div className="bg-[#23272f] border border-[#298dff] rounded-lg p-4">
                <div className="flex items-center gap-2 mb-1">
                  <Database className="w-4 h-4 text-[#298dff]" />
                  <span className="text-sm font-medium text-gray-300">{agent.mcpServer.name}</span>
                </div>
                <span className="text-xs text-gray-500">{agent.mcpServer.type}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
