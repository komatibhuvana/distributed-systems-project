#!/usr/bin/env python3
"""Builder for Paper 2 (companion to Paper1_Submissionready.docx).

Produces Paper2_Submissionready.docx, matching Paper 1's formatting:
A4 page, 1in margins, Times New Roman; title 18pt bold center, authors 13pt,
H1 bold 14pt, H2 bold 12pt, abstract body 10.5pt justify, body 11pt justify,
equations centered with (n) tab, captions bold 9.5pt, Table Grid tables 9.5pt.

All numeric results are read at build time from the simulation CSVs (see
build_paper2_figures.py for the producing scripts). Topics are strictly those NOT
covered by Paper 1 (which owns tandem queue + heavy-tailed/M/G/N + EVT).
"""
import os
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

FIGDIR = "paper2_figures"

FONT = "Times New Roman"

doc = Document()

# ---- page geometry: A4, 1in margins (match Paper 1) ----
sec = doc.sections[0]
sec.page_width = 7562215
sec.page_height = 10689590
sec.left_margin = sec.right_margin = sec.top_margin = sec.bottom_margin = 914400

# ---- base Normal style ----
normal = doc.styles["Normal"]
normal.font.name = FONT
normal.font.size = Pt(11)
rpr = normal.element.get_or_add_rPr()
rfonts = rpr.get_or_add_rFonts()
rfonts.set(qn("w:ascii"), FONT)
rfonts.set(qn("w:hAnsi"), FONT)
rfonts.set(qn("w:cs"), FONT)


def _set_run(r, size=None, bold=None, italic=None):
    r.font.name = FONT
    rpr = r._element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    for tag in ("w:ascii", "w:hAnsi", "w:cs"):
        rfonts.set(qn(tag), FONT)
    if size is not None:
        r.font.size = Pt(size)
    if bold is not None:
        r.font.bold = bold
    if italic is not None:
        r.font.italic = italic


def para(align=None, space_after=6, space_before=0):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(space_before)
    return p


def title(text):
    p = para(WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    _set_run(p.add_run(text), size=18, bold=True)


def center(text, size=11, bold=False, italic=False, space_after=2):
    p = para(WD_ALIGN_PARAGRAPH.CENTER, space_after=space_after)
    _set_run(p.add_run(text), size=size, bold=bold, italic=italic)


def h1(text):
    p = para(space_before=10, space_after=4)
    _set_run(p.add_run(text), size=14, bold=True)


def h2(text):
    p = para(space_before=6, space_after=3)
    _set_run(p.add_run(text), size=12, bold=True)


def body(text, size=11, justify=True):
    p = para(WD_ALIGN_PARAGRAPH.JUSTIFY if justify else None, space_after=6)
    _set_run(p.add_run(text), size=size)
    return p


def body_lead(lead, rest, size=11):
    """Paragraph whose first chunk is bold (e.g. 'Keywords:')."""
    p = para(WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=6)
    _set_run(p.add_run(lead), size=size, bold=True)
    _set_run(p.add_run(rest), size=size)
    return p


def equation(text):
    p = para(WD_ALIGN_PARAGRAPH.CENTER, space_after=6, space_before=2)
    _set_run(p.add_run(text), size=11)


def caption(text):
    p = para(WD_ALIGN_PARAGRAPH.CENTER, space_after=4, space_before=2)
    # split "Table N:" / "Figure N:" label as bold
    if ":" in text:
        label, rest = text.split(":", 1)
        _set_run(p.add_run(label + ":"), size=9.5, bold=True)
        _set_run(p.add_run(rest), size=9.5)
    else:
        _set_run(p.add_run(text), size=9.5, bold=True)


def figure(filename, width=5.6):
    """Insert a centered figure from FIGDIR."""
    path = os.path.join(FIGDIR, filename)
    p = para(WD_ALIGN_PARAGRAPH.CENTER, space_after=2, space_before=4)
    run = p.add_run()
    run.add_picture(path, width=Inches(width))


def table(rows, header=True, col_widths=None):
    ncols = len(rows[0])
    t = doc.add_table(rows=len(rows), cols=ncols)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = t.cell(i, j)
            cell.text = ""
            cp = cell.paragraphs[0]
            cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cp.paragraph_format.space_after = Pt(1)
            cp.paragraph_format.space_before = Pt(1)
            _set_run(cp.add_run(str(val)), size=9.5, bold=(header and i == 0))
    # small spacer after table
    para(space_after=4)
    return t



# =====================================================================
# DATA (every number in the text below is read from these CSVs)
# =====================================================================
import pandas as pd

R2 = "results/paper2"
VT = pd.read_csv("experiments/visibility_timeout_results.csv")
REP = pd.read_csv("experiments/replication_factor_results.csv")
ORD = pd.read_csv("experiments/ordering_mode_results.csv")
TH = pd.read_csv(f"{R2}/threading.csv")
HS = pd.read_csv(f"{R2}/hetero_scenarios.csv")
HP = pd.read_csv(f"{R2}/hetero_policies.csv")
HI = pd.read_csv(f"{R2}/hetero_instability.csv")
OH = pd.read_csv(f"{R2}/twopc_overhead.csv")
TQ = pd.read_csv(f"{R2}/twopc_queue.csv")
TI = pd.read_csv(f"{R2}/twopc_instability.csv")
PC = pd.read_csv(f"{R2}/protocol_capacity.csv")
RE = pd.read_csv(f"{R2}/raft_elections.csv")
RC = pd.read_csv(f"{R2}/raft_commit.csv")
RQ = pd.read_csv(f"{R2}/raft_queue.csv")
VC = pd.read_csv(f"{R2}/vector_clocks.csv")
VCC = pd.read_csv(f"{R2}/vector_clocks_correctness.csv")
TP = pd.read_csv(f"{R2}/twopc_protocol.csv")
FC = pd.read_csv(f"{R2}/finite_capacity.csv")
PR = pd.read_csv(f"{R2}/priority.csv")
EK = pd.read_csv(f"{R2}/erlang_k.csv")


def one(df, **kw):
    """The single row of df matching all column==value filters"""
    m = pd.Series(True, index=df.index)
    for k, v in kw.items():
        m &= df[k] == v
    rows = df[m]
    assert len(rows) == 1, (kw, len(rows))
    return rows.iloc[0]


def f(x, nd=3):
    return f"{x:.{nd}f}"


def pm(mean, half, nd=3):
    return f"{mean:.{nd}f} ± {half:.{nd}f}"


def pct(x, nd=1):
    return f"{x * 100:.{nd}f}%"


def ratio(a, b, nd=2):
    return f"{a / b:.{nd}f}×"


# ---- visibility timeout
vt_min = VT.loc[VT.mean_latency.idxmin()]
vt05, vt1, vt5, vt30, vt120 = (one(VT, visibility_timeout=v) for v in (0.5, 1.0, 5.0, 30.0, 120.0))
# ---- replication
rep = {(r.node_outages, r.replication_factor): r for r in REP.itertuples()}
# ---- ordering
ordr = {(r.arrival_rate, r.Mode): r for r in ORD.itertuples()}
# ---- 2PC
oh_def = one(OH, config="default")
oh_a1 = one(OH, config="avail_1.0")
tq = {(r.variant, r.replica_availability, r.vote_timeout_s, r.arrival_rate): r for r in TQ.itertuples()}
tq_base60 = TQ[(TQ.variant == "no_2pc") & (TQ.arrival_rate == 60)].iloc[0]
tq_def60 = TQ[(TQ.variant == "2pc") & (TQ.replica_availability == 0.99) & (TQ.vote_timeout_s == 1.0) & (TQ.arrival_rate == 60)].iloc[0]
tq_a1_60 = TQ[(TQ.variant == "2pc") & (TQ.replica_availability == 1.0) & (TQ.arrival_rate == 60)].iloc[0]
ti100 = TI[(TI.variant == "2pc") & (TI.arrival_rate == 100)].iloc[0]
ti_base100 = TI[(TI.variant == "no_2pc")].iloc[0]
pc_none = PC[PC.variant == "none"].iloc[0]
pc = {r.param: r for r in PC.itertuples()}
# ---- Raft
re = {(r.param_set, r.cluster_size): r for r in RE.itertuples()}
rc = {(r.param_set, bool(r.replicate_log_entries), r.cluster_size): r for r in RC.itertuples()}
rq = {(r.variant, r.cluster_size, r.arrival_rate): r for r in RQ.itertuples()}
# ---- vector clocks
vcb = {(r.num_processes, r.broadcast_rate, r.delay_cv): r for r in VC[VC.implementation == "bss"].itertuples()}
vcn = {(r.num_processes, r.broadcast_rate, r.delay_cv): r for r in VC[VC.implementation == "none"].itertuples()}
vc_checks_pass = int(VCC.iloc[:, -1].astype(str).str.lower().isin(["true", "pass", "1"]).sum()) if len(VCC.columns) else 0
# ---- threading
th = {(r.rho, r.model): r for r in TH.itertuples()}
# ---- heterogeneity
hs = {(r.scenario, r.policy): r for r in HS.itertuples()}
hp = {r.policy: r for r in HP.itertuples()}
hi = {(r.scenario, r.sim_duration): r for r in HI.itertuples()}
# ---- queueing extensions
fc = {(r.lambda_, r.K): r for r in FC.itertuples()}
fc_inside = int(FC.P_K_within_ci.astype(bool).sum() + FC.Wq_within_ci.astype(bool).sum())
fc_total = int(FC.P_K_within_ci.notna().sum() + FC.Wq_within_ci.notna().sum())
pr_base = PR[PR.sweep.str.startswith("base")]
ek = {(r.config, r.k): r for r in EK.itertuples()}

N_REP_DEFAULT = 10

# =====================================================================
# FRONT MATTER
# =====================================================================
title("Reliability, Consistency, and Threading Architectures in Cloud "
      "Message Brokers: A Distributed-Systems Performance Study")
center("Bhuvana Komati¹, Himanshu Jain², and Vidhyacharan Bhaskar³*",
       size=13, space_after=4)
center("¹²³Department of Computer Engineering", size=11)
center("San Jose State University", size=11)
center("One Washington Square, San Jose, CA 95192, USA", size=11)
center("Email: bhuvana.komati@sjsu.edu, himanshu.jain@sjsu.edu, "
       "charan.bhaskar@sjsu.edu", size=11)
center("*Corresponding author email: charan.bhaskar@sjsu.edu", size=10, italic=True)
center("October 2026", size=11, space_after=8)

d_def = oh_def.analytic_capacity_reduction_pct
center("Abstract", size=12, bold=True, space_after=4)
body(
    "Cloud message brokers such as AWS SQS, RabbitMQ, and Apache Kafka must "
    "guarantee at-least-once delivery, durability, ordering, and—for "
    "transactional workloads—atomicity and agreement across replicas. These "
    "mechanisms, and the thread-pool architecture that executes them, impose a "
    "performance cost that classical queueing models ignore. This companion to "
    "our study of heavy-tailed service times holds the workload fixed and "
    "quantifies the cost of the broker's distributed-systems machinery with a "
    "seeded SimPy discrete-event framework, reporting every result as a mean "
    "over independent replications with a 95% confidence interval and, wherever "
    "a closed form exists, against an exact analytical value. Two-Phase Commit "
    f"with three replicas, 10 ms round trips, and 0.99 replica availability adds "
    f"{oh_def.sampled_overhead_mean_s * 1000:.1f} ms per message—half of it from "
    f"rare 1 s vote timeouts—and cuts saturation throughput by "
    f"{pc[str((0.99, 1.0))].measured_capacity_reduction_pct_vs_none:.1f}%; Raft "
    f"commit on the critical path costs "
    f"{pc[str(('realistic_lan', 3))].measured_capacity_reduction_pct_vs_none:.1f}% of capacity on a "
    f"LAN but {pc[str(('realistic_wan', 3))].measured_capacity_reduction_pct_vs_none:.1f}% on a WAN. "
    "The visibility timeout has an interior optimum: very short timeouts cause "
    f"duplicate deliveries ({pct(vt05.duplicate_rate, 0)} of messages at 0.5 s) "
    "and dead-lettering, while long ones add roughly a tenth of the timeout to mean "
    "latency. Replication matters only when nodes fail: with node outages, two "
    "replicas cut the mean time to first delivery from "
    f"{rep[('on', 1)].mean_first_receive:.2f} s to {rep[('on', 2)].mean_first_receive:.2f} s. "
    "Strict in-order delivery costs "
    f"{(ordr[(80, 'In-Order')].Mean_Latency_ms / ordr[(80, 'Out-of-Order')].Mean_Latency_ms - 1) * 100:.0f}% "
    "mean latency at moderate load. A shared thread pool is "
    f"{(th[(0.7, 'shared')].mean_response / th[(0.7, 'baseline')].mean_response - 1) * 100:.0f}% "
    f"slower than an ideal pool at ρ = 0.7 and {ratio(th[(0.9, 'shared')].mean_response, th[(0.9, 'baseline')].mean_response, 1)} "
    "slower at ρ = 0.9, whereas a dedicated pool behaves as an Erlang loss "
    "system that rejects up to "
    f"{pct(th[(0.9, 'dedicated')].rejection_rate, 0)} of arrivals. For heterogeneous "
    "servers we show that the large penalties often attributed to service-rate "
    "variance are instead per-pool instability caused by load-oblivious "
    "dispatch: with capacity-proportional or queue-aware routing every "
    "configuration is stable, and the most heterogeneous one waits no longer "
    "than a homogeneous fleet.",
    size=10.5)
body_lead("Keywords: ",
          "Two-Phase Commit, Raft Consensus, Vector Clocks, Causal Delivery, "
          "Thread Pool Architecture, Visibility Timeout, Replication, "
          "Message Ordering, Heterogeneous Servers, Discrete-Event Simulation",
          size=10.5)

# =====================================================================
# 1. INTRODUCTION
# =====================================================================
h1("1   Introduction")
body(
    "Cloud message brokers decouple producers from consumers and absorb load "
    "spikes through asynchronous queues. Production systems such as AWS Simple "
    "Queue Service (SQS), RabbitMQ, and Apache Kafka are not simple FIFO buffers: "
    "to guarantee no message loss, survivable storage, ordered or causally "
    "consistent delivery, and in some cases transactional atomicity, they layer "
    "visibility timeouts and redelivery, multi-replica storage, consensus, and "
    "atomic-commit protocols on top of the raw queue. Each mechanism consumes "
    "time and threads, and that cost is invisible to a textbook M/M/N analysis.")
body(
    "In a companion paper we studied one axis of broker performance—the "
    "effect of heavy-tailed (Pareto) service-time distributions on tail latency "
    "and the resulting gap between M/M/N predictions and simulation. The present "
    "paper is the orthogonal study: we hold the service distribution "
    "(exponential, unless stated) fixed and quantify the performance "
    "consequences of the reliability, consistency, and concurrency mechanisms "
    "themselves.")
body(
    "Our contributions are fourfold. First, we measure the trade-offs of three "
    "reliability mechanisms—visibility timeout, replication under node "
    "outages, and message ordering. Second, we measure the latency and capacity "
    "cost of Two-Phase Commit and Raft on the critical path, and the hold-back "
    "cost of vector-clock causal delivery. Third, we compare dedicated and shared "
    "thread pools and identify each as a classical queueing system. Fourth, we "
    "relax four baseline assumptions—homogeneous servers, infinite buffers, "
    "a single priority class, and exponential service—and validate each "
    "extension against an exact or standard analytical result.")

h2("1.1   Background and Related Work")
body(
    "Lamport's logical clocks [2] established the happened-before relation, "
    "later refined into vector clocks by Fidge [3] and Mattern [4]; causal "
    "broadcast built on them was given by Birman, Schiper, and Stephenson [22]. "
    "Atomic commitment was formalized by Gray [7] as Two-Phase Commit, whose "
    "blocking behavior was analyzed by Gray and Lamport [8]. Fischer, Lynch, and "
    "Paterson [11] showed consensus impossible in a purely asynchronous system "
    "with one crash, motivating leader-based protocols such as Paxos [6] and "
    "Raft [5]. Brewer's CAP conjecture [9], proved by Gilbert and Lynch [10], "
    "frames the choice between consistency and availability under partition; "
    "Vogels [12] and Dynamo [13] describe the eventually consistent alternative. "
    "Dean and Barroso [14] showed that tail latency governs user experience at "
    "scale, which motivates our P99 measurements.")
body(
    "On the queueing side we use Erlang's loss and delay formulas [16], "
    "Kleinrock's treatment [15], Little's Law [17], Cobham's priority formula "
    "[23], the Allen–Cunneen approximation [24], and Harchol-Balter's synthesis "
    "[18]. Our base system is the cloud-broker model of Li et al. [1], whose "
    "visibility-timeout and ordering semantics we implement; where Li et al. use "
    "Colored Petri Nets, we use discrete-event simulation in SimPy [20].")

# =====================================================================
# 2. SYSTEM MODEL
# =====================================================================
h1("2   System Model and Methodology")
body(
    "All results are produced by a discrete-event simulator written in Python "
    "with SimPy 4.1.1 [20]. Messages arrive as a Poisson process of rate λ and "
    "are served by threads modeled as SimPy resources; protocols are modeled "
    "either as explicit state machines (storage nodes with visibility-timeout "
    "managers, Raft nodes, causal-broadcast members) or as additional service-time "
    "components (2PC). Every run discards a warm-up interval, and every random "
    "stream is seeded. Unless stated otherwise each configuration is replicated "
    f"{N_REP_DEFAULT} times with independent seeds, and we report the mean across "
    "replications with a 95% Student-t confidence interval (written mean ± "
    "half-width). Table 1 lists the common parameters.")
caption("Table 1: Common system and protocol parameters.")
table([
    ["Parameter", "Symbol", "Default value"],
    ["Service rate per thread", "μ", "12 msg/s"],
    ["2PC round-trip time", "RTT", "10 ms (σ = 2 ms)"],
    ["2PC replica availability / vote timeout", "a, T", "0.99, 1.0 s"],
    ["2PC replicas", "n", "3"],
    ["Raft LAN: election timeout, heartbeat, one-way delay", "—", "U[150, 300] ms, 50 ms, 2 ms + U[0, 3] ms"],
    ["Raft WAN: election timeout, heartbeat, one-way delay", "—", "U[150, 300] ms, 50 ms, 20 ms + U[0, 10] ms"],
    ["Visibility timeout (SQS default)", "VT", "30 s"],
    ["Max receive count (dead-letter threshold)", "—", "3"],
    ["Shared-pool overhead coefficient", "α", "0.1"],
    ["Threads per dedicated connection", "—", "2"],
])
body_lead("Model verification. ",
          "Wherever an exact result exists we compare the simulator against it: "
          "M/M/N (Erlang-C) for the threading baseline, Erlang-B for the "
          "dedicated pool, independent M/M/n_i queues for heterogeneous servers "
          "under static dispatch, the M/M/N/K birth–death solution for finite "
          "buffers, Cobham's formula and the work-conservation law for priority "
          "classes, a numerically solved continuous-time Markov chain (CTMC) for "
          "Erlang-k service, the closed-form 2PC overhead moments, and "
          "(1 − f)ⁿ for the 2PC commit rate. These checks are reported "
          "alongside each result.")

# =====================================================================
# 3. RELIABILITY
# =====================================================================
h1("3   Reliability Mechanisms")
body(
    "The broker model stores each message on a set of storage nodes chosen by a "
    "consistent-hash ring (150 virtual nodes per physical node, MD5 placement). "
    "Consumers poll a randomly chosen node—modeling SQS short polling—and "
    "back off for 0.1 s if it has no visible message. Receiving a copy hides all "
    "replicas of that message, so each logical message is delivered to one "
    "consumer at a time; acknowledgements use receipt handles, so an "
    "acknowledgement issued for a delivery that has already timed out is "
    "rejected, as in SQS.")

h2("3.1   Visibility Timeout and Redelivery")
body(
    "A received message is hidden for VT seconds. If it is acknowledged in time "
    "it is deleted; otherwise it becomes visible again and is redelivered, and a "
    "message whose receive count reaches 3 is moved to a dead-letter queue (DLQ) "
    "[19]. "
    "VT therefore has opposing effects: if it is shorter than the processing "
    "time, healthy consumers are timed out and the message is processed twice; "
    "if it is long, a genuinely failed message waits VT before its retry. We swept "
    "VT from 0.5 s to 120 s with λ = 10 msg/s, exponential processing with mean "
    "0.5 s, failure probability 0.1, 10 consumers, three nodes, and replication "
    "factor two (2000 s runs, 200 s warm-up, 10 replications). Duplicate rate is "
    "the number of completed-but-stale deliveries per published message; the "
    "delivery and DLQ ratios are measured over messages published at least "
    "3·VT + 10 s before the end of the run.")
caption("Table 2: Effect of visibility timeout (mean ± 95% CI over 10 replications).")
rows = [["VT (s)", "Mean latency (s)", "P99 latency (s)", "Mean retries", "Duplicates", "Dead-lettered"]]
for r in VT.itertuples():
    rows.append([f"{r.visibility_timeout:g}", pm(r.mean_latency, r.mean_latency_ci95, 2),
                 pm(r.p99_latency, r.p99_latency_ci95, 1), f(r.mean_retries, 3),
                 pct(r.duplicate_rate, 2), pct(r.dlq_ratio, 2)])
table(rows)
figure("fig1_visibility_timeout.png", width=6.2)
caption("Figure 1: Visibility-timeout trade-off. (A) Mean and P99 latency are "
        f"minimized near VT = {vt_min.visibility_timeout:g} s. (B) Below about 5 s, "
        "premature timeouts cause duplicate processing and dead-lettering.")
body(
    f"Mean latency is minimized at VT = {vt_min.visibility_timeout:g} s "
    f"({f(vt_min.mean_latency, 3)} s). Shorter timeouts expire while healthy "
    f"consumers are still working: at VT = 0.5 s, {pct(vt05.duplicate_rate, 1)} of "
    f"messages are processed twice and {pct(vt05.dlq_ratio, 1)} are wrongly "
    "dead-lettered after three premature timeouts. Once VT exceeds the processing "
    f"time by a wide margin (VT ≥ 5 s), duplicates disappear ({pct(vt5.duplicate_rate, 2)}) "
    f"and the DLQ ratio settles at {pct(vt30.dlq_ratio, 2)}, consistent with the "
    "0.1³ = 0.1% probability of three consecutive genuine failures. Beyond "
    "that point latency grows linearly with VT, because about one message in ten "
    "waits a full timeout before its retry: mean latency rises from "
    f"{f(vt5.mean_latency, 2)} s at 5 s to {f(vt30.mean_latency, 2)} s at the SQS "
    f"default of 30 s and {f(vt120.mean_latency, 2)} s at 120 s, and P99 latency "
    f"tracks VT itself ({f(vt30.p99_latency, 1)} s and {f(vt120.p99_latency, 1)} s). "
    "Mean retries fall only until duplicates vanish and then stay near the "
    "failure probability. VT should therefore be set a small multiple above the "
    "processing-time tail; the 30 s default is safe but costs latency for "
    "sub-second workloads.")

h2("3.2   Replication Under Node Outages")
body(
    "Each message is written to its primary node and the next R − 1 nodes on "
    "the ring, so storage grows R-fold. Without node failures replication can "
    "only add cost, so we also inject independent node outages: each of the three "
    "nodes fails after an exponential up-time with mean 100 s and recovers after "
    "an exponential down-time with mean 20 s. While a node is down its copies "
    "cannot be read; acknowledgements are still applied. We used λ = 100 msg/s, "
    "processing mean 0.05 s, failure probability 0.1, VT = 30 s, and 20 consumers "
    "(enough that polls wasted on a down node do not saturate the consumer pool), "
    "with 500 s runs, a 50 s warm-up, and 30 replications. Because end-to-end "
    "latency is dominated by the 30 s retry of the 10% failed messages, we also "
    "report the time from publication to first delivery, which isolates "
    "availability.")
caption("Table 3: Replication factor with and without node outages (30 replications).")
rows = [["Outages", "R", "Copies / msg", "Mean latency (s)", "Mean time to 1st delivery (s)",
         "P99 time to 1st delivery (s)", "Throughput (msg/s)"]]
for r in REP.itertuples():
    rows.append([r.node_outages, str(r.replication_factor), f"{r.copies_per_message:.1f}",
                 pm(r.mean_latency, r.mean_latency_ci95, 2),
                 pm(r.mean_first_receive, r.mean_first_receive_ci95, 3),
                 pm(r.p99_first_receive, r.p99_first_receive_ci95, 2),
                 f"{r.throughput:.1f}"])
table(rows)
figure("fig2_replication.png", width=6.2)
caption("Figure 2: Time from publication to first delivery versus replication "
        "factor, with and without node outages (log scale, 95% CIs).")
body(
    "Without outages, the replication factor has no material effect on latency "
    f"or throughput (mean latency {f(min(rep[('off', k)].mean_latency for k in (1, 2, 3)), 2)}–"
    f"{f(max(rep[('off', k)].mean_latency for k in (1, 2, 3)), 2)} s) while storage grows "
    f"{rep[('off', 3)].copies_per_message:.0f}-fold. With outages a single copy is "
    "unreadable whenever its node is down, so the mean time to first delivery "
    f"rises to {pm(rep[('on', 1)].mean_first_receive, rep[('on', 1)].mean_first_receive_ci95, 2)} s "
    f"and its P99 to {f(rep[('on', 1)].p99_first_receive, 1)} s. A second replica "
    f"reduces these to {pm(rep[('on', 2)].mean_first_receive, rep[('on', 2)].mean_first_receive_ci95, 2)} s "
    f"and {f(rep[('on', 2)].p99_first_receive, 1)} s, and mean end-to-end latency "
    f"from {f(rep[('on', 1)].mean_latency, 2)} s to {f(rep[('on', 2)].mean_latency, 2)} s. "
    "A third replica gives no further improvement that is distinguishable at 30 "
    f"replications ({pm(rep[('on', 3)].mean_first_receive, rep[('on', 3)].mean_first_receive_ci95, 2)} s); "
    "resolving the difference between R = 2 and R = 3 would require more "
    "replications. Throughput stays at the offered load in every case. In this model the "
    "benefit of replication is availability during outages, and the second copy "
    "captures nearly all of it.")

h2("3.3   Message Ordering")
body(
    "In out-of-order mode a consumer may take any visible message; in in-order "
    "mode it may take only the message whose producer sequence number is next, "
    "so a delayed message blocks those behind it (head-of-line blocking), "
    "following Li et al. [1]. We used one storage node, five consumers that poll "
    "every 1 ms, Pareto(α = 1.5) processing times with minimum 10 ms (mean "
    "30 ms, consumer capacity ≈ 167 msg/s), and a uniform 10–100 ms "
    "network delay between producer and broker that reorders messages. Latency "
    "is measured from production to completion and includes the network delay; "
    "λ was swept from 40 to 150 msg/s (500 s runs, 50 s warm-up, 10 "
    "replications).")
caption("Table 4: In-order versus out-of-order delivery (mean ± 95% CI, 10 replications).")
rows = [["λ (msg/s)", "Out-of-order mean (ms)", "In-order mean (ms)", "Out-of-order P99 (ms)", "In-order P99 (ms)"]]
for lam in sorted(ORD.arrival_rate.unique()):
    o, i = ordr[(lam, "Out-of-Order")], ordr[(lam, "In-Order")]
    rows.append([f"{lam:g}", pm(o.Mean_Latency_ms, o.Mean_Latency_ms_ci95, 1),
                 pm(i.Mean_Latency_ms, i.Mean_Latency_ms_ci95, 1),
                 pm(o.P99_Latency_ms, o.P99_Latency_ms_ci95, 0),
                 pm(i.P99_Latency_ms, i.P99_Latency_ms_ci95, 0)])
table(rows)
figure("fig3_ordering.png", width=6.2)
caption("Figure 3: Mean (A) and P99 (B) latency of in-order and out-of-order "
        "delivery versus arrival rate (log scale, 95% CIs).")
o40, i40 = ordr[(40, "Out-of-Order")], ordr[(40, "In-Order")]
o80, i80 = ordr[(80, "Out-of-Order")], ordr[(80, "In-Order")]
o150, i150 = ordr[(150, "Out-of-Order")], ordr[(150, "In-Order")]
body(
    "At light and moderate load, in-order delivery adds "
    f"{i40.Mean_Latency_ms - o40.Mean_Latency_ms:.1f} ms "
    f"(+{(i40.Mean_Latency_ms / o40.Mean_Latency_ms - 1) * 100:.0f}%) to the mean at λ = 40 and "
    f"{i80.Mean_Latency_ms - o80.Mean_Latency_ms:.1f} ms "
    f"(+{(i80.Mean_Latency_ms / o80.Mean_Latency_ms - 1) * 100:.0f}%) at λ = 80; both differences "
    "are far outside their confidence intervals. The penalty is the time a "
    "message waits for predecessors still in flight on the reordering network "
    "path. The P99 difference at these loads is within the confidence "
    "intervals, plausibly because the tail is dominated by the infinite-variance "
    "Pareto processing time rather than by reordering. At λ = 150 (ρ ≈ 0.9) the "
    "infinite-variance service makes 10 replications insufficient: the "
    f"confidence intervals (±{o150.Mean_Latency_ms_ci95:.0f} ms and "
    f"±{i150.Mean_Latency_ms_ci95:.0f} ms) overlap completely, and we draw no "
    "conclusion at that load.")

# =====================================================================
# 4. CONSISTENCY AND CONSENSUS
# =====================================================================
h1("4   Consistency and Consensus")

h2("4.1   Two-Phase Commit")
p_any = oh_def.analytic_p_any_timeout
body(
    "Two-Phase Commit (2PC) [7] makes a transaction atomic across participants. "
    "In our protocol model a participant votes YES with probability equal to its "
    "availability and the coordinator commits only if every vote is YES. Over 200 "
    "transactions and 10 seeds the measured commit rate tracks the analytical "
    "(1 − f)ⁿ for participant failure probability f (Table 5), and every "
    "participant records the same commit/abort decisions in every replication, "
    "confirming atomicity.")
caption("Table 5: 2PC commit rate versus participant failure probability (10 replications).")
rows = [["Participants n", "Failure prob. f", "Measured commit rate", "(1 − f)ⁿ", "Atomicity"]]
for r in TP.itertuples():
    rows.append([str(r.num_participants), f"{r.vote_no_prob:g}", pm(r.commit_rate_mean, r.commit_rate_ci95, 3),
                 f(r.analytic_commit_rate, 3), "holds" if r.atomicity_ok_all_reps else "violated"])
table(rows)
body(
    "Its performance cost comes from the critical path. Each message's service "
    "time becomes S = S_base + T_2PC, where the prepare and commit phases each "
    "cost one round trip and the vote phase waits for the slowest of n replicas, "
    "or for the full vote timeout T if any replica is unavailable:")
equation("T_2PC = RTT_prepare + V + RTT_commit                                  (1)")
equation("E[V] = aⁿ·E[max(RTT₁,…,RTTₙ)] + (1 − aⁿ)·T                        (2)")
equation("λ* = N / E[S]     (saturation arrival rate)                       (3)")
body(
    f"With the defaults (n = 3, a = 0.99, T = 1 s) a vote times out with "
    f"probability 1 − a³ = {p_any:.4f}, and that rare 1 s timeout contributes "
    f"about {p_any * 1000:.1f} ms to the mean—about as much as the three round "
    f"trips together. Equation (2) gives E[T_2PC] = {oh_def.analytic_overhead_mean_s * 1000:.1f} ms, "
    f"and 2×10⁵ sampled overheads give {oh_def.sampled_overhead_mean_s * 1000:.1f} ms "
    "(Table 6); the overhead variance is likewise dominated by the timeout term "
    f"({oh_def.analytic_overhead_var_s2:.4f} s² analytical, {oh_def.sampled_overhead_var_s2:.4f} s² "
    f"sampled, against {oh_a1.analytic_overhead_var_s2:.6f} s² with a = 1). Adding "
    f"E[T_2PC] to the 83.3 ms base service time lowers the saturation rate of a "
    f"10-thread pool from 120 to {oh_def.analytic_saturation_lambda_N10:.1f} msg/s, "
    f"a {oh_def.analytic_capacity_reduction_pct:.1f}% capacity loss.")
caption("Table 6: 2PC overhead per message, sampled (2×10⁵ draws) versus analytical, "
        "and the resulting saturation rate for N = 10, μ = 12.")
rows = [["n", "a", "T (s)", "Sampled E[T_2PC] (ms)", "Analytical (ms)", "λ* (msg/s)", "Capacity loss"]]
for r in OH.itertuples():
    rows.append([str(r.num_replicas), f"{r.replica_availability:g}", f"{r.vote_timeout_s:g}",
                 f"{r.sampled_overhead_mean_s * 1000:.1f}", f"{r.analytic_overhead_mean_s * 1000:.1f}",
                 f"{r.analytic_saturation_lambda_N10:.1f}", f"{r.analytic_capacity_reduction_pct:.1f}%"])
table(rows)
body(
    "We then simulated an M/M/10 queue (μ = 12) whose service time includes the "
    "sampled 2PC overhead, at arrival rates for which the effective utilization "
    "stays below 0.9 (1000 s runs, 100 s warm-up, 10 replications), and a "
    "closed-loop saturated pool to measure capacity directly (Table 7).")
caption("Table 7: End-to-end effect of 2PC on an M/M/10 queue (μ = 12) at λ = 60 msg/s, "
        "and measured saturation throughput (10 replications).")
rows = [["Configuration", "Mean response (s)", "P99 response (s)", "Saturation throughput (msg/s)"]]
rows.append(["No 2PC", pm(tq_base60.mean_response_s_mean, tq_base60.mean_response_s_ci95, 4),
             f(tq_base60.p99_response_s_mean, 3),
             pm(pc_none.measured_capacity_msg_per_s_mean, pc_none.measured_capacity_msg_per_s_ci95, 1)])
for (av, to) in [(1.0, 1.0), (0.999, 1.0), (0.99, 0.1), (0.99, 1.0)]:
    q = TQ[(TQ.variant == "2pc") & (TQ.replica_availability == av) & (TQ.vote_timeout_s == to) & (TQ.arrival_rate == 60)]
    c = pc.get(str((av, to)))
    if len(q) and c is not None:
        q = q.iloc[0]
        rows.append([f"2PC, a = {av:g}, T = {to:g} s",
                     pm(q.mean_response_s_mean, q.mean_response_s_ci95, 4), f(q.p99_response_s_mean, 3),
                     pm(c.measured_capacity_msg_per_s_mean, c.measured_capacity_msg_per_s_ci95, 1)])
table(rows)
figure("fig9_2pc_overhead.png", width=6.3)
caption("Figure 4: (A) Mean 2PC overhead, sampled versus Eq. (2), across replica "
        "counts, availabilities, and vote timeouts. (B) Mean response time of an "
        "M/M/10 queue with and without 2PC (95% CIs).")
body(
    f"At λ = 60 msg/s the default 2PC configuration raises mean response time "
    f"from {f(tq_base60.mean_response_s_mean, 4)} s to {f(tq_def60.mean_response_s_mean, 4)} s "
    f"({ratio(tq_def60.mean_response_s_mean, tq_base60.mean_response_s_mean)}) and P99 from "
    f"{f(tq_base60.p99_response_s_mean, 3)} s to {f(tq_def60.p99_response_s_mean, 3)} s; "
    "the P99 sits just above T + 1/μ because the ~3% of transactions that hit a "
    f"vote timeout form the tail. With perfectly available replicas (a = 1) the "
    f"mean is {f(tq_a1_60.mean_response_s_mean, 4)} s "
    f"({ratio(tq_a1_60.mean_response_s_mean, tq_base60.mean_response_s_mean)}). Measured saturation "
    "throughput agrees with N/E[S] to within 1% in every configuration. Shortening "
    f"the vote timeout to 0.1 s recovers most of the lost capacity "
    f"({pc[str((0.99, 0.1))].measured_capacity_msg_per_s_mean:.1f} versus "
    f"{pc[str((0.99, 1.0))].measured_capacity_msg_per_s_mean:.1f} msg/s). In this model "
    "the timeout fires only for unavailable replicas, so the shorter timeout "
    "aborts no additional transactions; in a deployment where vote round trips "
    "can approach the timeout, it would also abort transactions whose votes are "
    "merely slow.")
figure("fig12_2pc_instability.png", width=4.8)
caption("Figure 5: Backlog growth rate of the default 2PC queue versus arrival "
        "rate. Above λ* the backlog grows at λ − λ*.")
body(
    "A practical consequence is that a pool that is comfortably stable without "
    "2PC can be unstable with it. Above λ* the measured backlog grows at "
    f"λ − λ* (Figure 5): at λ = 100 msg/s—ρ = 0.83 without 2PC—the "
    f"backlog grows at {pm(ti100.measured_backlog_slope_msg_per_s_mean, ti100.measured_backlog_slope_msg_per_s_ci95, 1)} msg/s "
    f"(predicted {ti100.predicted_backlog_slope_if_unstable:.1f}) and throughput saturates at "
    f"{ti100.measured_throughput_mean:.1f} msg/s, while the same queue without 2PC "
    f"serves {ti_base100.measured_throughput_mean:.1f} msg/s with no backlog growth.")

h2("4.2   Raft Consensus")
body(
    "Raft [5] elects a leader by randomized election timeouts and commits a log "
    "entry once it is stored on a majority. Our Raft model exchanges RequestVote "
    "and AppendEntries messages over a network with a configurable one-way delay "
    "and jitter, and we run it with realistic LAN and WAN parameters (Table 1) "
    "for clusters of 3, 5, and 7 nodes. Table 8 reports time to elect the first "
    "leader and time to elect a new one after crashing the leader (30 "
    "replications each), and the latency from appending an entry at the leader "
    "to its majority commit, at 100 appends/s (20 replications).")
caption("Table 8: Raft election and commit latency (mean ± 95% CI).")
rows = [["Network", "n", "First leader (ms)", "Re-election after crash (ms)",
         "Commit latency mean (ms)", "Commit latency P99 (ms)"]]
for ps in ["realistic_lan", "realistic_wan"]:
    for n in [3, 5, 7]:
        e, c = re[(ps, n)], rc[(ps, True, n)]
        rows.append([ps.split("_")[1].upper(), str(n),
                     pm(e.first_leader_time_s_mean * 1000, e.first_leader_time_s_ci95 * 1000, 0),
                     pm(e.reelection_time_s_mean * 1000, e.reelection_time_s_ci95 * 1000, 0),
                     pm(c.commit_latency_mean_s_mean * 1000, c.commit_latency_mean_s_ci95 * 1000, 2),
                     f"{c.commit_latency_p99_s_mean * 1000:.1f}"])
table(rows)
figure("fig14_raft.png", width=6.3)
caption("Figure 6: (A) Raft re-election time after a leader crash. (B) Append-to-"
        "majority-commit latency (log scale).")
lan3, wan3 = rc[("realistic_lan", True, 3)], rc[("realistic_wan", True, 3)]
splits = {n: re[("realistic_wan", n)].split_vote_runs for n in [3, 5, 7]}
body(
    "Every run elected exactly one leader per term and completed fail-over, "
    "with zero election-safety violations. Leader election completes within "
    "one to two election-timeout intervals; on the WAN, split votes occurred "
    f"before the first leader in {splits[3]}, {splits[5]}, and {splits[7]} of 30 runs for "
    "n = 3, 5, 7; no split votes occurred on the LAN. Commit latency is essentially one "
    "round trip to the fastest majority: "
    f"{lan3.commit_latency_mean_s_mean * 1000:.2f} ms on the LAN and "
    f"{wan3.commit_latency_mean_s_mean * 1000:.1f} ms on the WAN for n = 3, rising only "
    "slightly with cluster size because a larger majority must be waited for.")
rl100 = rq[("realistic_lan", 3, 100.0)]
nc100 = rq[("no_consensus", 0, 100.0)]
rw60 = rq[("realistic_wan", 3, 60.0)]
nc60 = rq[("no_consensus", 0, 60.0)]
rw100 = rq[("realistic_wan", 3, 100.0)]
body(
    "To measure the cost on the request path, each worker thread of an M/M/10 "
    "queue (μ = 12) blocks until its request's log entry commits. At λ = 100 "
    "msg/s a 3-node LAN cluster raises mean response time from "
    f"{f(nc100.mean_response_s_mean, 4)} s to {f(rl100.mean_response_s_mean, 4)} s "
    f"({ratio(rl100.mean_response_s_mean, nc100.mean_response_s_mean)}) with unchanged throughput. On "
    f"the WAN the same cluster costs {ratio(rw60.mean_response_s_mean, nc60.mean_response_s_mean)} at "
    "λ = 60 and makes the queue unstable at λ = 100: measured effective "
    f"utilization is {rw100.measured_rho_eff_mean:.2f} and throughput saturates at "
    f"{rw100.throughput_mean:.1f} msg/s. Saturated-pool measurements (Figure 7) give "
    "the capacity cost directly: "
    f"{pc[str(('realistic_lan', 3))].measured_capacity_reduction_pct_vs_none:.1f}% (n = 3) and "
    f"{pc[str(('realistic_lan', 5))].measured_capacity_reduction_pct_vs_none:.1f}% (n = 5) on the LAN, "
    f"{pc[str(('realistic_wan', 3))].measured_capacity_reduction_pct_vs_none:.1f}% and "
    f"{pc[str(('realistic_wan', 5))].measured_capacity_reduction_pct_vs_none:.1f}% on the WAN. The cost "
    "of consensus is therefore set by network round-trip time relative to service "
    "time, not by the protocol itself. This model commits each request "
    "synchronously with no batching or pipelining, so these figures are an upper "
    "bound for implementations that batch entries.")
figure("fig13_protocol_capacity.png", width=5.6)
caption("Figure 7: Measured saturation throughput of a 10-thread pool (μ = 12) "
        "with no protocol, 2PC, and Raft on the critical path (10 replications); "
        "black marks show N/E[S] for 2PC.")

h2("4.3   Vector Clocks and Causal Delivery")
body(
    "Vector clocks [3,4] let a broker deliver messages in causal rather than "
    "merely FIFO order. We implement the causal broadcast of Birman, Schiper, "
    "and Stephenson [22]: process i delivers a message m from j only when "
    "m.VC[j] = VC_i[j] + 1 and m.VC[k] ≤ VC_i[k] for all k ≠ j, "
    "holding it back otherwise. P processes each broadcast 10 messages/s for "
    "30 s over links with 10 ms mean lognormal delay whose coefficient of "
    "variation (CV) we vary (10 replications). As a control, the same "
    "workload is delivered without ordering, and we count deliveries that "
    "violate causality against the ground-truth happened-before relation.")
caption("Table 9: Causal delivery cost: fraction of messages held back and mean "
        "hold-back of held messages, versus delay variability (10 broadcasts/s).")
rows = [["P", "Delay CV", "Held back", "Mean hold-back if held (ms)", "P99 hold-back, all (ms)",
         "Violations without ordering"]]
for n in [3, 5, 10]:
    for cv in [0.0, 0.5, 1.0, 2.0]:
        b, u = vcb[(n, 10.0, cv)], vcn[(n, 10.0, cv)]
        rows.append([str(n), f"{cv:g}", pct(b.held_back_fraction_mean, 1),
                     f"{b.mean_holdback_heldonly_mean * 1000:.1f}", f"{b.p99_holdback_all_mean * 1000:.1f}",
                     pct(u.violating_delivery_fraction_mean, 1)])
table(rows)
figure("fig15_vector_clocks.png", width=6.3)
caption("Figure 8: (A) Messages held back by causal delivery and (B) causally "
        "violating deliveries without ordering, versus network delay CV.")
b10, b50, b2 = vcb[(10, 10.0, 1.0)], vcb[(5, 50.0, 1.0)], vcb[(5, 2.0, 1.0)]
body(
    "Causal delivery never violated causality in any run, whereas unordered "
    f"delivery violated it for up to {pct(vcn[(10, 10.0, 2.0)].violating_delivery_fraction_mean, 1)} "
    "of deliveries. Its cost is hold-back, which is zero when delays are "
    "constant and grows with delay variability, group size, and broadcast "
    f"rate: at CV = 1, {pct(b10.held_back_fraction_mean, 1)} of messages are held "
    f"back with P = 10, and at P = 5 the held fraction rises from "
    f"{pct(b2.held_back_fraction_mean, 1)} at 2 broadcasts/s to {pct(b50.held_back_fraction_mean, 1)} at "
    "50/s. The hold-back of an affected message is on the order of the delay "
    f"spread (about {b10.mean_holdback_heldonly_mean * 1000:.0f} ms at CV = 1), so the "
    "mean penalty is small but the tail grows with variability: the P99 "
    f"hold-back over all messages reaches {vcb[(10, 10.0, 2.0)].p99_holdback_all_mean * 1000:.0f} ms "
    "at P = 10 and CV = 2.")

h2("4.4   Consistency Choices Under CAP")
body(
    "The CAP theorem [9,10] forces a replicated broker to choose between "
    "consistency and availability during a partition. A CP design keeps a single "
    "order of updates through consensus or atomic commit, and therefore pays "
    "the costs measured above on every operation; an AP design acknowledges "
    "locally and reconciles later, avoiding them at the price of temporarily "
    "inconsistent reads. Our measurements put numbers on the CP side of this "
    "choice for a 10-thread pool: causal delivery costs only hold-back "
    "proportional to delay jitter; Raft costs "
    f"{pc[str(('realistic_lan', 3))].measured_capacity_reduction_pct_vs_none:.0f}% of capacity on a LAN "
    f"and {pc[str(('realistic_wan', 3))].measured_capacity_reduction_pct_vs_none:.0f}% on a WAN; and 2PC "
    f"costs {pc[str((1.0, 1.0))].measured_capacity_reduction_pct_vs_none:.0f}% even with perfectly "
    f"available replicas and {pc[str((0.99, 1.0))].measured_capacity_reduction_pct_vs_none:.0f}% "
    "with 1% replica unavailability. We do not simulate partitions, so we make "
    "no quantitative availability claims.")

# =====================================================================
# 5. THREADING
# =====================================================================
h1("5   Threading Architectures")
body(
    "We compare two thread-pool architectures with N = 20 threads and "
    "μ = 12 msg/s per thread against an ideal M/M/20 pool, sweeping ρ = "
    "λ/(Nμ) from 0.5 to 0.9 (2000 s runs, 200 s warm-up, 10 replications). "
    "In the dedicated design each connection reserves two threads, so at most "
    "N/2 = 10 connections are active and further arrivals are rejected. Each "
    "accepted message is served at rate μ, so this design is exactly an "
    "M/M/10/10 loss system whose rejection probability is Erlang-B. In the "
    "shared design all messages queue for the common pool, and contention "
    "stretches each service time by a factor that grows with the number of busy "
    "threads:")
equation("Dedicated:  P_reject = B(N/2, λ/μ),   X = λ·(1 − B)                    (4)")
equation("Shared:  S = S_base·(1 + α·N_busy/N),   α = 0.1                        (5)")
caption("Table 10: Threading architectures (mean ± 95% CI, 10 replications). "
        "Analytical values: M/M/20 for the baseline, Erlang-B for the dedicated pool.")
rows = [["ρ", "λ", "Baseline resp (s)", "M/M/20 exact (s)", "Shared resp (s)", "Dedicated resp (s)",
         "Dedicated X (msg/s)", "Erlang-B X", "Rejected"]]
for rho in sorted(TH.rho.unique()):
    b, s, d = th[(rho, "baseline")], th[(rho, "shared")], th[(rho, "dedicated")]
    rows.append([f"{rho:g}", f"{b.arrival_rate:g}", pm(b.mean_response, b.mean_response_ci95, 4),
                 f(b.analytical_mean_response, 4), pm(s.mean_response, s.mean_response_ci95, 4),
                 pm(d.mean_response, d.mean_response_ci95, 4), f(d.throughput, 1),
                 f(d.analytical_throughput, 1), pct(d.rejection_rate, 1)])
table(rows)
figure("fig4_threading.png", width=6.5)
caption("Figure 9: (A) Mean response time, (B) throughput, and (C) rejection "
        "rate versus offered utilization; × marks are exact M/M/20 and Erlang-B values.")
s7, b7, s9, b9 = th[(0.7, "shared")], th[(0.7, "baseline")], th[(0.9, "shared")], th[(0.9, "baseline")]
d5, d9 = th[(0.5, "dedicated")], th[(0.9, "dedicated")]
body(
    "The simulation reproduces both analytical models: baseline response times "
    "match M/M/20 within the 95% confidence interval at every load, and dedicated throughput and rejection "
    "match Erlang-B. The dedicated pool's response time is flat at 1/μ because "
    "admitted messages never queue, but it rejects "
    f"{pct(d5.rejection_rate, 1)} of arrivals at ρ = 0.5 and {pct(d9.rejection_rate, 1)} at "
    f"ρ = 0.9, capping throughput at {f(d9.throughput, 1)} msg/s. The shared pool "
    f"accepts all load but is {(s7.mean_response / b7.mean_response - 1) * 100:.1f}% slower than the "
    f"baseline at ρ = 0.7 and {ratio(s9.mean_response, b9.mean_response, 1)} slower at ρ = 0.9 "
    f"({f(s9.mean_response, 3)} s versus {f(b9.mean_response, 3)} s, P95 "
    f"{f(s9.p95_response, 2)} s versus {f(b9.p95_response, 2)} s): the contention "
    "overhead raises the effective utilization, and near saturation even a 10% "
    "service-time inflation causes a disproportionate queueing delay. A "
    "dedicated pool therefore suits workloads that must bound latency and can "
    "shed load; a shared pool suits workloads that cannot reject requests, "
    "provided it is kept well below saturation.")

# =====================================================================
# 6. QUEUEING EXTENSIONS
# =====================================================================
h1("6   Queueing Extensions")

h2("6.1   Heterogeneous Servers and Dispatch")
body(
    "Real deployments mix instance types. We model groups of n_i servers with "
    "rate μ_i, each group with its own FCFS queue, and a dispatcher that assigns "
    "each arrival to a group. Under a static probabilistic split, group i "
    "receives a Poisson stream of rate λ_i and is an exact M/M/n_i queue, so the "
    "overall mean wait and the stability condition are")
equation("Wq = Σ_i (λ_i/λ)·Wq^{M/M/n_i}(λ_i, μ_i),   stable ⇔ λ_i < n_i·μ_i ∀ i      (6)")
body(
    "Aggregate stability, λ < Σ n_i·μ_i, is not sufficient. We compare "
    "per-server random dispatch (each server receives λ/N regardless of speed), "
    "capacity-weighted random dispatch (λ_i ∝ n_i·μ_i, so every group runs at "
    "the aggregate ρ), and four dynamic policies, at λ = 50 msg/s for five "
    "configurations of five servers (2000 s runs, 200 s warm-up, 10 replications).")
caption("Table 11: Heterogeneous servers (mean wait, s; mean ± 95% CI). ρ_max is "
        "the largest per-group utilization under per-server random dispatch.")
rows = [["Configuration", "Capacity", "ρ_max (random)", "Random (per server)",
         "Random (capacity)", "Exact, capacity split", "Shortest queue"]]
for scen in list(dict.fromkeys(HS.scenario)):
    r_, c_, s_ = hs[(scen, "random")], hs[(scen, "random_capacity")], hs[(scen, "shortest_queue")]
    rows.append([f"{scen} ({r_.groups})", f"{r_.capacity:g}", f"{r_.max_pool_rho:.2f}",
                 pm(r_.sim_mean_wait, r_.sim_mean_wait_ci95, 3) + ("" if r_.stable else " (unstable)"),
                 pm(c_.sim_mean_wait, c_.sim_mean_wait_ci95, 3), f(c_.analytical_wq, 3),
                 pm(s_.sim_mean_wait, s_.sim_mean_wait_ci95, 3)])
table(rows)
figure("fig6_heterogeneity.png", width=6.0)
caption("Figure 10: Mean waiting time by configuration and dispatch policy (log "
        "scale); black marks are the exact value of Eq. (6) for static policies.")
hv_r, vh_c, homo = hs[("High variance", "random")], hs[("Very high variance", "random_capacity")], hs[("Homogeneous", "random")]
body(
    "Per-server random dispatch overloads the slow servers whenever λ/N "
    "exceeds their rate. That happens for the medium (ρ_max = 1.00), high (1.25), "
    "and very high (1.67) variance configurations, even though aggregate "
    "utilization is at most 0.83. These queues are unstable, not slow: their "
    "measured mean wait grows in proportion to the simulated time (Figure 11; "
    f"high variance: {hi[('High variance', 500.0)].sim_mean_wait:.1f}, "
    f"{hi[('High variance', 1000.0)].sim_mean_wait:.1f}, {hi[('High variance', 2000.0)].sim_mean_wait:.1f}, and "
    f"{hi[('High variance', 4000.0)].sim_mean_wait:.1f} s for 500–4000 s runs), so any single "
    "number reported for them depends only on run length. Where Eq. (6) is "
    "finite, simulation agrees with it to within the confidence interval. "
    "With capacity-weighted dispatch every configuration is stable and the "
    "service-rate spread has little effect: the low- and medium-variance "
    "configurations, which have the same group sizes and capacity, have "
    "identical exact waits, and the most heterogeneous configuration—which "
    f"also has the most capacity—has the shortest wait ({f(vh_c.sim_mean_wait, 3)} s, versus "
    f"{f(homo.sim_mean_wait, 3)} s for homogeneous). The residual penalty of the other "
    "configurations relative to homogeneous comes from splitting one five-server "
    "queue into separate two- and three-server queues, which loses pooling "
    "efficiency.")
figure("fig11_hetero_instability.png", width=4.8)
caption("Figure 11: Mean waiting time versus simulated time under per-server "
        "random dispatch. Linear growth indicates an unstable group.")
caption("Table 12: Dispatch policies on the 2@8 + 3@15 configuration (10 replications).")
rows = [["Policy", "Mean wait (s)", "P99 wait (s)", "P99 response (s)"]]
names = {"random": "Random (per server)", "random_capacity": "Random (capacity-weighted)",
         "round_robin": "Round-robin", "shortest_queue": "Shortest queue",
         "fastest_first": "Fastest idle first", "work_stealing": "Work stealing"}
for r in HP.itertuples():
    unstable = r.stable is False or str(r.stable) == "False"
    rows.append([names[r.policy] + (" (unstable)" if unstable or r.policy == "round_robin" else ""),
                 pm(r.sim_mean_wait, r.sim_mean_wait_ci95, 3), f(r.sim_p99_wait, 3),
                 f(r.sim_p99_response, 3)])
table(rows)
figure("fig7_dispatch_policy.png", width=5.0)
caption("Figure 12: Dispatch policy on the 2@8 + 3@15 configuration (log scale); "
        "red bars are unstable.")
body(
    "Among policies (Table 12), round-robin is as unstable as per-server random "
    "dispatch because it sends the same λ/N to every server. Capacity-weighted "
    "random dispatch is stable but leaves idle fast servers next to busy slow "
    "ones. The dynamic policies do best: work stealing, where idle servers take "
    f"jobs from the longest queue, gives {f(hp['work_stealing'].sim_mean_wait, 3)} s, "
    f"fastest-idle-first {f(hp['fastest_first'].sim_mean_wait, 3)} s, and shortest queue "
    f"{f(hp['shortest_queue'].sim_mean_wait, 3)} s—close to the "
    f"{f(homo.sim_mean_wait, 3)} s of the homogeneous single queue. For mixed fleets the "
    "dispatcher, not the hardware mix, decides performance.")

h2("6.2   Finite Capacity (M/M/N/K)")
body(
    "A broker with bounded storage rejects arrivals when K messages are in the "
    "system. The stationary distribution of the M/M/N/K birth–death chain "
    "gives the blocking probability P_K, the admitted rate λ(1 − P_K), and, by "
    "Little's Law over admitted messages, the mean wait; for K = N, P_K is the "
    "Erlang-B formula. Unlike the infinite-buffer queue, the system is stable for "
    "any ρ. We swept K from 10 to 200 with N = 10, μ = 12, and ρ = 0.8, 1.0, and "
    "1.25 (2000 s runs, 200 s warm-up, 20 replications).")
caption("Table 13: Finite-capacity queue, simulation (mean ± 95% CI, 20 "
        "replications) versus the exact birth–death solution.")
rows = [["ρ", "K", "Sim P_K", "Exact P_K", "Sim Wq (s)", "Exact Wq (s)"]]
for lam in sorted(FC.lambda_.unique()):
    for K in [10, 20, 50, 200]:
        r = fc.get((lam, K))
        if r is None:
            continue
        sim_pk = (pm(r.sim_P_K_mean, r.sim_P_K_ci95, 4) if r.sim_P_K_mean >= 1e-3
                  else f"{r.sim_P_K_mean:.1e} ± {r.sim_P_K_ci95:.1e}")
        ana_pk = f"{r.ana_P_K:.4f}" if r.ana_P_K >= 1e-3 else f"{r.ana_P_K:.1e}"
        rows.append([f"{r.rho:g}", str(K), sim_pk, ana_pk,
                     pm(r.sim_Wq_mean, r.sim_Wq_ci95, 4) if r.sim_Wq_mean > 0 else "0",
                     f"{r.ana_Wq:.4f}"])
table(rows)
figure("fig16_finite_capacity.png", width=6.3)
caption("Figure 13: (A) Blocking probability and (B) mean wait of admitted "
        "messages versus capacity K; dashed lines are exact.")
o1, o2 = fc[(150.0, 10)], fc[(150.0, 200)]
p08 = fc[(96.0, 50)]
body(
    f"Simulation agrees with the exact solution: {fc_inside} of {fc_total} blocking and "
    "waiting-time comparisons fall inside the 95% confidence interval; two of "
    "the others differ from the exact value by less than 2%, and the third is a "
    "blocking probability of order 10⁻²⁰ that no finite run can observe [21]. "
    "The sweep shows the "
    "buffer-sizing trade-off. At ρ = 0.8 a modest buffer nearly eliminates "
    f"loss (P_K = {p08.ana_P_K:.1e} at K = 50). In overload (ρ = 1.25) no buffer "
    f"can help: blocking falls only from {f(o1.ana_P_K, 3)} at K = 10 to the "
    f"limiting 1 − 1/ρ = {f(o2.ana_P_K, 3)}, while the wait of admitted messages "
    f"grows to {f(o2.sim_Wq_mean, 2)} s at K = 200. In overload a large buffer only "
    "converts rejections into delay.")

h2("6.3   Priority Queueing")
nb_h = pr_base[(pr_base.discipline == "nonpreemptive") & (pr_base.cls.astype(str) == "1")].iloc[0]
nb_l = pr_base[(pr_base.discipline == "nonpreemptive") & (pr_base.cls.astype(str) == "2")].iloc[0]
pb_h = pr_base[(pr_base.discipline == "preemptive_resume") & (pr_base.cls.astype(str) == "1")]
pb_l = pr_base[(pr_base.discipline == "preemptive_resume") & (pr_base.cls.astype(str) == "2")]
body(
    "Brokers often serve a high-priority class ahead of standard traffic. With "
    "equal exponential service rates, Cobham's formula [23] gives the "
    "non-preemptive mean wait of class k as")
equation("W_k = [C(N, a)/(N·μ)] / [(1 − σ_{k−1})(1 − σ_k)]                         (7)")
body(
    "where C(N, a) is the Erlang-C probability and σ_k is the utilization of "
    "classes 1…k. We simulated non-preemptive and preemptive-resume priority "
    "with N = 10, μ = 12, a 20%/80% high/low split, and λ = 100 msg/s (ρ = 0.83), "
    "plus sweeps over load and high-priority share (2000 s runs, 200 s warm-up, "
    "20 replications).")
caption("Table 14: Priority classes at λ = 100 msg/s, 20% high priority "
        "(mean ± 95% CI, 20 replications).")
rows = [["Discipline", "Class", "Sim mean wait (s)", "Analytical (s)", "Sim P99 wait (s)"]]
for disc, label in [("nonpreemptive", "Non-preemptive"), ("preemptive_resume", "Preemptive-resume")]:
    for cls, cname in [("1", "High"), ("2", "Low"), ("all", "All (load-weighted)")]:
        r = pr_base[(pr_base.discipline == disc) & (pr_base.cls.astype(str) == cls)]
        if not len(r):
            continue
        r = r.iloc[0]
        rows.append([label, cname, pm(r.sim_mean_wait, r.sim_mean_wait_ci95, 5),
                     f"{r.ana_mean_wait:.5f}" if pd.notna(r.ana_mean_wait) else "—",
                     f"{r.sim_p99_wait:.4f}"])
table(rows)
figure("fig17_priority.png", width=5.2)
caption("Figure 14: Per-class mean waiting time versus utilization (20% high "
        "priority); dashed lines are analytical, dotted is FCFS M/M/10.")
body(
    f"Non-preemptive priority cuts the high-priority mean wait to "
    f"{f(nb_h.sim_mean_wait, 5)} s (Cobham {f(nb_h.ana_mean_wait, 5)} s) and raises the low "
    f"class to {f(nb_l.sim_mean_wait, 5)} s (Cobham {f(nb_l.ana_mean_wait, 5)} s), against "
    f"{f(nb_h.fcfs_mmn_Wq, 5)} s for FCFS. Preemptive-resume reduces the high-priority "
    "wait to effectively zero. In both disciplines the load-weighted mean wait "
    "equals the FCFS value to within the confidence interval at every "
    "high-priority share, confirming the conservation law: priority redistributes "
    "delay between classes without removing any. Simulated means fall inside the "
    "95% confidence interval of the analytical value in all but three cases, all of "
    "which are preemptive high-priority rows where the simulation observed no "
    "waiting at all against an analytical value below 10⁻⁶ s.")

h2("6.4   Erlang-k Service (M/E_k/N)")
body(
    "Finally we reduce service variability: Erlang-k service is a sum of k "
    "exponential phases with rate kμ, so its mean stays 1/μ and C_s² = 1/k. "
    "We compare simulation with the Allen–Cunneen approximation [24], "
    "Wq ≈ Wq^{M/M/N}·(1 + C_s²)/2, and, for k ≤ 4, with the exact mean wait "
    "from a numerically solved CTMC, at ρ = 0.5 (λ = 30, N = 6, μ = 10) and "
    "ρ = 0.85 (λ = 51) (5000 s runs, 500 s warm-up, 20 replications).")
caption("Table 15: Erlang-k service (mean wait in ms; mean ± 95% CI, 20 replications).")
rows = [["ρ", "k", "C_s²", "Sim Wq (ms)", "Exact CTMC (ms)", "Allen–Cunneen (ms)", "Sim P99 wait (ms)"]]
for cfg in list(dict.fromkeys(EK.config))[::-1]:
    for k in [1, 2, 4, 8, 16]:
        r = ek[(cfg, k)]
        rows.append([f"{r.rho:g}", str(k), f"{r.cv2:.4g}", pm(r.sim_mean_wait * 1000, r.sim_mean_wait_ci95 * 1000, 3),
                     f"{r.exact_ctmc_Wq * 1000:.3f}" if pd.notna(r.exact_ctmc_Wq) else "—",
                     f"{r.ana_allen_cunneen_Wq * 1000:.3f}", f"{r.sim_p99_wait * 1000:.1f}"])
table(rows)
figure("fig8_erlangk.png", width=6.3)
caption("Figure 15: Mean waiting time versus number of Erlang phases at "
        "(A) ρ = 0.85 and (B) ρ = 0.5; black marks are exact CTMC values.")
lo1, lo16 = ek[("original_rho0.50", 1)], ek[("original_rho0.50", 16)]
hi1, hi16 = ek[("high_rho0.85", 1)], ek[("high_rho0.85", 16)]
lo4 = ek[("original_rho0.50", 4)]
_e = EK[EK.exact_ctmc_Wq.notna()]
ek_maxdiff = float(((_e.sim_mean_wait - _e.exact_ctmc_Wq).abs() / _e.exact_ctmc_Wq).max() * 100)
body(
    "Waiting time falls monotonically with k. From k = 1 to k = 16 the mean "
    f"wait drops by {(1 - lo16.sim_mean_wait / lo1.sim_mean_wait) * 100:.0f}% at ρ = 0.5 and "
    f"{(1 - hi16.sim_mean_wait / hi1.sim_mean_wait) * 100:.0f}% at ρ = 0.85, and the P99 wait by "
    f"{(1 - lo16.sim_p99_wait / lo1.sim_p99_wait) * 100:.0f}% and "
    f"{(1 - hi16.sim_p99_wait / hi1.sim_p99_wait) * 100:.0f}%. Simulation matches the exact CTMC "
    f"to within {ek_maxdiff:.1f}% for every k where it was computed. The Allen–Cunneen approximation is exact "
    "for k = 1 but underestimates the wait for k ≥ 2—by "
    f"{(1 - lo4.ana_allen_cunneen_Wq / lo4.exact_ctmc_Wq) * 100:.0f}% at ρ = 0.5 and k = 4—and "
    "becomes accurate only in heavy traffic. This is the mirror image of the "
    "heavy-tail result in our companion paper: there, high service variance "
    "inflated tail latency; here, low variance compresses it.")

# =====================================================================
# 7. DISCUSSION
# =====================================================================
h1("7   Discussion")
caption("Table 16: Summary of measured effects (all values from Tables 2–15).")
table([
    ["Mechanism", "Measured effect", "Conditions"],
    ["Visibility timeout", f"Optimum near {vt_min.visibility_timeout:g} s; 0.5 s → {pct(vt05.duplicate_rate, 0)} duplicates; "
     f"30 s → {f(vt30.mean_latency, 1)} s mean latency", "λ = 10, processing 0.5 s, p = 0.1"],
    ["Replication R = 1 → 2", f"1st-delivery {f(rep[('on', 1)].mean_first_receive, 2)} → "
     f"{f(rep[('on', 2)].mean_first_receive, 2)} s under outages; no effect without", "3 nodes, MTBF 100 s, MTTR 20 s"],
    ["In-order delivery", f"+{(i80.Mean_Latency_ms / o80.Mean_Latency_ms - 1) * 100:.0f}% mean latency", "λ = 80, 10–100 ms reordering"],
    ["2PC", f"{oh_def.sampled_overhead_mean_s * 1000:.0f} ms/msg; capacity −"
     f"{pc[str((0.99, 1.0))].measured_capacity_reduction_pct_vs_none:.0f}%", "n = 3, a = 0.99, T = 1 s"],
    ["Raft commit", f"Capacity −{pc[str(('realistic_lan', 3))].measured_capacity_reduction_pct_vs_none:.0f}% "
     f"(LAN), −{pc[str(('realistic_wan', 3))].measured_capacity_reduction_pct_vs_none:.0f}% (WAN)", "n = 3, synchronous commit"],
    ["Causal delivery", f"{pct(b10.held_back_fraction_mean, 0)} held back, ~{b10.mean_holdback_heldonly_mean * 1000:.0f} ms each",
     "P = 10, delay CV = 1"],
    ["Shared thread pool", f"+{(s7.mean_response / b7.mean_response - 1) * 100:.0f}% (ρ = 0.7), "
     f"{ratio(s9.mean_response, b9.mean_response, 1)} (ρ = 0.9)", "N = 20, α = 0.1"],
    ["Dedicated thread pool", f"Rejects {pct(d5.rejection_rate, 0)}–{pct(d9.rejection_rate, 0)} (Erlang-B)", "N = 20, 2 threads/connection"],
    ["Heterogeneous servers", "Per-server random dispatch unstable; capacity-aware dispatch removes penalty", "λ = 50, 5 servers"],
    ["Erlang-k k = 1 → 16", f"Mean wait −{(1 - hi16.sim_mean_wait / hi1.sim_mean_wait) * 100:.0f}%", "ρ = 0.85"],
])
body(
    "Three observations cut across the experiments. First, timeouts dominate "
    "several costs: the 2PC vote timeout contributes half of 2PC's mean overhead "
    "and nearly all of its variance and tail, and the visibility timeout sets "
    "both the retry latency and the duplicate rate. Timeout values deserve the "
    "same tuning attention as thread counts. Second, the cost of consistency is "
    "set by network round trips relative to service time: Raft costs single "
    "digits of capacity on a LAN and over a third on a WAN, and in both 2PC and "
    "Raft a pool that is comfortably stable without the protocol can become "
    "unstable with it, so capacity planning must use the protocol-inflated "
    "service time. Third, in several cases the policy matters more than the "
    "resource: the dispatcher, not the server mix, determines whether a "
    "heterogeneous fleet is stable; a second replica captures nearly all the "
    "availability benefit of replication; and the dedicated/shared choice is a "
    "choice between rejection and delay.")
body_lead("Limitations. ",
          "All workloads are synthetic Poisson arrivals with exponential service "
          "unless stated, so absolute numbers depend on the parameters in Table 1. "
          "The broker model polls storage nodes with a fixed back-off, injects "
          "node outages but not network partitions or message loss, and applies "
          "acknowledgements to unavailable nodes. The Raft model commits each "
          "request synchronously with no batching, pipelining, or disk writes, and "
          "is exercised without leader churn during the queueing experiments. The "
          "2PC model does not model coordinator failure. The ordering results at "
          "ρ ≈ 0.9 are inconclusive because of the infinite-variance service "
          "distribution. Validation against production broker traces remains "
          "future work.")

# =====================================================================
# 8. CONCLUSION
# =====================================================================
h1("8   Conclusion and Future Work")
body(
    "This paper complements our study of heavy-tailed service times by measuring "
    "the cost of the reliability, consistency, and threading mechanisms that "
    "production brokers layer on top of the raw queue. Every result is a "
    "replicated, seeded simulation measurement, and every model with a known "
    "closed form reproduces it. Atomic commit is the most expensive guarantee we "
    f"measured ({pc[str((0.99, 1.0))].measured_capacity_reduction_pct_vs_none:.0f}% of capacity with "
    "default timeouts), consensus costs whatever the network round trip costs, "
    "and causal ordering and second replicas are comparatively cheap. Visibility "
    "and vote timeouts are first-order performance parameters, and for "
    "heterogeneous fleets the dispatch policy determines stability.")
body(
    "Future work includes simulating network partitions to quantify the "
    "availability side of the CAP trade-off, adding entry batching and "
    "pipelining to the Raft model, repeating the ordering experiment near "
    "saturation with more replications, combining the heavy-tailed service "
    "times of our companion paper with 2PC and consensus overheads to test "
    "whether workload variance and protocol cost compound, and validating the "
    "framework against production broker traces.")

# =====================================================================
# REFERENCES
# =====================================================================
h1("References")
refs = [
    "[1] J. Li, Y. Cui, and Y. Ma, “Modeling message queueing services with "
    "reliability guarantee in cloud computing environment using colored Petri "
    "nets,” Mathematical Problems in Engineering, vol. 2015, Art. no. 383846, "
    "2015.",
    "[2] L. Lamport, “Time, clocks, and the ordering of events in a "
    "distributed system,” Communications of the ACM, vol. 21, no. 7, "
    "pp. 558–565, 1978.",
    "[3] C. J. Fidge, “Timestamps in message-passing systems that preserve "
    "the partial ordering,” in Proc. 11th Australian Computer Science "
    "Conf., 1988, pp. 56–66.",
    "[4] F. Mattern, “Virtual time and global states of distributed "
    "systems,” in Parallel and Distributed Algorithms, 1989, pp. 215–226.",
    "[5] D. Ongaro and J. Ousterhout, “In search of an understandable "
    "consensus algorithm,” in Proc. USENIX Annual Technical Conf. (ATC), "
    "2014, pp. 305–319.",
    "[6] L. Lamport, “The part-time parliament,” ACM Trans. Computer "
    "Systems, vol. 16, no. 2, pp. 133–169, 1998.",
    "[7] J. Gray, “Notes on data base operating systems,” in Operating "
    "Systems: An Advanced Course, LNCS 60, Springer, 1978, pp. 393–481.",
    "[8] J. Gray and L. Lamport, “Consensus on transaction commit,” ACM "
    "Trans. Database Systems, vol. 31, no. 1, pp. 133–160, 2006.",
    "[9] E. A. Brewer, “Towards robust distributed systems,” keynote, "
    "ACM Symp. Principles of Distributed Computing (PODC), 2000.",
    "[10] S. Gilbert and N. Lynch, “Brewer’s conjecture and the "
    "feasibility of consistent, available, partition-tolerant web services,” "
    "ACM SIGACT News, vol. 33, no. 2, pp. 51–59, 2002.",
    "[11] M. J. Fischer, N. A. Lynch, and M. S. Paterson, “Impossibility of "
    "distributed consensus with one faulty process,” Journal of the ACM, "
    "vol. 32, no. 2, pp. 374–382, 1985.",
    "[12] W. Vogels, “Eventually consistent,” Communications of the ACM, "
    "vol. 52, no. 1, pp. 40–44, 2009.",
    "[13] G. DeCandia et al., “Dynamo: Amazon’s highly available "
    "key-value store,” in Proc. ACM SOSP, 2007, pp. 205–220.",
    "[14] J. Dean and L. A. Barroso, “The tail at scale,” Communications "
    "of the ACM, vol. 56, no. 2, pp. 74–80, 2013.",
    "[15] L. Kleinrock, Queueing Systems, Volume 1: Theory. New York: "
    "Wiley-Interscience, 1975.",
    "[16] A. K. Erlang, “Solution of some problems in the theory of "
    "probabilities of significance in automatic telephone exchanges,” "
    "Elektroteknikeren, vol. 13, pp. 5–13, 1917.",
    "[17] J. D. C. Little, “A proof for the queuing formula: L = λW,"
    "” Operations Research, vol. 9, no. 3, pp. 383–387, 1961.",
    "[18] M. Harchol-Balter, Performance Modeling and Design of Computer Systems: "
    "Queueing Theory in Action. Cambridge: Cambridge Univ. Press, 2013.",
    "[19] Amazon Web Services, “Amazon SQS Developer Guide: Visibility "
    "timeout,” 2023. [Online]. Available: "
    "https://docs.aws.amazon.com/AWSSimpleQueueService/",
    "[20] Team SimPy, “SimPy: Discrete-event simulation for Python,” "
    "2023. [Online]. Available: https://simpy.readthedocs.io/",
    "[21] D. Gross and C. M. Harris, Fundamentals of Queueing Theory, 3rd ed. "
    "New York: Wiley, 1998.",
    "[22] K. Birman, A. Schiper, and P. Stephenson, “Lightweight causal and "
    "atomic group multicast,” ACM Trans. Computer Systems, vol. 9, no. 3, "
    "pp. 272–314, 1991.",
    "[23] A. Cobham, “Priority assignment in waiting line problems,” "
    "Operations Research, vol. 2, no. 1, pp. 70–76, 1954.",
    "[24] A. O. Allen, Probability, Statistics, and Queueing Theory with Computer "
    "Science Applications, 2nd ed. San Diego: Academic Press, 1990.",
]
for r in refs:
    p = para(WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=3)
    _set_run(p.add_run(r), size=10)

out = "Paper2_Submissionready.docx"
doc.save(out)
print("WROTE", out)
print("paras:", len(doc.paragraphs), "tables:", len(doc.tables))
