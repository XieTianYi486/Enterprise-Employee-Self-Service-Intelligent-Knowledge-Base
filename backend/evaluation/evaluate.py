# ============================================================
# RAG 评测脚本
# 基于标注基准集（evaluation/qa_benchmark.json）对系统做回归评测：
#   1. 检索命中率（Top-K 是否召回黄金分块）—— 不调用 LLM，快速
#   2. 答案正确率 / 拒答准确率 / 幻觉率 —— 走完整 RAG 链路
#
# 用法:
#   python evaluation/evaluate.py                       # 全部指标
#   python evaluation/evaluate.py --mode retrieval      # 仅检索（快，无 LLM 调用）
#   python evaluation/evaluate.py --mode answer --limit 20
#   python evaluation/evaluate.py --fail-under 0.7      # 低于阈值时以退出码 1 结束（CI/回归用）
#
# 基准集条目格式:
#   {
#     "id": 1, "doc": "00_员工考勤管理制度_完整版.md", "category": "考勤",
#     "question": "迟到一次扣多少钱？",
#     "keywords": ["迟到", "50元"],        # 文档中逐字存在的原文关键词
#     "should_refuse": false,               # true = 知识库外问题，应拒答
#     "answer_summary": "..."               # 人工参考（不进评测逻辑）
#   }
# ============================================================

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

# backend 目录加入 sys.path（保证 import app 可用）
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.rag.retrievers.hybrid_retriever import get_hybrid_retriever  # noqa: E402
from app.rag.retrievers.bm25_retriever import get_bm25_retriever  # noqa: E402
from app.db.cache import cache  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVAL_DIR / "results"

# 拒答话术特征（与 chat_service 的拒答判定保持一致）
REFUSAL_PATTERNS = [
    "未找到相关信息", "未找到关于", "知识库中未找到", "无法回答",
    "建议您咨询", "无法获取", "参考资料中未涉及", "未涉及",
]

RETRIEVAL_TOP_K = 10   # 检索命中率评测的 Top-K 上限
EVAL_SECURITY_LEVEL = 4  # 以最高密级评测（可见全部文档）


# ==================== 工具函数 ====================

def _norm(text: str) -> str:
    """去空白归一化（LLM 输出常在数字与单位间加空格）"""
    return "".join((text or "").split())


def _load_benchmark(path: Path) -> List[dict]:
    """加载基准集，返回条目列表"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", [])
    if not items:
        raise ValueError(f"基准集为空: {path}")
    return items


def _resolve_golden_chunks(items: List[dict]) -> Dict[int, Set[str]]:
    """
    在 BM25 索引分块中定位"黄金分块"：包含条目全部关键词的分块。

    关键词是文档中逐字存在的原文，因此命中同一分块的概率高；
    找不到任何分块的条目（标注有误或文档未入库）返回空集合，评测时跳过。
    """
    corpus = get_bm25_retriever()._chunks
    golden: Dict[int, Set[str]] = {}

    for item in items:
        if item.get("should_refuse"):
            continue
        keywords = [k for k in item.get("keywords", []) if k]
        doc_name = item.get("doc")
        matched_ids = set()
        for chunk in corpus:
            if doc_name:
                # 索引里 document_name 是文档标题，基准集 doc 是文件名（标题为文件名子串）
                chunk_name = chunk.get("document_name") or ""
                if chunk_name not in doc_name:
                    continue
            content_norm = _norm(chunk.get("content", ""))
            if all(_norm(k) in content_norm for k in keywords):
                matched_ids.add(chunk.get("chunk_id", ""))
        golden[item["id"]] = matched_ids

    return golden


def _is_refusal(answer: str) -> bool:
    return any(p in (answer or "") for p in REFUSAL_PATTERNS)


# ==================== 检索评测 ====================

def eval_retrieval(items: List[dict], golden: Dict[int, Set[str]]) -> dict:
    """
    检索命中率评测（原始问题直接混合检索，不经过改写/重排/LLM）。

    指标：hit@1 / hit@3 / hit@5 / hit@10 —— 黄金分块出现在前 K 个结果中的条目占比。
    """
    retriever = get_hybrid_retriever()
    hits = {k: 0 for k in (1, 3, 5, RETRIEVAL_TOP_K)}
    total = 0
    skipped = 0
    details = []

    for item in items:
        if item.get("should_refuse"):
            continue
        gold_ids = golden.get(item["id"], set())
        if not gold_ids:
            skipped += 1
            continue

        total += 1
        results = retriever.search(
            query=item["question"],
            top_k=RETRIEVAL_TOP_K,
            security_level=EVAL_SECURITY_LEVEL,
        )
        retrieved_ids = [c.get("chunk_id", "") for c in results]
        first_hit_rank = None
        for rank, cid in enumerate(retrieved_ids, start=1):
            if cid in gold_ids:
                first_hit_rank = rank
                break

        for k in hits:
            if first_hit_rank is not None and first_hit_rank <= k:
                hits[k] += 1
        details.append({
            "id": item["id"], "question": item["question"],
            "hit_rank": first_hit_rank, "golden_count": len(gold_ids),
        })

    metrics = {
        "total": total,
        "skipped_unresolved": skipped,
        **{f"hit@{k}": (hits[k] / total if total else 0.0) for k in hits},
    }
    return {"metrics": metrics, "details": details}


# ==================== 答案评测 ====================

def eval_answer(items: List[dict], limit: Optional[int], golden: Dict[int, Set[str]]) -> dict:
    """
    答案评测（完整 RAG 链路：改写 → 多路召回 → 重排 → LLM 生成）。

    黄金分块未解析的可答题（标注有误或文档未入库）跳过，不计入指标。

    指标：
      - answer_accuracy     : 答案包含全部预期关键词的可答题占比
      - refusal_accuracy    : 应拒答条目确实拒答的占比
      - hallucination_rate  : 可答题中"回答了但无来源引用"的占比
      - incomplete_rate     : 可答题中"有来源但关键词缺失"的占比
    """
    from app.services.chat_service import ChatService

    # 清空问答缓存，避免上一轮评测的缓存命中干扰（向量缓存保留，加速重复评测）
    cache.clear_by_prefix("qa")

    service = ChatService()
    answerable = 0
    skipped = 0
    refusal_total = 0
    correct = 0
    refusal_correct = 0
    hallucination = 0
    incomplete = 0
    latencies: List[float] = []
    details = []

    for item in items[:limit] if limit else items:
        should_refuse = bool(item.get("should_refuse"))
        if not should_refuse and not golden.get(item["id"]):
            skipped += 1  # 知识库中无对应内容，无法评测
            continue

        result = service.ask(
            question=item["question"],
            security_level=EVAL_SECURITY_LEVEL,
        )
        answer = result.get("answer", "")
        sources = result.get("sources", [])
        latency = result.get("latency", {}).get("total_ms", 0)
        latencies.append(latency)

        keywords = [k for k in item.get("keywords", []) if k]
        answer_norm = _norm(answer)
        has_all_keywords = all(_norm(k) in answer_norm for k in keywords)
        is_refusal = _is_refusal(answer)

        if should_refuse:
            refusal_total += 1
            if is_refusal:
                refusal_correct += 1
        else:
            answerable += 1
            if has_all_keywords:
                correct += 1
            elif not sources:
                hallucination += 1  # 无来源引用却给出了回答
            else:
                incomplete += 1  # 有来源但答案不完整/不准确

        details.append({
            "id": item["id"], "question": item["question"],
            "should_refuse": should_refuse,
            "is_refusal": is_refusal,
            "has_sources": bool(sources),
            "keywords_ok": has_all_keywords,
            "total_ms": latency,
            "answer_preview": (answer or "")[:120],
        })

    metrics = {
        "answerable_total": answerable,
        "skipped_unresolved": skipped,
        "refusal_total": refusal_total,
        "answer_accuracy": (correct / answerable if answerable else 0.0),
        "refusal_accuracy": (refusal_correct / refusal_total if refusal_total else 0.0),
        "hallucination_rate": (hallucination / answerable if answerable else 0.0),
        "incomplete_rate": (incomplete / answerable if answerable else 0.0),
        "avg_total_ms": (sum(latencies) / len(latencies) if latencies else 0.0),
    }
    return {"metrics": metrics, "details": details}


# ==================== 报告 ====================

def _print_report(mode: str, results: dict) -> None:
    # 比率字段用百分比，耗时字段用毫秒
    PERCENT_FIELDS = {
        "hit@1", "hit@3", "hit@5", "hit@10",
        "answer_accuracy", "refusal_accuracy", "hallucination_rate", "incomplete_rate",
    }
    print("\n" + "=" * 60)
    print(f"RAG 评测报告 ({mode})")
    print("=" * 60)
    for key, value in results["metrics"].items():
        if key in PERCENT_FIELDS:
            print(f"  {key:<22}: {value:.2%}")
        elif key.endswith("_ms"):
            print(f"  {key:<22}: {value:.0f} ms")
        else:
            print(f"  {key:<22}: {value}")
    print("=" * 60)


def _save_report(report: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out_path = RESULTS_DIR / f"eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    # latest.json 供回归对比（git-save 流程读取）
    with open(RESULTS_DIR / "latest.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return out_path


# ==================== 主流程 ====================

def main() -> int:
    parser = argparse.ArgumentParser(description="企业知识库 RAG 评测脚本")
    parser.add_argument("--benchmark", type=Path,
                        default=EVAL_DIR / "qa_benchmark.json", help="基准集路径")
    parser.add_argument("--mode", choices=["retrieval", "answer", "all"],
                        default="all", help="评测模式")
    parser.add_argument("--limit", type=int, default=None,
                        help="只评测前 N 条（调试用）")
    parser.add_argument("--fail-under", type=float, default=None,
                        help="hit@5 与 answer_accuracy 的回归阈值，低于则退出码 1")
    args = parser.parse_args()

    items = _load_benchmark(args.benchmark)
    print(f"基准集条目: {len(items)}")

    # 黄金分块解析（检索与答案评测共用）
    golden = _resolve_golden_chunks(items)
    resolved = sum(1 for i in items if not i.get("should_refuse") and golden.get(i["id"]))
    print(f"黄金分块可解析条目: {resolved} / {len([i for i in items if not i.get('should_refuse')])}")

    report: dict = {"benchmark": str(args.benchmark), "results": {}}

    if args.mode in ("retrieval", "all"):
        print("\n[1/2] 检索命中率评测（不调用 LLM）...")
        t0 = time.time()
        ret = eval_retrieval(items, golden)
        print(f"  耗时 {time.time() - t0:.1f}s")
        _print_report("retrieval", ret)
        report["results"]["retrieval"] = ret

    if args.mode in ("answer", "all"):
        print("\n[2/2] 答案评测（完整 RAG 链路，含 LLM 调用）...")
        t0 = time.time()
        ans = eval_answer(items, args.limit, golden)
        print(f"  耗时 {time.time() - t0:.1f}s")
        _print_report("answer", ans)
        report["results"]["answer"] = ans

    out_path = _save_report(report)
    print(f"\n报告已保存: {out_path}")

    # 回归阈值判定（git-save / CI 使用）
    if args.fail_under is not None:
        hit5 = report["results"].get("retrieval", {}).get("metrics", {}).get("hit@5")
        acc = report["results"].get("answer", {}).get("metrics", {}).get("answer_accuracy")
        failures = []
        if hit5 is not None and hit5 < args.fail_under:
            failures.append(f"检索 hit@5 {hit5:.2%} < 阈值 {args.fail_under:.2%}")
        if acc is not None and acc < args.fail_under:
            failures.append(f"答案正确率 {acc:.2%} < 阈值 {args.fail_under:.2%}")
        if failures:
            # 使用纯 ASCII 输出，避免 Windows GBK 控制台对 emoji 的 UnicodeEncodeError
            print("\n[FAIL] 回归失败:\n  - " + "\n  - ".join(failures))
            return 1
        print(f"\n[PASS] 回归通过（阈值 {args.fail_under:.2%}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
