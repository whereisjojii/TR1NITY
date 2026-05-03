import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib as mpl

mpl.rcParams["font.family"] = "DejaVu Sans"

# 6 phases over 16 weeks (week-numbered)
phases = [
    # (label,                                 start_week, duration, shade)
    ("Phase 0 — Repo Foundation\n(repo, Docker Compose, CI, configs)", 0, 1, "#90CAF9"),
    (
        "Phase 1 — Multi-Source Ingestion\n(Wazuh + Firewall + WAF -> ECS index)",
        1,
        2,
        "#64B5F6",
    ),
    (
        "Phase 2 — The Brain (Correlation)\n(temporal grouping, ATT&CK, TI, SIGMA)",
        3,
        4,
        "#1E88E5",
    ),
    (
        "Phase 3 — The Cockpit (React UI)\n(queue, investigation, heatmap, cases)",
        7,
        4,
        "#1976D2",
    ),
    (
        "Phase 4 — FP Loop & Runbooks\n(3-layer FP system, 15 runbooks)",
        11,
        2,
        "#1565C0",
    ),
    (
        "Phase 5 — AI Assist (HITL)\n(llama.cpp+Vulkan, Foundation-Sec-8B, RAG)",
        13,
        2,
        "#0D47A1",
    ),
    (
        "Phase 6 — Polish, Reports, Launch\n(compliance PDF, demo, v1.0)",
        15,
        1,
        "#082F66",
    ),
]

fig, ax = plt.subplots(figsize=(11, 5.6))
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

bar_height = 0.55
y_positions = list(range(len(phases)))[::-1]  # reverse so Phase 0 is at top

for y, (label, start, dur, color) in zip(y_positions, phases):
    rect = FancyBboxPatch(
        (start, y - bar_height / 2),
        dur,
        bar_height,
        boxstyle="round,pad=0.02,rounding_size=0.10",
        linewidth=1.0,
        edgecolor="#0D47A1",
        facecolor=color,
    )
    ax.add_patch(rect)
    # Week range label inside the bar
    txt_color = (
        "white"
        if color in ("#1976D2", "#1565C0", "#0D47A1", "#082F66", "#1E88E5")
        else "#0D47A1"
    )
    if dur >= 2:
        ax.text(
            start + dur / 2,
            y,
            f"W{start+1}–W{start+dur}",
            va="center",
            ha="center",
            color=txt_color,
            fontsize=9,
            fontweight="bold",
        )
    else:
        ax.text(
            start + dur / 2,
            y,
            f"W{start+1}",
            va="center",
            ha="center",
            color=txt_color,
            fontsize=9,
            fontweight="bold",
        )

# Y-axis (phase labels)
ax.set_yticks(y_positions)
ax.set_yticklabels([p[0] for p in phases], fontsize=9, color="#0D47A1")

# X-axis (week labels)
ax.set_xlim(0, 16)
ax.set_xticks(range(0, 17, 1))
ax.set_xticklabels(
    [f"W{i}" if i > 0 else "" for i in range(0, 17)], fontsize=8, color="#0D47A1"
)
ax.set_xlabel("Project Timeline (Weeks)", fontsize=10, color="#0D47A1", labelpad=8)

# Style
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)
ax.spines["left"].set_color("#0D47A1")
ax.spines["bottom"].set_color("#0D47A1")
ax.spines["left"].set_linewidth(0.8)
ax.spines["bottom"].set_linewidth(0.8)
ax.tick_params(axis="both", colors="#0D47A1")

# Vertical milestone markers
milestones = [
    (1, "v0.1.0\nFoundation", "#90CAF9"),
    (3, "v0.2.0\nIngest", "#64B5F6"),
    (7, "v0.3.0\nBrain", "#1E88E5"),
    (11, "v0.4.0\nCockpit", "#1976D2"),
    (13, "v0.5.0\nFP Loop", "#1565C0"),
    (15, "v0.6.0\nAI", "#0D47A1"),
    (16, "v1.0.0\nLaunch", "#082F66"),
]
y_top = max(y_positions) + 1.0
for w, name, c in milestones:
    ax.axvline(w, color=c, linestyle="--", linewidth=0.7, alpha=0.55)
    ax.text(
        w,
        y_top - 0.05,
        name,
        ha="center",
        va="bottom",
        fontsize=7.5,
        color=c,
        fontweight="bold",
    )

ax.set_ylim(min(y_positions) - 0.7, y_top + 0.6)

# Title
ax.set_title(
    "TR1NITY — Project Timeline Gantt Chart  (16-Week Plan to v1.0)",
    fontsize=13,
    color="#0D47A1",
    fontweight="bold",
    pad=18,
)

plt.tight_layout()
plt.savefig(
    "/home/ubuntu/tr1nity-report/figures/gantt.png",
    dpi=200,
    bbox_inches="tight",
    facecolor="white",
)
plt.savefig(
    "/home/ubuntu/tr1nity-report/figures/gantt.pdf",
    bbox_inches="tight",
    facecolor="white",
)
print("OK")
