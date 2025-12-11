"""Comprehensive Memory Retrieval Test

Test all retrieval mode combinations:
- Data Source: episode, event_log, foresight
- Memory Scope: personal, group, all
- Retrieval Mode: bm25, embedding, rrf
- Profile Data Source: Only test fixed user_id + group_id combination (memory_scope / retrieval mode not applicable)

Usage:
    # Ensure API server is started
    uv run python src/run.py --port 8001
    
    # Run test in another terminal
    uv run python src/bootstrap.py demo/tools/test_retrieval_comprehensive.py
"""

import asyncio
import httpx
from typing import List, Dict, Any
from common_utils.datetime_utils import get_now_with_timezone
import time
from common_utils.language_utils import get_prompt_language


def get_test_query() -> str:
    """Get test query based on current language setting"""
    lang = get_prompt_language()
    return "运动" if lang == "zh" else "Sports"  # skip-i18n-check


class RetrievalTester:
    """Comprehensive Retrieval Tester"""

    def __init__(self, base_url: str = "http://localhost:8001"):
        """Initialize Tester

        Args:
            base_url: API server address
        """
        self.base_url = base_url
        self.retrieve_url = f"{base_url}/api/v3/agentic/retrieve_lightweight"

        # Test Configuration
        self.data_sources = ["episode", "event_log", "foresight", "profile"]
        self.memory_scopes = ["personal", "group"]
        self.retrieval_modes = ["embedding", "bm25", "rrf"]

        # Test Results Statistics
        self.total_tests = 0
        self.successful_tests = 0
        self.failed_tests = 0
        self.test_results = []

        # Timing Statistics
        self.start_time = None
        self.end_time = None
        self.total_request_time = 0.0  # Accumulated request time
        self.max_latency = 0.0  # Max latency
        self.min_latency = float('inf')  # Min latency

    async def test_retrieval(
        self,
        query: str,
        data_source: str,
        memory_scope: str,
        retrieval_mode: str,
        user_id: str = "test_user",
        group_id: str = None,
        top_k: int = 5,
        current_time: str = None,
        allow_empty: bool = False,
    ) -> Dict[str, Any]:
        """Execute single retrieval test

        Args:
            query: Query text
            data_source: Data source (episode/event_log/foresight/profile)
            memory_scope: Memory scope (personal/group)
            retrieval_mode: Retrieval mode (embedding/bm25/rrf)
            user_id: User ID
            group_id: Group ID
            top_k: Number of results
            current_time: Current time (valid only for foresight)

        Returns:
            Test result dictionary
        """
        self.total_tests += 1

        # Record single request start time
        request_start_time = time.time()

        # Build request payload
        payload = {
            "query": query,
            "user_id": user_id,
            "group_id": group_id,
            "top_k": top_k,
            "data_source": data_source,
            "retrieval_mode": retrieval_mode,
        }

        # Add optional parameters
        if current_time and data_source == "foresight":
            payload["current_time"] = current_time

        test_name = f"{data_source}_{memory_scope}_{retrieval_mode}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.retrieve_url, json=payload)
                response.raise_for_status()
                result = response.json()

                # Calculate single request elapsed time
                request_elapsed = (
                    time.time() - request_start_time
                ) * 1000  # Convert to ms
                self.total_request_time += request_elapsed

                if result.get("status") == "ok":
                    memories = result.get("result", {}).get("memories", [])
                    metadata = result.get("result", {}).get("metadata", {})
                    latency = metadata.get("total_latency_ms", 0)

                    # Update max/min latency
                    if latency > 0:
                        self.max_latency = max(self.max_latency, latency)
                        self.min_latency = min(self.min_latency, latency)

                    if len(memories) == 0:
                        if allow_empty:
                            self.successful_tests += 1
                            info_msg = f"{test_name}: Allowed empty result (took {latency:.2f}ms)"
                            print(f"  ✅ {info_msg}")
                            empty_result = {
                                "test_name": test_name,
                                "status": "✅ Success",
                                "query": query,
                                "data_source": data_source,
                                "retrieval_mode": retrieval_mode,
                                "count": 0,
                                "latency_ms": latency,
                                "metadata": metadata,
                                "memories": [],
                                "note": "allow_empty",
                            }
                            return empty_result
                        # Treat 0 results as failure for easier debugging
                        self.failed_tests += 1
                        warning_msg = (
                            f"{test_name}: Returned 0 memories (took {latency:.2f}ms)"
                        )
                        print(f"  ⚠️ {warning_msg}")
                        return {
                            "test_name": test_name,
                            "status": "⚠️ Empty Result",
                            "query": query,
                            "data_source": data_source,
                            "retrieval_mode": retrieval_mode,
                            "count": 0,
                            "latency_ms": latency,
                            "metadata": metadata,
                            "memories": [],
                        }

                    self.successful_tests += 1
                    test_result = {
                        "test_name": test_name,
                        "status": "✅ Success",
                        "query": query,
                        "data_source": data_source,
                        "retrieval_mode": retrieval_mode,
                        "count": len(memories),
                        "latency_ms": latency,
                        "request_time_ms": request_elapsed,  # Add full request time
                        "metadata": metadata,
                        "memories": memories[:3],  # Only save first 3
                    }

                    # Print scores (first 3)
                    score_info = ""
                    scores = [f"{m.get('score', 0):.4f}" for m in memories[:3]]
                    score_info = f", scores: [{', '.join(scores)}]"

                    print(
                        f"  ✅ {test_name}: Found {len(memories)} memories, API took {latency:.2f}ms, Total took {request_elapsed:.2f}ms{score_info}"
                    )

                    if data_source == "profile" and memories:
                        profile_entry = memories[0]
                        profile_data = profile_entry.get("profile") or {}
                        print("    👤 Profile Details (First Sample):")
                        print(
                            f"      user_id={profile_entry.get('user_id')}, "
                            f"group_id={profile_entry.get('group_id')}, "
                            f"version={profile_entry.get('version')}, "
                            f"scenario={profile_entry.get('scenario')}, "
                            f"updated_at={profile_entry.get('updated_at')}"
                        )
                        summary_text = profile_data.get("summary") or profile_data.get(
                            "output_reasoning"
                        )
                        if summary_text:
                            short_summary = summary_text[:80] + (
                                "..." if len(summary_text) > 80 else ""
                            )
                            print(f"      Summary: {short_summary}")
                        interests = profile_data.get("interests") or []
                        if interests:
                            interest_names = ", ".join(
                                [
                                    item.get("value")
                                    for item in interests[:3]
                                    if isinstance(item, dict) and item.get("value")
                                ]
                            )
                            if interest_names:
                                print(f"      Interests: {interest_names}")

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

    async def run_comprehensive_test(
        self,
        query: str,
        user_id: str = "test_user",
        group_id: str = None,
        current_time: str = None,
        query_overrides: Dict[str, str] | None = None,
        profile_group_id: str | None = None,
    ):
        """Run Comprehensive Retrieval Test

        Args:
            query: Query text
            user_id: User ID
            group_id: Group ID
            current_time: Current time (YYYY-MM-DD)
        """
        # Record test start time
        if self.start_time is None:
            self.start_time = time.time()

        print("\n" + "=" * 80)
        print(f"🧪 Starting Comprehensive Retrieval Test")
        print(f"   Query: {query}")
        print(f"   User ID: {user_id}")
        print(f"   Group ID: {group_id or 'None'}")
        print(f"   Current Time: {current_time or 'None'}")
        print("=" * 80)

        # Iterate through all combinations
        query_overrides = query_overrides or {}
        for data_source in self.data_sources:
            print(f"\n📊 Data Source: {data_source}")
            print("-" * 80)

            if data_source == "profile":
                profile_gid = profile_group_id or group_id
                if not profile_gid:
                    print("  ⚠️ Skipping profile test: missing group_id")
                    continue

                effective_query = query_overrides.get(data_source, query)
                print("\n  📁 Memory Scope: user_id + group_id (Fixed)")
                result = await self.test_retrieval(
                    query=effective_query or "",
                    data_source="profile",
                    memory_scope="group",
                    retrieval_mode="rrf",
                    user_id="user_001",
                    group_id=profile_gid,
                    current_time=current_time,
                )
                self.test_results.append(result)
                continue

            for memory_scope in self.memory_scopes:
                if memory_scope == "group":
                    user_id = None
                    group_id = "chat_user_001_assistant"
                if memory_scope == "personal":
                    user_id = "user_001"
                    group_id = "chat_user_001_assistant"
                print(f"\n  📁 Memory Scope: {memory_scope}")

                for retrieval_mode in self.retrieval_modes:
                    effective_query = query_overrides.get(data_source, query)
                    effective_group_id = group_id
                    if data_source == "profile":
                        effective_group_id = profile_group_id or group_id
                        if effective_group_id is None:
                            print("  ⚠️ Skipping profile test: missing group_id")
                            continue
                    result = await self.test_retrieval(
                        query=effective_query,
                        memory_scope=memory_scope,
                        data_source=data_source,
                        retrieval_mode=retrieval_mode,
                        user_id=user_id,
                        group_id=effective_group_id,
                        current_time=current_time,
                    )
                    self.test_results.append(result)

                    # Short delay to avoid hitting rate limits

    def print_summary(self):
        """Print Test Summary"""
        # Record test end time
        if self.end_time is None:
            self.end_time = time.time()

        total_elapsed = self.end_time - self.start_time if self.start_time else 0

        print("\n" + "=" * 80)
        print("📊 Test Summary")
        print("=" * 80)
        print(f"Total Tests: {self.total_tests}")
        print(f"Success: {self.successful_tests} ✅")
        print(f"Failed: {self.failed_tests} ❌")
        print(f"Success Rate: {(self.successful_tests/self.total_tests*100):.1f}%")

        # ⏱️ Timing Statistics
        print("\n⏱️  Performance Stats:")
        print(f"  Total Test Time: {total_elapsed:.2f}s")
        print(f"  Total Request Time: {self.total_request_time/1000:.2f}s")
        print(
            f"  Avg Request Time: {self.total_request_time/self.total_tests:.2f}ms"
            if self.total_tests > 0
            else "  Avg Request Time: N/A"
        )
        print(
            f"  Max API Latency: {self.max_latency:.2f}ms"
            if self.max_latency > 0
            else "  Max API Latency: N/A"
        )
        print(
            f"  Min API Latency: {self.min_latency:.2f}ms"
            if self.min_latency != float('inf')
            else "  Min API Latency: N/A"
        )

        # Stats by Data Source
        print("\n📈 By Data Source:")
        for data_source in self.data_sources:
            source_results = [
                r for r in self.test_results if r.get("data_source") == data_source
            ]
            success = len(
                [r for r in source_results if r.get("status") == "✅ Success"]
            )
            total = len(source_results)
            avg_count = (
                sum(r.get("count", 0) for r in source_results if r.get("count")) / total
                if total > 0
                else 0
            )
            avg_latency = (
                sum(
                    r.get("latency_ms", 0)
                    for r in source_results
                    if r.get("latency_ms")
                )
                / total
                if total > 0
                else 0
            )
            print(
                f"  {data_source}: {success}/{total} success, avg {avg_count:.1f} items, avg latency {avg_latency:.2f}ms"
            )

        # Stats by Retrieval Mode
        print("\n🔍 By Retrieval Mode:")
        for mode in self.retrieval_modes:
            mode_results = [
                r for r in self.test_results if r.get("retrieval_mode") == mode
            ]
            success = len([r for r in mode_results if r.get("status") == "✅ Success"])
            total = len(mode_results)
            avg_latency = (
                sum(r.get("latency_ms", 0) for r in mode_results if r.get("latency_ms"))
                / total
                if total > 0
                else 0
            )
            print(
                f"  {mode}: {success}/{total} success, avg latency {avg_latency:.2f}ms"
            )

        # Stats by Memory Scope
        print("\n📁 By Memory Scope:")
        for scope in self.memory_scopes:
            scope_results = [
                r for r in self.test_results if r.get("memory_scope") == scope
            ]
            success = len([r for r in scope_results if r.get("status") == "✅ Success"])
            total = len(scope_results)
            avg_count = (
                sum(r.get("count", 0) for r in scope_results if r.get("count")) / total
                if total > 0
                else 0
            )
            print(
                f"  {scope}: {success}/{total} success, avg returned {avg_count:.1f} items"
            )

        # Failed Tests Details
        failed_results = [
            r for r in self.test_results if r.get("status") != "✅ Success"
        ]
        if failed_results:
            print("\n❌ Failed Tests:")
            for r in failed_results:
                print(f"  - {r.get('test_name')}: {r.get('error', 'Unknown error')}")

    def export_results(
        self, output_file: str = "demo/results/retrieval_test_results.json"
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

        # Add timing info to export data
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
                "total_elapsed_seconds": (
                    round(self.end_time - self.start_time, 2)
                    if self.start_time and self.end_time
                    else 0
                ),
                "total_request_time_ms": round(self.total_request_time, 2),
                "avg_request_time_ms": (
                    round(self.total_request_time / self.total_tests, 2)
                    if self.total_tests > 0
                    else 0
                ),
                "max_latency_ms": (
                    round(self.max_latency, 2) if self.max_latency > 0 else 0
                ),
                "min_latency_ms": (
                    round(self.min_latency, 2)
                    if self.min_latency != float('inf')
                    else 0
                ),
            },
            "test_results": self.test_results,
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Test results saved to: {output_file}")


async def main():
    """Main Test Function"""

    # Record overall test start time
    overall_start_time = time.time()

    print("=" * 80)
    print("🧪 Comprehensive Memory Retrieval Test")
    print("=" * 80)
    print("\nThis test will systematically test all retrieval mode combinations:")
    print("  - Data Source: episode, event_log, foresight (Full 3×3×3 combination)")
    print("  - Profile Data Source: Only fixed user_id + group_id direct retrieval")
    print(
        "  - Retrieval Mode: embedding, bm25, rrf (Only applicable to non-profile data sources)"
    )
    print(
        f"\nTotal Tests: 3 × 3 × 3 + profile(1) = 28 combinations (Profile skipped if missing group_id)"
    )
    print(
        "\n⚠️  Please ensure API server is started: uv run python src/bootstrap.py src/run.py --port 8001"
    )
    print("\nPress Enter to continue...")
    input()

    # Create Tester
    tester = RetrievalTester()

    # Get query based on language setting
    test_query = get_test_query()
    print(f"\n🌐 Language: {get_prompt_language()}, Query: {test_query}")

    # ========== Test 1: Personal Memory Query ==========
    print("\n" + "🔬" * 40)
    print("Test Scenario 1: Personal Memory Query")
    print("🔬" * 40)
    test1_start = time.time()

    await tester.run_comprehensive_test(
        query=test_query,
        user_id="user_001",  # Use actual user_id in DB
        group_id=None,  # Do not specify group_id
        current_time=None,  # No current_time to avoid filtering expired group foresight
        query_overrides={
            # "event_log": "Beijing travel and food recommendation",  # Commented out English query
            "profile": "profile summary"
        },
        profile_group_id="chat_user_001_assistant",
    )
    test1_elapsed = time.time() - test1_start
    print(f"\n⏱️  Scenario 1 Duration: {test1_elapsed:.2f}s")

    # ========== Test 2: Group Memory Query ==========
    print("\n" + "🔬" * 40)
    print("Test Scenario 2: Group Memory Query")
    print("🔬" * 40)
    test2_start = time.time()

    await tester.run_comprehensive_test(
        query=test_query,
        user_id="user_001",  # Use actual user_id in DB
        group_id="chat_user_001_assistant",  # Use actual group_id in DB
        current_time=None,  # No current_time to avoid filtering expired group foresight
        query_overrides={
            # "event_log": "Beijing food and travel",  # Commented out English query
            "profile": "profile summary"
        },
        profile_group_id="chat_user_001_assistant",
    )
    test2_elapsed = time.time() - test2_start
    print(f"\n⏱️  Scenario 2 Duration: {test2_elapsed:.2f}s")

    # ========== Test 3: Foresight Specific Test (Validity Filtering) ==========
    print("\n" + "🔬" * 40)
    print("Test Scenario 3: Foresight Validity Filtering")
    print("🔬" * 40)
    test3_start = time.time()

    # Test currently valid foresight
    print("\n  📅 Sub-test 3.1: Retrieve currently valid foresight")
    result_current = await tester.test_retrieval(
        query=test_query,
        data_source="foresight",
        memory_scope="personal",
        retrieval_mode="rrf",
        user_id="user_001",  # Use actual user_id in DB
        current_time=get_now_with_timezone().strftime("%Y-%m-%d"),
    )

    # Test future time (should return more memories)
    print(
        "\n  📅 Sub-test 3.2: Retrieve foresight for future time (includes long-term predictions)"
    )
    result_future = await tester.test_retrieval(
        query=test_query,
        data_source="foresight",
        memory_scope="personal",
        retrieval_mode="rrf",
        user_id="user_001",  # Use actual user_id in DB
        current_time="2027-12-31",  # Future time
        allow_empty=True,
    )

    # Test past time (should return fewer memories)
    print("\n  📅 Sub-test 3.3: Retrieve foresight for past time (expired memories)")
    result_past = await tester.test_retrieval(
        query=test_query,
        data_source="foresight",
        memory_scope="personal",
        retrieval_mode="rrf",
        user_id="user_001",  # Use actual user_id in DB
        current_time="2024-01-01",  # Past time
        allow_empty=True,
    )

    test3_elapsed = time.time() - test3_start

    print(f"\n  📊 Time Filtering Comparison:")
    print(f"     Past (2024-01-01): {result_past.get('count', 0)} items")
    print(
        f"     Current ({get_now_with_timezone().strftime('%Y-%m-%d')}): {result_current.get('count', 0)} items"
    )
    print(f"     Future (2027-12-31): {result_future.get('count', 0)} items")
    print(f"\n⏱️  Scenario 3 Duration: {test3_elapsed:.2f}s")

    # ========== Print Summary ==========
    tester.print_summary()

    # Overall Duration
    overall_elapsed = time.time() - overall_start_time
    print(f"\n⏱️  Overall Test Duration: {overall_elapsed:.2f}s")
    print(
        f"   Scenario 1: {test1_elapsed:.2f}s ({test1_elapsed/overall_elapsed*100:.1f}%)"
    )
    print(
        f"   Scenario 2: {test2_elapsed:.2f}s ({test2_elapsed/overall_elapsed*100:.1f}%)"
    )
    print(
        f"   Scenario 3: {test3_elapsed:.2f}s ({test3_elapsed/overall_elapsed*100:.1f}%)"
    )

    # ========== Export Results ==========
    tester.export_results()

    print("\n" + "=" * 80)
    print("✅ Comprehensive Retrieval Test Completed!")
    print("=" * 80)


async def demo_foresight_evidence():
    """Demo Foresight Evidence Field Usage"""

    print("\n" + "=" * 80)
    print("💡 Foresight Evidence Field Demo")
    print("=" * 80)

    base_url = "http://localhost:8001"
    retrieve_url = f"{base_url}/api/v3/agentic/retrieve_lightweight"

    print("\n📖 Scenario Description:")
    print(
        "   User removed wisdom tooth → System generates foresight: 'Prefer soft food'"
    )
    print("   Evidence field storage reason: 'Just removed wisdom tooth'")
    print(
        "   When user queries 'recommended food', they can see the recommendation basis"
    )

    test_query = get_test_query()
    payload = {
        "query": test_query,
        "user_id": "robot_001",  # Use actual user_id in DB
        "data_source": "foresight",
        "retrieval_mode": "rrf",
        "top_k": 5,
        "current_time": get_now_with_timezone().strftime("%Y-%m-%d"),
    }

    print(f"\n🔍 Query: {payload['query']}")
    print(f"   Data Source: foresight")
    print(f"   Current Time: {payload['current_time']}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(retrieve_url, json=payload)
            response.raise_for_status()
            result = response.json()

            if result.get("status") == "ok":
                memories = result.get("result", {}).get("memories", [])
                metadata = result.get("result", {}).get("metadata", {})

                print(f"\n✅ Retrieval Success: Found {len(memories)} foresight items")
                print(f"   Latency: {metadata.get('total_latency_ms', 0):.2f}ms")

                if memories:
                    print("\n📝 Foresight Details (including evidence):")
                    for i, mem in enumerate(memories[:5], 1):
                        print(f"\n  [{i}] Relevance: {mem.get('score', 0):.4f}")
                        print(f"      Content: {mem.get('episode', '')[:100]}")

                        # Highlight Evidence Field
                        evidence = mem.get('evidence', '')
                        if evidence:
                            print(f"      🔍 Evidence: {evidence}")

                        # Show Time Range
                        timestamp = mem.get('timestamp', '')
                        if timestamp:
                            if isinstance(timestamp, str):
                                print(f"      ⏰ Time: {timestamp[:10]}")
                            else:
                                print(f"      ⏰ Time: {timestamp}")

                        # Show Metadata
                        metadata_detail = mem.get('metadata', {})
                        if metadata_detail:
                            print(f"      📋 Metadata: {metadata_detail}")
                else:
                    print("\n  💡 No related foresight found")
                    print("     Possible reasons:")
                    print(
                        "     1. Foresight not generated yet (need to run extract_memory.py first)"
                    )
                    print("     2. Query not relevant to existing foresight")
                    print("     3. Foresight expired (end_time < current_time)")
            else:
                print(f"\n❌ Retrieval Failed: {result.get('message')}")

    except httpx.ConnectError:
        print(f"\n❌ Cannot connect to API server ({base_url})")
        print(
            "   Please start service first: uv run python src/bootstrap.py src/run.py --port 8001"
        )
    except Exception as e:
        print(f"\n❌ Exception: {e}")


async def main_menu():
    """Main Menu"""

    print("\n" + "=" * 80)
    print("🧪 Memory Retrieval Test Tool")
    print("=" * 80)
    print("\nSelect Test Mode:")
    print("  1. Comprehensive Retrieval Test (27 combinations)")
    print("  2. Foresight Evidence Demo")
    print("  3. Run Both")
    print("\n⚠️  Note: Ensure test data exists (run extract_memory.py)")
    print("\nEnter option (1/2/3): ", end="")

    choice = input().strip()

    if choice == "1":
        await main()
    elif choice == "2":
        await demo_foresight_evidence()
    elif choice == "3":
        await main()
        await demo_foresight_evidence()
    else:
        print("❌ Invalid option, please re-run")


if __name__ == "__main__":
    asyncio.run(main_menu())
