"""
RAG 系统评测脚本
================
用法：
    # 仅检索指标
    python eval.py --mode retrieval

    # 检索 + 幻觉评测
    python eval.py --mode full

    # 与原项目对比
    python eval.py --mode compare --original ../RAG_example

指标说明：
    - Hit@k：     top-k 结果中包含至少1条相关文档的 query 比例
    - MRR：       第一个命中文档排名的倒数均值（越靠前越好）
    - Recall@k：  命中的相关文档数 / 总相关文档数
    - Faithfulness：LLM-as-Judge 评判回答是否忠实于检索文档（1-5 分）
    - 幻觉率：      包含文档外信息的回答比例
"""

import config_data as config  # 必须在最前：设置环境变量

import json
import os
import sys
import time
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("eval")

# ============================================================
# 评测数据集加载
# ============================================================

def load_dataset(path="eval_dataset.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# 检索指标
# ============================================================

def evaluate_retrieval(retriever, test_set, k_list=(1, 3, 5)):
    """
    Hit@k / MRR / Recall@k，支持按 category 分组统计
    """
    results = {k: {"hit": 0, "mrr_sum": 0.0, "recall_sum": 0.0} for k in k_list}
    cat_results = {}  # category → {k: {hit, mrr_sum, recall_sum, count}}
    details = []

    for item in test_set:
        query = item["query"]
        relevant = set(item["relevant_docs"])
        category = item.get("category", "未分类")
        if not relevant:
            continue  # 拒答类问题不参与检索指标

        try:
            docs = retriever.invoke(query)
        except Exception as e:
            logger.warning("检索失败 query=%s: %s", query[:30], e)
            continue

        hit_at_k = {k: False for k in k_list}
        mrr_score = 0.0
        recall_count = 0

        for rank, doc in enumerate(docs, start=1):
            source = Path(doc.metadata.get("source", "")).name
            if source in relevant:
                recall_count += 1
                if mrr_score == 0.0:
                    mrr_score = 1.0 / rank
            for k in k_list:
                if rank <= k and source in relevant:
                    hit_at_k[k] = True

        for k in k_list:
            if hit_at_k[k]:
                results[k]["hit"] += 1
            results[k]["mrr_sum"] += mrr_score
            results[k]["recall_sum"] += recall_count / len(relevant) if relevant else 0

        # 按 category 统计
        if category not in cat_results:
            cat_results[category] = {k: {"hit": 0, "mrr_sum": 0.0, "recall_sum": 0.0, "count": 0} for k in k_list}
        for k in k_list:
            if hit_at_k[k]:
                cat_results[category][k]["hit"] += 1
            cat_results[category][k]["mrr_sum"] += mrr_score
            cat_results[category][k]["recall_sum"] += recall_count / len(relevant) if relevant else 0
            cat_results[category][k]["count"] += 1

        details.append({
            "query": query,
            "category": category,
            "hit": {k: hit_at_k[k] for k in k_list},
            "mrr": mrr_score,
            "recall": recall_count / len(relevant) if relevant else 0,
            "retrieved_sources": [Path(d.metadata.get("source", "")).name for d in docs[:5]],
            "relevant_sources": list(relevant),
        })

    n = len([t for t in test_set if t.get("relevant_docs")])
    summary = {}
    for k in k_list:
        summary[f"Hit@{k}"] = f"{results[k]['hit']}/{n} = {results[k]['hit']/n:.1%}" if n else "N/A"
        summary[f"MRR@{k}"] = f"{results[k]['mrr_sum']/n:.4f}" if n else "N/A"
        summary[f"Recall@{k}"] = f"{results[k]['recall_sum']/n:.1%}" if n else "N/A"

    # 按类别统计汇总
    cat_summary = {}
    for cat, cr in cat_results.items():
        cat_n = cr[k_list[0]]["count"]
        cat_summary[cat] = {}
        for k in k_list:
            cat_summary[cat][f"Hit@{k}"] = f"{cr[k]['hit']}/{cat_n} = {cr[k]['hit']/cat_n:.1%}" if cat_n else "N/A"

    return summary, details, cat_summary


# ============================================================
# 幻觉评测（LLM-as-Judge）
# ============================================================

FAITHFULNESS_PROMPT = """你是一个严格的评测员。请判断以下 AI 回答是否完全忠实于提供的参考资料。

评分标准（1-5 分）：
- 5 分：回答的所有事实都能在参考资料中找到明确依据，没有任何编造
- 4 分：回答基本忠实，但有一处轻微的推断（参考资料可以合理推导）
- 3 分：回答部分忠实，但存在 1-2 处参考资料中没有的信息
- 2 分：回答大量信息不在参考资料中，只有少量相关内容
- 1 分：回答完全脱离参考资料，通篇编造

参考资料：
{context}

用户问题：{question}

AI 回答：{answer}

请给出：
1. 评分（1-5）
2. 扣分原因（如果 <5 分，逐条说明哪些内容在参考资料中找不到）

输出 JSON 格式：{{"score": 5, "reason": "..."}}"""


def evaluate_faithfulness(rag_service, test_set, llm_judge=None):
    """
    LLM-as-Judge 评估忠实度。
    如果未提供 llm_judge，使用 rag_service 自带的 LLM。
    """
    scores = []
    details = []

    for item in test_set:
        query = item["query"]
        relevant = item.get("relevant_docs", [])

        # 先检索
        try:
            docs = rag_service.retriever.invoke(query)
        except Exception as e:
            logger.warning("检索失败 query=%s: %s", query[:30], e)
            continue

        # 生成回答
        context = "\n\n".join(d.page_content for d in docs)
        try:
            stream = rag_service.chain.stream(
                {"input": query, "docs": docs},
                config={"configurable": {"session_id": f"eval_{int(time.time())}"}}
            )
            answer = "".join(list(stream))
        except Exception as e:
            logger.warning("生成失败 query=%s: %s", query[:30], e)
            continue

        # LLM 裁判评分
        if llm_judge is None:
            llm_judge = rag_service.llm

        judge_prompt = FAITHFULNESS_PROMPT.format(
            context=context,
            question=query,
            answer=answer,
        )
        try:
            resp = llm_judge.invoke(judge_prompt)
            resp_text = resp.content if hasattr(resp, "content") else str(resp)
            # 尝试从响应中提取 JSON
            import re
            json_match = re.search(r"\{[^}]+\}", resp_text)
            if json_match:
                judge_result = json.loads(json_match.group())
            else:
                judge_result = {"score": 0, "reason": f"无法解析评分: {resp_text[:100]}"}
        except Exception as e:
            logger.warning("裁判评分失败 query=%s: %s", query[:30], e)
            judge_result = {"score": 0, "reason": str(e)}

        hallucinated = judge_result.get("score", 0) < 4
        scores.append(judge_result.get("score", 0))
        details.append({
            "query": query,
            "answer": answer[:300],
            "faithfulness_score": judge_result.get("score"),
            "hallucinated": hallucinated,
            "reason": judge_result.get("reason", ""),
            "has_relevant_docs": bool(relevant),
        })

    if not scores:
        return {"error": "无有效评测结果"}

    avg_score = sum(scores) / len(scores)
    hallucination_rate = sum(1 for s in scores if s < 4) / len(scores)

    # 按是否有相关文档分组
    with_docs_scores = [s for s, d in zip(scores, details) if d["has_relevant_docs"]]
    without_docs_scores = [s for s, d in zip(scores, details) if not d["has_relevant_docs"]]

    summary = {
        "平均忠实度 (1-5)": f"{avg_score:.2f}",
        "幻觉率 (<4分为幻觉)": f"{hallucination_rate:.1%}",
        "知识库内问题忠实度": f"{sum(with_docs_scores)/len(with_docs_scores):.2f}" if with_docs_scores else "N/A",
        "知识库外问题忠实度": f"{sum(without_docs_scores)/len(without_docs_scores):.2f}" if without_docs_scores else "N/A",
        "评测样本数": len(scores),
    }

    return summary, details


# ============================================================
# 主评测入口
# ============================================================

def run_retrieval_eval(retriever, test_set):
    logger.info("=" * 60)
    logger.info("【检索指标评测】")
    logger.info("=" * 60)
    summary, details, cat_summary = evaluate_retrieval(retriever, test_set)
    for metric, value in summary.items():
        logger.info("  %s: %s", metric, value)
    if cat_summary:
        logger.info("  --- 按查询类别 ---")
        for cat, metrics in cat_summary.items():
            logger.info("  [%s] Hit@1=%s  Hit@3=%s", cat, metrics.get("Hit@1", "N/A"), metrics.get("Hit@3", "N/A"))
    return summary, details, cat_summary


def run_full_eval(rag_service, test_set):
    logger.info("=" * 60)
    logger.info("【完整评测（检索 + 幻觉）】")
    logger.info("=" * 60)

    # 检索
    ret_summary, ret_details, cat_summary = evaluate_retrieval(rag_service.retriever, test_set)
    for metric, value in ret_summary.items():
        logger.info("  %s: %s", metric, value)
    if cat_summary:
        logger.info("  --- 按查询类别 ---")
        for cat, metrics in cat_summary.items():
            logger.info("  [%s] Hit@1=%s  Hit@3=%s", cat, metrics.get("Hit@1", "N/A"), metrics.get("Hit@3", "N/A"))

    # 幻觉
    logger.info("-" * 60)
    faith_summary, faith_details = evaluate_faithfulness(rag_service, test_set)
    logger.info("【幻觉 / 忠实度评测】")
    for metric, value in faith_summary.items():
        logger.info("  %s: %s", metric, value)

    return {
        "retrieval": ret_summary,
        "retrieval_by_category": cat_summary,
        "faithfulness": faith_summary,
        "retrieval_details": ret_details,
        "faithfulness_details": faith_details,
    }


def run_compare(rag_retriever, chroma_db, test_set):
    """在同一份数据上对比检索策略：混合检索 vs 单一向量检索"""
    logger.info("=" * 60)
    logger.info("【对比评测：改进项目 vs 原项目（同一知识库）】")
    logger.info("=" * 60)

    # 改进项目：BM25 + Chroma + Rerank
    logger.info("\n--- 改进项目 (BM25 + Chroma + Rerank) ---")
    new_summary, new_details, new_cat = evaluate_retrieval(rag_retriever, test_set)
    for metric, value in new_summary.items():
        logger.info("  %s: %s", metric, value)
    if new_cat:
        logger.info("  --- 按查询类别 ---")
        for cat, metrics in new_cat.items():
            logger.info("  [%s] Hit@1=%s  Hit@3=%s", cat, metrics.get("Hit@1", "N/A"), metrics.get("Hit@3", "N/A"))

    # 模拟原项目：单一 Chroma 向量检索 k=1
    logger.info("\n--- 原项目 (单一 Chroma 向量检索 k=1) ---")
    original_retriever = chroma_db.as_retriever(search_kwargs={"k": 1})
    orig_summary, orig_details, orig_cat = evaluate_retrieval(original_retriever, test_set, k_list=(1, 3))
    for metric, value in orig_summary.items():
        logger.info("  %s: %s", metric, value)
    if orig_cat:
        logger.info("  --- 按查询类别 ---")
        for cat, metrics in orig_cat.items():
            logger.info("  [%s] Hit@1=%s", cat, metrics.get("Hit@1", "N/A"))

    # 对比提升
    logger.info("\n--- 提升幅度 ---")
    new_hit1_val = float(new_summary["Hit@1"].split("=")[-1].replace("%", "")) / 100
    orig_hit1_val = float(orig_summary.get("Hit@1", "0/0 = 0%").split("=")[-1].replace("%", "")) / 100
    if orig_hit1_val > 0:
        delta = (new_hit1_val - orig_hit1_val) / orig_hit1_val * 100
        logger.info("  Hit@1:  %.1f%% → %.1f%%  (%+.0f%%)", orig_hit1_val * 100, new_hit1_val * 100, delta)
    else:
        logger.info("  Hit@1:  %.1f%% → %.1f%%", orig_hit1_val * 100, new_hit1_val * 100)

    new_hit3_val = float(new_summary["Hit@3"].split("=")[-1].replace("%", "")) / 100
    orig_hit3_val = float(orig_summary.get("Hit@3", "0/0 = 0%").split("=")[-1].replace("%", "")) / 100
    if orig_hit3_val > 0:
        delta = (new_hit3_val - orig_hit3_val) / orig_hit3_val * 100
        logger.info("  Hit@3:  %.1f%% → %.1f%%  (%+.0f%%)", orig_hit3_val * 100, new_hit3_val * 100, delta)
    else:
        logger.info("  Hit@3:  %.1f%% → %.1f%%", orig_hit3_val * 100, new_hit3_val * 100)

    new_mrr = float(new_summary["MRR@1"].strip())
    orig_mrr = float(orig_summary.get("MRR@1", "0").strip())
    logger.info("  MRR :   %.4f → %.4f", orig_mrr, new_mrr)

    return {
        "improved": new_summary,
        "improved_by_category": new_cat,
        "original": orig_summary,
        "original_by_category": orig_cat,
        "improved_details": new_details,
        "original_details": orig_details,
    }


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RAG 系统评测")
    parser.add_argument("--dataset", default="eval_dataset.json", help="评测数据集路径")
    parser.add_argument("--mode", choices=["retrieval", "full", "compare"], default="retrieval",
                        help="retrieval=仅检索指标, full=检索+幻觉, compare=与原项目对比")
    parser.add_argument("--original", default="../RAG_example", help="原项目路径（compare 模式使用）")
    parser.add_argument("--output", default="eval_result.json", help="详细结果输出文件")
    args = parser.parse_args()

    # 加载数据集
    dataset_path = args.dataset
    if not os.path.exists(dataset_path):
        logger.error("数据集文件不存在: %s", dataset_path)
        sys.exit(1)
    test_set = load_dataset(dataset_path)
    logger.info("加载评测数据集: %d 条", len(test_set))

    # 检查向量库
    from langchain_chroma import Chroma
    from langchain_community.embeddings import DashScopeEmbeddings

    persist_dir = config.persist_directory
    if not os.path.exists(persist_dir):
        logger.error("向量库不存在: %s —— 请先运行知识库入库", persist_dir)
        sys.exit(1)

    embedding = DashScopeEmbeddings(
        model=config.embedding_model_name,
        dashscope_api_key=config.DASHSCOPE_API_KEY,
    )
    db = Chroma(
        collection_name=config.collection_name,
        embedding_function=embedding,
        persist_directory=persist_dir,
    )
    doc_count = db._collection.count()
    logger.info("向量库文档数: %d", doc_count)
    if doc_count == 0:
        logger.error("向量库为空 —— 请先上传文档再评测")
        sys.exit(1)

    # 运行评测
    result = None
    if args.mode in ("retrieval", "full"):
        from rag import RagService
        rag_service = RagService()

        if args.mode == "retrieval":
            summary, details, cat_summary = run_retrieval_eval(rag_service.retriever, test_set)
            result = {"summary": summary, "by_category": cat_summary, "details": details}
        else:
            result = run_full_eval(rag_service, test_set)

    elif args.mode == "compare":
        # 同一份 Chroma 数据，对比两种检索策略
        from rag import RagService
        rag_service = RagService()

        result = run_compare(rag_service.retriever, db, test_set)

    # 保存详细结果
    output_path = args.output
    with open(output_path, "w", encoding="utf-8") as f:
        # 序列化时处理不可序列化的对象
        def serialize(obj):
            if isinstance(obj, dict):
                return {k: serialize(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize(v) for v in obj]
            elif hasattr(obj, "__dict__"):
                return str(obj)
            return obj
        json.dump(serialize(result), f, ensure_ascii=False, indent=2)
    logger.info("详细结果已保存到: %s", output_path)

    # 打印汇总
    print("\n" + "=" * 60)
    print("评测完成")
    print("=" * 60)
