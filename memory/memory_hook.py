import json
import sys
import os

import boto3
from bedrock_agentcore.memory import MemoryClient
from strands.hooks import HookProvider, MessageAddedEvent, HookRegistry, AgentInitializedEvent

# Add parent directory to path to import logger
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import logger


class ShortTermMemoryHook(HookProvider):
    def __init__(self, memory_client: MemoryClient, memory_id: str, actor_id: str, session_id: str):
        self.session = boto3.Session()
        self.region = self.session.region_name
        self.memory_client = MemoryClient(region_name=self.region)
        self.memory_id = memory_id
        self.actor_id = actor_id
        self.session_id = session_id
    
    def on_agent_initialized(self, event: AgentInitializedEvent):
        """Load recent conversation history when agent starts"""
        try:
            # Get last 5 conversation turns
            recent_turns = self.memory_client.get_last_k_turns(
                memory_id=self.memory_id,
                actor_id=self.actor_id,
                session_id=self.session_id,
                k=5,
                branch_name="main"
            )
            
            if recent_turns:
                context_messages = []
                for turn in recent_turns:
                    for message in turn:
                        role = message['role'].lower()
                        content = message['content']['text']
                        context_messages.append(f"{role.title()}: {content}")
                
                context = "\n".join(context_messages)
                logger.info(f"Context from memory: {context}")
                
                # Add context to agent's system prompt
                event.agent.system_prompt += f"\n\nRecent conversation history:\n{context}\n\nContinue the conversation naturally based on this context."
                
                logger.info(f"✅ Loaded {len(recent_turns)} recent conversation turns")
            else:
                logger.info("No previous conversation history found")
                
        except Exception as e:
            logger.error(f"Failed to load conversation history: {e}")
    
    def on_message_added(self, event: MessageAddedEvent):
        """Store conversation turns in memory"""
        messages = event.agent.messages
        logger.info("------------------------")
        logger.info(json.dumps(messages, indent=4))
        logger.info("------------------------")
        try:
            if "toolResult" in messages[-1]["content"][0]:
                self.memory_client.create_event(
                memory_id=self.memory_id,
                actor_id=self.actor_id,
                session_id=self.session_id,
                messages=[(messages[-1]["content"][0]["toolResult"]["content"][0]["text"], messages[-1]["role"])]
            )
            else:
                self.memory_client.create_event(
                    memory_id=self.memory_id,
                    actor_id=self.actor_id,
                    session_id=self.session_id,
                    messages=[(messages[-1]["content"][0]["text"], messages[-1]["role"])]
                )
            
        except Exception as e:
            logger.error(f"Failed to store message: {e}")
    
    def register_hooks(self, registry: HookRegistry) -> None:
        # Register memory hooks
        registry.add_callback(MessageAddedEvent, self.on_message_added)
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)