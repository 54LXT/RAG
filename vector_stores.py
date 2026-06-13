import config_data as config  # 必须在最前：设置 HF_HUB_OFFLINE
import os
import pickle
from langchain_chroma import Chroma
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

class VectorStoreService:
    def __init__(self, embedding):
        self.vector_store = Chroma(
            collection_name=config.collection_name,
            embedding_function=embedding,
            persist_directory=config.persist_directory,
        )
        self.bm25_path = os.path.join(config.persist_directory, "bm25.pkl")

    def _get_bm25_retriever(self):
        data = self.vector_store.get()
        current_count = len(data["documents"])

        if current_count > 0 and os.path.exists(self.bm25_path):
            with open(self.bm25_path, "rb") as f:
                cached = pickle.load(f)
            if isinstance(cached, tuple) and cached[1] == current_count:
                return cached[0]

        # 从向量库重建 BM25，保留元数据
        docs = [
            Document(
                page_content=data["documents"][i],
                metadata=data["metadatas"][i]
            )
            for i in range(current_count)
        ]

        bm25_retriever = BM25Retriever.from_documents(docs, k=10)
        with open(self.bm25_path, "wb") as f:
            pickle.dump((bm25_retriever, current_count), f)
        return bm25_retriever

    def get_retriever(self):
        bm25_retriever = self._get_bm25_retriever()
        vector_retriever = self.vector_store.as_retriever(search_kwargs={"k": 10})

        ensemble_retriever = EnsembleRetriever(
            retrievers=[bm25_retriever, vector_retriever],
            weights=[0.4, 0.6]
        )

        rerank_model = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base")
        compressor = CrossEncoderReranker(
            model = rerank_model,
            top_n = config.top_k
        )

        final_retriever = ContextualCompressionRetriever(
            base_compressor=compressor,
            base_retriever=ensemble_retriever
        )
        return final_retriever

    def refresh_retriever(self):
        """清理 BM25 缓存并重建检索器（入库后调用，确保新文档可被检索）"""
        if os.path.exists(self.bm25_path):
            os.remove(self.bm25_path)
        return self.get_retriever()