SYSTEM_PROMPT = """你是一个 Claude Code Skill 架构师。
你需要把书籍骨架和章节萃取结果整合成一致、去重、可执行的 Skill 设计，并只输出合法 JSON。"""

USER_PROMPT_TEMPLATE = """请整合以下分析结果。

书籍骨架 JSON：
{skeleton_json}

章节分析 JSON：
{chapters_json}

输出 JSON 字段：
- skill_name
- description
- core_principles
- workflows
- checklists
- examples
- anti_patterns
"""
