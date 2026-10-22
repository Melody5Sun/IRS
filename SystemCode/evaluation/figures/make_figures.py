"""生成评测文档里的图。数字抄自 README.md 对应表格（来源见各表的「运行」列），改数字时两处一起改。

用法：python SystemCode/evaluation/figures/make_figures.py（需要 matplotlib；图中文字为英文，供最终报告使用）
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

OUT = Path(__file__).resolve().parent
BEFORE, AFTER = "#2a78d6", "#eb6834"  # 分类色第 1、2 位：修改前 / 修改后
INK, MUTED, GRID = "#1f1f1e", "#6b6a63", "#e4e3dd"

# 中文字体：取系统里第一个能用的
for name in ("WenQuanYi Zen Hei", "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "PingFang SC"):
    if any(f.name == name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = name
        break
plt.rcParams.update({"axes.edgecolor": GRID, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False})


def grouped(ax, labels, before, after, title, ylim):
    x = range(len(labels))
    width = 0.36
    for offset, values, color, name in ((-width / 2, before, BEFORE, "Before"), (width / 2, after, AFTER, "After")):
        bars = ax.bar([i + offset for i in x], values, width - 0.04, color=color, label=name)
        ax.bar_label(bars, fmt="%g", fontsize=8, color=INK, padding=2)
    ax.set_xticks(list(x), labels)
    ax.set_ylim(*ylim)
    ax.set_title(title, color=INK, fontsize=11, loc="left")
    ax.yaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)


# 图 1：W4 混合盲评，哑铃图：修改前 → 修改后的箭头，和"同一批修改前的行被评两次"的差距（评分者噪声）放在一起看
dims = ["Factual\nconsistency", "Better than\noriginal", "JD fit", "Correct\nreason"]
W4 = {  # 组: (修改前首次评分, 修改前混合盲评, 修改后混合盲评)
    "With RAG (production path, 20 rows each)": ([4.60, 3.35, 3.00, 4.25], [4.20, 3.15, 2.95, 3.55], [4.45, 3.30, 3.30, 3.70]),
    "No-RAG control (10 rows each)": ([4.60, 3.40, 3.20, 4.00], [4.20, 3.30, 3.20, 3.70], [4.00, 2.80, 3.20, 3.70]),
}
fig, axes = plt.subplots(1, 2, figsize=(11, 3.4), sharey=True)
axes[0].invert_yaxis()  # 共享 y 轴，只翻转一次
for ax, (title, (first, before, after)) in zip(axes, W4.items()):
    for y, (f, b, a) in enumerate(zip(first, before, after)):
        # 灰色带：同一批修改前的行两次打分的差距
        ax.plot([min(f, b), max(f, b)], [y, y], color=GRID, lw=9, solid_capstyle="round", zorder=1)
        ax.annotate("", xy=(a, y), xytext=(b, y),
                    arrowprops={"arrowstyle": "-|>", "color": MUTED, "lw": 1.2, "shrinkA": 6, "shrinkB": 6}, zorder=2)
        ax.scatter([b], [y], s=70, color=BEFORE, edgecolor="white", linewidth=1.5, zorder=3)
        ax.scatter([a], [y], s=70, color=AFTER, edgecolor="white", linewidth=1.5, zorder=3)
        ax.text(5.35, y, f"{a - b:+.2f}", va="center", ha="right", fontsize=10, color=INK, fontweight="bold")
    ax.set_yticks(range(len(dims)), dims)
    ax.set_xlim(2.5, 5.4)
    ax.set_xticks([3, 4, 5])
    ax.xaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0, labelsize=10, labelcolor=INK)
    ax.set_title(title, color=INK, fontsize=11, loc="left")
    ax.text(5.35, -0.75, "Δ", ha="right", fontsize=9, color=MUTED)
axes[0].set_xlabel("Mean blind rating (1–5)", color=MUTED)
axes[1].set_xlabel("Mean blind rating (1–5)", color=MUTED)
handles = [
    plt.Line2D([], [], marker="o", ls="", color=BEFORE, markersize=8, label="Before (pre-R3)"),
    plt.Line2D([], [], marker="o", ls="", color=AFTER, markersize=8, label="After (R4)"),
    plt.Line2D([], [], color=GRID, lw=7, label="Gap between two ratings of the same before-rows (rater noise)"),
]
fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=9, bbox_to_anchor=(0.5, -0.02))
fig.tight_layout(rect=(0, 0.08, 1, 1))
fig.savefig(OUT / "w4_blind_rating.png", dpi=160)

# 图 4：解析各项指标，同一套新金标下旧 prompt（R4-前）vs 新 prompt（R4）；全部为 1.000 不变的指标不画
parse = [  # (指标, 旧 prompt, 新 prompt)
    ("Entry F1 (all sections)", 0.879, 0.883), ("projects F1", 0.941, 0.906), ("research F1", 0.914, 0.914),
    ("educations F1", 0.980, 1.000), ("certificates F1", 0.917, 0.917), ("skill_groups F1", 0.989, 0.955),
    ("additional_info F1", 0.462, 0.538), ("Field accuracy (17 fields)", 0.997, 0.994),
    ("Long-text fact retention", 0.939, 0.925), ("Long-text semantic similarity", 0.963, 0.945), ("skills F1", 0.787, 0.783),
]
fig, ax = plt.subplots(figsize=(8, 5.6))
height = 0.38
for i, (name, old, new) in enumerate(parse):
    ax.barh(i - height / 2, old, height - 0.04, color=BEFORE, label="Old prompt" if i == 0 else None)
    ax.barh(i + height / 2, new, height - 0.04, color=AFTER, label="New prompt" if i == 0 else None)
    ax.text(1.24, i, f"{new - old:+.3f}", va="center", ha="right", fontsize=9.5, color=INK,
            fontweight="bold" if abs(new - old) >= 0.01 else "normal")
    ax.text(old + 0.008, i - height / 2, f"{old:.3f}", va="center", fontsize=7.5, color=MUTED)
    ax.text(new + 0.008, i + height / 2, f"{new:.3f}", va="center", fontsize=7.5, color=MUTED)
ax.set_yticks(range(len(parse)), [name for name, _, _ in parse])
ax.invert_yaxis()
ax.set_xlim(0, 1.25)
ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
ax.xaxis.grid(True, color=GRID)
ax.set_axisbelow(True)
ax.tick_params(axis="y", length=0, labelcolor=INK)
ax.text(1.24, -0.9, "Δ", ha="right", fontsize=9, color=MUTED)
ax.set_title("Parsing metrics: old vs new prompt (same new gold labels, 14 resumes)", color=INK, fontsize=11, loc="left")
ax.legend(frameon=False, fontsize=9, loc="lower left", bbox_to_anchor=(0, -0.13), ncol=2)
fig.tight_layout()
fig.savefig(OUT / "parsing_before_after.png", dpi=160)

# 图 2：改写占位数（R4 前后）
fig, ax = plt.subplots(figsize=(6, 3.2))
grouped(ax, ["Avg. new placeholders\nper change", "Max new placeholders\nin one change"], [1.84, 7], [0.44, 2], "New placeholders in rewrites (14 resume × job pairs)", (0, 8))
ax.legend(frameon=False, fontsize=9)
fig.tight_layout()
fig.savefig(OUT / "rewrite_placeholders.png", dpi=160)

# 图 3：additional_info F1 拆解：金标重标的贡献 vs prompt 修改的贡献
fig, ax = plt.subplots(figsize=(6, 3.2))
steps = ["Old prompt\nold gold", "Old prompt\nnew gold", "New prompt\nnew gold"]
values = [0.368, 0.462, 0.538]
bars = ax.bar(steps, values, 0.5, color=[BEFORE, BEFORE, AFTER])
ax.bar_label(bars, fmt="%.3f", fontsize=9, color=INK, padding=2)
ax.set_ylim(0, 0.7)
ax.set_title("Parsing additional_info F1 (14 gold-labelled resumes)", color=INK, fontsize=11, loc="left")
ax.yaxis.grid(True, color=GRID)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(OUT / "additional_info_f1.png", dpi=160)
print("ok")
