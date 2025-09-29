from typing import Any, Dict, Optional

from crewai.events import (
    AgentEvaluationCompletedEvent,
    AgentEvaluationFailedEvent,
    AgentEvaluationStartedEvent,
    AgentExecutionCompletedEvent,
    AgentExecutionErrorEvent,
    AgentExecutionStartedEvent,
    AgentLogsExecutionEvent,
    AgentLogsStartedEvent,
    AgentReasoningCompletedEvent,
    AgentReasoningFailedEvent,
    AgentReasoningStartedEvent,
    CrewKickoffCompletedEvent,
    CrewKickoffFailedEvent,
    CrewKickoffStartedEvent,
    FlowFinishedEvent,
    FlowStartedEvent,
    KnowledgeQueryCompletedEvent,
    KnowledgeQueryFailedEvent,
    KnowledgeQueryStartedEvent,
    KnowledgeRetrievalCompletedEvent,
    KnowledgeRetrievalStartedEvent,
    LiteAgentExecutionCompletedEvent,
    LiteAgentExecutionErrorEvent,
    LiteAgentExecutionStartedEvent,
    LLMCallCompletedEvent,
    LLMCallFailedEvent,
    LLMCallStartedEvent,
    LLMGuardrailCompletedEvent,
    LLMGuardrailStartedEvent,
    MemoryQueryCompletedEvent,
    MemoryQueryFailedEvent,
    MemoryQueryStartedEvent,
    MemoryRetrievalCompletedEvent,
    MemoryRetrievalStartedEvent,
    MemorySaveCompletedEvent,
    MemorySaveFailedEvent,
    MemorySaveStartedEvent,
    MethodExecutionFailedEvent,
    MethodExecutionFinishedEvent,
    MethodExecutionStartedEvent,
    TaskCompletedEvent,
    TaskFailedEvent,
    TaskStartedEvent,
    ToolExecutionErrorEvent,
    ToolUsageFinishedEvent,
    ToolUsageStartedEvent,
)
from crewai.events.base_event_listener import BaseEventListener
from crewai.events.event_bus import CrewAIEventsBus
from opentelemetry import trace

from write_a_book_with_flows.tracing import setup_tracing


class BraintrustListener(BaseEventListener):
    def __init__(self):
        super().__init__()
        setup_tracing()
        self.tracer = trace.get_tracer(__name__)
        self.flow_context = None
        self.flow_span = None

    def setup_listeners(self, crewai_event_bus: CrewAIEventsBus):
        # Flow Events - these create the parent trace context
        @crewai_event_bus.on(FlowStartedEvent)
        def on_flow_started(source, event):
            flow_name = getattr(event, "flow_name", "Unknown Flow")
            flow_class_name = source.__class__.__name__ if source else "Flow"

            # Start the main flow span and capture its context
            span_name = f"{flow_class_name} Execution: {flow_name}"
            self.flow_span = self.tracer.start_span(span_name)
            self.flow_context = trace.set_span_in_context(self.flow_span)

            self.flow_span.set_attribute("flow.name", flow_name)
            self.flow_span.set_attribute("flow.class", flow_class_name)
            self.flow_span.set_attribute("event.type", "flow_execution")
            print(f"Flow started: {flow_class_name} - {flow_name}")

        @crewai_event_bus.on(FlowFinishedEvent)
        def on_flow_finished(source, event):
            flow_name = getattr(event, "flow_name", "BookFlow")
            print(f"Flow finished: {flow_name}")
            if self.flow_span:
                self.flow_span.set_attribute("event.type", "flow_completed")
                self.flow_span.end()
                self.flow_span = None
                self.flow_context = None

        # Method Execution Events
        @crewai_event_bus.on(MethodExecutionStartedEvent)
        def on_method_started(source, event):
            method_name = getattr(event, "method_name", "Unknown Method")
            self._handle_event(
                "method_execution_started",
                f"Method: {method_name}",
                {"method.name": method_name},
            )

        @crewai_event_bus.on(MethodExecutionFinishedEvent)
        def on_method_finished(source, event):
            method_name = getattr(event, "method_name", "Unknown Method")
            self._handle_event(
                "method_execution_finished",
                f"Method Completed: {method_name}",
                {"method.name": method_name},
            )

        # Crew Events
        @crewai_event_bus.on(CrewKickoffStartedEvent)
        def on_crew_started(source, event):
            crew_name = getattr(source, "name", "Unknown Crew")
            self._handle_event(
                "crew_kickoff_started", f"Crew: {crew_name}", {"crew.name": crew_name}
            )

        @crewai_event_bus.on(CrewKickoffCompletedEvent)
        def on_crew_completed(source, event):
            crew_name = getattr(source, "name", "Unknown Crew")
            self._handle_event(
                "crew_kickoff_completed",
                f"Crew Completed: {crew_name}",
                {"crew.name": crew_name},
            )

        # Task Events
        @crewai_event_bus.on(TaskStartedEvent)
        def on_task_started(source, event):
            task_description = getattr(source, "description", "Unknown Task")
            task_name = (
                task_description[:50] + "..."
                if len(task_description) > 50
                else task_description
            )
            self._handle_event(
                "task_started",
                f"Task: {task_name}",
                {"task.description": task_description},
            )

        @crewai_event_bus.on(TaskCompletedEvent)
        def on_task_completed(source, event):
            task_description = getattr(source, "description", "Unknown Task")
            task_name = (
                task_description[:50] + "..."
                if len(task_description) > 50
                else task_description
            )
            self._handle_event(
                "task_completed",
                f"Task Completed: {task_name}",
                {"task.description": task_description},
            )

        # Agent Events
        @crewai_event_bus.on(AgentExecutionStartedEvent)
        def on_agent_started(source, event):
            agent_role = getattr(source, "role", "Unknown Agent")
            self._handle_event(
                "agent_execution_started",
                f"Agent: {agent_role}",
                {"agent.role": agent_role},
            )

        @crewai_event_bus.on(AgentExecutionCompletedEvent)
        def on_agent_completed(source, event):
            agent_role = getattr(source, "role", "Unknown Agent")
            self._handle_event(
                "agent_execution_completed",
                f"Agent Completed: {agent_role}",
                {"agent.role": agent_role},
            )

        @crewai_event_bus.on(AgentExecutionErrorEvent)
        def on_agent_error(source, event):
            agent_role = getattr(source, "role", "Unknown Agent")
            error_msg = getattr(event, "error", "Unknown Error")
            self._handle_event(
                "agent_execution_error",
                f"Agent Error: {agent_role}",
                {"agent.role": agent_role, "error.message": str(error_msg)},
            )

        # LLM Events
        @crewai_event_bus.on(LLMCallStartedEvent)
        def on_llm_started(source, event):
            model = getattr(event, "model", "Unknown Model")
            self._handle_event(
                "llm_call_started", f"LLM Call: {model}", {"llm.model": model}
            )

        @crewai_event_bus.on(LLMCallCompletedEvent)
        def on_llm_completed(source, event):
            model = getattr(event, "model", "Unknown Model")
            self._handle_event(
                "llm_call_completed", f"LLM Completed: {model}", {"llm.model": model}
            )

        @crewai_event_bus.on(LLMCallFailedEvent)
        def on_llm_failed(source, event):
            model = getattr(event, "model", "Unknown Model")
            error_msg = getattr(event, "error", "Unknown Error")
            self._handle_event(
                "llm_call_failed",
                f"LLM Failed: {model}",
                {"llm.model": model, "error.message": str(error_msg)},
            )

        # Tool Usage Events
        @crewai_event_bus.on(ToolUsageStartedEvent)
        def on_tool_started(source, event):
            tool_name = getattr(event, "tool_name", "Unknown Tool")
            self._handle_event(
                "tool_usage_started", f"Tool: {tool_name}", {"tool.name": tool_name}
            )

        @crewai_event_bus.on(ToolUsageFinishedEvent)
        def on_tool_finished(source, event):
            tool_name = getattr(event, "tool_name", "Unknown Tool")
            self._handle_event(
                "tool_usage_finished",
                f"Tool Completed: {tool_name}",
                {"tool.name": tool_name},
            )

        @crewai_event_bus.on(ToolExecutionErrorEvent)
        def on_tool_error(source, event):
            tool_name = getattr(event, "tool_name", "Unknown Tool")
            error_msg = getattr(event, "error", "Unknown Error")
            self._handle_event(
                "tool_execution_error",
                f"Tool Error: {tool_name}",
                {"tool.name": tool_name, "error.message": str(error_msg)},
            )

        # Memory Events
        @crewai_event_bus.on(MemorySaveStartedEvent)
        def on_memory_save_started(source, event):
            self._handle_event("memory_save_started", "Memory Save Started", {})

        @crewai_event_bus.on(MemorySaveCompletedEvent)
        def on_memory_save_completed(source, event):
            self._handle_event("memory_save_completed", "Memory Save Completed", {})

        @crewai_event_bus.on(MemorySaveFailedEvent)
        def on_memory_save_failed(source, event):
            error_msg = getattr(event, "error", "Unknown Error")
            self._handle_event(
                "memory_save_failed",
                "Memory Save Failed",
                {"error.message": str(error_msg)},
            )

        @crewai_event_bus.on(MemoryRetrievalStartedEvent)
        def on_memory_retrieval_started(source, event):
            self._handle_event(
                "memory_retrieval_started", "Memory Retrieval Started", {}
            )

        @crewai_event_bus.on(MemoryRetrievalCompletedEvent)
        def on_memory_retrieval_completed(source, event):
            self._handle_event(
                "memory_retrieval_completed", "Memory Retrieval Completed", {}
            )

        @crewai_event_bus.on(MemoryQueryStartedEvent)
        def on_memory_query_started(source, event):
            self._handle_event("memory_query_started", "Memory Query Started", {})

        @crewai_event_bus.on(MemoryQueryCompletedEvent)
        def on_memory_query_completed(source, event):
            self._handle_event("memory_query_completed", "Memory Query Completed", {})

        @crewai_event_bus.on(MemoryQueryFailedEvent)
        def on_memory_query_failed(source, event):
            error_msg = getattr(event, "error", "Unknown Error")
            self._handle_event(
                "memory_query_failed",
                "Memory Query Failed",
                {"error.message": str(error_msg)},
            )

        # Knowledge Events
        @crewai_event_bus.on(KnowledgeQueryStartedEvent)
        def on_knowledge_query_started(source, event):
            self._handle_event("knowledge_query_started", "Knowledge Query Started", {})

        @crewai_event_bus.on(KnowledgeQueryCompletedEvent)
        def on_knowledge_query_completed(source, event):
            self._handle_event(
                "knowledge_query_completed", "Knowledge Query Completed", {}
            )

        @crewai_event_bus.on(KnowledgeQueryFailedEvent)
        def on_knowledge_query_failed(source, event):
            error_msg = getattr(event, "error", "Unknown Error")
            self._handle_event(
                "knowledge_query_failed",
                "Knowledge Query Failed",
                {"error.message": str(error_msg)},
            )

        @crewai_event_bus.on(KnowledgeRetrievalStartedEvent)
        def on_knowledge_retrieval_started(source, event):
            self._handle_event(
                "knowledge_retrieval_started", "Knowledge Retrieval Started", {}
            )

        @crewai_event_bus.on(KnowledgeRetrievalCompletedEvent)
        def on_knowledge_retrieval_completed(source, event):
            self._handle_event(
                "knowledge_retrieval_completed", "Knowledge Retrieval Completed", {}
            )

        # Agent Reasoning Events
        @crewai_event_bus.on(AgentReasoningStartedEvent)
        def on_reasoning_started(source, event):
            agent_role = getattr(source, "role", "Unknown Agent")
            self._handle_event(
                "agent_reasoning_started",
                f"Agent Reasoning: {agent_role}",
                {"agent.role": agent_role},
            )

        @crewai_event_bus.on(AgentReasoningCompletedEvent)
        def on_reasoning_completed(source, event):
            agent_role = getattr(source, "role", "Unknown Agent")
            self._handle_event(
                "agent_reasoning_completed",
                f"Agent Reasoning Completed: {agent_role}",
                {"agent.role": agent_role},
            )

        @crewai_event_bus.on(AgentReasoningFailedEvent)
        def on_reasoning_failed(source, event):
            agent_role = getattr(source, "role", "Unknown Agent")
            error_msg = getattr(event, "error", "Unknown Error")
            self._handle_event(
                "agent_reasoning_failed",
                f"Agent Reasoning Failed: {agent_role}",
                {"agent.role": agent_role, "error.message": str(error_msg)},
            )

        # Agent Evaluation Events
        @crewai_event_bus.on(AgentEvaluationStartedEvent)
        def on_evaluation_started(source, event):
            agent_role = getattr(source, "role", "Unknown Agent")
            self._handle_event(
                "agent_evaluation_started",
                f"Agent Evaluation: {agent_role}",
                {"agent.role": agent_role},
            )

        @crewai_event_bus.on(AgentEvaluationCompletedEvent)
        def on_evaluation_completed(source, event):
            agent_role = getattr(source, "role", "Unknown Agent")
            self._handle_event(
                "agent_evaluation_completed",
                f"Agent Evaluation Completed: {agent_role}",
                {"agent.role": agent_role},
            )

        @crewai_event_bus.on(AgentEvaluationFailedEvent)
        def on_evaluation_failed(source, event):
            agent_role = getattr(source, "role", "Unknown Agent")
            error_msg = getattr(event, "error", "Unknown Error")
            self._handle_event(
                "agent_evaluation_failed",
                f"Agent Evaluation Failed: {agent_role}",
                {"agent.role": agent_role, "error.message": str(error_msg)},
            )

        # Lite Agent Events
        @crewai_event_bus.on(LiteAgentExecutionStartedEvent)
        def on_lite_agent_started(source, event):
            agent_role = getattr(source, "role", "Unknown Agent")
            self._handle_event(
                "lite_agent_execution_started",
                f"Lite Agent: {agent_role}",
                {"agent.role": agent_role},
            )

        @crewai_event_bus.on(LiteAgentExecutionCompletedEvent)
        def on_lite_agent_completed(source, event):
            agent_role = getattr(source, "role", "Unknown Agent")
            self._handle_event(
                "lite_agent_execution_completed",
                f"Lite Agent Completed: {agent_role}",
                {"agent.role": agent_role},
            )

        @crewai_event_bus.on(LiteAgentExecutionErrorEvent)
        def on_lite_agent_error(source, event):
            agent_role = getattr(source, "role", "Unknown Agent")
            error_msg = getattr(event, "error", "Unknown Error")
            self._handle_event(
                "lite_agent_execution_error",
                f"Lite Agent Error: {agent_role}",
                {"agent.role": agent_role, "error.message": str(error_msg)},
            )

        # LLM Guardrail Events
        @crewai_event_bus.on(LLMGuardrailStartedEvent)
        def on_guardrail_started(source, event):
            self._handle_event("llm_guardrail_started", "LLM Guardrail Started", {})

        @crewai_event_bus.on(LLMGuardrailCompletedEvent)
        def on_guardrail_completed(source, event):
            self._handle_event("llm_guardrail_completed", "LLM Guardrail Completed", {})

        # Agent Logging Events
        @crewai_event_bus.on(AgentLogsStartedEvent)
        def on_agent_logs_started(source, event):
            agent_role = getattr(source, "role", "Unknown Agent")
            self._handle_event(
                "agent_logs_started",
                f"Agent Logs: {agent_role}",
                {"agent.role": agent_role},
            )

        @crewai_event_bus.on(AgentLogsExecutionEvent)
        def on_agent_logs_execution(source, event):
            agent_role = getattr(source, "role", "Unknown Agent")
            self._handle_event(
                "agent_logs_execution",
                f"Agent Logs Execution: {agent_role}",
                {"agent.role": agent_role},
            )

        # Task Failure Events
        @crewai_event_bus.on(TaskFailedEvent)
        def on_task_failed(source, event):
            task_description = getattr(source, "description", "Unknown Task")
            error_msg = getattr(event, "error", "Unknown Error")
            task_name = (
                task_description[:50] + "..."
                if len(task_description) > 50
                else task_description
            )
            self._handle_event(
                "task_failed",
                f"Task Failed: {task_name}",
                {"task.description": task_description, "error.message": str(error_msg)},
            )

        # Method Execution Failure Events
        @crewai_event_bus.on(MethodExecutionFailedEvent)
        def on_method_failed(source, event):
            method_name = getattr(event, "method_name", "Unknown Method")
            error_msg = getattr(event, "error", "Unknown Error")
            self._handle_event(
                "method_execution_failed",
                f"Method Failed: {method_name}",
                {"method.name": method_name, "error.message": str(error_msg)},
            )

        # Crew Failure Events
        @crewai_event_bus.on(CrewKickoffFailedEvent)
        def on_crew_failed(source, event):
            crew_name = getattr(source, "name", "Unknown Crew")
            error_msg = getattr(event, "error", "Unknown Error")
            self._handle_event(
                "crew_kickoff_failed",
                f"Crew Failed: {crew_name}",
                {"crew.name": crew_name, "error.message": str(error_msg)},
            )

    def _handle_event(
        self,
        event_type: str,
        span_name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """Creates a span for an event using the stored flow context."""
        span_context = self.flow_context if self.flow_context else None

        with self.tracer.start_as_current_span(span_name, context=span_context) as span:
            span.set_attribute("event.type", event_type)

            # Add any additional event-specific attributes
            if attributes:
                for key, value in attributes.items():
                    if value:  # Only set non-empty values
                        span.set_attribute(key, value)

            print(f"[{event_type.upper()}] {span_name}")
