# ============================================================
# 评测脚本 Windows 控制台编码回归测试
# 背景：evaluate.py 曾在输出中使用 emoji，Windows GBK(cp936) 控制台
#       抛 UnicodeEncodeError，导致 --fail-under 回归流程直接崩溃。
# 修复：输出文案改为 GBK 可编码文本（[PASS]/[FAIL]）。
# 本文件在"强制 GBK 标准输出"下真实执行命令行主流程（不调用 LLM /
# Embedding API，评测函数被替换为桩），验证不再崩溃。
# ============================================================

import importlib.util
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
EVALUATE_PATH = BACKEND_DIR / "evaluation" / "evaluate.py"


@pytest.fixture(scope="module")
def evaluate_module():
    """按文件路径加载 evaluate.py（evaluation 目录不是 Python 包）"""
    spec = importlib.util.spec_from_file_location("evaluate_under_test", EVALUATE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_cli_under_gbk(module, monkeypatch, tmp_path, argv, metrics):
    """在 GBK(cp936, errors=strict) 标准输出下执行 main()，返回 (退出码, 输出文本)"""
    monkeypatch.setattr(sys, "argv", ["evaluate.py", *argv])
    # 报告写入临时目录，避免污染真实 evaluation/results/
    monkeypatch.setattr(module, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(module, "_load_benchmark", lambda path: [
        {"id": 1, "doc": "00_示例.md", "question": "示例问题", "keywords": ["示例"]},
    ])
    monkeypatch.setattr(module, "_resolve_golden_chunks", lambda items: {1: {"c1"}})
    monkeypatch.setattr(module, "eval_retrieval", lambda items, golden: {
        "metrics": {"total": 1, "skipped_unresolved": 0, **metrics},
        "details": [],
    })

    buf = io.BytesIO()
    wrapper = io.TextIOWrapper(buf, encoding="gbk", errors="strict", newline="\n")
    with redirect_stdout(wrapper):
        code = module.main()
    wrapper.flush()
    return code, buf.getvalue().decode("gbk")


class TestEvaluateOutputEncodableInGbk:
    def test_源码不含GBK不可编码字符(self):
        """整份源码（含全部输出文案）必须能被 GBK 编码，防止 emoji 回归"""
        source = EVALUATE_PATH.read_text(encoding="utf-8")
        source.encode("gbk")  # 含 emoji 时抛 UnicodeEncodeError

    def test_回归失败路径在GBK控制台不崩溃(self, evaluate_module, monkeypatch, tmp_path):
        """--fail-under 未达标：输出 [FAIL] 文案，退出码 1，无 UnicodeEncodeError"""
        code, out = _run_cli_under_gbk(
            evaluate_module, monkeypatch, tmp_path,
            ["--mode", "retrieval", "--fail-under", "0.9"],
            {"hit@1": 0.0, "hit@3": 0.0, "hit@5": 0.0, "hit@10": 0.1},
        )
        assert code == 1
        assert "[FAIL]" in out
        assert "hit@5" in out

    def test_回归通过路径在GBK控制台不崩溃(self, evaluate_module, monkeypatch, tmp_path):
        """阈值达标：输出 [PASS] 文案，退出码 0"""
        code, out = _run_cli_under_gbk(
            evaluate_module, monkeypatch, tmp_path,
            ["--mode", "retrieval", "--fail-under", "0.5"],
            {"hit@1": 0.9, "hit@3": 0.9, "hit@5": 0.9, "hit@10": 1.0},
        )
        assert code == 0
        assert "[PASS]" in out
