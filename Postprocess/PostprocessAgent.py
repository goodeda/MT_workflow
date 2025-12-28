import re
from typing import List, Dict, Tuple, Optional, Union
from autogen import ConversableAgent, GroupChat, GroupChatManager


# --- 1. 全局状态存储 (沿用之前的思路) ---

class PostProcessRegistry:
    def __init__(self):
        # 存储翻译后的中间结果
        self.translated_segments: Dict[int, str] = {}
        self.final_outputs: Dict[int, str] = {}
        # 记录重试次数，防止无限循环
        self.retry_count: Dict[int, int] = {}


post_registry = PostProcessRegistry()


# --- 2. 核心后处理逻辑函数 (供 Agent 调用) ---

def check_tags_consistency(original_masked: str, translated_text: str) -> Tuple[bool, str]:
    """
    检查标签一致性：从原文和译文中提取 [[...]]，对比是否完全一致
    """
    pattern = r"\[\[.*?\]\]"
    original_tags = set(re.findall(pattern, original_masked))
    translated_tags = set(re.findall(pattern, translated_text))

    missing = original_tags - translated_tags
    extra = translated_tags - original_tags

    if missing or extra:
        error_msg = f"Tag mismatch! Missing: {missing}, Extra: {extra}"
        return False, error_msg
    return True, "Tags are consistent."


def perform_final_reduction(text: str, mask_map: Dict[str, str]) -> str:
    """
    物理还原：将占位符替换回原始敏感数据
    """
    final_text = text
    for placeholder, original in mask_map.items():
        final_text = final_text.replace(placeholder, original)
    return final_text


# --- 3. 代理定义 ---

def setup_post_processing_agents(config_list: List[Dict]):
    # 3.1 质量检查员 (Inspector)
    inspector_agent = ConversableAgent(
        name="Inspector_Agent",
        system_message="""你是一个翻译质量检查员。
        1. 检查译文是否存在严重的语法错误或漏译。
        2. 检查译文是否遵循了术语表。
        如果翻译质量不合格，请回复 'REJECT:' 并给出改进建议。
        如果合格，请回复 'APPROVED'。""",
        llm_config={"config_list": config_list, "temperature": 0},
        human_input_mode="NEVER",
    )

    # 3.2 标签校验员 (TagChecker - 纯代码逻辑)
    tag_checker_agent = ConversableAgent(
        name="Tag_Checker",
        llm_config=False,
        human_input_mode="NEVER",
    )

    def tag_check_reply(recipient, messages, sender, config):
        # 模拟从上下文中获取原文和译文进行对比
        # 实际开发中需通过消息历史解析
        last_msg = messages[-1]["content"]
        # 这里仅为逻辑演示：假设检查失败
        is_ok, msg = check_tags_consistency("[[MASK_1]] test", last_msg)
        if not is_ok:
            return True, f"REJECT: {msg}. Please re-translate and fix the tags."
        return True, "TAG_OK"

    tag_checker_agent.register_reply([ConversableAgent, None], tag_check_reply, position=0)

    # 3.3 润色专家 (Polisher)
    polisher_agent = ConversableAgent(
        name="Polisher_Agent",
        system_message="""你是一个翻译润色专家。
        你的职责是在保持原意和标签[[...]]不变的前提下，让中文译文更加地道、流畅。
        仅输出润色后的文本。""",
        llm_config={"config_list": config_list, "temperature": 0.3},  # 润色可以稍微有一点点创造力
        human_input_mode="NEVER",
    )

    # 3.4 还原代理 (Reid_Agent)
    reid_agent = ConversableAgent(
        name="Reid_Agent",
        llm_config=False,
        human_input_mode="NEVER",
    )

    return inspector_agent, tag_checker_agent, polisher_agent, reid_agent


# --- 4. 状态流转控制 (FSM 逻辑规划) ---

def state_transition_logic(last_speaker, groupchat):
    """
    定义翻译工作流的后处理流转顺序
    """
    messages = groupchat.messages
    last_content = messages[-1]["content"] if messages else ""

    # 1. 如果翻译刚完成 -> 交给标签检查员
    if last_speaker.name == "Translation_Agent":
        return groupchat.agent_by_name("Tag_Checker")

    # 2. 如果标签检查通过 -> 交给质量检查员
    if last_speaker.name == "Tag_Checker":
        if "TAG_OK" in last_content:
            return groupchat.agent_by_name("Inspector_Agent")
        else:
            # 标签不合格 -> 打回翻译代理
            return groupchat.agent_by_name("Translation_Agent")

    # 3. 如果质量检查完成
    if last_speaker.name == "Inspector_Agent":
        if "REJECT" in last_content:
            # 质量不合格 -> 打回翻译代理
            return groupchat.agent_by_name("Translation_Agent")
        else:
            # 质量合格 -> 交给润色专家
            return groupchat.agent_by_name("Polisher_Agent")

    # 4. 润色完成后 -> 最终还原
    if last_speaker.name == "Polisher_Agent":
        return groupchat.agent_by_name("Reid_Agent")

    return None


# --- 5. 模拟执行流 ---

if __name__ == "__main__":
    # 此处假设我们已经有了前面的配置
    config = [{"model": "gpt-4", "api_key": "dummy"}]

    inspect, tags, polish, reid = setup_post_processing_agents(config)

    # 模拟一个被打回的场景
    print(">>> [模拟运行] 开始后处理流程...")
    print("1. Tag_Checker 检查中...")
    # 逻辑测试：假设标签缺失
    ok, error = check_tags_consistency("[[MASK_1]]", "翻译结果中丢失了标签")
    if not ok:
        print(f"   [状态: 失败] {error}")
        print("   [决策: 打回] 重新触发 Translation_Agent 进行修复。")

    print("\n2. Reid_Agent 最终还原测试...")
    mock_mask_map = {"[[EMAIL_123]]": "support@autogen.ai"}
    mock_translated = "请联系 [[EMAIL_123]] 获取支持。"
    final = perform_final_reduction(mock_translated, mock_mask_map)
    print(f"   [原始译文]: {mock_translated}")
    print(f"   [还原结果]: {final}")