SYSTEM_PROMPT = """你是一个将单章内容萃取为可操作知识模块的分析器。
你需要提取框架、方法、案例、反模式和行动步骤，并只输出合法 JSON。"""

USER_PROMPT_TEMPLATE = """请分析以下章节。

章节编号：{chapter_number}
章节标题：{chapter_title}

章节内容：
{chapter_content}

输出 JSON 字段：
- chapter_number
- chapter_title
- frameworks
- methodologies
- cases
- anti_patterns
- actionable_steps
"""
