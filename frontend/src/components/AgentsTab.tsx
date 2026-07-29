import { AgentCard } from './AgentCard'
import { AgentHierarchy } from './AgentHierarchy'
import { Network, Database, Search, FileText, Activity } from 'lucide-react'

// Orchestrator agent data
const orchestratorData = {
  name: "Orchestrator Agent",
  description: "Central coordination hub that intelligently routes clinical queries to specialized agents"
}

// Sub-agents with their MCP servers
const subAgentsData = [
  {
    name: "PubMed Research Agent",
    description: "Searches biomedical literature and research papers from PubMed database",
    mcpServer: {
      name: "PubMed MCP Server",
      type: "Biomedical Literature Database"
    }
  },
  {
    name: "Clinical Trials Agent",
    description: "Queries active and completed clinical trials from ClinicalTrials.gov",
    mcpServer: {
      name: "Clinical Trials MCP Server",
      type: "Clinical Trials Database"
    }
  },
  {
    name: "Model Inference Agent",
    description: "Predicts disease likelihood using AutoGluon and TabPFN models on patient data",
    mcpServer: {
      name: "SageMaker Endpoints",
      type: "ML Inference (AutoGluon + TabPFN)"
    }
  }
]

// Sample agent data - you can replace this with data from your API
const agentsData = [
  {
    "capabilities": {
      "streaming": true
    },
    "defaultInputModes": ["text"],
    "defaultOutputModes": ["text"],
    "description": "Searches and analyzes biomedical literature from PubMed to provide evidence-based clinical insights",
    "name": "PubMed Research Agent",
    "preferredTransport": "BedrockAgentCore",
    "protocolVersion": "1.0.0",
    "skills": [
      {
        "description": "Advanced search capabilities across PubMed's extensive medical literature database",
        "id": "search_pubmed",
        "name": "PubMed Literature Search",
        "tags": ["research", "evidence-based", "literature"]
      }
    ],
    "url": "arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/pubmed_agent_a2a-EXAMPLE",
    "version": "1.0.0"
  },
  {
    "capabilities": {
      "streaming": true
    },
    "defaultInputModes": ["text"],
    "defaultOutputModes": ["text"],
    "description": "Provides comprehensive clinical trial information and research opportunities",
    "name": "Clinical Trials Agent",
    "preferredTransport": "BedrockAgentCore",
    "protocolVersion": "1.0.0",
    "skills": [
      {
        "description": "Search and analyze clinical trials data from ClinicalTrials.gov",
        "id": "run_clinical_trial",
        "name": "Clinical Trials Search",
        "tags": ["trials", "research", "treatment"]
      }
    ],
    "url": "arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/orchestrator-EXAMPLE",
    "version": "1.0.0"
  },
  {
    "capabilities": {
      "streaming": true
    },
    "defaultInputModes": ["text"],
    "defaultOutputModes": ["text"],
    "description": "Predicts disease likelihood for patients using dual-model inference (AutoGluon + TabPFN) on the Synthea Coherent dataset. Supports Hypertension, Stroke, Coronary Heart Disease, and Alzheimer's Disease.",
    "name": "Model Inference Agent",
    "preferredTransport": "BedrockAgentCore",
    "protocolVersion": "1.0.0",
    "skills": [
      {
        "description": "Run the full disease prediction pipeline: parse query, load patient data, select model, run dual-model inference, and format structured response",
        "id": "predict_disease",
        "name": "Disease Likelihood Prediction",
        "tags": ["prediction", "ml-inference", "sagemaker"]
      },
      {
        "description": "Delegate literature queries to the PubMed specialist agent for evidence grounding",
        "id": "send_pubmed_query",
        "name": "Literature Delegation",
        "tags": ["literature", "pubmed", "delegation"]
      }
    ],
    "url": "arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/model_inference_agent-EXAMPLE",
    "version": "1.0.0"
  }
]

export function AgentsTab() {
  return (
    <div className="space-y-8">
      {/* Header Section */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-gradient-to-r from-[#667eea] to-[#764ba2] rounded-full flex items-center justify-center mx-auto mb-4">
            <Network className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-2xl font-bold text-gray-800 mb-2">Multi-Agent Architecture</h2>
          <p className="text-gray-600 max-w-3xl mx-auto">
            Our Clinical Decision Support system uses a sophisticated multi-agent architecture to provide 
            comprehensive healthcare intelligence. Each specialized agent focuses on specific medical domains 
            to deliver accurate, evidence-based responses.
          </p>
        </div>
        
        {/* Agent Hierarchy Visualization */}
        <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-8">
          <AgentHierarchy 
            orchestrator={orchestratorData}
            subAgents={subAgentsData}
          />
        </div>
      </div>

      {/* Capabilities Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
            <Search className="w-6 h-6 text-blue-600" />
          </div>
          <h3 className="text-lg font-semibold text-gray-800 mb-2">Literature Search</h3>
          <p className="text-gray-600 text-sm">
            Access to millions of peer-reviewed medical publications through PubMed integration
          </p>
        </div>
        
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mb-4">
            <Database className="w-6 h-6 text-green-600" />
          </div>
          <h3 className="text-lg font-semibold text-gray-800 mb-2">Clinical Trials</h3>
          <p className="text-gray-600 text-sm">
            Real-time access to clinical trial data and research opportunities worldwide
          </p>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center mb-4">
            <Activity className="w-6 h-6 text-orange-600" />
          </div>
          <h3 className="text-lg font-semibold text-gray-800 mb-2">Disease Prediction</h3>
          <p className="text-gray-600 text-sm">
            Dual-model ML inference (AutoGluon + TabPFN) for disease likelihood prediction on patient data
          </p>
        </div>
        
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mb-4">
            <FileText className="w-6 h-6 text-purple-600" />
          </div>
          <h3 className="text-lg font-semibold text-gray-800 mb-2">Evidence Synthesis</h3>
          <p className="text-gray-600 text-sm">
            Intelligent analysis and synthesis of medical evidence for clinical decision making
          </p>
        </div>
      </div>

      {/* Agent Details */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <div className="mb-6">
          <h2 className="text-xl font-bold text-gray-800 mb-2">Specialized Agent Details</h2>
          <p className="text-gray-600">
            Each agent is optimized for specific healthcare domains with advanced capabilities and real-time data access
          </p>
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {agentsData.map((agent, index) => (
            <AgentCard
              key={`${agent.name}-${index}`}
              name={agent.name}
              description={agent.description}
              version={agent.version}
              url={agent.url}
              protocolVersion={agent.protocolVersion}
              skills={agent.skills}
              capabilities={agent.capabilities}
              defaultInputModes={agent.defaultInputModes}
              defaultOutputModes={agent.defaultOutputModes}
            />
          ))}
        </div>
      </div>
    </div>
  )
}