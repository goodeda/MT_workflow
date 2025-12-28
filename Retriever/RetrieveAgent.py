import re
from typing import List, Dict, Union, Optional, Tuple, Annotated
from autogen import ConversableAgent


# --- 1. 模拟底层检索驱动 (生产环境需替换为 ES/Milvus 客户端) ---

class MockStorage:
    def __init__(self):
        # 模拟术语表
        self.glossary = {
            "AutoGen": "自动智能体框架",
            "workflow": "工作流",
            "deterministic": "确定性"
        }
        # 模拟翻译记忆库
        self.tm_data = [
            {"src": "The workflow is highly deterministic.", "tgt": "该工作流具有高度确定性。"},
            {"src": "Using AutoGen for complex tasks.", "tgt": "使用 AutoGen 处理复杂任务。"}
        ]

    def exact_term_match(self, text: str) -> List[Dict]:
        found = []
        for k, v in self.glossary.items():
            if k.lower() in text.lower():
                found.append({"term": k, "translation": v})
        return found

    def hybrid_tm_match(self, text: str) -> List[Dict]:
        # 此处应为：关键词检索(BM25) + 向量检索(Vector) 的融合结果
        # 暂时用简单逻辑模拟
        results = []
        for entry in self.tm_data:
            if any(word.lower() in entry["src"].lower() for word in text.split() if len(word) > 3):
                results.append(entry)
        return results


storage = MockStorage()


# --- 2. 术语 Agent 逻辑 (TerminologyAgent) ---

def terminology_reply_func(
        recipient: ConversableAgent,
        messages: Optional[List[Dict[str, str]]] = None,
        sender: Optional[ConversableAgent] = None,
        config: Optional[any] = None,
) -> Tuple[bool, Union[str, Dict]]:
    """
    专门负责术语精准检索的 Agent 逻辑
    """
    last_msg = messages[-1].get("content", "")
    # 假设消息中包含需要处理的 Segments（实际开发中可从全局状态 Registry 读取）
    # 这里演示针对单段文本的处理
    matches = storage.exact_term_match(last_msg)

    response = "--- Terminology Results ---\n"
    if matches:
        for m in matches:
            response += f"Found Term: {m['term']} -> {m['translation']}\n"
    else:
        response += "No matching terms found."

    return True, response


# --- 3. 翻译记忆 Agent 逻辑 (MemoryRetrieverAgent) ---

def memory_reply_func(
        recipient: ConversableAgent,
        messages: Optional[List[Dict[str, str]]] = None,
        sender: Optional[ConversableAgent] = None,
        config: Optional[any] = None,
) -> Tuple[bool, Union[str, Dict]]:
    """
    负责 TM 记忆库混合检索的 Agent 逻辑
    """
    last_msg = messages[-1].get("content", "")
    matches = storage.hybrid_tm_match(last_msg)

    response = "--- Translation Memory Results ---\n"
    if matches:
        for m in matches:
            response += f"Matched TM: {m['src']} | {m['tgt']}\n"
    else:
        response += "No similar translation memory found."

    return True, response


# --- 4. 构建代理架构 ---

def setup_retrieval_system():
    # 术语 Agent
    terminology_agent = ConversableAgent(
        name="TerminologyAgent",
        llm_config=False,
        human_input_mode="NEVER"
    )
    terminology_agent.register_reply(
        [ConversableAgent, None],
        reply_func=terminology_reply_func,
        position=0
    )

    # 翻译记忆 Agent
    memory_agent = ConversableAgent(
        name="MemoryRetrieverAgent",
        llm_config=False,
        human_input_mode="NEVER"
    )
    memory_agent.register_reply(
        [ConversableAgent, None],
        reply_func=memory_reply_func,
        position=0
    )

    # 协调者 (User Proxy)
    user_proxy = ConversableAgent(
        name="Admin",
        llm_config=False,
        human_input_mode="NEVER"
    )

    return user_proxy, terminology_agent, memory_agent


# --- 5. 执行模拟 ---

if __name__ == "__main__":
    admin, term_agent, mem_agent = setup_retrieval_system()

    test_segment = "How to design a deterministic workflow using AutoGen?"

    print(f">>> 待检索段落: {test_segment}\n")

    # 分别调度两个 Agent 获取结果
    # 在生产环境下，这里可以用 GroupChatManager 或异步并行触发
    admin.initiate_chat(term_agent, message=test_segment, max_turns=1)
    print("-" * 30)
    admin.initiate_chat(mem_agent, message=test_segment, max_turns=1)