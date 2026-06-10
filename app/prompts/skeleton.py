SYSTEM_PROMPT = """你是一个擅长将书籍萃取为 Claude Code Skill 的结构化阅读专家。
你的任务是识别一本书的核心论点、框架、章节脉络和术语，并只输出合法 JSON。"""

USER_PROMPT_TEMPLATE = """请基于以下材料生成书籍骨架分析。

目录：
{toc}

前言：
{preface}

章节速览：
{chapter_glimpses}

输出 JSON 字段：
- thesis: 全书核心论点
- frameworks: 可迁移的方法论框架列表
- chapter_index: 章节索引和作用
- glossary: 关键术语
- distillable_score: 0 到 1 的可萃取评分
"""
