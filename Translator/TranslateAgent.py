import json
from typing import List, Dict, Optional, Tuple
from autogen import ConversableAgent

# --- 1. 翻译指令模板设计 ---

TRANSLATION_SYSTEM_PROMPT = """You are a professional, highly accurate translation engine.
Your goal is to translate the given segment from English to Chinese.

### CRITICAL RULES:
1. **Consistency**: Use the provided 'Terminology' for specific words.
2. **Tags/Placeholders**: Keep all placeholders like [[MASK_VAR_XXXX]] or [[EMAIL_XXXX]] EXACTLY as they are. DO NOT translate or modify them.
3. **Style**: Follow the style of the 'Translation Memory' if provided.
4. **Output**: Return ONLY the translated text. No explanations, no notes.

### DETERMINISTIC REQUIREMENT:
- Produce the most literal and contextually accurate translation.
- Maintain a formal and technical tone.
"""


# --- 2. 翻译代理类实现 ---

class TranslationEngine:
    def __init__(self, llm_config: Dict):
        # 强制覆盖确定性参数
        deterministic_config = llm_config.copy()
        deterministic_config.update({
            "temperature": 0,
            "seed": 42,
            "cache_seed": 42,
        })

        self.agent = ConversableAgent(
            name="Translation_Agent",
            system_message=TRANSLATION_SYSTEM_PROMPT,
            llm_config=deterministic_config,
            human_input_mode="NEVER",
        )

    def construct_prompt(self, segment: str, terms: List[Dict], tm: List[Dict]) -> str:
        """
        组装最终发送给大模型的 Prompt
        """
        prompt = f"Target Segment: {segment}\n\n"

        if terms:
            prompt += "### Terminology Reference (MUST USE):\n"
            for t in terms:
                prompt += f"- {t['term']} -> {t['translation']}\n"
            prompt += "\n"

        if tm:
            prompt += "### Translation Memory (Style Reference):\n"
            for entry in tm:
                prompt += f"Source: {entry['src']}\nTarget: {entry['tgt']}\n"
            prompt += "\n"

        prompt += "Translated Chinese Text:"
        return prompt


# --- 3. 模拟工作流组装逻辑 ---

def run_translation_phase(config_list):
    # 1. 初始化翻译引擎
    engine = TranslationEngine({"config_list": config_list})

    # 2. 获取之前步骤的模拟数据
    # 假设这是从前面的 Registry 中汇总的信息
    from Preprocess.PreprocessAgent import registry as pre_reg
    from Retriever.RetrieveAgent import storage  # 模拟从检索代理获取

    # 模拟一个处理好的上下文数据结构
    processed_data = [
        {
            "id": 0,
            "masked_seg": "The [[MASK_VAR_A1B2]] workflow is deterministic.",
            "terms": [{"term": "workflow", "translation": "工作流"},
                      {"term": "deterministic", "translation": "确定性"}],
            "tm": [{"src": "The workflow is highly deterministic.", "tgt": "该工作流具有高度确定性。"}]
        }
    ]

    translated_results = []

    print(">>> 开始执行确定性翻译...\n")

    for item in processed_data:
        # 组装 Prompt
        final_prompt = engine.construct_prompt(
            item["masked_seg"],
            item["terms"],
            item["tm"]
        )

        # 调用 Agent (此处会触发 LLM 调用)
        # 实际上在 AutoGen 中，这里可以使用 client.create 或是 initiate_chat
        # 为了演示逻辑，我们展示如何发送消息
        response = engine.agent.generate_reply(messages=[{"content": final_prompt, "role": "user"}])

        translated_results.append({
            "id": item["id"],
            "original_masked": item["masked_seg"],
            "translation": response
        })

        print(f"Segment {item['id']} Translation: {response}")

    return translated_results


# --- 4. 运行模拟 (需要配置 API KEY) ---

if __name__ == "__main__":
    # 实际运行时请替换为真实配置
    config_list = [{"model": "gpt-4-turbo", "api_key": ""}]

    # 注意：如果没有 API Key，这段代码在执行 generate_reply 时会报错。
    # 这里主要展示组装逻辑。
    try:
        results = run_translation_phase(config_list)
    except Exception as e:
        print(f"\n[注意] LLM 调用失败（正常现象，因为未配置 Key）: {e}")
        print("\n但是 Prompt 组装逻辑如下：")
        # 打印一下组装出来的最终 Prompt 样式
        from Retriever.RetrieveAgent import storage

        test_engine = TranslationEngine({"config_list": []})
        sample_prompt = test_engine.construct_prompt(
            "Use [[MASK_VAR_XYZ]] for AutoGen.",
            [{"term": "AutoGen", "translation": "自动智能体框架"}],
            []
        )
        print(sample_prompt)