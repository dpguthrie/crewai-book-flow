# Braintrust Instrumentor for CrewAI

OpenTelemetry instrumentation for CrewAI that creates properly nested traces in Braintrust.

## Features

- **Automatic trace hierarchy**: Maintains proper parent-child relationships between Flow → Crew → Task → Tool
- **Detailed span names**: Uses actual names (e.g., "Flow Execution: BookFlow", "Crew Execution: OutlineCrew")
- **No manual context management**: Uses method wrapping for automatic context propagation
- **Extensible**: Works with other OpenTelemetry instrumentors

## Installation

```bash
pip install braintrust wrapt opentelemetry-sdk
```

## Quick Start

```python
from write_a_book_with_flows.instrumentation import BraintrustInstrumentor

# Initialize and instrument
instrumentor = BraintrustInstrumentor()
instrumentor.instrument()

# Your CrewAI code
flow = MyFlow()
flow.kickoff()
```

## Usage with Other Instrumentors

```python
from write_a_book_with_flows.instrumentation import BraintrustInstrumentor
from opentelemetry.instrumentation.openai import OpenAIInstrumentor

# Set up Braintrust + CrewAI
instrumentor = BraintrustInstrumentor()
instrumentor.instrument()

# Add OpenAI instrumentation (shares the same tracer provider)
OpenAIInstrumentor().instrument(tracer_provider=instrumentor.tracer_provider)
```

## Environment Variables

```bash
# Required: Braintrust API key
BRAINTRUST_API_KEY="your-api-key"

# Optional: Braintrust project
BRAINTRUST_PARENT="project_name:your-project"

# Recommended: Disable CrewAI's built-in telemetry to avoid duplicate traces
CREWAI_DISABLE_TELEMETRY="true"
```

## What Gets Instrumented

The instrumentor wraps these CrewAI methods:

- `Flow.kickoff_async` → Root flow execution span
- `Crew.kickoff` → Crew execution span  
- `Task._execute_core` → Task execution span
- `ToolUsage._use` → Tool usage span (optional)

## Trace Structure

```
Flow Execution: BookFlow
├── Crew Execution: OutlineCrew
│   ├── Task Execution: Research the topic...
│   ├── Task Execution: Research the topic...
│   │   ├── Tool: SerperDevTool
│   │   └── LLM Call: gpt-4o (if OpenAI instrumented)
│   └── Task Execution: Create outline...
└── Crew Execution: WriteChapterCrew
    └── ...
```

## Advanced Usage

### Custom TracerProvider

```python
from opentelemetry.sdk.trace import TracerProvider
from write_a_book_with_flows.instrumentation import BraintrustInstrumentor

# Use your own provider
provider = TracerProvider()
# ... configure provider ...

instrumentor = BraintrustInstrumentor(tracer_provider=provider)
instrumentor.instrument()
```

## How It Works

Unlike event-based listeners, this instrumentor uses **method wrapping** to intercept
function calls and create spans. This ensures:

1. **Automatic hierarchy**: Each wrapped method creates a span in the current OpenTelemetry context
2. **No orphaned spans**: All operations happen within the execution scope
3. **Proper async support**: Handles both sync and async methods correctly

The instrumentor uses `wrapt.wrap_function_wrapper` to intercept methods without
modifying CrewAI's source code.