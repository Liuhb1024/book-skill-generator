# 大重构计划：对齐专业项目标准

> 基于 the-knowledge-guy、book-to-skill、Anthropic 官方 skills 规范的全面重构

---

## 目标

砍掉所有 JSON 输出，AI 直接写 Markdown。参照专业项目的 SKILL.md 格式、Prompt 设计、章节处理方式，彻底重做蒸馏管线。

---

## 架构变更

```
改造前（当前）：
  Stage 1: AI → JSON → Python json.loads → SkeletonOutput
  Stage 2: AI → JSON → Python json.loads → ChapterOutput → Pydantic 校验（大量失败）
  Stage 3: AI → JSON → Python 解析 → dict
  Stage 4: Python Jinja2 把 dict 渲染成 Markdown
  问题：JSON 解析是单点故障，int/str 类型不匹配导致 8/9 章数据全丢

改造后：
  Stage 1: AI → Markdown（spine.md，结构化但容错）
  Stage 2: AI → Markdown（每章一个 .md 文件，固定 heading 模板）
  Stage 3: AI → Markdown（SKILL.md 主体，整合所有章节结果）
  Stage 4: Python 组装 Markdown 文件（不解析、不转换，直接拼接）
  优势：LLM 输出 Markdown 天然容错，没有 JSON 解析失败风险
```

---

## 改什么

### Part A: 章节检测增强（Python 层）

文件：`app/parsers/chapter_detector.py`

**参照：** the-knowledge-guy 的 `parse_book_number_kind()` + `assign_book_numbers()`

新增能力：
1. 不仅识别"第X章"，还要识别：
   - `Chapter N`（英文）
   - `引言` / `Introduction` / `前言` / `Preface` → label 为 `intro`
   - `附录` / `Appendix` → label 为 `appendix`
   - `后记` / `后记` / `Epilogue` → label 为 `epilogue`
   - 纯数字标题 `1. xxx`、`2. xxx`

2. 章节编号规范化：
   - 中文数字（一、二、三...）→ 保留原样，同时生成阿拉伯数字版本
   - 每个章节同时有 `display_number`（用户看到的）和 `file_number`（文件名用的）

3. 前端/后置内容识别：
   - 版权页、目录、致谢 → 标记为 `fm`（front matter），不参与蒸馏
   - 索引、参考文献 → 标记为 `bm`（back matter），不参与蒸馏

4. 章节内容智能截断：
   - 每章内容传给 AI 前，首 8000 + 尾 8000 字（保留信息密度最高的部分）
   - 去掉纯空白行、页码标记等噪音

---

### Part B: Stage 1 重写（骨架提取）

文件：`app/pipeline/stage1_skeleton.py` + `app/prompts/skeleton.py`

**参照：** the-knowledge-guy 的 Pass 0 SPINE + concept-map-spec.md

不再输出 JSON。输出一个 Markdown 文件 `spine.md`，结构：

```markdown
# 《书名》知识骨架

## 全书核心论点
<100字内>

## 核心框架（6-10个）
### 框架名
- **是什么**：一句话
- **何时用**：触发条件
- **怎么用**：简要步骤
- **首次出现**：第X章

（重复6-10次）

## 章节主题索引
| 章节编号 | 标题 | 一句话主题 | 关键术语 |
|---------|------|-----------|---------|
| 1 | xxx | xxx | a, b, c |

## 关键术语表
| 术语 | 定义 | 所在章节 |
|------|------|---------|

## 概念关系
- 框架A → 是框架B的理论基础（第3章 → 第7章）
- 框架C ↔ 与框架D互补

## 可蒸馏度评估
- 评分：0.0-1.0
- 理由：一句话
```

Prompt 要点：
- 必须输出上述 Markdown 结构，逐段严格遵循
- 核心框架每一条都要包含"是什么、何时用、怎么用"
- 概念关系至少 3 条
- 不输出 JSON，不输出代码块

---

### Part C: Stage 2 重写（章节蒸馏）

文件：`app/pipeline/stage2_chapters.py` + `app/prompts/chapter.py`

**参照：** book-to-skill 的 Step 7 chapter template + the-knowledge-guy 的 chapter-template.md

这是最大的改动。不再输出 JSON，AI 直接写每章的 Markdown 文件。

每章输出的 Markdown 模板：

```markdown
# 第N章：完整标题

## 核心要旨
<1-2句话，本章最重要的一个观点>

## 本章框架
### 框架名
- **作者的精确表述**：<保持原书的命名>
- **何时使用**：<具体触发场景>
- **如何使用**：<步骤或标准>
- **书中案例**：<本章提到的具体例子>

（如本章有多个框架，重复以上结构）

## 关键概念
- **术语**：<一句话精确定义>（5-10个本章最重要的术语）

## 思维模型
<2-4条，用"当X时用Y"或"把X看作Y"的口吻写>

## 方法论/可执行步骤
1. 步骤一
2. 步骤二
...

## 反模式/常见误区
- **不要做X**：<为什么失败> — 正确做法是Y

## 关键收获
1. <实践者必须记住的可执行洞察>
2. ...
（3-7条）

## 与其他章节的关联
- 第X章：<关联原因>
```

Prompt 要点：
- 严格按上述 heading 结构输出
- 如果某节没有内容，写"本章未涉及"而不是省略
- 密度优先：每句话都要传递信息
- 实践者口吻："当X时用Y"
- 绝对不输出 JSON
- 不要抄原文，用自己的话重组

---

### Part D: Stage 3 重写（知识整合 → 直接生成 SKILL.md）

文件：`app/pipeline/stage3_integrate.py` + `app/prompts/integrate.py`

**参照：** the-knowledge-guy 的 Step 9 + Anthropic 官方 skills 规范 + book-to-skill 的 SKILL.md 模板

不再输出 JSON。直接生成 SKILL.md 的完整 Markdown 内容。

输出的 SKILL.md 结构：

```markdown
---
name: <小写英文slug，如"peak-deliberate-practice">
description: 基于《书名》蒸馏的 AI 技能。当需要运用<作者>的<核心框架1>、<核心框架2>、<核心框架3>等方法论时使用此技能。也可在用户询问<标志性概念>时激活。
allowed-tools: Read
---

# 《书名》
**作者**：XXX | **章节**：N章 | **生成日期**：YYYY-MM-DD

## 如何使用这个 Skill
- `/slug` — 加载核心心智模型和框架总览
- `/slug <主题>` — 我会查找主题索引，定位到对应章节
- `/slug ch<N>` — 深入阅读指定章节
- 问我"有哪些章节？"查看完整章节目录

## 全书核心论点
<2-3句，书的核心论点>

## 核心框架与心智模型
<约2000字，6-10个最重要的框架>
对每个框架：
- **框架名** — 是什么 + 何时用 + 怎么用，实践者口吻
- 标注来源章节

### 概念关系图
- 框架A → 框架B（理论基础）
- 框架C ↔ 框架D（互补关系）
- ...

## 章节索引
| 编号 | 标题 | 核心框架 | 文件 |
|------|------|---------|------|
| 1 | xxx | f1, f2 | [ch01](chapters/01-xxx.md) |
| 2 | xxx | f3 | [ch02](chapters/02-xxx.md) |

## 主题索引
- **术语A** / **同义词** → 第1章、第3章
- **术语B** → 第2章、第5章
（按字母/拼音排序）

## 触发场景
- 当用户询问关于<主题X>时 → 查阅第Y章
- 当用户需要运用<方法论Z>时 → 使用<框架W>
- ...

## 支持文件
- [术语表](guides/glossary.md)
- [速查表](guides/cheatsheet.md)

## 范围与限制
本 Skill 覆盖《书名》的内容。不包含书中未涉及的领域知识。
```

Prompt 要点：
- 输出完整的 SKILL.md Markdown，不做任何 JSON 包装
- 严格遵循 Anthropic skills 规范：YAML frontmatter 至少包含 name、description
- name 使用英文小写 slug
- description 要说清楚"什么时候用这个 skill"
- 主题索引是关键的导航层，必须完整

---

### Part E: Stage 4 简化（打包）

文件：`app/pipeline/stage4_package.py`

由于 Stage 2 和 3 已经直接输出 Markdown，Stage 4 不再需要 Jinja2 渲染。

改为：
1. 创建 Skill 目录结构
2. 将 Stage 1 的 spine.md 放入 `raw/` 目录
3. 将 Stage 2 的各章 Markdown 直接写入 `chapters/` 目录
4. 将 Stage 3 的 SKILL.md 内容直接写入 `SKILL.md`
5. 生成 README.md（保持 Jinja2）
6. 生成 glossary.md 和 cheatsheet.md（如果 Stage 1 产生了术语表数据）
7. 打包 zip

不再需要：
- Jinja2 SKILL.md 模板（AI 直接写了）
- JSON 解析逻辑
- dict → Markdown 转换函数

---

### Part F: 数据模型简化

文件：`app/models.py`

删除不再需要的模型：
- `SkeletonOutput` → 改为 spine.md 的路径
- `ChapterOutput` → 不再需要 Pydantic 校验，AI 直接写文件
- Stage 3 输出的 dict → 改为 SKILL.md 的文本内容

新增/保留的模型：
- `BookMeta`：保持
- `ChapterInfo`：保持（Python 层使用）
- `PipelineResult`：保持
- 新增 `ChapterLabel`：{index, display_number, file_number, title, kind}

---

## 改造后的文件清单

需要修改的文件：
- `app/parsers/chapter_detector.py` — 增强章节识别（Part A）
- `app/prompts/skeleton.py` — 重写为 Markdown 输出（Part B）
- `app/prompts/chapter.py` — 重写为 Markdown 输出（Part C）
- `app/prompts/integrate.py` — 重写为 SKILL.md 输出（Part D）
- `app/pipeline/stage1_skeleton.py` — 返回 spine.md 文本而非 SkeletonOutput 对象
- `app/pipeline/stage2_chapters.py` — 不再解析 JSON，AI 直接写 Markdown 文件
- `app/pipeline/stage3_integrate.py` — 不再解析 JSON，直接获取 SKILL.md 文本
- `app/pipeline/stage4_package.py` — 简化为文件组装，去掉 Jinja2 渲染
- `app/pipeline/runner.py` — 适配新的接口
- `app/models.py` — 删除 JSON 相关模型
- `app/main.py` — SSE 进度推送适配

可以删除的文件：
- `app/templates/SKILL.md.j2` — 不再需要
- `app/templates/README.md.j2` — 可以保留，但简化

---

## 验收标准

1. 所有已有测试仍然通过：`python -m pytest tests/ -v`
2. 新增测试覆盖 chapter_detector 的新能力
3. 用《刻意练习》EPUB 重新蒸馏：
   - 每章 chapters/*.md 有完整 Markdown 内容（不是错误信息）
   - SKILL.md 包含"如何使用这个 Skill"章节
   - SKILL.md 包含主题索引
   - SKILL.md 的章节索引有每章的核心框架标注
   - SKILL.md frontmatter 的 name、description 符合 Anthropic 规范
   - 框架描述包含"何时用"和"怎么用"
4. 成本不增加（仍然用 deepseek-v4-flash 做章节蒸馏）

---

## 参考来源

| 参考 | 借鉴内容 |
|------|---------|
| the-knowledge-guy extract.py | chapter_detector 增强（Part A） |
| the-knowledge-guy reference/chapter-template.md | Stage 2 章节 Markdown 模板（Part C） |
| the-knowledge-guy reference/concept-map-spec.md | SKILL.md 结构与路由指令（Part D） |
| book-to-skill SKILL.md Step 7 | 章节模板的 heading 结构 + token 预算（Part C） |
| book-to-skill SKILL.md Step 9 | 主 SKILL.md 的索引格式（Part D） |
| Anthropic skills 仓库 | YAML frontmatter 规范 + name/description 要求（Part D） |
| cangjie-skill | 多维度提取思路（框架/方法论/案例/反模式）（Part C） |
