# Gondola v2.3

**An AI-powered coding assistant built by an AI orchestra leader.**

Built in 3 weeks using lunch breaks and 3 hours a night—with a lot of help from Claude Code and Gemini CLI. If I can build this, imagine what you can do.

---

## What is Gondola?

Gondola is a **bring-your-own-key** AI coding assistant that runs locally in your browser or terminal. It doesn't phone home to big tech, doesn't train on your code, and respects your privacy.

### Key Features

- **25+ Tools**: File operations, code search, semantic understanding, project indexing
- **Risk Analysis**: Pre-flight safety checks before edits
- **Multi-Model Support**: Works with Venice AI, Together AI (Kimi K2.5, Llama, Qwen, and more)
- **Project Indexing**: Compressed project understanding for large codebases
- **Necromancer Persistence**: Git-based state recovery using shadow branches
- **Web UI + CLI**: Choose your interface
- **Context Management**: Token-aware conversation handling
- **Agent State Tracking**: Loop prevention and progress monitoring

---

## Quick Start

### Prerequisites

- Python 3.8+
- A Together AI API key (required)
- Optional: Venice AI API key for additional models

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/gondola.git
cd gondola

# Install dependencies
pip install -r requirements.txt

# Set up your API keys (choose one method)

# Method 1: Environment variables
export TOGETHER_API_KEY="your_key_here"
export VENICE_API_KEY="your_key_here"  # optional

# Method 2: Config file
cp app_config.json.template app_config.json
# Edit app_config.json with your keys

# Run the Web UI
python venice-web-ui/server.py

# Or run the CLI
python venice_cli_v2.py
```

The Web UI will be available at `http://localhost:5050`

---

## Supported Models

| Model | Provider | Context | Best For |
|-------|----------|---------|----------|
| Kimi K2.5 | Together AI | 32k | General coding |
| Llama 4 Maverick | Together AI | 128k | Long context |
| Qwen 3 235B | Together AI | 131k | Function calling |
| DeepSeek v3.2 | Venice AI | 160k | Reasoning |
| Claude Opus 4.5 | Venice AI | 203k | Complex tasks |
| GPT-5.2 Code | Venice AI | 262k | Elite coding |

*Note: Claude models require Venice AI. Together AI does not offer Claude.*

---

## Architecture

```
gondola_v2.2/
├── venice/              # Core Python package
│   ├── cli.py          # CLI entry point
│   ├── core.py         # Models, UI, colors
│   ├── api.py          # API utilities
│   ├── workspace.py    # Secure file sandbox
│   ├── memory.py       # Persistent storage
│   ├── agent_state.py  # Session tracking
│   ├── project_index.py # Code understanding
│   ├── context_manager.py # Token management
│   ├── risk_analyzer.py # Edit safety
│   └── tools/          # 25+ tool implementations
├── venice-web-ui/      # Flask web interface
│   ├── server.py       # Main server
│   ├── static/         # CSS, JS
│   └── templates/      # HTML
└── venice_cli_v2.py    # CLI launcher
```

---

## The Story

I'm not a developer. I'm an AI orchestra leader.

I built Gondola using:
- **Claude Code** for architecture and complex logic
- **Gemini CLI** for quick iterations and debugging
- **3 weeks** of lunch breaks and late nights
- **Determination** to prove what's possible

Every line of code was written by AI, but every architectural decision was human. This is the future of software development.

---

## Support the Project

If Gondola helps you build something amazing, consider supporting continued development:

[![GitHub Sponsors](https://img.shields.io/github/sponsors/yourusername?style=social)](https://github.com/sponsors/yourusername)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Buy%20me%20a%20coffee-ff5f5f?style=flat&logo=ko-fi)](https://ko-fi.com/yourusername)

Your support means:
- ☕ $5 = 30 minutes of bug fixes
- 🍕 $20 = 2 hours of new features
- 💻 $100 = Priority issue resolution

---

## Roadmap

- [ ] Docker containerization
- [ ] Plugin system for custom tools
- [ ] Multi-workspace support
- [ ] Team collaboration features
- [ ] VS Code extension

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Acknowledgments

- Built with [Claude](https://claude.ai) and [Gemini](https://gemini.google.com)
- Inspired by the future of human-AI collaboration
- Thanks to everyone who believed an AI orchestra leader could ship software

---

**"If you can describe it, AI can build it."**
