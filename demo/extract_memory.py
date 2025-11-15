import asyncio
import json
from pathlib import Path
import httpx

from demo.tools.clear_all_data import clear_all_memories


def load_conversation_data(file_path: str) -> tuple:
    """从 JSON 文件加载对话数据
    
    Returns:
        tuple: (messages, group_id, group_name)
    """
    data_file = Path(file_path)
    if not data_file.exists():
        raise FileNotFoundError(f"数据文件不存在: {file_path}")
    
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 提取消息列表和元信息
    messages = data.get('conversation_list', [])
    conversation_meta = data.get('conversation_meta', {})
    group_id = conversation_meta.get('group_id', 'unknown_group')
    group_name = conversation_meta.get('name', 'unknown')
    
    # 为每条消息添加 group_id 和 group_name
    for msg in messages:
        msg['group_id'] = group_id
        msg['group_name'] = group_name
    
    print(f"从 {file_path} 加载了 {len(messages)} 条消息")
    print(f"group_id: {group_id}")
    print(f"group_name: {group_name}")
    
    return messages, group_id, group_name


async def test_v3_memorize_api():
    """测试 V3 API 的 /memorize 接口（单条消息存储）"""

    await clear_all_memories()
    
    base_url = "http://localhost:8001" 
    memorize_url = f"{base_url}/api/v3/agentic/memorize"  # 正确的路由路径
    
    print("=" * 100)
    print("🧪 测试 V3 API HTTP 接口 - 记忆存储")
    print("=" * 100)
    
    # 加载真实对话数据
    data_file = "data/assistant_chat_zh.json"
    try:
        test_messages, group_id, group_name = load_conversation_data(data_file)
    except FileNotFoundError as e:
        print(f"❌ 错误: {e}")
        return False
    
    profile_scene = "assistant"
    
    print(f"\n📤 Sending {len(test_messages)} messages to V3 API")
    print(f"   URL: {memorize_url}")
    print(f"   Profile scene: {profile_scene}")
    print()
    print("ℹ️  How it works:")
    print("   • Messages accumulate in Redis until boundary condition is met")
    print("   • '⏳ Queued' = Message stored, waiting for extraction trigger")
    print("   • '✓ Extracted' = Boundary detected, memories saved to database")
    print()
    
    total_accumulated = 0
    total_extracted = 0
    
    async with httpx.AsyncClient(timeout=500.0) as client:
        for idx, message in enumerate(test_messages, 1):
            print(f"[{idx}/{len(test_messages)}] {message['sender']}: {message['content'][:40]}...")
            
            # 为每条消息添加 scene 字段
            message['scene'] = profile_scene
            
            try:
                response = await client.post(
                    memorize_url,
                    json=message,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    saved_count = result.get("result", {}).get("count", 0)
                    status_info = result.get("result", {}).get("status_info", "unknown")
                    
                    if status_info == "accumulated":
                        total_accumulated += 1
                        print(f"   ⏳ Queued")
                    elif status_info == "extracted":
                        total_extracted += saved_count
                        print(f"   ✓ Extracted {saved_count} memories")
                    else:
                    
                        if saved_count > 0:
                            total_extracted += saved_count
                            print(f"   ✓ Extracted {saved_count} memories")
                        else:
                            total_accumulated += 1
                            print(f"   ⏳ Queued")
                else:
                    print(f"   ✗ Failed: HTTP {response.status_code}")
                    print(f"      {response.text[:200]}")
                    
            except httpx.ConnectError:
                print(f"   ✗ Connection failed: Unable to connect to {base_url}")
                print(f"      Ensure V3 API service is running")
                return False
            except httpx.ReadTimeout:
                print(f"   ⚠ Timeout: Processing exceeded 500s")
                print(f"      Skipping message and continuing...")
                continue  # 跳过超时的消息，继续处理下一条
            except Exception as e:
                print(f"   ✗ Error: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                return False

    print("\n" + "=" * 100)
    print("✓ Test completed successfully")
    print("\n📊 Summary:")
    print(f"   Total messages:    {len(test_messages)}")
    print(f"   Queued:            {total_accumulated}")
    print(f"   Extracted:         {total_extracted}")
    
    if total_accumulated > 0 and total_extracted == 0:
        print("\nℹ️  Note: All messages are queued, awaiting boundary detection trigger")
        print(f"   Check queue: redis-cli -p 6479 -n 8 LLEN chat_history:{group_id}")
    elif total_extracted > 0:
        print("\n✓ Memory extraction successful")
        print("   View in database:")
        print("   • MemCells: db.memcells.find()")
        print("   • Episodes: db.episodememory.find()")
    
    print("\n📝 Next steps:")
    print("   Run retrieval test: python src/bootstrap.py demo/tools/test_retrieval_comprehensive.py")
    print("=" * 100)
    
    return True

if __name__ == "__main__":
    asyncio.run(test_v3_memorize_api())