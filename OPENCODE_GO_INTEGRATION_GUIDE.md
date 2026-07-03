# OpenCode Go API Integration Guide

## Overview

The DocTel system now uses **OpenCode Go API** (formerly Zen API) for cloud-based model inference. This provides access to multiple AI models including DeepSeek, GPT, Claude, and more.

## Configuration

### Environment Variables

Your `.env` file should be configured as follows:

```env
# OpenCode Go API Configuration
OPENCODE_GO_API_KEY=sk-MO0RQnYzWjNbL1krBZ64piUmM2vaQtPAtO3hpFJzEj9gvYskGeoHHdXJ5JbUpvfD
OPENCODE_GO_BASE_URL=https://opencode.ai/go/v1

# DeepSeek API (uses OpenCode Go as proxy)
DEEPSEEK_API_KEY=sk-MO0RQnYzWjNbL1krBZ64piUmM2vaQtPAtO3hpFJzEj9gvYskGeoHHdXJ5JbUpvfD
DEEPSEEK_MODEL=deepseek-v4-flash-free
DEEPSEEK_BASE_URL=https://opencode.ai/go/v1
```

## Available Models

### Free Tier Models
- **DeepSeek V4 Flash (Free)** - `go/deepseek-v4-flash-free`
  - Ultra-fast, suitable for most queries
  - No cost, rate-limited

### Budget Tier Models
- **GPT 4o Mini** - `go/gpt-4o-mini`
- **Claude 3.5 Haiku** - `go/claude-3-5-haiku`
- **Gemini 2 Flash** - `go/gemini-2-flash`
- **Qwen 2 72B** - `go/qwen2-72b`

### Mid Tier Models
- **GPT 4 Turbo** - `go/gpt-4-turbo`
- **Claude 3.5 Sonnet** - `go/claude-3-5-sonnet`
- **Gemini 2 Pro** - `go/gemini-2-pro`
- **DeepSeek V3** - `go/deepseek-v3`

### Premium Tier Models
- **Claude Opus 4.1** - `go/claude-opus-4-1`
- **GPT 4o** - `go/gpt-4o`

## API Endpoints

### 1. Get Available Models
```
GET /api/models/available
```

Returns list of installed local models + available OpenCode Go models.

**Response:**
```json
{
  "installed": [
    "ollama-model-1",
    "ollama-model-2",
    "go/deepseek-v4-flash-free",
    ...
  ],
  "available": [...],
  "default_model": "llama3.2:8b",
  "models": [
    {
      "name": "go/deepseek-v4-flash-free",
      "size": 0,
      "size_human": "Cloud",
      "family": "deepseek",
      "parameter_size": "DeepSeek V4 Flash (Free)",
      "quantization_level": "free",
      "ready": true
    },
    ...
  ]
}
```

### 2. Chat with Any Model
```
POST /api/ask
Content-Type: application/json

{
  "question": "What is machine learning?",
  "model": "go/deepseek-v4-flash-free",
  "scope": "all",
  "session_id": "optional-session-uuid"
}
```

**Supports:**
- Local Ollama models: `llama3.2:8b`, `qwen3:7b`, etc.
- OpenCode models: `go/deepseek-v4-flash-free`, `go/gpt-4o-mini`, etc.
- DeepSeek API: Auto-routing to DeepSeek models

**Response:**
```json
{
  "answer": "Machine learning is a subset of artificial intelligence...",
  "citations": [...],
  "cross_references": [...],
  "used_model": "go/deepseek-v4-flash-free",
  "session_id": "session-uuid"
}
```

### 3. Stream Response (WebSocket/SSE)
```
POST /api/ask/stream
Content-Type: application/json

{
  "question": "Write a poem about AI",
  "model": "go/claude-3-5-sonnet"
}
```

Streams chunks of the response for real-time display.

## Model Selection Logic

The system automatically selects the best model based on your request:

1. **Explicit Selection**: If you specify a `model` in your request, that model is used
2. **Session History**: If no model specified, the last used model in the session is used
3. **System Default**: Falls back to configured default model
4. **Automatic Fallback**: If primary model fails:
   - Tries OpenCode models if not already using them
   - Falls back to Gemini if configured
   - Finally tries local Ollama models

## Troubleshooting

### 422 Unprocessable Entity Error

**Cause**: Invalid model name or request format

**Solution**:
1. Verify the model ID is correct (e.g., `go/deepseek-v4-flash-free`, not `deepseek-v4-flash-free`)
2. Ensure your API key is valid
3. Check the request payload is valid JSON
4. Verify the model is available for your account tier

**Example Fix**:
```json
// ❌ Wrong
{"model": "deepseek-v4-flash-free"}

// ✅ Correct
{"model": "go/deepseek-v4-flash-free"}
```

### API Key Errors

- **401 Unauthorized**: Invalid API key - check your `OPENCODE_GO_API_KEY`
- **402 Payment Required**: Account balance depleted
- **429 Too Many Requests**: Rate limit exceeded

### Model Not Found

- **404**: Model not available on the API
- **Solution**: Use `/api/models/available` to see which models are available

### Streaming Issues

If streaming responses don't work:

1. Ensure the model supports streaming (all listed models do)
2. Check your connection is stable
3. Verify the model name is correct
4. Try a non-streaming request first to verify the model works

## Local Ollama Models

The system also supports local Ollama models alongside OpenCode models:

### Running Ollama

```bash
# Start Ollama server (if not already running)
ollama serve

# In another terminal, list available models
ollama list

# Pull a model if needed
ollama pull llama3.2:8b
ollama pull qwen3:7b
```

### Using Local Models

```json
{
  "question": "What is quantum computing?",
  "model": "llama3.2:8b"  // Uses local model
}
```

### Training Local Models

You can fine-tune local Ollama models using the training pipeline:

```bash
# Check trainer configuration
cat app/services/trainer_service.py

# Models available for training
TRAINING_MODELS=llama3.2-3b,llama3.2-8b,qwen2.5-7b
```

## Model Comparison

| Model | Speed | Cost | Quality | Best For |
|-------|-------|------|---------|----------|
| DeepSeek V4 Flash | Very Fast | Free | Good | Quick queries, general use |
| GPT 4o Mini | Fast | Low | Very Good | Balanced performance |
| Claude Haiku | Very Fast | Low | Good | Speed-focused |
| GPT 4 Turbo | Moderate | Medium | Excellent | Complex reasoning |
| Claude Sonnet | Moderate | Medium | Excellent | Quality outputs |
| Claude Opus | Slow | High | Exceptional | Best quality |

## Integration Architecture

```
┌─────────────────────────┐
│   Frontend/Mobile App   │
└────────────┬────────────┘
             │ GET /api/models/available
             │ POST /api/ask
             ▼
┌─────────────────────────┐
│   FastAPI Backend       │
│  (app/main.py)          │
└────────────┬────────────┘
             │
      ┌──────┴──────┬──────────┬──────────┐
      ▼             ▼          ▼          ▼
┌──────────┐  ┌──────────┐ ┌────────┐ ┌────────┐
│ Ollama   │  │ DeepSeek │ │ Gemini │ │OpenCode│
│ (Local)  │  │ (API)    │ │ (API)  │ │  Go    │
└──────────┘  └──────────┘ └────────┘ └────────┘
```

## Example Usage in Frontend

```typescript
// Get available models
const modelsResponse = await fetch('/api/models/available');
const models = await modelsResponse.json();

// Select a model from UI dropdown
const selectedModel = 'go/deepseek-v4-flash-free';

// Send question
const response = await fetch('/api/ask', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    question: 'What is AI?',
    model: selectedModel,
    scope: 'all'
  })
});

const result = await response.json();
console.log('Answer:', result.answer);
console.log('Used Model:', result.used_model);
```

## API Key Management

- Get your API key at: https://opencode.ai/go
- Keep your key secure (in `.env`, never commit to git)
- Rotate keys regularly
- Monitor API usage on dashboard: https://opencode.ai/dashboard

## Performance Tips

1. **For Speed**: Use `go/deepseek-v4-flash-free` or `go/gemini-2-flash`
2. **For Quality**: Use `go/claude-3-5-sonnet` or `go/gpt-4-turbo`
3. **For Cost**: Use free tier models like `go/deepseek-v4-flash-free`
4. **Batch Requests**: Group multiple queries to reduce overhead
5. **Cache Results**: Store frequently asked questions locally

## Support & Documentation

- OpenCode Go Docs: https://opencode.ai/docs/go
- API Status: https://status.opencode.ai
- Community Discord: https://discord.gg/opencode
