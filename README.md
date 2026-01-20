<div align="center" id="readme-top">

<h1>
  <a href="https://everm.ai/" target="_blank">
    <img src="figs/logo.png" alt="EverMemOS" height="40" />
  </a>
  <br>
  EverMemOS
</h1>

<p><strong>Let every interaction be driven by understanding</strong></p>

[![Release][release-badge]][releases]
[![Python][python-badge]][python]
[![License][license-badge]][license]
[![Docker][docker-badge]][docker]

[![README in English][lang-en-badge]][lang-en-readme]
[![简体中文][lang-zh-badge]][lang-zh-readme]

[Documentation][documentation] •
[API Reference][api-docs] •
[Demo][demo-section]

</div>

<br>

<details open>
<summary><kbd>Table of Contents</kbd></summary>

<br>

- [Welcome to EverMemOS][welcome]
- [Features][features-section]
- [Quick Start][quick-start]
  - [Prerequisites][prerequisites]
  - [Installation][installation]
  - [Run the Demo][run-demo]
- [How It Works][how-it-works]
- [API Usage][api-usage]
- [Evaluation][evaluation-section]
- [Documentation][docs-section]
- [Contributing][contributing]
- [License][license-section]

<br>

</details>

## Welcome to EverMemOS

EverMemOS is an open-source intelligent memory system for conversational AI. It extracts, structures, and retrieves information from conversations — enabling AI agents to maintain context, recall past interactions, and build user profiles over time.

On the **LoCoMo** benchmark, EverMemOS achieved **92.3%** reasoning accuracy (LLM-Judge evaluation).

<br>

| Community | Purpose |
| --------- | ------- |
| [![GitHub Issues][issues-badge]][issues] | Report bugs and request features |
| [![GitHub Discussions][discussions-badge]][discussions] | Ask questions and share ideas |
| [![Email][email-badge]][email] | Contact the team |

<br>

## Features

<br>

| Feature | Description |
| ------- | ----------- |
| **Coherent Narrative** | Automatically links conversation fragments into thematic context — AI understands the whole story, not just isolated sentences |
| **Evidence-Based Perception** | Proactively captures deep connections between memories and tasks — responses are grounded in real context |
| **Living Profiles** | Real-time user profile updates that evolve with each conversation — AI learns who you are, not just what you said |

<br>

<p align="center">
  <img src="figs/overview.png" alt="EverMemOS Architecture Overview" />
</p>

<div align="right">

[![][back-to-top]][readme-top]

</div>

## Quick Start

### Prerequisites

| Category | Requirements |
| -------- | ------------ |
| **Runtime** | Python 3.10+, [uv][uv] package manager |
| **Services** | Docker 20.10+, Docker Compose 2.0+ |
| **Hardware** | CPU ≥ 2 cores, RAM ≥ 4 GB |
| **API Keys** | LLM API key, [DeepInfra][deepinfra] API key (for embedding/rerank) |

<br>

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/EverMind-AI/EverMemOS.git
cd EverMemOS

# 2. Start dependency services (MongoDB, Elasticsearch, Milvus, Redis)
docker-compose up -d

# 3. Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# 4. Install project dependencies
uv sync

# 5. Configure environment
cp env.template .env
# Edit .env with your API keys (LLM_API_KEY, VECTORIZE_API_KEY)
```

<br>

### Run the Demo

```bash
# Terminal 1: Start the API server
uv run python src/run.py --port 8001

# Terminal 2: Run the simple demo
uv run python src/bootstrap.py demo/simple_demo.py
```

The demo stores sample conversations, waits for indexing, and searches for relevant memories — showing the complete workflow in action.

<br>

**Full Demo Experience:**

```bash
# Extract memories from sample data
uv run python src/bootstrap.py demo/extract_memory.py

# Start interactive chat with memory
uv run python src/bootstrap.py demo/chat_with_memory.py
```

See the [Demo Guide][demo-guide] for detailed instructions.

<div align="right">

[![][back-to-top]][readme-top]

</div>

## How It Works

EverMemOS operates along two tracks: **memory construction** and **memory perception**.

<br>

### Memory Construction

Builds structured, retrievable long-term memory from raw conversations.

| Component | Purpose |
| --------- | ------- |
| **MemCell Extraction** | Identifies key information to generate atomic memory units |
| **Memory Integration** | Organizes by theme and participants into episodes and profiles |
| **Storage & Indexing** | Persists data with keyword and semantic indexes for fast recall |

<br>

### Memory Perception

Recalls relevant memories through multi-round reasoning and intelligent fusion.

| Strategy | Description |
| -------- | ----------- |
| **Hybrid Retrieval** | Parallel semantic + keyword search with RRF fusion |
| **Intelligent Reranking** | Deep relevance scoring to prioritize critical information |
| **Lightweight Mode** | Pure BM25 for latency-sensitive scenarios |
| **Agentic Recall** | Multi-round query generation for complex intents |

<div align="right">

[![][back-to-top]][readme-top]

</div>

## API Usage

### Store a Memory

```bash
curl -X POST http://localhost:8001/api/v1/memories \
  -H "Content-Type: application/json" \
  -d '{
    "message_id": "msg_001",
    "create_time": "2025-02-01T10:00:00+00:00",
    "sender": "user_001",
    "sender_name": "Alice",
    "content": "I love playing basketball on weekends",
    "group_id": "group_001",
    "scene": "assistant"
  }'
```

<br>

### Search Memories

```bash
curl -X GET http://localhost:8001/api/v1/memories/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What sports does the user like?",
    "user_id": "user_001",
    "data_source": "episode",
    "memory_scope": "personal",
    "retrieval_mode": "rrf"
  }'
```

See the [API Documentation][api-docs] for complete reference.

<div align="right">

[![][back-to-top]][readme-top]

</div>

## Evaluation

Run benchmarks to test EverMemOS performance:

```bash
# Quick smoke test
uv run python -m evaluation.cli --dataset locomo --system evermemos --smoke

# Full evaluation
uv run python -m evaluation.cli --dataset locomo --system evermemos

# View results
cat evaluation/results/locomo-evermemos/report.txt
```

Supported datasets: `locomo`, `longmemeval`, `personamem`

See the [Evaluation Guide][evaluation-guide] for details.

<div align="right">

[![][back-to-top]][readme-top]

</div>

## Documentation

| Guide | Description |
| ----- | ----------- |
| [Quick Start][getting-started] | Installation and configuration |
| [Configuration Guide][config-guide] | Environment variables and services |
| [API Usage Guide][api-usage-guide] | Endpoints and data formats |
| [Development Guide][dev-guide] | Architecture and best practices |
| [Memory API][api-docs] | Complete API reference |
| [Demo Guide][demo-guide] | Interactive examples |
| [Evaluation Guide][evaluation-guide] | Benchmark testing |

<div align="right">

[![][back-to-top]][readme-top]

</div>

## Contributing

Contributions are welcome! Please read the [Contributing Guide][contributing-doc] first.

### Contributors

Thanks to all the developers who have contributed to this project!

<a href="https://github.com/EverMind-AI/EverMemOS/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=EverMind-AI/EverMemOS" />
</a>

<div align="right">

[![][back-to-top]][readme-top]

</div>

## License

This project is licensed under the [Apache License 2.0][license].

<br>

## Acknowledgments

- [Memos][memos] — Inspiration for memory system design
- [Nemori][nemori] — Self-organizing long-term memory concepts

<br>

---

<div align="center">

**If this project helps you, please give us a ⭐**

Made with ❤️ by the EverMemOS Team

</div>

<!-- Navigation -->
[readme-top]: #readme-top
[welcome]: #welcome-to-evermemos
[features-section]: #features
[quick-start]: #quick-start
[prerequisites]: #prerequisites
[installation]: #installation
[run-demo]: #run-the-demo
[how-it-works]: #how-it-works
[api-usage]: #api-usage
[evaluation-section]: #evaluation
[docs-section]: #documentation
[contributing]: #contributing
[license-section]: #license
[demo-section]: #run-the-demo

<!-- Badges -->
[back-to-top]: https://img.shields.io/badge/-Back_to_top-gray?style=flat-square
[release-badge]: https://img.shields.io/github/v/release/EverMind-AI/EverMemOS?color=369eff&labelColor=gray&logo=github&style=flat-square
[python-badge]: https://img.shields.io/badge/Python-3.10+-0084FF?style=flat-square&logo=python&logoColor=white
[license-badge]: https://img.shields.io/badge/License-Apache%202.0-00B894?style=flat-square
[docker-badge]: https://img.shields.io/badge/Docker-Supported-4A90E2?style=flat-square&logo=docker&logoColor=white
[lang-en-badge]: https://img.shields.io/badge/English-lightgrey?style=flat-square
[lang-zh-badge]: https://img.shields.io/badge/简体中文-lightgrey?style=flat-square
[issues-badge]: https://img.shields.io/badge/GitHub-Issues-blue?style=flat-square&logo=github
[discussions-badge]: https://img.shields.io/badge/GitHub-Discussions-blue?style=flat-square&logo=github
[email-badge]: https://img.shields.io/badge/Email-Contact_Us-blue?style=flat-square&logo=gmail

<!-- Links -->
[releases]: https://github.com/EverMind-AI/EverMemOS/releases
[python]: https://www.python.org/
[license]: https://github.com/EverMind-AI/EverMemOS/blob/main/LICENSE
[docker]: https://www.docker.com/
[lang-en-readme]: README.md
[lang-zh-readme]: README_zh.md
[issues]: https://github.com/EverMind-AI/EverMemOS/issues
[discussions]: https://github.com/EverMind-AI/EverMemOS/discussions
[email]: mailto:evermind@shanda.com

<!-- External -->
[uv]: https://github.com/astral-sh/uv
[deepinfra]: https://deepinfra.com/
[memos]: https://github.com/usememos/memos
[nemori]: https://github.com/nemori-ai/nemori

<!-- Documentation -->
[documentation]: https://everm.ai/
[api-docs]: docs/api_docs/memory_api.md
[getting-started]: docs/dev_docs/getting_started.md
[config-guide]: docs/usage/CONFIGURATION_GUIDE.md
[api-usage-guide]: docs/dev_docs/api_usage_guide.md
[dev-guide]: docs/dev_docs/development_guide.md
[demo-guide]: demo/README.md
[evaluation-guide]: evaluation/README.md
[contributing-doc]: CONTRIBUTING.md
