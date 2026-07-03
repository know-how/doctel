# OpenCode Go Models - Quick Reference

## Model Selection in UI

When users select a model from the dropdown, they'll see:

```
Free Models
├─ DeepSeek V4 Flash (Free)          [go/deepseek-v4-flash-free]

Budget Models
├─ GPT 4o Mini                        [go/gpt-4o-mini]
├─ Claude 3.5 Haiku                   [go/claude-3-5-haiku]
├─ Gemini 2 Flash                     [go/gemini-2-flash]
└─ Qwen 2 72B                         [go/qwen2-72b]

Mid-Range Models
├─ GPT 4 Turbo                        [go/gpt-4-turbo]
├─ Claude 3.5 Sonnet                  [go/claude-3-5-sonnet]
├─ Gemini 2 Pro                       [go/gemini-2-pro]
└─ DeepSeek V3                        [go/deepseek-v3]

Premium Models
├─ Claude Opus 4.1                    [go/claude-opus-4-1]
└─ GPT 4o                             [go/gpt-4o]

Local Models (Ollama)
├─ llama3.2:8b                        [local]
├─ llama3.2:3b                        [local]
└─ qwen2.5:7b                         [local]
```

## HTTP Status Codes

### Success (200)
✓ Response received successfully
- Has `answer`, `citations`, `cross_references`, `used_model`

### Client Errors (4xx)

#### 400 Bad Request
- Missing `question` field
- Invalid `project_id` format
- Invalid model specified

**Response**:
```json
{
  "error": "invalid_generation_model",
  "model": "invalid-model-name"
}
```

**Fix**: Check model name format (should be `go/model-name`)

#### 403 Forbidden
- User doesn't have access to project
- Session belongs to another user

#### 404 Not Found
- Document not found
- Resource doesn't exist

### Server Errors (5xx)

#### 500 Internal Server Error
- 422 Validation: Model name or request format invalid
- Backend service failed

**Check**: Verify model ID format and API configuration

#### 503 Service Unavailable
- OpenCode Go API is not configured
- Required API key is missing

**Response**:
```json
{
  "error": "zen_not_configured",
  "message": "OPENCODE_GO_API_KEY is not set. Get one at https://opencode.ai/go..."
}
```

**Fix**: Add OPENCODE_GO_API_KEY to .env file

## API Request/Response Examples

### Example 1: Simple Chat with Free Model
```bash
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "question": "Explain quantum computing briefly",
    "model": "go/deepseek-v4-flash-free"
  }'
```

**Response**:
```json
{
  "answer": "Quantum computing uses quantum bits (qubits) to process information using quantum mechanics principles...",
  "citations": [],
  "cross_references": [],
  "used_model": "go/deepseek-v4-flash-free",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Example 2: Project-Scoped Chat with Premium Model
```bash
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "question": "Analyze the key findings in our recent report",
    "model": "go/claude-3-5-sonnet",
    "scope": "project",
    "project_id": 42
  }'
```

**Response**:
```json
{
  "answer": "Based on the document analysis, the key findings are...",
  "citations": [
    {
      "document_id": "doc123",
      "snippet": "Revenue increased by 25% year-over-year...",
      "page": 3
    }
  ],
  "cross_references": [
    {
      "filename": "Q4_Report.pdf",
      "reason": "Used as retrieval context"
    }
  ],
  "used_model": "go/claude-3-5-sonnet",
  "session_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

### Example 3: Streaming Response
```bash
curl -X POST http://localhost:8000/api/ask/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "question": "Write a technical overview of machine learning",
    "model": "go/claude-opus-4-1"
  }'
```

**Response** (Server-Sent Events):
```
data: {"chunk":"Machine","model":"go/claude-opus-4-1","session_id":"..."}

data: {"chunk":" learning","model":"go/claude-opus-4-1","session_id":"..."}

data: {"chunk":" is","model":"go/claude-opus-4-1","session_id":"..."}

data: {"chunk":" a..."}
...
data: [DONE]
```

## Model Characteristics

### Performance by Speed
1. **Fastest**: DeepSeek V4 Flash, Gemini 2 Flash, Claude Haiku
2. **Fast**: Claude Sonnet, GPT 4o Mini
3. **Moderate**: DeepSeek V3, Gemini 2 Pro, GPT 4 Turbo
4. **Slower**: Claude Opus 4.1, GPT 4o

### Performance by Quality
1. **Best**: Claude Opus 4.1, GPT 4o, Claude Sonnet
2. **Excellent**: GPT 4 Turbo, DeepSeek V3, Claude Haiku
3. **Very Good**: DeepSeek V4 Flash, GPT 4o Mini, Gemini 2 Pro
4. **Good**: Gemini 2 Flash, Qwen 2 72B

### Cost Tier
- **Free**: DeepSeek V4 Flash (rate limited)
- **Budget**: $0.08-$0.30 per 1M tokens
- **Mid**: $0.27-$3.50 per 1M tokens
- **Premium**: $5-$15 per 1M tokens

## Model Selection Guide

### I want speed 🚀
Use: `go/deepseek-v4-flash-free` or `go/gemini-2-flash`

### I want quality 🎯
Use: `go/claude-opus-4-1` or `go/gpt-4o`

### I want balance ⚖️
Use: `go/claude-3-5-sonnet` or `go/gpt-4-turbo`

### I want to save money 💰
Use: `go/deepseek-v4-flash-free` (free tier)

### I want to use local models 🏠
Use: `llama3.2:8b` or `qwen2.5:7b`

## Fallback Behavior

If the requested model fails, the system automatically tries:
1. Other OpenCode models (if not already tried)
2. Gemini API (if configured)
3. DeepSeek API (if configured)
4. Local Ollama models

**Result**: Users get an answer even if their preferred model is down

## Session Management

Each conversation has a `session_id`:
- First request: System generates new UUID
- Subsequent requests: Pass same `session_id` to continue conversation
- Model choice: Remembered in session, can be overridden per request

```bash
# First message
curl -X POST http://localhost:8000/api/ask \
  -d '{"question": "What is AI?", "model": "go/claude-3-5-sonnet"}'
# Returns: session_id: "abc123"

# Follow-up message
curl -X POST http://localhost:8000/api/ask \
  -d '{
    "question": "Tell me more",
    "session_id": "abc123"
    // Model remembered from previous request
  }'
```

## Troubleshooting Checklist

- [ ] Is OPENCODE_GO_API_KEY set in .env?
- [ ] Is the model name in correct format (go/model-name)?
- [ ] Does the model exist in the available models list?
- [ ] Is the API key valid and has balance?
- [ ] Is the question not empty?
- [ ] Is the user authenticated?
- [ ] Is the project_id valid (for project-scoped queries)?

## Local Development

### Enable verbose logging
```bash
# In .env
LOGLEVEL=DEBUG
```

### Test endpoint directly
```bash
python -c "
import asyncio
from app.services.opencode_zen_service import generate
print(asyncio.run(generate('Hi', model='go/deepseek-v4-flash-free')))
"
```

### Monitor API usage
View at: https://opencode.ai/dashboard/usage

## Limits & Quotas

- Max tokens per request: 2048
- Temperature: Fixed at 0.3 (deterministic)
- Rate limit: Per tier (check dashboard)
- Timeout: 45 seconds per request

## Future Enhancements

- [ ] Model comparison side-by-side
- [ ] Cost estimation before request
- [ ] Usage analytics dashboard
- [ ] Custom system prompts per model
- [ ] Model-specific parameters (temperature, top_p)
