SYSTEM_PROMPT = """你是 Claude Code Skill 架构师，负责把书籍骨架和章节 Markdown 整合为正式 SKILL.md。
只输出完整 SKILL.md，不输出 JSON，不使用代码块包裹。"""

USER_PROMPT_TEMPLATE = """请根据以下材料输出完整 SKILL.md。

书名：{book_title}
作者：{author}
slug：{slug}
章节数：{chapter_count}
生成日期：{generated_date}

知识骨架：
{spine_md}

章节 Markdown：
{chapters_md}

必须输出以下结构：

---
name: {slug}
description: 基于《{book_title}》蒸馏的 AI 技能。当需要运用作者的核心框架、方法论时使用。也可在用户询问标志性概念时激活。
allowed-tools: Read
---

# 《{book_title}》
**作者**：{author} | **章节**：{chapter_count}章 | **生成日期**：{generated_date}

## 如何使用这个 Skill
- `/{slug}` — 加载核心心智模型和框架总览
- `/{slug} <主题>` — 查找主题索引，定位对应章节
- `/{slug} ch<N>` — 深入阅读指定章节
- 问我“有哪些章节？”查看完整目录

## 全书核心论点
<2-3句>

## 核心框架与心智模型
<约2000字，6-10个最重要的框架。每个框架写清是什么、何时使用、如何使用，并标注来源章节。>

### 概念关系图
- 框架A → 框架B（理论基础）
- 框架C ↔ 框架D（互补）
- 框架E → 框架F（实践路径）

## 章节索引
| 编号 | 标题 | 核心框架 | 文件 |
|------|------|---------|------|
| 1 | xxx | f1, f2 | [ch01](chapters/01-xxx.md) |

## 主题索引
- **术语A** → 第1章、第3章
- **术语B** → 第2章

## 触发场景
- 当用户询问<主题X> → 查阅第Y章
- 当用户需要运用<方法论Z> → 使用<框架W>

## 支持文件
- [术语表](guides/glossary.md)

## 范围与限制
本 Skill 覆盖《{book_title}》的内容。不包含书中未涉及的领域知识。

要求：
- 输出完整 SKILL.md，不做 JSON 包装。
- name 必须是英文小写 slug：{slug}
- description 要说清楚什么时候用这个 skill。
- 主题索引是关键导航层，尽可能完整。
- 概念关系图至少 3 条边。
- 不要出现 JSON 字段名如 chapter_number。
"""
