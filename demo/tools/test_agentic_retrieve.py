"""Agentic Retrieval Complete Test Script

Follows the same logic as test_retrieval_comprehensive.py:
- Multi-scenario testing (Personal, Group, Multi-dimensional)
- Statistics summary (Success rate, multi-round ratio, average latency)
- Export results to JSON

Usage:
    # Ensure API server is started
    uv run python src/run.py --port 8001
    
    # Run test in another terminal
    uv run python src/bootstrap.py demo/tools/test_agentic_retrieve.py
    
    # Or use Mock LLM (no real API Key needed)
    uv run python src/bootstrap.py demo/tools/test_agentic_retrieve.py --mock-llm
"""

import asyncio
import httpx
import os
from typing import List, Dict, Any, Optional
from common_utils.datetime_utils import get_now_with_timezone

try:
    from aiohttp import web
except ImportError:
    web = None


class AgenticRetrievalTester:
    """Agentic Retrieval Tester"""

    def __init__(self, base_url: str = "http://localhost:8001"):
        """Initialize tester

        Args:
            base_url: API server address
        """
        self.base_url = base_url
        self.retrieve_url = f"{base_url}/api/v3/agentic/retrieve_agentic"

        # Test Result Statistics
        self.total_tests = 0
        self.successful_tests = 0
        self.failed_tests = 0
        self.test_results = []

        # Agentic Specific Statistics
        self.multi_round_count = 0
        self.sufficient_count = 0

    async def test_agentic(
        self,
        query: str,
        user_id: str,
        group_id: str = None,
        top_k: int = 10,
        time_range_days: int = 365,
        llm_config: Dict[str, Any] = None,
        test_name: str = None,
    ) -> Dict[str, Any]:
        """Execute single Agentic retrieval test

        Args:
            query: Query text
            user_id: User ID
            group_id: Group ID
            top_k: Number of results
            time_range_days: Time range (days)
            llm_config: LLM configuration
            test_name: Test name

        Returns:
            Test result dictionary
        """
        self.total_tests += 1

        if test_name is None:
            test_name = f"agentic_{self.total_tests}"

        # Build request parameters
        payload = {
            "query": query,
            "user_id": user_id,
            "top_k": top_k,
            "time_range_days": time_range_days,
            "llm_config": llm_config or {},
        }

        if group_id:
            payload["group_id"] = group_id

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(self.retrieve_url, json=payload)
                response.raise_for_status()
                result = response.json()

                if result.get("status") == "ok":
                    memories = result.get("result", {}).get("memories", [])
                    metadata = result.get("result", {}).get("metadata", {})

                    # Extract Agentic specific info
                    is_multi_round = metadata.get("is_multi_round", False)
                    is_sufficient = metadata.get("is_sufficient", None)
                    reasoning = metadata.get("reasoning", "")
                    missing_info = metadata.get("missing_info", [])
                    refined_queries = metadata.get("refined_queries", [])
                    round1_count = metadata.get("round1_count", 0)
                    round2_count = metadata.get("round2_count", 0)
                    final_count = metadata.get("final_count", len(memories))
                    latency = metadata.get("total_latency_ms", 0)

                    # Update stats
                    if is_multi_round:
                        self.multi_round_count += 1
                    if is_sufficient:
                        self.sufficient_count += 1

                    self.successful_tests += 1
                    test_result = {
                        "test_name": test_name,
                        "status": "✅ Success",
                        "query": query,
                        "user_id": user_id,
                        "group_id": group_id,
                        "count": len(memories),
                        "latency_ms": latency,
                        "is_multi_round": is_multi_round,
                        "is_sufficient": is_sufficient,
                        "reasoning": reasoning,
                        "missing_info": missing_info,
                        "refined_queries": refined_queries,
                        "round1_count": round1_count,
                        "round2_count": round2_count,
                        "final_count": final_count,
                        "metadata": metadata,
                        "memories": memories[:3],  # Save only top 3
                    }

                    # Print detailed info
                    print(f"\n  ✅ {test_name}: Found {len(memories)} memories")
                    print(f"     Query: {query[:50]}{'...' if len(query) > 50 else ''}")
                    print(f"     Latency: {latency:.2f}ms")
                    print(f"     Multi-round: {'Yes' if is_multi_round else 'No'}")
                    print(f"     Sufficient: {'Yes' if is_sufficient else 'No'}")
                    if reasoning:
                        print(
                            f"     LLM Judgment: {reasoning[:60]}{'...' if len(reasoning) > 60 else ''}"
                        )
                    if refined_queries:
                        print(f"     Refined Queries: {refined_queries}")
                    print(
                        f"     Round1: {round1_count} items → Round2: {round2_count} items → Final: {final_count} items"
                    )

                    # Print summaries of top 3 memories
                    if memories:
                        print(f"\n     🎯 Top 3 Memory Summary:")
                        for i, mem in enumerate(memories[:3], 1):
                            score = mem.get('score', 0)
                            subject = mem.get('subject', '')
                            summary = mem.get('summary', '')
                            episode = mem.get('episode', '')
                            content = subject or summary or episode[:60]
                            print(
                                f"       [{i}] Score: {score:.4f} | {content[:50]}{'...' if len(content) > 50 else ''}"
                            )

                    return test_result
                else:
                    self.failed_tests += 1
                    error_msg = result.get('message', 'Unknown error')
                    print(f"  ❌ {test_name}: Retrieval failed - {error_msg}")
                    return {
                        "test_name": test_name,
                        "status": "❌ Failed",
                        "error": error_msg,
                    }

        except httpx.ConnectError:
            self.failed_tests += 1
            print(f"  ❌ {test_name}: Cannot connect to API server")
            return {
                "test_name": test_name,
                "status": "❌ Connection Failed",
                "error": "Cannot connect to API server",
            }
        except Exception as e:
            self.failed_tests += 1
            print(f"  ❌ {test_name}: Exception - {e}")
            return {"test_name": test_name, "status": "❌ Exception", "error": str(e)}

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("📊 Agentic Retrieval Test Summary")
        print("=" * 80)
        print(f"Total Tests: {self.total_tests}")
        print(f"Success: {self.successful_tests} ✅")
        print(f"Failed: {self.failed_tests} ❌")
        if self.total_tests > 0:
            print(f"Success Rate: {(self.successful_tests/self.total_tests*100):.1f}%")

        # Agentic Specific Stats
        print(f"\n🔍 Agentic Feature Stats:")
        if self.successful_tests > 0:
            print(
                f"  Multi-round: {self.multi_round_count}/{self.successful_tests} ({(self.multi_round_count/self.successful_tests*100):.1f}%)"
            )
            print(
                f"  LLM Sufficient: {self.sufficient_count}/{self.successful_tests} ({(self.sufficient_count/self.successful_tests*100):.1f}%)"
            )

        # Average Latency
        successful_results = [
            r for r in self.test_results if r.get("status") == "✅ Success"
        ]
        if successful_results:
            avg_latency = sum(r.get("latency_ms", 0) for r in successful_results) / len(
                successful_results
            )
            avg_count = sum(r.get("count", 0) for r in successful_results) / len(
                successful_results
            )
            print(f"\n📈 Average Metrics:")
            print(f"  Avg Latency: {avg_latency:.2f}ms")
            print(f"  Avg Recall: {avg_count:.1f} items")

        # Failed Test Details
        failed_results = [
            r for r in self.test_results if r.get("status") != "✅ Success"
        ]
        if failed_results:
            print("\n❌ Failed Tests:")
            for r in failed_results:
                print(f"  - {r.get('test_name')}: {r.get('error', 'Unknown error')}")

    def export_results(
        self, output_file: str = "demo/results/agentic_test_results.json"
    ):
        """Export test results to JSON file

        Args:
            output_file: Output file path
        """
        import json
        from pathlib import Path

        # Ensure output directory exists
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build export data
        export_data = {
            "test_time": get_now_with_timezone().isoformat(),
            "summary": {
                "total_tests": self.total_tests,
                "successful_tests": self.successful_tests,
                "failed_tests": self.failed_tests,
                "success_rate": (
                    f"{(self.successful_tests/self.total_tests*100):.1f}%"
                    if self.total_tests > 0
                    else "0%"
                ),
                "multi_round_count": self.multi_round_count,
                "sufficient_count": self.sufficient_count,
            },
            "test_results": self.test_results,
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Test results saved to: {output_file}")


async def start_mock_llm(port: int = 9001) -> Optional["web.AppRunner"]:
    """Start Mock LLM Server"""
    if web is None:
        raise RuntimeError(
            "aiohttp is required to enable Mock LLM, please run first: uv add aiohttp"
        )

    import json

    async def handle(request: web.Request) -> web.Response:
        data = await request.json()
        prompt = data.get("messages", [{}])[0].get("content", "")

        # Return different responses based on prompt content
        if "改进查询" in prompt or "Refine query" in prompt:  # skip-i18n-check
            # Multi-query generation
            content = json.dumps(
                {
                    "queries": [
                        "What are the user's favorite restaurants?",
                        "robot_001's taste preferences?",
                        "User's dietary habits and restrictions?",
                    ],
                    "reasoning": "mock refinement: Generated multiple complementary queries",
                },
                ensure_ascii=False,
            )
        else:
            # Sufficiency check
            content = json.dumps(
                {
                    "is_sufficient": True,
                    "reasoning": "mock sufficient: Retrieval results are sufficient",
                    "missing_information": [],
                },
                ensure_ascii=False,
            )

        return web.json_response(
            {
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 50,
                    "completion_tokens": 15,
                    "total_tokens": 65,
                },
            }
        )

    app = web.Application()
    app.router.add_post("/chat/completions", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    print(f"✅ Mock LLM Started: http://127.0.0.1:{port}/chat/completions")
    return runner


async def main():
    """Main Test Function"""

    print("=" * 80)
    print("🧪 Agentic Retrieval Complete Test")
    print("=" * 80)
    print(
        "\nThis test will systematically test multiple scenarios of Agentic Retrieval:"
    )
    print("  1. Personal memory query (no group_id)")
    print("  2. Group memory query (with group_id)")
    print("  3. Multi-dimensional deep dive query (complex question)")
    print(
        "\n⚠️  Please ensure API server is started: uv run python src/bootstrap.py src/run.py --port 8001"
    )

    # Check if LLM API Key exists
    api_key = (
        os.getenv("OPENROUTER_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("LLM_API_KEY")
    )
    base_url = (
        os.getenv("OPENROUTER_BASE_URL")
        or os.getenv("LLM_BASE_URL")
        or "https://openrouter.ai/api/v1"
    )
    model = os.getenv("LLM_MODEL") or "qwen/qwen3-235b-a22b-2507"

    use_mock = False
    mock_runner = None

    if not api_key:
        print(
            "\n⚠️  LLM API Key not detected (OPENROUTER_API_KEY/OPENAI_API_KEY/LLM_API_KEY)"
        )
        print("   Will use Mock LLM for testing (Simulated LLM response)")
        use_mock = True
    else:
        print(f"\n✅ Detected LLM Configuration:")
        print(f"   Base URL: {base_url}")
        print(f"   Model: {model}")
        print(f"   API Key: {api_key[:10]}...")

    print("\n⏳ Starting test...")

    # Start Mock LLM (if needed)
    if use_mock:
        try:
            mock_runner = await start_mock_llm(port=9001)
            api_key = "mock-key"
            base_url = "http://127.0.0.1:9001"
            model = "mock-llm"
            await asyncio.sleep(0.2)  # Wait for server start
        except Exception as e:
            print(f"❌ Failed to start Mock LLM: {e}")
            print("   Hint: To use Mock LLM, please install: uv add aiohttp")
            return

    # LLM Config
    llm_config = {"api_key": api_key, "base_url": base_url, "model": model}

    try:
        # Create Tester
        tester = AgenticRetrievalTester()

        # ========== Test Scenario 1: Personal Memory Query ==========
        print("\n" + "🔬" * 40)
        print("Test Scenario 1: Personal Memory Query (No group_id)")
        print("🔬" * 40)

        result1 = await tester.test_agentic(
            query="Beijing travel food recommendations",  # Keep query in English if data supports it, or Chinese if data is Chinese
            user_id="robot_001",
            group_id=None,
            top_k=10,
            time_range_days=365,
            llm_config=llm_config,
            test_name="Scenario1_PersonalMemory",
        )
        tester.test_results.append(result1)
        await asyncio.sleep(1)

        # ========== Test Scenario 2: Group Memory Query ==========
        print("\n" + "🔬" * 40)
        print("Test Scenario 2: Group Memory Query (With group_id)")
        print("🔬" * 40)

        result2 = await tester.test_agentic(
            query="Beijing food and travel recommendations",
            user_id="robot_001",
            group_id="chat_user_001_assistant",
            top_k=15,
            time_range_days=365,
            llm_config=llm_config,
            test_name="Scenario2_GroupMemory",
        )
        tester.test_results.append(result2)
        await asyncio.sleep(1)

        # ========== Test Scenario 3: Multi-dimensional Deep Dive ==========
        print("\n" + "🔬" * 40)
        print("Test Scenario 3: Multi-dimensional Deep Dive (Complex Question)")
        print("🔬" * 40)

        result3 = await tester.test_agentic(
            query="What are the user's personality traits, interests, dietary preferences, and travel habits?",
            user_id="robot_001",
            group_id="chat_user_001_assistant",
            top_k=20,
            time_range_days=365,
            llm_config=llm_config,
            test_name="Scenario3_MultiDim",
        )
        tester.test_results.append(result3)
        await asyncio.sleep(1)

        # ========== Test Scenario 4: Short Period Query ==========
        print("\n" + "🔬" * 40)
        print("Test Scenario 4: Short Period Query (Within 30 days)")
        print("🔬" * 40)

        result4 = await tester.test_agentic(
            query="Recent Beijing travel plans",
            user_id="robot_001",
            group_id="chat_user_001_assistant",
            top_k=10,
            time_range_days=30,
            llm_config=llm_config,
            test_name="Scenario4_ShortPeriod",
        )
        tester.test_results.append(result4)

        # ========== Print Summary ==========
        tester.print_summary()

        # ========== Export Results ==========
        tester.export_results()

        print("\n" + "=" * 80)
        print("✅ Agentic Retrieval Test Completed!")
        print("=" * 80)

    finally:
        # Cleanup Mock LLM
        if mock_runner:
            await mock_runner.cleanup()
            print("\n✅ Mock LLM Closed")


if __name__ == "__main__":
    asyncio.run(main())
