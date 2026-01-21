<div align="center" id="readme-top">

<h2>
  <a href="https://everm.ai/" target="_blank">
    <!-- <img src="figs/logo.png" alt="EverMemOS" height="100" /> -->
  </a>
  <br>
  EverMemOS
</h2>

EverMemOS is an open-source, enterprise-grade intelligent memory system. Our mission is to build AI memory that never forgets, making every conversation built on previous understanding.

<br>

[![arXiv](https://img.shields.io/badge/arXiv-EverMemOS_Paper-F5C842?labelColor=555&style=flat-square&logo=arxiv&logoColor=white)](https://arxiv.org/abs/2601.02163)
[![Python][python-badge]][python]
[![Docker][docker-badge]][docker]
[![FastAPI][fastapi-badge]][fastapi]
[![MongoDB][mongodb-badge]][mongodb]
[![Elasticsearch][elasticsearch-badge]][elasticsearch]
[![Milvus][milvus-badge]][milvus]
[![License][license-badge]][license]

<p><strong>Share EverMemOS Repository</strong></p>

[![][share-x-shield]][share-x-link]
[![][share-linkedin-shield]][share-linkedin-link]
[![][share-reddit-shield]][share-reddit-link]
[![][share-telegram-shield]][share-telegram-link]
[![][share-whatsapp-shield]][share-whatsapp-link]
[![][share-mastodon-shield]][share-mastodon-link]

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

![image](https://github.com/user-attachments/assets/2a2a4f15-9185-47b3-9182-9c28145e18a4)
![image](https://github.com/user-attachments/assets/a392bc68-403f-48c4-97e3-fd01dc108080)

<!-- <p align="center">
  <img src="figs/overview.png" alt="EverMemOS Architecture Overview" />
</p> -->

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

<!-- Header Badges -->
[release-badge]: https://img.shields.io/github/v/release/EverMind-AI/EverMemOS?color=369eff&labelColor=gray&logo=github&style=flat-square
[release-date-badge]: https://img.shields.io/github/release-date/EverMind-AI/EverMemOS?labelColor=gray&style=flat-square
[commits-badge]: https://img.shields.io/github/commit-activity/m/EverMind-AI/EverMemOS?labelColor=gray&color=pink&style=flat-square
[issues-closed-badge]: https://img.shields.io/github/issues-search?query=repo%3AEverMind-AI%2FEverMemOS%20is%3Aclosed&label=issues%20closed&labelColor=gray&color=green&style=flat-square
[contributors-badge]: https://img.shields.io/github/contributors/EverMind-AI/EverMemOS?color=c4f042&labelColor=gray&style=flat-square
[license-badge]: https://img.shields.io/badge/License-Apache%202.0-blue?labelColor=gray&style=flat-square

<!-- Tech Stack Badges -->
[python-badge]: https://img.shields.io/badge/Python-3.10+-0084FF?style=flat-square&logo=python&logoColor=white
[docker-badge]: https://img.shields.io/badge/Docker-Supported-4A90E2?style=flat-square&logo=docker&logoColor=white
[fastapi-badge]: https://img.shields.io/badge/FastAPI-Latest-26A69A?style=flat-square&logo=fastapi&logoColor=white
[mongodb-badge]: https://img.shields.io/badge/MongoDB-7.0+-00C853?style=flat-square&logo=mongodb&logoColor=white
[elasticsearch-badge]: https://img.shields.io/badge/Elasticsearch-8.x-0084FF?style=flat-square&logo=elasticsearch&logoColor=white
[milvus-badge]: https://img.shields.io/badge/Milvus-2.4+-00A3E0?style=flat-square

<!-- Language Badges -->
[lang-en-badge]: https://img.shields.io/badge/English-lightgrey?style=flat-square
[lang-zh-badge]: https://img.shields.io/badge/简体中文-lightgrey?style=flat-square

<!-- Community Badges -->
[issues-badge]: https://img.shields.io/badge/GitHub-Issues-blue?style=flat-square&logo=github
[discussions-badge]: https://img.shields.io/badge/GitHub-Discussions-blue?style=flat-square&logo=github
[email-badge]: https://img.shields.io/badge/Email-Contact_Us-blue?style=flat-square&logo=gmail

<!-- Misc Badges -->
[back-to-top]: https://img.shields.io/badge/-Back_to_top-gray?style=flat-square

<!-- Header Badge Links -->
[releases]: https://github.com/EverMind-AI/EverMemOS/releases
[commit-activity]: https://github.com/EverMind-AI/EverMemOS/graphs/commit-activity
[issues-closed]: https://github.com/EverMind-AI/EverMemOS/issues?q=is%3Aissue+is%3Aclosed
[contributors]: https://github.com/EverMind-AI/EverMemOS/graphs/contributors
[license]: https://github.com/EverMind-AI/EverMemOS/blob/main/LICENSE

<!-- Tech Stack Links -->
[python]: https://www.python.org/
[docker]: https://www.docker.com/
[fastapi]: https://fastapi.tiangolo.com/
[mongodb]: https://www.mongodb.com/
[elasticsearch]: https://www.elastic.co/elasticsearch/
[milvus]: https://milvus.io/

<!-- Language Links -->
[lang-en-readme]: README.md
[lang-zh-readme]: README_zh.md

<!-- Community Links -->
[issues]: https://github.com/EverMind-AI/EverMemOS/issues
[discussions]: https://github.com/EverMind-AI/EverMemOS/discussions
[email]: mailto:evermind@shanda.com

<!-- External Links -->
[uv]: https://github.com/astral-sh/uv
[deepinfra]: https://deepinfra.com/
[memos]: https://github.com/usememos/memos
[nemori]: https://github.com/nemori-ai/nemori

<!-- Documentation Links -->
[documentation]: https://everm.ai/
[api-docs]: docs/api_docs/memory_api.md
[getting-started]: docs/dev_docs/getting_started.md
[config-guide]: docs/usage/CONFIGURATION_GUIDE.md
[api-usage-guide]: docs/dev_docs/api_usage_guide.md
[dev-guide]: docs/dev_docs/development_guide.md
[demo-guide]: demo/README.md
[evaluation-guide]: evaluation/README.md
[contributing-doc]: CONTRIBUTING.md

<!-- Share Badges (using warm cream #faf9f5 from EverMemOS theme) -->
[share-linkedin-link]: https://linkedin.com/feed/?shareActive=true&text=Check%20this%20GitHub%20repository%20out%20%F0%9F%A4%AF%20EverMemOS%20-%20An%20open-source%20intelligent%20memory%20system%20for%20conversational%20AI.%20Let%20every%20interaction%20be%20driven%20by%20understanding.%20https%3A%2F%2Fgithub.com%2FEverMind-AI%2FEverMemOS%20%23AI%20%23Memory%20%23LLM
[share-linkedin-shield]: https://img.shields.io/badge/-share%20on%20linkedin-faf9f5?labelColor=faf9f5&color=555&style=flat-square&logo=linkedin&logoColor=555
[share-mastodon-link]: https://mastodon.social/share?text=Check%20this%20GitHub%20repository%20out%20%F0%9F%A4%AF%20EverMemOS%20-%20An%20open-source%20intelligent%20memory%20system%20for%20conversational%20AI.%20Let%20every%20interaction%20be%20driven%20by%20understanding.%20https://github.com/EverMind-AI/EverMemOS%20%23AI%20%23Memory%20%23LLM
[share-mastodon-shield]: https://img.shields.io/badge/-share%20on%20mastodon-faf9f5?labelColor=faf9f5&logo=mastodon&logoColor=555&style=flat-square
[share-reddit-link]: https://www.reddit.com/submit?title=Check%20this%20GitHub%20repository%20out%20%F0%9F%A4%AF%20EverMemOS%20-%20An%20open-source%20intelligent%20memory%20system%20for%20conversational%20AI.%20Let%20every%20interaction%20be%20driven%20by%20understanding.%20%23AI%20%23Memory%20%23LLM&url=https%3A%2F%2Fgithub.com%2FEverMind-AI%2FEverMemOS
[share-reddit-shield]: https://img.shields.io/badge/-share%20on%20reddit-faf9f5?labelColor=faf9f5&logo=reddit&logoColor=555&style=flat-square
[share-telegram-link]: https://t.me/share/url?text=Check%20this%20GitHub%20repository%20out%20%F0%9F%A4%AF%20EverMemOS%20-%20An%20open-source%20intelligent%20memory%20system%20for%20conversational%20AI.%20Let%20every%20interaction%20be%20driven%20by%20understanding.%20%23AI%20%23Memory%20%23LLM&url=https%3A%2F%2Fgithub.com%2FEverMind-AI%2FEverMemOS
[share-telegram-shield]: https://img.shields.io/badge/-share%20on%20telegram-faf9f5?labelColor=faf9f5&logo=telegram&logoColor=555&style=flat-square
[share-weibo-link]: http://service.weibo.com/share/share.php?sharesource=weibo&title=Check%20this%20GitHub%20repository%20out%20%F0%9F%A4%AF%20EverMemOS%20-%20An%20open-source%20intelligent%20memory%20system%20for%20conversational%20AI.%20Let%20every%20interaction%20be%20driven%20by%20understanding.%20%23AI%20%23Memory%20%23LLM&url=https%3A%2F%2Fgithub.com%2FEverMind-AI%2FEverMemOS
[share-weibo-shield]: https://img.shields.io/badge/-share%20on%20weibo-faf9f5?labelColor=faf9f5&logo=sinaweibo&logoColor=555&style=flat-square
[share-whatsapp-link]: https://api.whatsapp.com/send?text=Check%20this%20GitHub%20repository%20out%20%F0%9F%A4%AF%20EverMemOS%20-%20An%20open-source%20intelligent%20memory%20system%20for%20conversational%20AI.%20Let%20every%20interaction%20be%20driven%20by%20understanding.%20https%3A%2F%2Fgithub.com%2FEverMind-AI%2FEverMemOS%20%23AI%20%23Memory%20%23LLM
[share-whatsapp-shield]: https://img.shields.io/badge/-share%20on%20whatsapp-faf9f5?labelColor=faf9f5&logo=whatsapp&logoColor=555&style=flat-square
[share-x-link]: https://x.com/intent/tweet?hashtags=AI%2CMemory%2CLLM&text=Check%20this%20GitHub%20repository%20out%20%F0%9F%A4%AF%20EverMemOS%20-%20An%20open-source%20intelligent%20memory%20system%20for%20conversational%20AI.%20Let%20every%20interaction%20be%20driven%20by%20understanding.&url=https%3A%2F%2Fgithub.com%2FEverMind-AI%2FEverMemOS
[share-x-shield]: https://img.shields.io/badge/-share%20on%20x-faf9f5?labelColor=faf9f5&logo=x&logoColor=555&style=flat-square
