# Together AI Function Calling - Agent Reference

## Overview

Function calling (also called *tool calling*) enables LLMs to respond with structured function names and arguments that you can execute in your application. This allows models to interact with external systems, retrieve real-time data, and power agentic AI workflows.

## Core Concepts

- **Tools Parameter**: Pass function descriptions to the `tools` parameter
- **Tool Calls**: Models return `tool_calls` when they determine a function should be used
- **Function Execution**: You execute these functions and optionally pass results back to the model
- **Streaming Support**: Function calling works with streaming responses via `delta.tool_calls`

## Basic Implementation Pattern

### 1. Define Function Schema
```json
{
  "type": "function",
  "function": {
    "name": "function_name",
    "description": "Function description",
    "parameters": {
      "type": "object",
      "properties": {
        "param_name": {
          "type": "string",
          "description": "Parameter description"
        }
      },
      "required": ["param_name"]
    }
  }
}
```

### 2. Make API Call with Tools
```python
response = client.chat.completions.create(
    model="Qwen/Qwen2.5-7B-Instruct-Turbo",
    messages=[...],
    tools=[function_schema]
)
```

### 3. Process Tool Calls
```python
tool_calls = response.choices[0].message.tool_calls
for tool_call in tool_calls:
    function_name = tool_call.function.name
    function_args = json.loads(tool_call.function.arguments)
    # Execute function and get results
```

### 4. Return Results to Model
```python
messages.append({
    "tool_call_id": tool_call.id,
    "role": "tool", 
    "name": function_name,
    "content": function_response
})
```

## Supported Models

### Text Models with Function Calling
- `openai/gpt-oss-120b`
- `openai/gpt-oss-20b`
- `moonshotai/Kimi-K2-Thinking`
- `moonshotai/Kimi-K2-Instruct-0905`
- `zai-org/GLM-4.5-Air-FP8`
- `Qwen/Qwen3-Next-80B-A3B-Instruct`
- `Qwen/Qwen3-Next-80B-A3B-Thinking`
- `Qwen/Qwen3-235B-A22B-Thinking-2507`
- `Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8`
- `Qwen/Qwen3-235B-A22B-fp8-tput`
- `deepseek-ai/DeepSeek-R1`
- `deepseek-ai/DeepSeek-V3`
- `meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8`
- `meta-llama/Llama-4-Scout-17B-16E-Instruct`
- `meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo`
- `meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo`
- `meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo`
- `meta-llama/Llama-3.3-70B-Instruct-Turbo`
- `meta-llama/Llama-3.2-3B-Instruct-Turbo`
- `Qwen/Qwen2.5-7B-Instruct-Turbo`
- `Qwen/Qwen2.5-72B-Instruct-Turbo`
- `mistralai/Mistral-Small-24B-Instruct-2501`
- `arcee-ai/virtuoso-large`

### Vision Models with Function Calling
- `Qwen/Qwen3-VL-32B-Instruct`

## Function Calling Patterns

### 1. Simple Function Calling
- **Description**: One function, one call
- **Use Cases**: Basic utilities, simple queries
- **Example**: Single weather function for one location

### 2. Multiple Function Calling
- **Description**: Choose from many functions
- **Use Cases**: Many tools, LLM has to choose
- **Example**: Weather vs stock price functions

### 3. Parallel Function Calling
- **Description**: Same function, multiple calls
- **Use Cases**: Complex prompts, multiple tools called
- **Example**: Weather for multiple cities

### 4. Parallel Multiple Function Calling
- **Description**: Multiple functions, parallel calls
- **Use Cases**: Complex single requests with many tools
- **Example**: Stock prices AND weather for multiple cities

### 5. Multi-Step Function Calling
- **Description**: Sequential function calling in one turn
- **Use Cases**: Data processing workflows
- **Example**: Get weather → Process results → Generate response

### 6. Multi-Turn Function Calling
- **Description**: Conversational context + functions
- **Use Cases**: AI Agents with humans in the loop
- **Example**: Travel planning across multiple conversation turns

## Tool Choice Options

The `tool_choice` parameter controls function usage:

### String Values
- `"auto"` (default): Model decides whether to call a function or generate text
- `"none"`: Model will never call functions, only generates text  
- `"required"`: Model must call at least one function

### Object Value
```json
{
  "type": "function",
  "function": {"name": "specific_function_name"}
}
```
- Forces model to use a specific function

## Streaming Function Calls

Function calling works with streaming:

```python
stream = client.chat.completions.create(
    model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    messages=[...],
    tools=tools,
    stream=True,
)

for chunk in stream:
    delta = chunk.choices[0].delta
    tool_calls = getattr(delta, "tool_calls", [])
    # Process streaming tool calls
```

Streaming returns tool calls incrementally:
```json
// delta 1
[
  {
    "index": 0,
    "id": "call_fwbx4e156wigo9ayq7tszngh",
    "type": "function",
    "function": {"name": "get_weather", "arguments": ""}
  }
]

// delta 2  
[
  {
    "index": 0,
    "function": {"arguments": "{\"location\":\"New York City, USA\"}"}
  }
]
```

## Vision Language Function Calling

Vision models can combine image understanding with tool use:

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_stock_price",
            "description": "Get the current stock price for the given stock symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "The stock symbol, e.g. AAPL, GOOGL, TSLA"
                    }
                },
                "required": ["symbol"]
            }
        }
    }
]

response = client.chat.completions.create(
    model="Qwen/Qwen3-VL-32B-Instruct",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What is the stock price of the company from the image"},
                {"type": "image_url", "image_url": {"url": "company_logo.jpg"}}
            ]
        }
    ],
    tools=tools,
)
```

## Best Practices

### 1. Function Descriptions
- Write clear, specific descriptions
- Include examples in parameter descriptions
- Specify required vs optional parameters

### 2. Error Handling
- Validate function arguments before execution
- Handle function execution errors gracefully
- Provide meaningful error messages back to the model

### 3. Context Management
- Maintain conversation history across turns
- Include function results in subsequent messages
- Use system messages to guide behavior

### 4. Performance Optimization
- Use parallel function calling for multiple similar operations
- Implement proper function result caching
- Consider streaming for real-time responses

### 5. Security Considerations
- Validate and sanitize all function inputs
- Implement proper authentication for external APIs
- Log function calls for debugging and monitoring

## Common Use Cases

### Data Retrieval
- Weather information
- Stock prices
- News headlines
- Database queries

### External System Integration
- Calendar management
- Email sending
- File operations
- API integrations

### Agent Workflows
- Travel planning
- Research assistance
- Code generation and execution
- Multi-step problem solving

## API Endpoints

### Chat Completions with Tools
```
POST https://api.together.xyz/v1/chat/completions
```

### Required Headers
```
Authorization: Bearer $TOGETHER_API_KEY
Content-Type: application/json
```

## Error Handling

Common issues and solutions:

1. **Invalid Function Schema**: Ensure JSON schema is valid
2. **Function Execution Errors**: Wrap function calls in try-catch blocks
3. **Model Refusal**: Some models may refuse certain function calls
4. **Rate Limiting**: Implement retry logic with exponential backoff

## Resources

- [Together AI Documentation](https://docs.together.ai/docs/function-calling)
- [API Reference](https://docs.together.ai/reference)
- [Model Compatibility](https://docs.together.ai/docs/models)
- [Community Examples](https://github.com/togethercomputer/together-python)