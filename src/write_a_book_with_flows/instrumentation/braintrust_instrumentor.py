"""Braintrust OpenTelemetry Instrumentor for CrewAI.

This module provides instrumentation for CrewAI using method wrapping to maintain
proper trace hierarchy. It wraps key methods in Flow, Crew, and Task execution
to create properly nested OpenTelemetry spans.

Example usage:
    ```python
    from braintrust_instrumentor import BraintrustInstrumentor
    from opentelemetry.instrumentation.openai import OpenAIInstrumentor

    # Set up Braintrust + CrewAI instrumentation
    instrumentor = BraintrustInstrumentor()
    instrumentor.instrument()

    # Optionally add other instrumentors
    OpenAIInstrumentor().instrument()
    ```
"""

import inspect
from typing import Any, Callable, Mapping, Optional, Tuple

from braintrust.otel import BraintrustSpanProcessor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Status, StatusCode
from wrapt import wrap_function_wrapper


class BraintrustInstrumentor:
    """Instrumentor for CrewAI that creates properly nested traces in Braintrust.

    This instrumentor sets up OpenTelemetry with Braintrust's span processor and
    wraps key CrewAI methods to create properly nested trace hierarchies.

    Args:
        tracer_provider: Optional TracerProvider. If not provided, creates a new one.

    Example:
        ```python
        instrumentor = BraintrustInstrumentor()
        instrumentor.instrument()

        # Your CrewAI code here
        flow = MyFlow()
        flow.kickoff()
        ```
    """

    def __init__(self, tracer_provider: Optional[TracerProvider] = None):
        """Initialize the instrumentor and set up tracing.

        Args:
            tracer_provider: Optional TracerProvider to use. If not provided,
                           creates a new one with BraintrustSpanProcessor.
        """
        # Set up or use provided tracer provider
        if tracer_provider is None:
            current_provider = trace.get_tracer_provider()
            if isinstance(current_provider, TracerProvider):
                tracer_provider = current_provider
            else:
                tracer_provider = TracerProvider()
                trace.set_tracer_provider(tracer_provider)

            # Add Braintrust span processor
            tracer_provider.add_span_processor(BraintrustSpanProcessor())  # type: ignore

        self.tracer_provider = tracer_provider
        self.tracer = trace.get_tracer(__name__)
        self._instrumented = False
        self._original_methods = {}

    def instrument(self):
        """Instrument CrewAI by wrapping key execution methods."""
        if self._instrumented:
            return

        # Wrap Flow.kickoff_async (the actual entry point)
        wrap_function_wrapper(
            module="crewai.flow.flow",
            name="Flow.kickoff_async",
            wrapper=self._wrap_flow_kickoff,
        )

        # Wrap Crew.__init__ to track crew creation
        wrap_function_wrapper(
            module="crewai.crew",
            name="Crew.__init__",
            wrapper=self._wrap_crew_init,
        )

        # Wrap Crew.kickoff for crew execution
        wrap_function_wrapper(
            module="crewai.crew", name="Crew.kickoff", wrapper=self._wrap_crew_kickoff
        )

        # Wrap Task.__init__ to track task creation
        try:
            wrap_function_wrapper(
                module="crewai.task",
                name="Task.__init__",
                wrapper=self._wrap_task_init,
            )
        except Exception:
            pass

        # Wrap Task._execute_core for task execution
        wrap_function_wrapper(
            module="crewai.task",
            name="Task._execute_core",
            wrapper=self._wrap_task_execute,
        )

        # Wrap ToolUsage._use for tool-level spans
        try:
            wrap_function_wrapper(
                module="crewai.tools.tool_usage",
                name="ToolUsage._use",
                wrapper=self._wrap_tool_use,
            )
        except Exception:
            # Tool usage wrapping is optional
            pass

        self._instrumented = True

    def _wrap_flow_kickoff(
        self,
        wrapped: Callable[..., Any],
        instance: Any,
        args: Tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> Any:
        """Wrap Flow.kickoff_async to create the root span."""

        flow_name = instance.name or instance.__class__.__name__
        span_name = f"Flow Execution: {flow_name}"

        # Handle async methods
        if inspect.iscoroutinefunction(wrapped):

            async def async_wrapper():
                with self.tracer.start_as_current_span(span_name) as span:
                    span.set_attribute("flow.name", flow_name)
                    span.set_attribute("flow.class", instance.__class__.__name__)
                    span.set_attribute("event.type", "flow_execution")

                    # Add flow ID if available
                    if hasattr(instance, "flow_id"):
                        span.set_attribute("flow.id", str(instance.flow_id))

                    try:
                        result = await wrapped(*args, **kwargs)
                        span.set_status(StatusCode.OK)
                        return result
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        raise

            return async_wrapper()

        # Synchronous version
        with self.tracer.start_as_current_span(span_name) as span:
            span.set_attribute("flow.name", flow_name)
            span.set_attribute("flow.class", instance.__class__.__name__)
            span.set_attribute("event.type", "flow_execution")

            # Add flow ID if available
            if hasattr(instance, "flow_id"):
                span.set_attribute("flow.id", str(instance.flow_id))

            try:
                result = wrapped(*args, **kwargs)
                span.set_status(StatusCode.OK)
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    def _wrap_crew_init(
        self,
        wrapped: Callable[..., Any],
        instance: Any,
        args: Tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> Any:
        """Wrap Crew.__init__ to track crew creation."""
        # Call the original __init__ first to ensure the instance is initialized
        result = wrapped(*args, **kwargs)

        # Note: We skip suppression check to allow child instrumentation to work

        # Get crew name from instance
        crew_name = getattr(instance, "name", "Crew")

        span_name = f"Crew Created: {crew_name}"

        with self.tracer.start_as_current_span(span_name) as span:
            span.set_attribute("crew.name", crew_name)
            span.set_attribute("event.type", "crew_created")

            if hasattr(instance, "id"):
                span.set_attribute("crew.id", str(instance.id))

            if hasattr(instance, "process"):
                span.set_attribute("crew.process", str(instance.process))

            if hasattr(instance, "tasks"):
                span.set_attribute("crew.task_count", len(instance.tasks))

        return result

    def _wrap_crew_kickoff(
        self,
        wrapped: Callable[..., Any],
        instance: Any,
        args: Tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> Any:
        """Wrap Crew.kickoff to create crew-level spans."""
        # Note: We skip suppression check to allow child instrumentation (OpenAI) to work

        # Try to get crew name from various sources
        crew_name = (
            getattr(instance, "name", None)
            or getattr(instance, "_crew_name", None)
            or instance.__class__.__name__
        )
        span_name = f"Crew Execution: {crew_name}"

        with self.tracer.start_as_current_span(span_name) as span:
            span.set_attribute("crew.name", crew_name)
            span.set_attribute("event.type", "crew_execution")

            # Add crew details
            if hasattr(instance, "id"):
                span.set_attribute("crew.id", str(instance.id))

            if hasattr(instance, "process"):
                span.set_attribute("crew.process", str(instance.process))

            # Add task count
            if hasattr(instance, "tasks"):
                span.set_attribute("crew.task_count", len(instance.tasks))

            try:
                result = wrapped(*args, **kwargs)
                span.set_status(StatusCode.OK)
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    def _wrap_task_init(
        self,
        wrapped: Callable[..., Any],
        instance: Any,
        args: Tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> Any:
        """Wrap Task.__init__ to track task creation."""
        # Call the original __init__ first
        result = wrapped(*args, **kwargs)

        # Note: We skip suppression check to allow child instrumentation to work

        # Get task name/description
        task_description = getattr(instance, "description", "Unknown Task")
        task_name = (
            task_description[:50] + "..."
            if len(task_description) > 50
            else task_description
        )
        span_name = f"Task Created: {task_name}"

        with self.tracer.start_as_current_span(span_name) as span:
            span.set_attribute("task.description", task_description)
            span.set_attribute("event.type", "task_created")

            if hasattr(instance, "id"):
                span.set_attribute("task.id", str(instance.id))

            if hasattr(instance, "expected_output"):
                span.set_attribute("task.expected_output", instance.expected_output)

        return result

    def _wrap_task_execute(
        self,
        wrapped: Callable[..., Any],
        instance: Any,
        args: Tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> Any:
        """Wrap Task._execute_core to create task-level spans."""
        # Note: We skip suppression check to allow child instrumentation (OpenAI) to work

        # Get task description for span name
        task_description = getattr(instance, "description", "Unknown Task")
        task_name = (
            task_description[:50] + "..."
            if len(task_description) > 50
            else task_description
        )
        span_name = f"Task Execution: {task_name}"

        # Get agent from args or kwargs
        agent = args[0] if args else kwargs.get("agent")
        agent_role = getattr(agent, "role", "Unknown Agent") if agent else "No Agent"

        with self.tracer.start_as_current_span(span_name) as span:
            span.set_attribute("task.description", task_description)
            span.set_attribute("event.type", "task_execution")

            if hasattr(instance, "id"):
                span.set_attribute("task.id", str(instance.id))

            if hasattr(instance, "expected_output"):
                span.set_attribute("task.expected_output", instance.expected_output)

            # Add agent information
            span.set_attribute("agent.role", agent_role)

            try:
                result = wrapped(*args, **kwargs)
                span.set_status(StatusCode.OK)
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    def _wrap_tool_use(
        self,
        wrapped: Callable[..., Any],
        instance: Any,
        args: Tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> Any:
        """Wrap ToolUsage._use to create tool-level spans."""
        # Note: We skip suppression check to allow child instrumentation to work

        # Get tool name from kwargs
        tool = kwargs.get("tool")
        tool_name = getattr(tool, "name", "Unknown Tool") if tool else "Unknown Tool"
        span_name = f"Tool: {tool_name}"

        with self.tracer.start_as_current_span(span_name) as span:
            span.set_attribute("tool.name", tool_name)
            span.set_attribute("event.type", "tool_usage")

            try:
                result = wrapped(*args, **kwargs)
                span.set_status(StatusCode.OK)
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise


# Global instrumentor instance
_instrumentor = None


def get_instrumentor() -> BraintrustInstrumentor:
    """Get or create the global instrumentor instance."""
    global _instrumentor
    if _instrumentor is None:
        _instrumentor = BraintrustInstrumentor()
    return _instrumentor
