<div align="center">

<h1 style="font-family: 'Bookman Old Style', serif;">
  EverMemOS
  <br>
  <a href="https://everm.ai/" target="_blank">
    <img src="figs/logo.png" alt="EverMemOS" height="34" />
  </a>
</h1>

<p><strong>Let every interaction be driven by understanding</strong> · Enterprise-Grade Intelligent Memory System</p>

<p>
  <a href="https://arxiv.org/abs/2601.02163">
    <img alt="arXiv" src="https://img.shields.io/badge/arXiv-2601.02163-b31b1b?style=flat-square&logo=arxiv&logoColor=white" />
  </a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-0084FF?style=flat-square&logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-Apache%202.0-00B894?style=flat-square&logo=apache&logoColor=white" />
  <img alt="Docker" src="https://img.shields.io/badge/Docker-Supported-4A90E2?style=flat-square&logo=docker&logoColor=white" />
  <a href="https://github.com/EverMind-AI/EverMemOS/releases">
    <img alt="Release" src="https://img.shields.io/badge/release-v1.2.0-4A90E2?style=flat-square" />
  </a>
  <a href="https://github.com/EverMind-AI/EverMemOS/stargazers">
    <img alt="Stars" src="https://img.shields.io/github/stars/EverMind-AI/EverMemOS?style=flat-square" />
  </a>
</p>


</div>

---

[🚀 Quick Start](#quick-start) • [📖 Documentation](docs/) • [🎯 Demos](docs/usage/DEMOS.md) • [🤝 Contributing](#contributing) • [💬 Discord](https://discord.gg/pfwwskxp)

---

## Introduction

> 💬 **More than memory — it's foresight.**

**EverMemOS** enables AI to not only remember what happened, but understand the meaning behind memories and use them to guide decisions. Achieving **93% reasoning accuracy** on the LoCoMo benchmark, EverMemOS provides long-term memory capabilities for conversational AI agents through structured extraction, intelligent retrieval, and progressive profile building.

<p align="center">
  <img src="figs/overview.png" alt="EverMemOS Architecture Overview" width="800"/>
</p>

**How it works:** EverMemOS extracts structured memories from conversations (Encoding), organizes them into episodes and profiles (Consolidation), and intelligently retrieves relevant context when needed (Retrieval).

📄 [Paper](https://arxiv.org/abs/2601.02163) • 📚 [Vision & Overview](docs/OVERVIEW.md) • 🏗️ [Architecture](docs/ARCHITECTURE.md) • 📖 [Full Documentation](docs/)

**Latest**: v1.2.0 with API enhancements + DB efficiency improvements ([Changelog](docs/CHANGELOG.md))

---

## Why EverMemOS?

- 🎯 **93% Accuracy** - Best-in-class performance on LoCoMo benchmark
- 🚀 **Production Ready** - Enterprise-grade with Milvus vector DB, Elasticsearch, MongoDB, and Redis
- 🔧 **Easy Integration** - Simple REST API, works with any LLM
- 📊 **Multi-Modal Memory** - Episodes, facts, preferences, relations
- 🔍 **Smart Retrieval** - BM25, embeddings, or agentic search

<p align="center">
  <img src="figs/benchmark.png" alt="EverMemOS Benchmark Results" width="800"/>
  <br>
  <em>EverMemOS outperforms existing memory systems across all major benchmarks</em>
</p>

---

## Quick Start

### Prerequisites
- Python 3.10+ • Docker 20.10+ • uv package manager • 4GB RAM

**Verify Prerequisites:**
```bash
# Verify you have the required versions
python --version  # Should be 3.10+
docker --version  # Should be 20.10+
```

### Installation

```bash
# 1. Clone and navigate
git clone https://github.com/EverMind-AI/EverMemOS.git
cd EverMemOS

# 2. Start Docker services
docker-compose up -d

# 3. Install uv and dependencies
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# 4. Configure API keys
cp env.template .env
# Edit .env and set:
#   - LLM_API_KEY (for memory extraction)
#   - VECTORIZE_API_KEY (for embedding/rerank)

# 5. Start server
uv run python src/run.py --port 8001

# 6. Verify installation
curl http://localhost:8001/health
# Expected response: {"status": "healthy", ...}
```

✅ Server running at `http://localhost:8001` • [Full Setup Guide](docs/installation/SETUP.md)

---

## Basic Usage

Store and retrieve memories with simple Python code:

```python
import requests

API_BASE = "http://localhost:8001/api/v1"

# 1. Store a conversation memory
requests.post(f"{API_BASE}/memories", json={
    "message_id": "msg_001",
    "create_time": "2025-02-01T10:00:00+00:00",
    "sender": "user_001",
    "content": "I love playing soccer on weekends"
})

# 2. Search for relevant memories
response = requests.get(f"{API_BASE}/memories/search", json={
    "query": "What sports does the user like?",
    "user_id": "user_001",
    "memory_types": ["episodic_memory"],
    "retrieve_method": "hybrid"
})

result = response.json().get("result", {})
for memory_group in result.get("memories", []):
    print(f"Memory: {memory_group}")
```

**Try it now**: `uv run python src/bootstrap.py demo/simple_demo.py` ([Demo Guide](docs/usage/DEMOS.md))

📖 [More Examples](docs/usage/USAGE_EXAMPLES.md) • 📚 [API Reference](docs/api_docs/memory_api.md) • 🎯 [Interactive Demos](docs/usage/DEMOS.md)

---

## Advanced Techniques

- **[Group Chat Conversations](docs/advanced/GROUP_CHAT_GUIDE.md)** - Combine messages from multiple speakers
- **[Conversation Metadata Control](docs/advanced/METADATA_CONTROL.md)** - Fine-grained control over conversation context
- **[Memory Retrieval Strategies](docs/advanced/RETRIEVAL_STRATEGIES.md)** - Lightweight vs Agentic retrieval modes
- **[Batch Operations](docs/usage/BATCH_OPERATIONS.md)** - Process multiple messages efficiently

---

## Evaluation & Benchmarking

EverMemOS achieves **93% overall accuracy** on the LoCoMo benchmark, outperforming comparable memory systems.

### Benchmark Results

<p align="center">
  <img src="figs/benchmark_2.png" alt="EverMemOS Benchmark Results" width="800"/>
</p>

### Supported Benchmarks

- **[LoCoMo](https://github.com/snap-research/locomo)** - Long-context memory benchmark with single/multi-hop reasoning
- **[LongMemEval](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned)** - Multi-session conversation evaluation
- **[PersonaMem](https://huggingface.co/datasets/bowen-upenn/PersonaMem)** - Persona-based memory evaluation

### Quick Start

```bash
# Install evaluation dependencies
uv sync --group evaluation

# Run smoke test (quick verification)
uv run python -m evaluation.cli --dataset locomo --system evermemos --smoke

# Run full evaluation
uv run python -m evaluation.cli --dataset locomo --system evermemos

# View results
cat evaluation/results/locomo-evermemos/report.txt
```

📊 [Full Evaluation Guide](evaluation/README.md) • 📈 [Complete Results](https://huggingface.co/datasets/EverMind-AI/EverMemOS_Eval_Results)

---

## Contributing

We welcome contributions! Here's how you can help:

- 🐛 **[Report Bugs](https://github.com/EverMind-AI/EverMemOS/issues/new?template=bug_report.md)** - Help us improve
- ✨ **[Request Features](https://github.com/EverMind-AI/EverMemOS/issues/new?template=feature_request.md)** - Share your ideas
- 💻 **[Submit PRs](CONTRIBUTING.md)** - Read our contribution guide
- 💬 **[Join Discord](https://discord.gg/pfwwskxp)** - Connect with the community
- 📧 **[Email Us](mailto:evermind@shanda.com)** - General inquiries

**Community**: [GitHub Discussions](https://github.com/EverMind-AI/EverMemOS/discussions) • [Reddit](https://www.reddit.com/r/EverMindAI/) • [X/Twitter](https://x.com/EverMindAI)

📖 Read our [Contribution Guidelines](CONTRIBUTING.md) for code standards and Git workflow.

---

## License & Citation

Licensed under [Apache 2.0](LICENSE) • [Citation Info](docs/CITATION.md) • [Acknowledgments](docs/ACKNOWLEDGMENTS.md)

---

<div align="center">

**If this project helps you, please give us a ⭐**

Made with ❤️ by the EverMemOS Team

</div>
