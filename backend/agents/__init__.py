"""
Specialized LangGraph agent nodes for the Lakera Guard demo.

Each agent showcases a different Lakera security protection:
- input_guard: Prompt injection & jailbreak detection
- router: Intent classification to pick the right agent
- rag_agent: Knowledge Q&A with indirect injection protection
- tool_agent: MCP tool execution with tool-output scanning
- pii_agent: Data handling with PII detection
- output_guard: Final content moderation on all responses
"""
