# Gondola Future Plans & Roadmap

This document tracks planned features, architectural improvements, and UX enhancements for Gondola.

## 🚀 Model Management Enhancements
- [ ] **Capability Metadata**: Store context window sizes and tool-calling support in the model configuration to improve "Context Pulse" accuracy and agent reliability.
- [ ] **Provider Health Checks**: Implement real-time status indicators (ping) to verify API key validity and provider availability before starting a session.
- [ ] **Model Aliasing**: Support "Friendly Names" for complex model IDs (e.g., "Kimi Fast" instead of `moonshotai/Kimi-K2-Instruct-0905`).
- [ ] **Pre-flight Validation**: Automatically test new models with a "Hello World" prompt before adding them to the persistent configuration.

## ⚙️ Configuration & Persistence
- [ ] **Smart Defaulting**: Persist the "Last Used Model" across sessions so the workspace restores exactly where the user left off.
- [ ] **Config Splitting**: Separate API keys (`secrets.json`) from model lists (`models.json`) to allow users to share model configurations without exposing private keys.
- [ ] **JSON Persistence for Models Tab**: (In Progress) Ensure all UI-driven model additions/removals are saved to disk.

## 🎨 UI & UX
- [ ] **Model Categorization**: Group models by strength (Reasoning, Coding, Fast/Cheap) in the selection dropdown.
- [ ] **Enhanced Thinking Logs**: Improve the readability of the "Matrix-style" thinking blocks for long-running tasks.

## 🛠️ Advanced Tooling
- [ ] **Plugin System**: Allow users to add custom Python-based tools to the `venice/tools/` directory dynamically.
- [ ] **Multi-Workspace Support**: Better handling of switching between different project roots without restarting the server.

## 🔧 Developer Experience
- [ ] **Docker Containerization**: Package Gondola as a container for consistent deployment and easier onboarding.
- [ ] **VS Code Extension**: Provide a lightweight extension that forwards the current file/selection to Gondola for inline edits.
- [ ] **CLI Profiles**: Support multiple named configurations (e.g., `gondola --profile open-source`) with different keys and default models.

## 🧠 Agent Intelligence
- [ ] **Auto-Context Gathering**: Before any edit, the agent should automatically pull in related files (imports, tests, configs) without the user explicitly asking.
- [ ] **Loop Detection & Recovery**: Smarter heuristics to detect when the agent is stuck repeating itself and auto-inject a recovery prompt.
- [ ] **Cost & Token Tracking**: Show running estimates of API spend and token usage per conversation, with configurable soft limits.

## 🧪 Testing & Quality
- [ ] **Automated Test Suite**: Expand the existing test coverage to include end-to-end flows for each major tool.
- [ ] **Stress Testing**: Simulate high-concurrency tool calls to ensure the Flask server and memory layer remain stable.
- [ ] **Regression Benchmarks**: A set of standard coding tasks that every release must complete without degradation.

## 📦 Distribution & Community
- [ ] **PyPI Package**: Publish `gondola-ai` to PyPI so users can `pip install gondola-ai` and run `gondola` from anywhere.
- [ ] **Community Model Pack**: Curated lists of "best models for coding" JSON files that users can import in one click.
- [ ] **Public Roadmap Voting**: Let GitHub users vote on upcoming features to prioritize development time.

---

*Last updated: $(date +%Y-%m-%d)*  
*Feel free to open an issue or PR to suggest new items or claim any task.*
