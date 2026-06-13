# RAG 项目分析

## 1. 项目概述

一个基于 LangChain + ChromaDB 的 RAG（检索增强生成）问答系统，支持多格式文档上传、混合检索、流式问答。

### 技术栈

| 层 | 技术 |
|---|------|
| LLM | 阿里 DashScope Qwen Max |
| Embedding | DashScope text-embedding-v4 |
| 向量库 | ChromaDB |
| 重排序 | BAAI/bge-reranker-base (HuggingFace CrossEncoder) |
| 关键词检索 | BM25 (langchain_community) |
| 框架 | LangChain (LCEL) |
| API 服务 | FastAPI + SSE 流式 |
| 前端 | Vue 3 + Vite / Streamlit |

---

## 2. 抗幻觉策略（9 项）

| 策略 | 说明 | 代码位置 |
|------|------|----------|
| 系统提示词约束 | "只根据参考资料回答，不要编造"，无答案则明确拒绝 | [rag.py:71-78](rag.py#L71-L78) |
| 低温度生成 | temperature=0.1，减少随机编造 | [rag.py:88](rag.py#L88) |
| 混合检索 | BM25(40%) + 向量(60%) 融合，兼顾精确匹配和语义搜索 | [vector_stores.py:49-52](vector_stores.py#L49-L52) |
| 交叉编码器重排序 | bge-reranker-base 对候选文档二次精排，过滤噪声 | [vector_stores.py:54-58](vector_stores.py#L54-L58) |
| 对话历史截断 | 滑动窗口，丢弃超出 6000 token 的旧消息 | [rag.py:35-58](rag.py#L35-L58) |
| 文本清洗 | 去 URL/邮箱/装饰符/多余空白 | [knowledge_base.py:34-54](knowledge_base.py#L34-L54) |
| 分块去重 | 同一 source 文件重新上传时先删旧再写新 | [knowledge_base.py:168-174](knowledge_base.py#L168-L174) |
| 源文档展示 | 回答附加检索来源，用户可验证 | [server.py:80-84](server.py#L80-L84) |
| LLM-as-Judge 评估 | 自动化评测幻觉率，1-5 分忠实度评分 | [eval.py:133-239](eval.py#L133-L239) |

---

## 3. 记忆管理（双层策略）

### 第一层：会话 LRU 淘汰

- 位置：[file_history_store.py](file_history_store.py)
- 核心：[file_history_store.py:62-76](file_history_store.py#L62-L76) `get_history()`
- 用 `OrderedDict` 实现 LRU，超过 100 个会话时淘汰最久未访问的
- 淘汰前自动持久化到 `chat_history.json`
- 语言学习历史保留在 `InMemoryChatMessageHistory` 中

### 第二层：消息滑动窗口

- 位置：[rag.py:35-58](rag.py#L35-L58) `_trim_history()`
- 用 `tiktoken (cl100k_base)` 估算 token 数
- 从头部逐条丢弃旧消息，至少保留最后一条
- 阈值：6000 tokens（`.env` 中 `MAX_HISTORY_TOKENS` 可配）
- 截断是临时的，不修改存储中的完整历史

### 连接

LangChain `RunnableWithMessageHistory` 自动衔接两层：[rag.py:110-115](rag.py#L110-L115)

---

## 4. 多模态实现

策略：**把一切格式变成纯文本，然后统一对待**。

- 调度入口：[knowledge_base.py:107-118](knowledge_base.py#L107-L118) `load_document()`

| 格式 | 解析器 | 代码位置 |
|------|--------|----------|
| TXT | UTF-8 直接读取 | [knowledge_base.py:56-63](knowledge_base.py#L56-L63) |
| PDF | PyMuPDF (fitz) 逐页提取 | [knowledge_base.py:66-78](knowledge_base.py#L66-L78) |
| DOCX | python-docx（段落 + 表格） | [knowledge_base.py:81-93](knowledge_base.py#L81-L93) |
| 图片 | EasyOCR (ch_sim+en, CPU) | [knowledge_base.py:17-26](knowledge_base.py#L17-L26) + [96-104](knowledge_base.py#L96-L104) |

全部经过 `clean_text()` 清洗后进入统一的分块/embedding/检索管线。

---

## 5. 文本清洗

8 步骤：[knowledge_base.py:34-54](knowledge_base.py#L34-L54)

1. 统一换行符（`\r\n` / `\r` → `\n`）
2. 压缩连续空行（3+ → 2 个）
3. 逐行 strip() 去首尾空白
4. 过滤空行
5. 去 URL 和邮箱（保护 `@` 密码如 `Kria@2025!`）
6. 去装饰线（`----` `####` `~~~~`）
7. 重新拼合文本
8. 合并多余空格

---

## 6. 知识库维护

三层设计：

| 机制 | 实现 | 位置 |
|------|------|------|
| 增量覆盖写入 | source 级删旧写新 | [knowledge_base.py:138-178](knowledge_base.py#L138-L178) |
| BM25 缓存校验 | 文档计数 checksum，不一致则重建 | [vector_stores.py:21-43](vector_stores.py#L21-L43) |
| 缓存失效 | `refresh_retriever()` 删 pickle → 下次检索自动重建 | [vector_stores.py:66-70](vector_stores.py#L66-L70) |
| 全量重建 | `shutil.rmtree(chroma_db)` + 批量入库 | [batch_ingest.py](batch_ingest.py) |

核心原则：**ChromaDB 是唯一权威数据源**，BM25 是从它重建的可丢弃缓存。

---

## 7. 评估体系

### 评测数据集

[eval_dataset.json](eval_dataset.json) — 20 条手工标注的测试用例，覆盖：
- 关键词匹配（4 条）
- 精确字符串/BM25 考验（5 条）
- 语义泛化/向量检索考验（4 条）
- 混合查询（1 条）
- 拒答测试（4 条，`relevant_docs: []`）

### 检索指标（[eval.py:50-126](eval.py#L50-L126)）

- **Hit@k**: top-k 中至少命中 1 个相关文档的比例
- **MRR**: 第一个命中文档排名的倒数均值
- **Recall@k**: 相关文档被找回的比例
- 匹配方式：按文件名匹配 `Path(doc.metadata["source"]).name`
- 支持按 `category` 分类统计

### 幻觉指标（[eval.py:156-239](eval.py#L156-L239)）

- **LLM-as-Judge**: 独立 LLM 调用，用 1-5 分标准评判回答忠实度
- 评分标准 prompt：[eval.py:133-153](eval.py#L133-L153)
- 分数 < 4 判定为幻觉
- 分组统计：知识库内/外分别计算忠实度

### 三种运行模式

```
python eval.py --mode retrieval    # 仅检索指标
python eval.py --mode full         # 检索 + 幻觉
python eval.py --mode compare      # 对比两种检索策略
```
