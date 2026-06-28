# RAG 检索增强生成问答系统

基于 LangChain + ChromaDB 的 RAG（Retrieval-Augmented Generation）问答系统，支持多格式文档上传、混合检索、流式问答和自动化评测。

## 技术栈

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

## 项目结构

```
rag/
├── server.py              # FastAPI 后端服务（SSE 流式问答 + 文件上传）
├── rag.py                 # RAG 核心服务（检索 + 生成链 + 历史截断）
├── vector_stores.py       # 混合检索引擎（BM25 + Chroma + CrossEncoder Rerank）
├── knowledge_base.py      # 文档解析与入库（TXT/PDF/DOCX/图片OCR）
├── config_data.py         # 全局配置管理
├── file_history_store.py  # 会话记忆管理（LRU 淘汰 + 磁盘持久化）
├── batch_ingest.py        # 批量文档入库脚本
├── generate_corpus.py     # 大规模测试语料生成器
├── eval.py                # 自动化评测脚本（检索指标 + 幻觉检测）
├── app_qa.py              # Streamlit 问答界面
├── app_file_uploader.py   # Streamlit 文件上传界面
├── chroma_db/             # ChromaDB 持久化目录
├── data/                  # 上传文件存储目录
├── eval_dataset.json      # 评测数据集（20 条手工标注用例）
├── chat_history.json      # 会话历史持久化文件
└── frontend/              # Vue 3 + Vite 前端
    ├── src/
    │   ├── main.js
    │   ├── api/
    │   └── components/
    │       └── SourceViewer.vue
    ├── index.html
    ├── package.json
    └── vite.config.js
```

## 核心特性

### 1. 混合检索策略

- **BM25 关键词检索**（权重 0.4）— 精确匹配
- **向量语义检索**（权重 0.6）— 语义泛化
- **CrossEncoder 重排序** (bge-reranker-base) — 对候选文档二次精排，取 top-k

### 2. 多格式文档支持

| 格式 | 解析方式 |
|------|----------|
| TXT | UTF-8 直接读取 |
| PDF | PyMuPDF (fitz) 逐页提取 |
| DOCX | python-docx（段落 + 表格） |
| 图片 | EasyOCR（中英文，CPU） |

全部经过文本清洗后统一进入分块/Embedding/检索管线。

### 3. 文本清洗预处理

- 统一换行符（`\r\n` / `\r` → `\n`）
- 压缩连续空行
- 去除 URL 和邮箱
- 去除无意义装饰线（`----` `####` `~~~~`）
- 合并多余空格

### 4. 抗幻觉策略

- 系统提示词约束：「只根据参考资料回答，不要编造」
- 低温度生成（temperature=0.1）
- 混合检索确保高质量上下文
- CrossEncoder 重排序过滤噪声
- 对话历史滑动窗口截断（默认 6000 tokens）
- 源文档展示，用户可追溯验证
- LLM-as-Judge 自动化幻觉评测

### 5. 双层记忆管理

- **会话级 LRU 淘汰**：OrderedDict 实现，超过上限淘汰最久未访问的会话，淘汰前自动持久化
- **消息级滑动窗口**：tiktoken 估算 token 数，从头部丢弃旧消息，确保不超出上下文窗口

### 6. 自动化评测体系

支持三种评测模式：

```bash
# 仅检索指标（Hit@k / MRR / Recall@k）
python eval.py --mode retrieval

# 检索 + 幻觉评测（LLM-as-Judge 忠实度评分）
python eval.py --mode full

# 与原项目（单一向量检索）对比
python eval.py --mode compare --original ../RAG_example
```

**检索指标：**
- Hit@k：top-k 结果中至少命中 1 个相关文档的查询比例
- MRR：第一个命中文档排名倒数的均值
- Recall@k：相关文档被召回的比例
- 支持按查询类别分组统计

**幻觉指标：**
- LLM-as-Judge 1-5 分忠实度评分
- 分数 < 4 判定为幻觉
- 按知识库内/外分组统计

## 快速开始

### 前置要求

- Python 3.10+
- Node.js 18+（Vue 前端）
- 阿里云 DashScope API Key

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd rag
```

### 2. 配置环境变量

创建 `.env` 文件（参考配置如下）：

```env
DASHSCOPE_API_KEY=your_api_key_here
HF_ENDPOINT=https://hf-mirror.com
CHAT_MODEL_NAME=qwen-max
EMBEDDING_MODEL_NAME=text-embedding-v4
PERSIST_DIRECTORY=./chroma_db
COLLECTION_NAME=rag_collection
TOP_K=3
CHUNK_SIZE=512
CHUNK_OVERLAP=64
MAX_HISTORY_TOKENS=6000
MAX_SESSIONS=100
MAX_UPLOAD_MB=50
```

### 3. 安装 Python 依赖

```bash
pip install langchain langchain-community langchain-chroma langchain-classic \
    tiktoken fastapi uvicorn pymupdf python-docx easyocr \
    dashscope streamlit python-dotenv
```

### 4. 启动后端服务

```bash
# FastAPI 服务（端口 8000）
python server.py
# 或
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 启动前端（可选）

```bash
cd frontend
npm install
npm run dev          # 开发模式，端口 3000，自动代理 /api → 8000
```

### 6. Streamlit 界面（可选）

```bash
streamlit run app_qa.py          # 问答界面
streamlit run app_file_uploader.py # 文件上传界面
```

## 使用流程

### 上传文档

```bash
# 通过 API 上传（支持 TXT/PDF/DOCX/PNG/JPG/BMP，最大 50MB）
curl -X POST http://localhost:8000/api/upload \
  -F "file=@/path/to/document.pdf"
```

### 流式问答

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "你的问题", "session_id": "user_001"}'
```

响应格式为 SSE（Server-Sent Events）：
- `{"type": "token", "content": "..."}` — 逐 token 流式生成
- `{"type": "sources", "docs": [...]}` — 参考来源列表
- `{"type": "done"}` — 回答结束

### 查看历史记录

```bash
curl http://localhost:8000/api/history/user_001
```

## 批量入库

用于一次性入库大量文档：

```bash
# 1. 生成测试语料
python generate_corpus.py --count 1000 --output-dir data_gen

# 2. 清空旧库并批量入库
python batch_ingest.py
```

## 配置说明

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `DASHSCOPE_API_KEY` | - | 阿里云 API Key（必填） |
| `CHAT_MODEL_NAME` | qwen-max | 对话模型 |
| `EMBEDDING_MODEL_NAME` | text-embedding-v4 | Embedding 模型 |
| `TOP_K` | 3 | 重排序后保留文档数 |
| `CHUNK_SIZE` | 512 | 文本分块 token 数 |
| `CHUNK_OVERLAP` | 64 | 分块重叠 token 数 |
| `MAX_HISTORY_TOKENS` | 6000 | 对话历史最大 token 数 |
| `MAX_SESSIONS` | 100 | 最大内存驻留会话数 |
| `MAX_UPLOAD_MB` | 50 | 单次文件上传大小上限 |
| `HF_ENDPOINT` | https://hf-mirror.com | HuggingFace 镜像（国内加速） |

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload` | 上传文档（multipart/form-data） |
| POST | `/api/chat` | 流式问答（SSE） |
| GET | `/api/history/{session_id}` | 获取会话历史 |

## 浏览器直接访问

启动后端后，打开浏览器访问：

- **API 文档**：http://localhost:8000/docs（FastAPI 自动生成 Swagger UI）

## License

MIT
