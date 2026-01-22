<div align="center" id="readme-top">

# EverMemOS

EverMemOS is an open-source, enterprise-grade intelligent memory system. 

<br>

[![][arxiv-badge]][arxiv-link]
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
[![][share-weibo-shield]][share-mastodon-link]


[Documentation][documentation] •
[API Reference][api-docs] •
[Demo][demo-section]

[![README in English][lang-en-badge]][lang-en-readme]
[![简体中文][lang-zh-badge]][lang-zh-readme]

</div>


![divider][divider-light]
![divider][divider-dark]

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

Welcome to EverMemOS! Join our community to help improve the project and collaborate with talented developers worldwide.

| Community | Purpose |
| :-------- | :------ |
| [![Discord][discord-badge]][discord] | Join our Discord community |
| [![X][x-badge]][x] | Follow updates on X |
| [![LinkedIn][linkedin-badge]][linkedin] | Connect with us on LinkedIn |
| [![Reddit][reddit-badge]][reddit] | Join the Reddit community |


### 🌟 Star us and stay tuned with us 

![star us gif](https://github.com/user-attachments/assets/0c512570-945a-483a-9f47-8e067bd34484)

<br>

## Why EveryMemOS

### How EverMemOS works
![image](https://github.com/user-attachments/assets/2a2a4f15-9185-47b3-9182-9c28145e18a4)

EverMemOS enables AI to not only remember what happened, but understand the meaning behind memories and use them to guide decisions. Achieving 93% reasoning accuracy on the LoCoMo benchmark, EverMemOS provides long-term memory capabilities for conversational AI agents through structured extraction, intelligent retrieval, and progressive profile building.

![divider][divider-light]
![divider][divider-dark]


### EverMemOS benchmark

![image](https://github.com/user-attachments/assets/9583e4de-8f3b-4681-ab5f-10ee82327da8)

* 🎯 93% Accuracy - Best-in-class performance on LoCoMo benchmark
* 🚀 Production Ready - Enterprise-grade with Milvus vector DB, Elasticsearch, MongoDB, and Redis
* 🔧 Easy Integration - Simple REST API, works with any LLM
* 📊 Multi-Modal Memory - Episodes, facts, preferences, relations
* 🔍 Smart Retrieval - BM25, embeddings, or agentic search

<br>

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

![divider][divider-light]
![divider][divider-dark]


### Installation

① Clone the repository and cd into the project
```bash
git clone https://github.com/EverMind-AI/EverMemOS.git

cd EverMemOS
```

② Start dependency services (MongoDB, Elasticsearch, Milvus and Redis)
```bash
docker-compose up -d
```

③ Install uv and use uv to install dependencies
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

uv sync
```

④ Configure API Keys
```bash
cp env.template .env

# Edit .env and set:
#   - LLM_API_KEY (for memory extraction)
#   - VECTORIZE_API_KEY (for embedding/rerank)
```

⑤ Start server
```bash
uv run python src/run.py --port 8001
```

⑥ Verify installation
```bash
curl http://localhost:8001/health
# Expected response: {"status": "healthy", ...}
```

![divider][divider-light]
![divider][divider-dark]

### Run the Demo

① Terminal 1: Start the API server
```bash
uv run python src/run.py --port 8001
```

② Terminal 2: Run the simple demo
```bash
uv run python src/bootstrap.py demo/simple_demo.py
```

The demo stores sample conversations, waits for indexing, and searches for relevant memories — showing the complete workflow in action.

![divider][divider-light]
![divider][divider-dark]

**Full Demo Experience**

① Extract memories from sample data
```bash
uv run python src/bootstrap.py demo/extract_memory.py
```

② Start interactive chat with memory
```
uv run python src/bootstrap.py demo/chat_with_memory.py
```

See the [Demo Guide][demo-guide] for detailed instructions.

<br>

<div align="right">

[![][back-to-top]][readme-top]

</div>

<!-- ## How It Works

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
| **Agentic Recall** | Multi-round query generation for complex intents | -->

<br>

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

![divider][divider-light]
![divider][divider-dark]

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

<br>

<div align="right">

[![][back-to-top]][readme-top]

</div>

## Evaluation

Run benchmarks to test EverMemOS performance:

### Quick smoke test
```bash
uv run python -m evaluation.cli --dataset locomo --system evermemos --smoke
```

### Full evaluation
```bash
uv run python -m evaluation.cli --dataset locomo --system evermemos
```

### View results
```bash
cat evaluation/results/locomo-evermemos/report.txt
```

Supported datasets: `locomo`, `longmemeval`, `personamem`

See the [Evaluation Guide][evaluation-guide] for details.

<br>

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

### Contributing

We love open-source energy! Whether you’re squashing bugs, shipping features, sharpening docs, or just tossing in wild ideas, every PR moves EverMemOS forward. Browse [Issues](https://github.com/EverMind-AI/EverMemOS/issues) and [Projects](https://github.com/EverMind-AI/EverMemOS/projects) to find your perfect entry point—then show us what you’ve got. Let’s build the future of memory together.

<br>

> [!TIP]
>
> **Welcome all kinds of contributions** 🙏
>
> Join us in building EverMemOS better! Every contribution makes a difference, from code to documentation. Share your projects on social media to inspire others!
>
> Connect with one of the EverMemOS maintainers [@elliotchen200][elliotchen200-x] on 𝕏 or [@cyfyifanchen][cyfyifanchen-github] on GitHub for project updates, discussions, and collaboration opportunities.

<br>

![divider][divider-light]
![divider][divider-dark]

### Code Contributors

[![TEN][contributors-image]][contributors]

### Contribution Guidelines

Contributions are welcome! Please read the [contribution guidelines][contribution-guidelines-doc] first.

<br>

![divider][divider-light]
![divider][divider-dark]

### License

This project is licensed under the [Apache License 2.0][license].

<!-- <br>

## Acknowledgments

- [Memos][memos] — Inspiration for memory system design
- [Nemori][nemori] — Self-organizing long-term memory concepts -->

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

<!-- Dividers -->
[divider-light]: https://github.com/user-attachments/assets/aec54c94-ced9-4683-ae58-0a5a7ed803bd#gh-light-mode-only
[divider-dark]: https://github.com/user-attachments/assets/d57fad08-4f49-4a1c-bdfc-f659a5d86150#gh-dark-mode-only

<!-- Header Badges -->
[arxiv-badge]: https://img.shields.io/badge/arXiv-EverMemOS_Paper-F5C842?labelColor=gray&style=flat-square&logo=arxiv&logoColor=white
[arxiv-link]: https://arxiv.org/abs/2601.02163
[release-badge]: https://img.shields.io/github/v/release/EverMind-AI/EverMemOS?color=369eff&labelColor=gray&logo=github&style=flat-square
[release-date-badge]: https://img.shields.io/github/release-date/EverMind-AI/EverMemOS?labelColor=gray&style=flat-square
[commits-badge]: https://img.shields.io/github/commit-activity/m/EverMind-AI/EverMemOS?labelColor=gray&color=pink&style=flat-square
[issues-closed-badge]: https://img.shields.io/github/issues-search?query=repo%3AEverMind-AI%2FEverMemOS%20is%3Aclosed&label=issues%20closed&labelColor=gray&color=green&style=flat-square
[contributors-badge]: https://img.shields.io/github/contributors/EverMind-AI/EverMemOS?color=c4f042&labelColor=gray&style=flat-square
[license-badge]: https://img.shields.io/badge/License-Apache%202.0-blue?labelColor=gray&labelColor=F5C842&style=flat-square

<!-- Tech Stack Badges -->
[python-badge]: https://img.shields.io/badge/Python-3.10+-blue?labelColor=gray&style=flat-square&logo=python&logoColor=white&labelColor=F5C842
[docker-badge]: https://img.shields.io/badge/Docker-Supported-4A90E2?labelColor=gray&style=flat-square&logo=docker&logoColor=white&labelColor=F5C842
[fastapi-badge]: https://img.shields.io/badge/FastAPI-Latest-26A69A?labelColor=gray&style=flat-square&logo=fastapi&logoColor=white&labelColor=F5C842
[mongodb-badge]: https://img.shields.io/badge/MongoDB-7.0+-00C853?labelColor=gray&style=flat-square&logo=mongodb&logoColor=white&labelColor=F5C842
[elasticsearch-badge]: https://img.shields.io/badge/Elasticsearch-8.x-0084FF?labelColor=gray&style=flat-square&logo=elasticsearch&logoColor=white&labelColor=F5C842
[milvus-badge]: https://img.shields.io/badge/Milvus-2.4+-00A3E0?labelColor=gray&style=flat-square&labelColor=F5C842

<!-- Language Badges -->
[lang-en-badge]: https://img.shields.io/badge/English-lightgrey?style=flat-square
[lang-zh-badge]: https://img.shields.io/badge/简体中文-lightgrey?style=flat-square

<!-- Community Badges -->
[discord-badge]: https://img.shields.io/badge/Discord-EverMemOS-5865F2?style=flat-square&logo=discord&logoColor=white
[x-badge]: https://img.shields.io/badge/X-EverMemOS-000000?style=flat-square&logo=x&logoColor=white
[linkedin-badge]: https://img.shields.io/badge/LinkedIn-EverMemOS-0A66C2?style=flat-square&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyBmaWxsPSIjZmZmIiByb2xlPSJpbWciIHZpZXdCb3g9IjAgMCAyNCAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48dGl0bGU%2BTGlua2VkSW48L3RpdGxlPjxwYXRoIGQ9Ik0yMC40NDcgMjAuNDUyaC0zLjU1NHYtNS41NjljMC0xLjMyOC0uMDI3LTMuMDM3LTEuODUyLTMuMDM3LTEuODUzIDAtMi4xMzYgMS40NDUtMi4xMzYgMi45Mzl2NS42NjdIOS4zNTFWOWgzLjQxNHYxLjU2MWguMDQ2Yy40NzctLjkgMS42MzctMS44NSAzLjM3LTEuODUgMy42MDEgMCA0LjI2NyAyLjM3IDQuMjY3IDUuNDU1djYuMjg2ek01LjMzNyA3LjQzM2MtMS4xNDQgMC0yLjA2My0uOTI2LTIuMDYzLTIuMDY1IDAtMS4xMzguOTItMi4wNjMgMi4wNjMtMi4wNjMgMS4xNCAwIDIuMDY0LjkyNSAyLjA2NCAyLjA2MyAwIDEuMTM5LS45MjUgMi4wNjUtMi4wNjQgMi4wNjV6bTEuNzgyIDEzLjAxOUgzLjU1NVY5aDMuNTY0djExLjQ1MnpNMjIuMjI1IDBIMS43NzFDLjc5MiAwIDAgLjc3NCAwIDEuNzI5djIwLjU0MkMwIDIzLjIyNy43OTIgMjQgMS43NzEgMjRoMjAuNDUxQzIzLjIgMjQgMjQgMjMuMjI3IDI0IDIyLjI3MVYxLjcyOUMyNCAuNzc0IDIzLjIgMCAyMi4yMjIgMGguMDAzeiIvPjwvc3ZnPg%3D%3D
[reddit-badge]: https://img.shields.io/badge/Reddit-EverMemOS-FF4500?style=flat-square&logo=reddit&logoColor=white

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
[discord]: https://discord.gg/gYep5nQRZJ
[x]: https://x.com/EverMindAI
[linkedin]: https://www.linkedin.com/company/evermind-ai/
[reddit]: https://www.reddit.com/r/EverMindAI/

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

<!-- Share Badges (dark gray #555) -->
[share-linkedin-link]: https://linkedin.com/feed/?shareActive=true&text=Check%20this%20GitHub%20repository%20out%20%F0%9F%A4%AF%20EverMemOS%20-%20An%20open-source%20intelligent%20memory%20system%20for%20conversational%20AI.%20Let%20every%20interaction%20be%20driven%20by%20understanding.%20https%3A%2F%2Fgithub.com%2FEverMind-AI%2FEverMemOS%20%23AI%20%23Memory%20%23LLM
[share-linkedin-shield]: https://img.shields.io/badge/-Share%20on%20Linkedin-555?labelColor=555&style=flat-square&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyBmaWxsPSIjZmZmIiByb2xlPSJpbWciIHZpZXdCb3g9IjAgMCAyNCAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48dGl0bGU%2BTGlua2VkSW48L3RpdGxlPjxwYXRoIGQ9Ik0yMC40NDcgMjAuNDUyaC0zLjU1NHYtNS41NjljMC0xLjMyOC0uMDI3LTMuMDM3LTEuODUyLTMuMDM3LTEuODUzIDAtMi4xMzYgMS40NDUtMi4xMzYgMi45Mzl2NS42NjdIOS4zNTFWOWgzLjQxNHYxLjU2MWguMDQ2Yy40NzctLjkgMS42MzctMS44NSAzLjM3LTEuODUgMy42MDEgMCA0LjI2NyAyLjM3IDQuMjY3IDUuNDU1djYuMjg2ek01LjMzNyA3LjQzM2MtMS4xNDQgMC0yLjA2My0uOTI2LTIuMDYzLTIuMDY1IDAtMS4xMzguOTItMi4wNjMgMi4wNjMtMi4wNjMgMS4xNCAwIDIuMDY0LjkyNSAyLjA2NCAyLjA2MyAwIDEuMTM5LS45MjUgMi4wNjUtMi4wNjQgMi4wNjV6bTEuNzgyIDEzLjAxOUgzLjU1NVY5aDMuNTY0djExLjQ1MnpNMjIuMjI1IDBIMS43NzFDLjc5MiAwIDAgLjc3NCAwIDEuNzI5djIwLjU0MkMwIDIzLjIyNy43OTIgMjQgMS43NzEgMjRoMjAuNDUxQzIzLjIgMjQgMjQgMjMuMjI3IDI0IDIyLjI3MVYxLjcyOUMyNCAuNzc0IDIzLjIgMCAyMi4yMjIgMGguMDAzeiIvPjwvc3ZnPg%3D%3D
[share-mastodon-link]: https://mastodon.social/share?text=Check%20this%20GitHub%20repository%20out%20%F0%9F%A4%AF%20EverMemOS%20-%20An%20open-source%20intelligent%20memory%20system%20for%20conversational%20AI.%20Let%20every%20interaction%20be%20driven%20by%20understanding.%20https://github.com/EverMind-AI/EverMemOS%20%23AI%20%23Memory%20%23LLM
[share-mastodon-shield]: https://img.shields.io/badge/-Share%20on%20Mastodon-555?labelColor=555&logo=mastodon&logoColor=white&style=flat-square
[share-reddit-link]: https://www.reddit.com/submit?title=Check%20this%20GitHub%20repository%20out%20%F0%9F%A4%AF%20EverMemOS%20-%20An%20open-source%20intelligent%20memory%20system%20for%20conversational%20AI.%20Let%20every%20interaction%20be%20driven%20by%20understanding.%20%23AI%20%23Memory%20%23LLM&url=https%3A%2F%2Fgithub.com%2FEverMind-AI%2FEverMemOS
[share-reddit-shield]: https://img.shields.io/badge/-Share%20on%20Reddit-555?labelColor=555&logo=reddit&logoColor=white&style=flat-square
[share-telegram-link]: https://t.me/share/url?text=Check%20this%20GitHub%20repository%20out%20%F0%9F%A4%AF%20EverMemOS%20-%20An%20open-source%20intelligent%20memory%20system%20for%20conversational%20AI.%20Let%20every%20interaction%20be%20driven%20by%20understanding.%20%23AI%20%23Memory%20%23LLM&url=https%3A%2F%2Fgithub.com%2FEverMind-AI%2FEverMemOS
[share-telegram-shield]: https://img.shields.io/badge/-Share%20on%20Telegram-555?labelColor=555&logo=telegram&logoColor=white&style=flat-square
[share-weibo-link]: http://service.weibo.com/share/share.php?sharesource=weibo&title=Check%20this%20GitHub%20repository%20out%20%F0%9F%A4%AF%20EverMemOS%20-%20An%20open-source%20intelligent%20memory%20system%20for%20conversational%20AI.%20Let%20every%20interaction%20be%20driven%20by%20understanding.%20%23AI%20%23Memory%20%23LLM&url=https%3A%2F%2Fgithub.com%2FEverMind-AI%2FEverMemOS
[share-weibo-shield]: https://img.shields.io/badge/-Share%20on%20Weibo-555?labelColor=555&logo=sinaweibo&logoColor=white&style=flat-square
[share-whatsapp-link]: https://api.whatsapp.com/send?text=Check%20this%20GitHub%20repository%20out%20%F0%9F%A4%AF%20EverMemOS%20-%20An%20open-source%20intelligent%20memory%20system%20for%20conversational%20AI.%20Let%20every%20interaction%20be%20driven%20by%20understanding.%20https%3A%2F%2Fgithub.com%2FEverMind-AI%2FEverMemOS%20%23AI%20%23Memory%20%23LLM
[share-whatsapp-shield]: https://img.shields.io/badge/-Share%20on%20Whatsapp-555?labelColor=555&logo=whatsapp&logoColor=white&style=flat-square
[share-x-link]: https://x.com/intent/tweet?hashtags=AI%2CMemory%2CLLM&text=Check%20this%20GitHub%20repository%20out%20%F0%9F%A4%AF%20EverMemOS%20-%20An%20open-source%20intelligent%20memory%20system%20for%20conversational%20AI.%20Let%20every%20interaction%20be%20driven%20by%20understanding.&url=https%3A%2F%2Fgithub.com%2FEverMind-AI%2FEverMemOS
[share-x-shield]: https://img.shields.io/badge/-Share%20on%20X-555?labelColor=555&logo=x&logoColor=white&style=flat-square
