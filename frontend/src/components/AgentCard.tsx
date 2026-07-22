import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card'
import { Badge } from './ui/badge'
import { Globe, Zap, Code } from 'lucide-react'

interface AgentSkill {
  description: string
  id: string
  name: string
  tags: string[]
}

interface AgentCardProps {
  name: string
  description: string
  version: string
  url: string
  protocolVersion: string
  skills: AgentSkill[]
  capabilities: {
    streaming: boolean
  }
  defaultInputModes: string[]
  defaultOutputModes: string[]
}

export function AgentCard({ 
  name, 
  description, 
  version, 
  url, 
  protocolVersion, 
  skills, 
  capabilities,
  defaultInputModes,
  defaultOutputModes 
}: AgentCardProps) {
  return (
    <Card className="bg-[#1a1e27] border-gray-700 hover:border-[#298dff] transition-colors">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-gray-200 text-lg">{name}</CardTitle>
            <CardDescription className="text-gray-400 mt-1">
              {description}
            </CardDescription>
          </div>
          <Badge variant="secondary" className="bg-[#298dff] text-white">
            v{version}
          </Badge>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* Connection Info */}
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Globe className="w-4 h-4" />
          <span className="font-mono text-xs">{url}</span>
        </div>
        
        {/* Capabilities */}
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-gray-300">Capabilities</h4>
          <div className="flex flex-wrap gap-2">
            {capabilities.streaming && (
              <Badge variant="outline" className="border-green-500 text-green-400">
                <Zap className="w-3 h-3 mr-1" />
                Streaming
              </Badge>
            )}
            <Badge variant="outline" className="border-blue-500 text-blue-400">
              Protocol v{protocolVersion}
            </Badge>
          </div>
        </div>

        {/* Input/Output Modes */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <h4 className="text-sm font-medium text-gray-300 mb-1">Input</h4>
            <div className="flex flex-wrap gap-1">
              {defaultInputModes.map((mode) => (
                <Badge key={mode} variant="outline" className="text-xs border-gray-600 text-gray-400">
                  {mode}
                </Badge>
              ))}
            </div>
          </div>
          <div>
            <h4 className="text-sm font-medium text-gray-300 mb-1">Output</h4>
            <div className="flex flex-wrap gap-1">
              {defaultOutputModes.map((mode) => (
                <Badge key={mode} variant="outline" className="text-xs border-gray-600 text-gray-400">
                  {mode}
                </Badge>
              ))}
            </div>
          </div>
        </div>

        {/* Skills */}
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-gray-300">Skills</h4>
          <div className="space-y-2">
            {skills.map((skill) => (
              <div key={skill.id} className="bg-[#23272f] border border-gray-600 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <Code className="w-4 h-4 text-[#298dff]" />
                  <span className="font-mono text-sm text-gray-300">{skill.name}</span>
                </div>
                <p className="text-xs text-gray-400">{skill.description}</p>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}