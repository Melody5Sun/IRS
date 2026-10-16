import csv
import json

import scripts.evaluate_rewrite as evaluate_rewrite


def test_detector_report_counts_per_split() -> None:
    cases = [
        {"text": "Responsible for building the payment API with FastAPI and Redis", "issues": ["weak_action_verb"], "section": "experience"},
        {"text": "Built the payment API with FastAPI, cutting latency by 30% for 2M users", "issues": [], "section": "experience"},
    ]
    counts = evaluate_rewrite.detector_report(cases, "heldout", verbose=False)
    assert counts["weak_action_verb"]["tp"] == 1
    assert counts["weak_action_verb"]["fp"] == 0


def test_score_averages_each_arm(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(evaluate_rewrite, "OUTPUT_ROOT", tmp_path)
    (tmp_path / "w4_key.json").write_text(json.dumps({"R01": "rag", "R02": "rag", "R03": "no_rag"}), encoding="utf-8")
    with (tmp_path / "w4_rating_sheet.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["编号", *evaluate_rewrite.RATING_DIMENSIONS])
        writer.writerows([["R01", 5, 4, 3, 2], ["R02", 3, 4, 5, ""], ["R03", 1, 1, 1, 1]])
    with (tmp_path / "rejected_changes_review.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["组", "判定(真编造/误拒)"])
        writer.writerows([["有 RAG", "误拒"], ["有 RAG", ""]])

    evaluate_rewrite.score()

    out = capsys.readouterr().out
    # 空格不计入均值：理由正确一列 R01 一行算 2.000
    assert "有 RAG（2 行）" in out and "4.000" in out and "2.000" in out
    assert "无 RAG（1 行）" in out and "1.000" in out
    assert "有 RAG 误拒 1" in out and "有 RAG 未判定 1" in out
