# Gondola v2.3 - Setup Guide

## Quick Start (5 minutes)

### 1. Get Your API Keys

**Together AI (Required)**
- Sign up: https://api.together.xyz/settings/api-keys
- Create a new API key
- Copy it for later

**Venice AI (Optional)**
- Sign up: https://venice.ai/settings/api
- Get API key for Claude models

### 2. Install

```bash
# Clone the repo
git clone https://github.com/yourusername/gondola.git
cd gondola

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure

**Option A: Environment Variables (Recommended)**
```bash
export TOGETHER_API_KEY="your_together_key_here"
export VENICE_API_KEY="your_venice_key_here"  # optional
```

**Option B: Config File**
```bash
cp app_config.json.template app_config.json
# Edit app_config.json with your keys
```

### 4. Run

**Web UI (Recommended for beginners)**
```bash
python venice-web-ui/server.py
```
Open http://localhost:5050 in your browser

**CLI (For terminal lovers)**
```bash
python venice_cli_v2.py
```

### 5. Docker (Alternative)

```bash
# Create .env file
echo "TOGETHER_API_KEY=your_key_here" > .env

# Run with Docker Compose
docker-compose up -d
```

---

## Model Selection

### Together AI Models (Recommended)

| Model | Best For | Context |
|-------|----------|---------|
| Kimi K2.5 | General coding | 32k |
| Llama 4 Maverick | Long files | 128k |
| Qwen 3 235B | Function calling | 131k |
| DeepSeek v3.2 | Reasoning | 160k |

### Venice AI Models (Optional)

| Model | Best For | Context |
|-------|----------|---------|
| Claude Opus 4.5 | Complex tasks | 203k |
| Claude Sonnet 4.5 | High intelligence | 203k |
| GPT-5.2 Code | Elite coding | 262k |

**Note:** Together AI does not offer Claude models. Use Venice AI for Claude.

---

## Troubleshooting

### "API Key not found"
- Check your environment variables: `echo $TOGETHER_API_KEY`
- Or verify `app_config.json` exists and has correct format

### "Connection refused"
- Make sure the server is running: `python venice-web-ui/server.py`
- Check port 5040 isn't in use: `lsof -i :5040`

### "Model not available"
- Verify your API key has access to the model
- Check model availability on Together AI or Venice AI dashboard

### "Out of memory"
- Reduce context window in model settings
- Close other applications
- Use a model with smaller context (e.g., Kimi K2.5 instead of GPT-5.2)

---

## Next Steps

- Read the [README](README.md) for full feature list
- Check [RECENT_UPDATES.md](RECENT_UPDATES.md) for latest changes
- Join the community: [Discord/Forum link]
- Support the project: [GitHub Sponsors link]

---

**Questions?** Open an issue on GitHub or reach out on [Twitter/Mastodon].
