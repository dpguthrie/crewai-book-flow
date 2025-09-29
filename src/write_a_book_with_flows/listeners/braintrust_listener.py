from typing import Any, Dict, Optional

from crewai.events import (
    AgentExecutionCompletedEvent,
    AgentExecutionStartedEvent,
    CrewKickoffCompletedEvent,
    CrewKickoffStartedEvent,
    FlowFinishedEvent,
    FlowStartedEvent,
    MethodExecutionFinishedEvent,
    MethodExecutionStartedEvent,
    TaskCompletedEvent,
    TaskStartedEvent,
)
from crewai.events.base_event_listener import BaseEventListener
from crewai.events.event_bus import CrewAIEventsBus
from opentelemetry import context, trace

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
            # Attach this context to make it current
            context.attach(self.flow_context)

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
