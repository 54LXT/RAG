import os

# 强制使用 HuggingFace 国内镜像（必须在所有 import 之前）
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from dotenv import load_dotenv
load_dotenv(override=True)

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

chat_model_name = os.getenv("CHAT_MODEL_NAME", "qwen-max")
embedding_model_name = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-v4")

persist_directory = os.getenv("PERSIST_DIRECTORY", "./chroma_db")
collection_name = os.getenv("COLLECTION_NAME", "rag_collection")

top_k = int(os.getenv("TOP_K", "3"))

chunk_size = int(os.getenv("CHUNK_SIZE", "512"))
chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "64"))

# 对话历史最大保留 token 数（滑动窗口截断，超出后丢弃最早的对话轮次）
max_history_tokens = int(os.getenv("MAX_HISTORY_TOKENS", "6000"))

# 最大内存驻留会话数（超出后 LRU 淘汰到磁盘）
max_sessions = int(os.getenv("MAX_SESSIONS", "100"))

# 单次文件上传大小上限（MB）
max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "50"))