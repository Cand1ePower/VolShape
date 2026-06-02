import sys
import os
import asyncio

# 添加当前目录到 sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.mem0_client import memory_client, add_memory_async, search_memory_async

async def main():
    print("Testing mem0 memory client initialization and functionality...")
    
    test_user = "test_user_12345"
    test_messages = [{"role": "user", "content": "我平时只喜欢在下午两点后练腿，因为那时候力量最充足。"}]
    
    print("\n1. Testing adding memory...")
    await add_memory_async(test_messages, user_id=test_user)
    print("Successfully called add_memory_async (run in executor)")
    
    # 等待一会，因为 add_memory 是异步执行在 executor 中的，且 mem0 提取记忆需要请求 LLM 和 Embedding
    print("Waiting 5 seconds for memory extraction to complete...")
    await asyncio.sleep(5)
    
    print("\n2. Testing searching memory...")
    search_res = await search_memory_async("腿部训练时间", user_id=test_user)
    print(f"Search results for '腿部训练时间':\n{search_res}")
    
    if search_res:
        print("\nSUCCESS: Memory was successfully stored and retrieved!")
    else:
        print("\nWARNING: Search returned empty. Check if DeepSeek API and Embedding API are working and if key is valid.")

if __name__ == "__main__":
    asyncio.run(main())
