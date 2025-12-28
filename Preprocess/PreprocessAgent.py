import re
import uuid
from typing import List, Dict, Union, Optional, Tuple
from autogen import ConversableAgent


# --- 1. 核心业务逻辑 (保持不变) ---

class TranslationRegistry:
    def __init__(self):
        self.mask_map: Dict[str, str] = {}
        self.segments: List[str] = []

    def reset(self):
        self.mask_map.clear()
        self.segments.clear()


registry = TranslationRegistry()


def local_masking_logic(text: str) -> str:
    patterns = {
        "EMAIL": r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+',
        "IP": r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
        "URL": r'https?://[^\s]+'
    }
    processed_text = text
    for label, pattern in patterns.items():
        def replace(match):
            original = match.group(0)
            placeholder = f"[[{label}_{uuid.uuid4().hex[:4].upper()}]]"
            registry.mask_map[placeholder] = original
            return placeholder

        processed_text = re.sub(pattern, replace, processed_text)
    return processed_text


def local_splitting_logic(text: str) -> List[str]:
    sentence_delimiters = r'(?<=[。！？\.!\?])\s*'
    sentences = re.split(sentence_delimiters, text)
    return [s.strip() for s in sentences if s.strip()]


# --- 2. 修正后的 AutoGen 回复逻辑 ---

def preprocessor_reply_func(
        recipient: ConversableAgent,
        messages: Optional[List[Dict[str, str]]] = None,
        sender: Optional[ConversableAgent] = None,
        config: Optional[any] = None,
) -> Tuple[bool, Union[str, Dict]]:
    """
    符合 AutoGen 规范的回复函数。
    返回: (是否终止后续回复逻辑, 回复内容)
    """
    if not messages:
        return True, "No message received."

    # 获取最后一条消息内容
    last_msg = messages[-1].get("content", "")

    registry.reset()
    # 执行处理
    masked_text = local_masking_logic(last_msg)
    registry.segments = local_splitting_logic(masked_text)

    # 构造输出
    output = "--- 预处理完成 ---\n"
    output += f"分段数量: {len(registry.segments)}\n"
    for i, s in enumerate(registry.segments):
        output += f"段落 {i + 1}: {s}\n"

    # 返回 True 表示该代理已处理完毕，不需要再调用其他回复钩子或 LLM
    return True, output


# --- 3. 代理设置 ---

def setup_local_workflow():
    # 执行者：Regex_Preprocessor
    executor_agent = ConversableAgent(
        name="Regex_Preprocessor",
        llm_config=False,
        human_input_mode="NEVER",
    )

    # 关键：使用 register_reply 正确注册本地代码逻辑
    executor_agent.register_reply(
        [ConversableAgent, None],
        reply_func=preprocessor_reply_func,
        position=0
    )

    # 用户端
    user_proxy = ConversableAgent(
        name="User_Proxy",
        llm_config=False,
        human_input_mode="NEVER"
    )

    return user_proxy, executor_agent


# --- 4. 运行测试 ---

if __name__ == "__main__":
    user, preprocessor = setup_local_workflow()

    test_input = (
        "Please contact support@example.com for further assistance. "
        "The server is located at 192.168.0.101! "
        "请访问我们的官网 https://openai.com 获取更多信息。我们要确保翻译的一致性。"
    )

    print(">>> 正在启动本地预处理流程...\n")

    # 启动对话
    user.initiate_chat(
        preprocessor,
        message=test_input,
        max_turns=1
    )

    print("\n>>> 最终提取的脱敏映射表 (Registry):")
    for placeholder, original in registry.mask_map.items():
        print(f"{placeholder} => {original}")