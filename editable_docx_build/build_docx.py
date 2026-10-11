#!/usr/bin/env python3
"""Build a fully editable (text-based) .docx of paper1 from the PDF text layer
plus figures cropped from the original image-only docx."""
import os
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")

doc = Document()

# ---- base styles ----
normal = doc.styles["Normal"]
normal.font.name = "Times New Roman"
normal.font.size = Pt(11)
normal.paragraph_format.space_after = Pt(6)
normal.paragraph_format.line_spacing = 1.15

for sec in doc.sections:
    sec.page_height = Inches(11.69)   # A4
    sec.page_width = Inches(8.27)
    sec.left_margin = sec.right_margin = Inches(1.0)
    sec.top_margin = sec.bottom_margin = Inches(1.0)

USABLE_W = 6.0  # inches

# Ensure a Hyperlink character style exists (blue + underlined) for citation links.
from docx.enum.style import WD_STYLE_TYPE
try:
    _hl = doc.styles["Hyperlink"]
except KeyError:
    _hl = doc.styles.add_style("Hyperlink", WD_STYLE_TYPE.CHARACTER)
    _hl.font.color.rgb = RGBColor(0x05, 0x63, 0xC1)
    _hl.font.underline = True


import re
CITE_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def _run(p, text, size, bold=False, italic=False):
    r = p.add_run(text)
    r.font.name = "Times New Roman"
    r.font.size = Pt(size)
    r.bold = bold
    r.italic = italic
    return r


def _link(p, anchor, text, size):
    """Append an internal hyperlink (jumps to a bookmark) styled as plain black text."""
    hp = OxmlElement("w:hyperlink")
    hp.set(qn("w:anchor"), anchor)
    r = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    rStyle = OxmlElement("w:rStyle")
    rStyle.set(qn("w:val"), "Hyperlink")
    rPr.append(rStyle)
    rf = OxmlElement("w:rFonts")
    rf.set(qn("w:ascii"), "Times New Roman")
    rf.set(qn("w:hAnsi"), "Times New Roman")
    rPr.append(rf)
    szv = OxmlElement("w:sz")
    szv.set(qn("w:val"), str(int(size * 2)))
    rPr.append(szv)
    col = OxmlElement("w:color")
    col.set(qn("w:val"), "0563C1")
    rPr.append(col)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rPr.append(u)
    r.append(rPr)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    hp.append(r)
    p._p.append(hp)


def add_text(p, text, size=11, bold=False, italic=False):
    """Add text to paragraph p, turning every [n] (or [a, b, c]) into clickable
    internal links to the matching reference bookmark(s)."""
    pos = 0
    for m in CITE_RE.finditer(text):
        if m.start() > pos:
            _run(p, text[pos:m.start()], size, bold, italic)
        nums = [x.strip() for x in m.group(1).split(",")]
        _run(p, "[", size, bold, italic)
        for i, n in enumerate(nums):
            if i > 0:
                _run(p, ", ", size, bold, italic)
            _link(p, f"ref{n}", n, size)
        _run(p, "]", size, bold, italic)
        pos = m.end()
    if pos < len(text):
        _run(p, text[pos:], size, bold, italic)


def add_bookmark(p, name, bmid):
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(bmid))
    start.set(qn("w:name"), name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(bmid))
    pPr = p._p.find(qn("w:pPr"))
    if pPr is not None:
        pPr.addnext(start)
    else:
        p._p.insert(0, start)
    p._p.append(end)


def para(text, align=None, size=None, bold=False, italic=False, space_after=None):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    add_text(p, text, size or 11, bold, italic)
    if space_after is not None:
        p.paragraph_format.space_after = Pt(space_after)
    return p


def heading(num, text, size=14):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(f"{num}   {text}" if num else text)
    r.bold = True
    r.font.size = Pt(size)
    r.font.name = "Times New Roman"
    return p


def subheading(num, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(f"{num}   {text}")
    r.bold = True
    r.font.size = Pt(12)
    return p


def equation(expr, number):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(expr)
    r.italic = True
    r.font.size = Pt(11)
    # right-aligned equation number via tab
    r2 = p.add_run("\t\t(" + str(number) + ")")
    return p


def caption(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(10)
    parts = text.split(":", 1)
    _run(p, parts[0] + ":", 9.5, bold=True)
    if len(parts) > 1:
        add_text(p, parts[1], size=9.5)
    return p


def figure(fname, cap):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run()
    run.add_picture(os.path.join(FIG, fname), width=Inches(USABLE_W))
    caption(cap)


def shade_cell(cell, color="D9D9D9"):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), color)
    tcPr.append(shd)


def table(cap, headers, rows, widths=None):
    caption(cap)
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ""
        rp = hdr[i].paragraphs[0].add_run(h)
        rp.bold = True
        rp.font.size = Pt(10)
        hdr[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        shade_cell(hdr[i])
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            add_text(cells[i].paragraphs[0], str(val), size=10)
            if i > 0:
                cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    if widths:
        for r in t.rows:
            for i, w in enumerate(widths):
                r.cells[i].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


J = WD_ALIGN_PARAGRAPH.JUSTIFY
C = WD_ALIGN_PARAGRAPH.CENTER

# ============================ TITLE BLOCK ============================
tp = para("Tandem Queue Performance Modeling with Heavy-Tailed Service Times in Cloud Message Brokers",
          align=C, size=18, bold=True, space_after=12)
# Author line with superscript affiliation markers (IEEE style)
authors = [("Bhuvana Komati", "1", False),
           ("Himanshu Jain", "2", False),
           ("Vidhyacharan Bhaskar", "3*", True)]  # True = prefix with "and"; * = corresponding author
pa = doc.add_paragraph()
pa.alignment = C
pa.paragraph_format.space_after = Pt(4)
for i, (nm, sup, use_and) in enumerate(authors):
    if i > 0:
        _run(pa, ", " + ("and " if use_and else ""), 13)
    _run(pa, nm, 13)
    s = pa.add_run(sup)
    s.font.name = "Times New Roman"
    s.font.size = Pt(13)
    s.font.superscript = True

# Shared affiliation (prefixed with the three superscript markers)
aff = doc.add_paragraph()
aff.alignment = C
aff.paragraph_format.space_after = Pt(0)
sp = aff.add_run("1,2,3")
sp.font.name = "Times New Roman"
sp.font.size = Pt(11)
sp.font.superscript = True
_run(aff, "Department of Computer Engineering", 11)
para("San Jose State University", align=C, size=11, space_after=0)
para("One Washington Square, San Jose, CA 95192, USA", align=C, size=11, space_after=2)
para("Email: bhuvana.komati@sjsu.edu, himanshu.jain@sjsu.edu, charan.bhaskar@sjsu.edu",
     align=C, size=11, space_after=2)
para("*Corresponding author email: charan.bhaskar@sjsu.edu", align=C, size=10, italic=True, space_after=4)
para("March 2026", align=C, size=11, space_after=12)

# ---- Abstract ----
para("Abstract", align=C, size=12, bold=True, space_after=4)
abstract = ("Cloud message brokers such as AWS SQS, RabbitMQ, and Apache Kafka serve as critical "
            "infrastructure components enabling asynchronous communication in modern distributed systems. "
            "Accurate performance modeling of these systems is essential for capacity planning, service "
            "level agreement compliance, and cost optimization. The foundational work of Li et al. [1] "
            "introduced a tandem queue model for cloud message brokers using Colored Petri Nets with M/M/N "
            "queueing assumptions. However, this model relies on exponential service time distributions, "
            "which fail to capture the heavy-tailed behavior observed in real cloud workloads. This paper "
            "extends the Li et al. framework by incorporating Pareto-distributed service times through M/G/N "
            "queueing models. We develop an enhanced analytical and simulation framework using Python and "
            "SimPy that supports heavy-tailed service time distributions, advanced M/G/N approximations "
            "including the Kingman, Whitt, and Allen-Cunneen methods, and tandem queue configurations with "
            "traffic amplification from message retransmissions. Our simulation validates the base paper’s "
            "traffic inflation formula Λ₂ = λ/(1 − p) to within 0.2% error while revealing that standard "
            "M/M/N models underestimate P99 latency by approximately 45% when workloads exhibit "
            "Pareto-distributed service times. We further demonstrate that Gaussian-based tail approximations "
            "are inadequate for heavy-tailed scenarios and propose Extreme Value Theory as a more accurate "
            "alternative for tail risk estimation. The framework provides interactive engineering tools "
            "through a React frontend and FastAPI backend for real-time capacity planning and performance analysis.")
para(abstract, align=J, size=10.5)
kw = doc.add_paragraph()
kw.alignment = J
_run(kw, "Keywords: ", 10.5, bold=True)
_run(kw, "Heavy-Tailed Distribution, Pareto Distribution, P99 Latency, Message Brokers, "
         "Tandem Queue, M/G/N Approximation", 10.5)

# ============================ 1 INTRODUCTION ============================
heading("1", "Introduction")
para("Cloud message brokers serve as the backbone of modern distributed systems, enabling reliable "
     "asynchronous communication between services. Systems such as AWS SQS, RabbitMQ, Apache Kafka, and "
     "Azure Queue Storage collectively handle billions of messages daily across global infrastructure "
     "deployments. The performance characteristics of these systems directly impact application "
     "responsiveness, user experience, and operational costs. Accurate performance modeling is therefore "
     "critical for determining server capacity requirements, ensuring compliance with service level "
     "agreements such as P99 latency guarantees below 100 milliseconds, optimizing infrastructure costs by "
     "avoiding over-provisioning, and understanding how failure-induced retransmissions affect system "
     "behavior under load.", align=J)
para("Traditional queueing models based on the M/M/N framework assume exponential service times, which "
     "possess convenient mathematical properties including memorylessness and finite variance. However, "
     "extensive empirical evidence from major cloud providers demonstrates that real-world service times "
     "exhibit heavy-tailed behavior that deviates significantly from exponential assumptions. As shown in "
     "Table 1, the discrepancy between M/M/N predictions and observed Pareto-distributed behavior is "
     "substantial across multiple performance metrics.", align=J)

table("Table 1: Comparison of M/M/N Predictions versus Observed Pareto Behavior",
      ["Metric", "M/M/N Prediction", "Reality (Pareto)"],
      [["P99/Mean Ratio", "4.6x", "36x"],
       ["Tail Behavior", "Exponential decay", "Power-law (slow)"],
       ["Variance", "Finite, bounded", "Can be infinite"]],
      widths=[2.0, 2.0, 2.0])

para("The objectives of this paper are fivefold. First, we reproduce and validate the base paper’s "
     "M/M/N analytical results through discrete-event simulation. Second, we extend the model to support "
     "heavy-tailed Pareto service time distributions using M/G/N approximations. Third, we quantify the "
     "“reality gap” between classical exponential assumptions and heavy-tailed behavior in terms of mean "
     "latency, P50, and P99 metrics. Fourth, we evaluate the accuracy of three established M/G/N "
     "approximation methods against simulation. Fifth, we demonstrate the inadequacy of Gaussian-based P99 "
     "estimation and propose Extreme Value Theory as an alternative.", align=J)

subheading("1.1", "Background and Literature Survey")
para("The study of queueing systems has a rich history dating back to Erlang’s pioneering work on "
     "telephone exchange modeling [2]. Kleinrock [3] established the theoretical foundations for analyzing "
     "computer communication networks using queueing theory, while Gross and Harris [4] provided "
     "comprehensive treatments of queueing system fundamentals that remain standard references. Little’s "
     "Law, which relates the average number of customers in a system to the arrival rate and average time "
     "spent, was formally proven by Little [5] and serves as a cornerstone of queueing analysis.", align=J)
para("The recognition that real-world network traffic exhibits self-similar and heavy-tailed "
     "characteristics was a watershed moment in performance modeling. Crovella and Bestavros [6] "
     "demonstrated that World Wide Web traffic displays self-similarity caused by heavy-tailed file size "
     "distributions, fundamentally challenging the Poisson arrival assumptions prevalent in earlier models. "
     "Leland et al. [7] provided early statistical evidence of self-similar traffic patterns in Ethernet "
     "networks, while Paxson and Floyd [8] extended these findings to wide-area network traffic.", align=J)
para("In the context of cloud computing, Dean and Barroso [9] published their influential “Tail at "
     "Scale” paper demonstrating that P99 latencies dominate user experience in large-scale distributed "
     "systems. They showed that even rare slow responses become common when aggregated across thousands of "
     "servers. DeCandia et al. [10] documented heavy-tailed response time distributions in Amazon’s Dynamo "
     "key-value store, while the Netflix technology team [11] reported Pareto-distributed latencies in their "
     "microservice architecture.", align=J)
para("For M/G/N queue approximations, Kingman [12] developed the heavy-traffic approximation that adjusts "
     "M/M/N wait times using the coefficient of variation of service times. Whitt [13] proposed refined "
     "approximations for GI/G/m queues that account for both inter-arrival and service time variability. "
     "Allen [14] presented the Allen-Cunneen approximation, which provides an alternative correction factor "
     "for general service time distributions. Marchal [15] contributed bounds and approximations for "
     "multi-server queues that complement these methods.", align=J)
para("Extreme Value Theory has emerged as a powerful tool for tail risk estimation in computing systems. "
     "Coles [16] provided the statistical foundations for modeling extreme values, while Beirlant et al. "
     "[17] extended these methods to heavy-tailed distributions commonly encountered in network traffic "
     "analysis. Resnick [18] developed the theoretical framework connecting heavy-tailed phenomena to "
     "extreme value distributions.", align=J)
para("The base paper by Li et al. [1] introduced a tandem queue model for cloud message brokers using "
     "Colored Petri Nets. Their model captures the two-stage pipeline architecture of message broker "
     "systems and derives a traffic inflation formula that accounts for message retransmissions due to "
     "delivery failures. While their work validated the model against M/M/N analytical solutions, it "
     "assumed exponential service times throughout, leaving the impact of heavy-tailed distributions "
     "unexplored. Harchol-Balter [19] provided extensive analysis of how heavy-tailed job sizes affect "
     "queueing system performance, demonstrating that standard models can severely underestimate tail "
     "latencies. Nair et al. [20] studied the impact of heavy tails on cloud service performance, confirming "
     "that Pareto-distributed service times are common in production environments.", align=J)
para("Our work builds directly on Li et al.’s tandem queue framework while addressing its key limitation "
     "by incorporating heavy-tailed service time distributions and evaluating the resulting impact on tail "
     "latency estimation.", align=J)

# ============================ 2 TANDEM QUEUE MODEL ============================
heading("2", "The Tandem Queue Model")
para("The tandem queue model captures the two-stage architecture of cloud message broker systems where "
     "messages flow sequentially from a sender stage to a receiver stage. In this architecture, producers "
     "submit messages to Stage 1, which handles initial processing including validation, serialization, and "
     "routing. Messages that complete Stage 1 processing proceed to Stage 2, which manages delivery to "
     "consumers including deserialization, acknowledgment handling, and persistence. When a message delivery "
     "fails at Stage 2 with probability p, the message is retransmitted, creating a feedback loop that "
     "amplifies the effective traffic arriving at Stage 2.", align=J)
para("Figure 1 illustrates the complete tandem queue architecture. The diagram shows the two processing "
     "stages connected in series, with the feedback path for failed messages clearly indicated. Stage 1 "
     "operates with N₁ = 10 servers each processing at rate μ₁ = 10 messages per second, while Stage 2 "
     "operates with N₂ = 8 servers at rate μ₂ = 12 messages per second. The external arrival rate is "
     "λ = 80 messages per second, and the failure probability is p = 0.1. The asymmetry between stages "
     "reflects real-world broker deployments where the receiver stage typically has fewer but faster servers "
     "due to the simpler nature of delivery operations compared to ingestion.", align=J)

figure("fig1_tandem_arch.png",
       "Figure 1: Tandem queue architecture showing the two-stage message broker pipeline. Stage 1 "
       "(sender) receives external arrivals at rate λ and processes them through N₁ servers. Stage 2 "
       "(receiver) handles delivery through N₂ servers. Failed deliveries with probability p are "
       "retransmitted, creating traffic amplification at Stage 2. System parameters: λ = 80 msg/s, "
       "μ₁ = 10 msg/s, μ₂ = 12 msg/s, N₁ = 10, N₂ = 8, p = 0.1.")

para("The system parameters used throughout our experiments are summarized in Table 2.", align=J)
table("Table 2: Tandem Queue System Parameters",
      ["Parameter", "Symbol", "Value"],
      [["Arrival rate", "λ", "80 msg/s"],
       ["Service rate (Stage 1)", "μ₁", "10 msg/s"],
       ["Service rate (Stage 2)", "μ₂", "12 msg/s"],
       ["Servers (Stage 1)", "N₁", "10"],
       ["Servers (Stage 2)", "N₂", "8"],
       ["Failure probability", "p", "0.1"]],
      widths=[2.6, 1.4, 2.0])

subheading("2.1", "Traffic Inflation")
para("The most significant insight from the tandem queue model is the traffic amplification effect caused "
     "by message retransmissions. When messages fail with probability p and are retransmitted, the effective "
     "arrival rate at Stage 2 exceeds the external arrival rate. Li et al. [1] derived the effective arrival "
     "rate at Stage 2 as:", align=J)
equation("Λ₂ = λ / (1 − p)", 1)
para("where λ is the external arrival rate and p is the failure probability. For our parameters with "
     "λ = 80 messages per second and p = 0.1, this yields Λ₂ = 80/0.9 = 88.89 messages per second, "
     "representing an 11% traffic increase. This amplification can push a system operating near capacity "
     "into an unstable regime where queues grow without bound.", align=J)
para("Our simulation validates this formula with high precision. Figure 2 presents the M/M/N validation "
     "results comparing analytical predictions against simulation measurements across multiple utilization "
     "levels. The simulation confirms the traffic inflation formula to within 0.2% error, demonstrating that "
     "the retransmission feedback mechanism is accurately captured by the geometric series model underlying "
     "Equation 1.", align=J)

figure("fig2_mmn_line.png",
       "Figure 2: M/M/N validation comparing analytical solutions against SimPy simulation results. The "
       "close agreement across all utilization levels confirms the accuracy of our simulation framework and "
       "validates the traffic inflation formula from Li et al. [1].")

para("Figure 3 shows the relationship between mean delivery time and the number of processing threads, "
     "reproducing Figure 11 from the base paper. The figure compares our simulation results against the "
     "analytical predictions from Li et al. [1] for two reliability configurations: q=99% (failure "
     "probability p=0.01) and q=88% (failure probability p=0.12). In both configurations, mean delivery time "
     "decreases consistently as the thread count increases from 4 to 10, with no crossovers between the "
     "analytical and simulation curves. The close agreement between our simulation (solid lines) and the "
     "base paper values (dashed lines) validates the accuracy of our SimPy implementation. The diminishing "
     "returns at higher thread counts reflect the transition from a queueing-dominated regime to a "
     "service-time-dominated regime, where adding more threads yields progressively smaller latency "
     "reductions. Error bars represent 95% confidence intervals computed from 10 independent replications. "
     "The system parameters used are λ = 30.3 msg/s, μ₁ = μ₂ = 10.0 msg/s/thread, and D_link = 10 ms.",
     align=J)

figure("fig3_delivery_thr.png",
       "Figure 3: Mean delivery time versus number of threads, reproducing Figure 11 from Li et al. [1]. "
       "Results are shown for two reliability levels: q=99% (p=0.01) and q=88% (p=0.12). Simulation results "
       "(solid lines with circles) closely match the base paper values (dashed lines with squares), "
       "validating the M/M/N model. System parameters: λ = 30.3 msg/s, μ₁ = μ₂ = 10.0 msg/s/thread, "
       "D_link = 10 ms, 10 replications.")

# ============================ 3 MATHEMATICAL FOUNDATION ============================
heading("3", "Mathematical Foundation")
para("This section presents the queueing-theoretic equations underlying our framework. Well-known results "
     "from classical queueing theory are presented with citations to their original sources, while our "
     "extensions for heavy-tailed distributions are presented as numbered equations representing "
     "contributions of this work.", align=J)

subheading("3.1", "M/M/N Baseline")
para("The M/M/N queueing model assumes Poisson arrivals and exponential service times with N identical "
     "servers. The server utilization is defined as ρ = λ/(N·μ), where λ is the arrival rate and μ is the "
     "per-server service rate [3]. The system is stable when ρ < 1, meaning the aggregate service capacity "
     "exceeds the arrival rate. The traffic intensity, defined as a = λ/μ, represents the offered load "
     "measured in Erlangs [2].", align=J)
para("Table 3 summarizes the core M/M/N equations used in our baseline model. The Erlang-C formula gives "
     "the probability that an arriving customer must wait because all servers are busy. The mean queue wait "
     "time follows directly from the Erlang-C probability, and Little’s Law [5] relates the average number "
     "of customers in the system to the arrival rate and mean sojourn time.", align=J)
table("Table 3: M/M/N Baseline Equations [3, 2, 5]",
      ["Quantity", "Formula"],
      [["Utilization", "ρ = λ / (N·μ)"],
       ["Traffic intensity", "a = λ / μ"],
       ["Erlang-C probability",
        "C(N, a) = [(aᴺ/N!)·(N/(N−a))] / [Σ(k=0..N−1) aᵏ/k! + (aᴺ/N!)·(N/(N−a))]"],
       ["Mean queue wait", "Wq = C(N, a) / [μ·N·(1−ρ)]"],
       ["Little’s Law", "L = λ·W"]],
      widths=[2.0, 4.0])

subheading("3.2", "Heavy-Tailed Extensions")
para("The Pareto distribution captures the power-law tail behavior observed in real cloud workloads. Its "
     "probability density function is given by:", align=J)
equation("f(x) = (α·xₘ^α) / x^(α+1),     x ≥ xₘ", 2)
para("where xₘ is the scale parameter (minimum value) and α is the shape parameter controlling tail "
     "heaviness. The mean of the Pareto distribution exists only when α > 1 and is given by:", align=J)
equation("E[X] = (α·xₘ) / (α − 1)", 3)
para("The variance exists only when α > 2:", align=J)
equation("Var(X) = (xₘ²·α) / [(α − 1)²·(α − 2)]", 4)
para("This is a critical property: when α ≤ 2, the variance becomes infinite, rendering traditional "
     "confidence intervals and standard deviation-based metrics meaningless. For α ≤ 1, even the mean is "
     "undefined. Our experiments use α = 2.5, which is realistic for cloud workloads and yields a finite "
     "but large variance.", align=J)
para("The squared coefficient of variation, which measures service time variability relative to the mean, "
     "is:", align=J)
equation("Cs² = Var(X) / E[X]² = 1 / [α(α − 2)]", 5)
para("For the exponential distribution Cs² = 1, while for Pareto with α = 2.5 we obtain "
     "Cs² = 1/(2.5 × 0.5) = 0.8. This coefficient drives the M/G/N approximations that extend the baseline "
     "model to general service time distributions.", align=J)
para("Kingman’s approximation [12] adjusts the M/M/N wait time using the coefficient of variation:", align=J)
equation("Wq^(M/G/N) ≈ Wq^(M/M/N) · (1 + Cs²) / 2", 6)
para("Whitt [13] proposed a refined approximation that accounts for higher-order effects of service time "
     "variability, while Allen [14] developed the Allen-Cunneen approximation as an alternative correction. "
     "These three methods provide complementary estimates that bracket the true M/G/N performance, as we "
     "validate experimentally in Section 5.", align=J)

# ============================ 4 HEAVY-TAILED BEHAVIOR ============================
heading("4", "Heavy-Tailed Behavior and the Reality Gap")
para("The distinction between exponential and Pareto tail behavior has profound implications for "
     "performance modeling. An exponential distribution’s tail decays rapidly, making extreme values "
     "exceedingly rare. In contrast, a Pareto distribution’s tail follows a power law, meaning extreme "
     "values occur with much higher probability. Specifically, the probability of observing a value "
     "exceeding 10 times the mean is 0.0000454 for an exponential distribution but 0.0316 for a Pareto "
     "distribution with α = 2.5, making such extreme events approximately 696 times more likely under "
     "heavy-tailed conditions.", align=J)
para("This phenomenon manifests in cloud message queues as the well-known Pareto principle: a small "
     "fraction of messages consumes a disproportionate share of processing resources. In practice, "
     "approximately 20% of messages account for 80% of total processing time, 1% of requests generate "
     "roughly 50% of tail latency, and rare “straggler” messages dominate P99 performance metrics. These "
     "observations are consistent with the findings of Dean and Barroso [9], who demonstrated that tail "
     "latencies become increasingly problematic as system scale grows.", align=J)
para("Figure 4 presents a four-panel analysis of the heavy-tail impact on queue performance for an M/G/N "
     "queue with λ = 100 msg/s, N = 10 threads, and μ = 12 msg/s/thread. Panel (A) shows mean wait time "
     "decreasing as the Pareto shape parameter α increases from 2.1 to 4.0, confirming that heavier tails "
     "(lower α) produce longer average waits. Panel (B) plots P99 latency for both wait time and total "
     "response time against α, revealing that tail latency is far more sensitive to the shape parameter "
     "than mean latency, with P99 response time reaching nearly 0.5 seconds at α = 2.1. Panel (C) displays "
     "the squared coefficient of variation Cs² as a function of α, showing the rapid increase in service "
     "time variability as α approaches 2.0, where variance becomes infinite. The red dashed line at "
     "Cs² = 1 marks the exponential distribution baseline, below which the Pareto distribution has lower "
     "variability than exponential but still exhibits heavy-tailed behavior. Panel (D) presents the response "
     "time CDF for four values of α, with all curves smoothly increasing to 1.0 without crossovers. Lower "
     "α values produce CDFs that rise more slowly, indicating a higher probability of extreme response "
     "times. Error bars in panels (A) through (C) represent 95% confidence intervals from 10 independent "
     "replications. These results collectively demonstrate that the Pareto shape parameter has a dramatic "
     "effect on tail performance that standard M/M/N models fail to capture.", align=J)

figure("fig4_heavytail_4p.png",
       "Figure 4: Four-panel analysis of heavy-tail impact on M/G/N queue performance. (A) Mean wait time "
       "versus Pareto shape parameter α. (B) P99 latency for wait and response time versus α. (C) Squared "
       "coefficient of variation Cs² versus α, with the exponential baseline at Cs² = 1. (D) Response time "
       "CDF for α ∈ {2.1, 2.5, 3.0, 4.0}. System parameters: λ = 100 msg/s, N = 10 threads, "
       "μ = 12 msg/s/thread, 10 replications.")

para("The variance properties of the Pareto distribution are summarized in Table 4. The transition from "
     "finite to infinite variance at α = 2 represents a qualitative change in system behavior: below this "
     "threshold, traditional statistical methods based on the central limit theorem no longer apply, and "
     "sample means converge to the true mean at a much slower rate.", align=J)
table("Table 4: Pareto Variance Properties by Shape Parameter",
      ["α Value", "Variance", "Implication"],
      [["α > 2", "Finite", "Traditional statistics apply"],
       ["1 < α ≤ 2", "Infinite", "Mean exists, variance does not"],
       ["α ≤ 1", "Undefined", "Even the mean is infinite"]],
      widths=[1.5, 1.5, 3.0])

subheading("4.1", "The Reality Gap")
para("We validated our SimPy simulation framework against the base paper’s analytical M/M/N formulas "
     "before introducing heavy-tailed extensions. Table 5 confirms that our simulation matches analytical "
     "predictions within 2% across all key metrics, establishing confidence in the simulation "
     "infrastructure.", align=J)
table("Table 5: Baseline M/M/N Validation: Analytical versus Simulation",
      ["Metric", "Analytical", "Simulation", "Error"],
      [["Mean Wait (Wq)", "0.0125s", "0.0127s", "1.6%"],
       ["Queue Length (Lq)", "1.00", "0.98", "2.0%"],
       ["Utilization (ρ)", "0.80", "0.802", "0.2%"]],
      widths=[2.1, 1.3, 1.3, 1.3])
para("With the baseline validated, we introduced Pareto-distributed service times with α = 2.5 and "
     "compared the results against the M/M/N predictions. Figure 5 presents this comparison, which we term "
     "the “reality gap.” The divergence between the two models is striking and grows more severe at higher "
     "percentiles. Table 6 quantifies this gap across three key metrics.", align=J)

figure("fig5_reality_gap.png",
       "Figure 5: The reality gap between M/M/N analytical predictions and M/G/N simulation with Pareto "
       "service times (α = 2.5). The divergence is most pronounced at the P99 level, where the M/M/N model "
       "underestimates latency by over 150%.")

table("Table 6: The Reality Gap: M/M/N Predictions versus Pareto Simulation",
      ["Metric", "Analytical M/M/N", "SimPy Pareto", "Error"],
      [["Mean Wait (ms)", "12.5", "18.2", "+45.6%"],
       ["P50 Latency (ms)", "8.3", "11.7", "+41.0%"],
       ["P99 Latency (ms)", "57.5", "145.8", "+153.6%"]],
      widths=[1.8, 1.8, 1.4, 1.0])
para("The P99 latency is underestimated by over 150%, which has severe practical consequences. Systems "
     "provisioned based on M/M/N P99 predictions would experience two to three times more SLA violations "
     "than expected, with the worst-affected 1% of users experiencing dramatically degraded service. "
     "Furthermore, the resulting timeouts trigger retransmissions that compound the problem through the "
     "traffic inflation mechanism described in Section 2.", align=J)

subheading("4.2", "Tail Risk and Extreme Value Theory")
para("The standard P99 approximation based on Gaussian assumptions computes W₉₉ = μ_W + 2.33σ_W [4], "
     "which yields 57.5 ms for our parameters. However, the actual simulation P99 is 145.8 ms, representing "
     "a 45% underestimation. This failure occurs because the Gaussian approximation assumes that latency "
     "follows a normal distribution, where the tail probability decays as P(W > w) ≈ 1 − Φ((w − μ)/σ). "
     "For Pareto-distributed latencies, the tail instead follows a power law P(W > w) ~ w^(−α), which "
     "decays far more slowly.", align=J)
para("Figure 6 presents the tail risk assessment comparing EVT-based estimation against the Gaussian "
     "approximation. The Gaussian method systematically underestimates tail probabilities, while the "
     "Generalized Pareto Distribution (GPD) from Extreme Value Theory [16] provides accurate estimates. The "
     "GPD models exceedances above a high threshold u as:", align=J)
equation("P(X > u + x | X > u) = (1 + ξ·x/σ)^(−1/ξ)", 7)
para("where ξ is the tail index and σ is the scale parameter, both estimated from the simulation data. "
     "This approach is justified by the Pickands-Balkema-de Haan theorem [17], which establishes that "
     "exceedances over sufficiently high thresholds converge to the GPD regardless of the underlying "
     "distribution.", align=J)

figure("fig6_tail_risk.png",
       "Figure 6: Tail risk assessment comparing Gaussian-based P99 approximation against EVT-based "
       "estimation using the Generalized Pareto Distribution. The Gaussian method (dashed line) "
       "systematically underestimates tail probabilities, while the GPD (solid line) accurately captures the "
       "heavy-tailed behavior observed in simulation.")

para("We validated three M/G/N approximation methods against our simulation results, as summarized in "
     "Table 7. The Whitt approximation [13] achieves the best overall accuracy with 5.1% mean wait error "
     "and 18.2% P99 error. The Kingman approximation [12] is simplest to compute but least accurate at the "
     "tails, while the Allen-Cunneen method [14] provides intermediate accuracy. All three methods "
     "significantly outperform the naive M/M/N model for heavy-tailed workloads, though none achieves the "
     "accuracy of direct simulation for P99 estimation.", align=J)
table("Table 7: M/G/N Approximation Validation Against Simulation",
      ["Method", "Mean Wait Error", "P99 Error"],
      [["Kingman [12]", "8.2%", "23.5%"],
       ["Whitt [13]", "5.1%", "18.2%"],
       ["Allen-Cunneen [14]", "6.7%", "21.0%"]],
      widths=[2.2, 1.9, 1.9])

# ============================ 5 EXPERIMENTAL RESULTS ============================
heading("5", "Experimental Results and Validation")
para("This section presents the experimental validation of our framework, including baseline reproduction "
     "of the Li et al. results, convergence analysis, and load testing across varying arrival rates.", align=J)

subheading("5.1", "Simulation Framework")
para("We implemented our simulation framework using SimPy 4.1.1 [21], a process-based discrete-event "
     "simulation library for Python. The backend exposes simulation capabilities through a FastAPI REST API, "
     "while a React 18 frontend provides interactive visualization tools. Statistical analysis relies on "
     "NumPy and SciPy, with Matplotlib generating all figures. We chose SimPy over the Colored Petri Net "
     "formalism used by Li et al. [1] because SimPy offers greater flexibility in specifying arbitrary "
     "service time distributions, integrates naturally with Python’s scientific computing ecosystem, and "
     "supports REST API integration for interactive analysis. Algorithm 1 presents the pseudocode for our "
     "M/M/N queue simulation.", align=J)

# Algorithm block
alg_title = doc.add_paragraph()
alg_title.paragraph_format.space_before = Pt(6)
rt = alg_title.add_run("Algorithm 1  M/M/N Queue Simulation")
rt.bold = True
alg_steps = [
    "1:  procedure SIMULATEMMNQUEUE(arrival_rate, service_rate, num_servers, num_messages)",
    "2:      Initialize simulation environment",
    "3:      Create server pool with num_servers servers",
    "4:      Initialize empty list for wait times",
    "5:      for each message m ranging from 1 through num_messages do",
    "6:          Record arrival time of message m",
    "7:          Request a server from the pool",
    "8:          if no server is available then",
    "9:              Wait until a server becomes free",
    "10:         end if",
    "11:         Compute wait time as current time minus arrival time",
    "12:         Generate service time from exponential distribution with rate service_rate",
    "13:         Hold server for duration of service time",
    "14:         Release server back to pool",
    "15:         Record total sojourn time (wait plus service)",
    "16:     end for",
    "17:     return collected wait times for statistical analysis",
    "18: end procedure",
]
for step in alg_steps:
    ps = doc.add_paragraph()
    ps.paragraph_format.space_after = Pt(0)
    ps.paragraph_format.line_spacing = 1.0
    rs = ps.add_run(step)
    rs.font.name = "Courier New"
    rs.font.size = Pt(9)
doc.add_paragraph().paragraph_format.space_after = Pt(2)

subheading("5.2", "Baseline Reproduction")
para("Figure 7 presents the detailed M/M/N validation results across a range of system configurations. The "
     "simulation accurately reproduces the analytical predictions for mean wait time, queue length, and "
     "utilization, with errors consistently below 2%. This level of agreement establishes confidence in our "
     "simulation infrastructure and confirms that the SimPy-based approach produces results equivalent to "
     "the Colored Petri Net formalism used in the original paper.", align=J)

figure("fig7_mmn_bars.png",
       "Figure 7: Detailed M/M/N validation results comparing analytical predictions against simulation "
       "across multiple configurations. Error bars represent 95% confidence intervals computed from 30 "
       "independent replications. All metrics agree within 2%, validating the simulation framework.")

para("Figure 8 presents the utilization validation, reproducing Figure 13 from the base paper. The figure "
     "compares sender and broker utilization across thread counts for two reliability configurations: q=99% "
     "(p=0.01) and q=88% (p=0.12). In both panels, utilization decreases consistently as the number of "
     "threads increases, which is expected since adding servers reduces the per-server load. The broker "
     "utilization (magenta) is higher than the sender utilization (green) due to the traffic amplification "
     "effect, where retransmissions increase the effective arrival rate at the broker stage by a factor of "
     "1/(1 − p). Our simulation results (solid lines with filled markers) closely match the base paper "
     "values (dashed lines with open markers) across all thread counts and both configurations. The "
     "separation between sender and broker curves is more pronounced in the q=88% configuration (panel B) "
     "because the higher failure probability p=0.12 produces greater traffic amplification than p=0.01. "
     "System parameters are λ = 30.3 msg/s, μ₁ = μ₂ = 10.0 msg/s/thread, and D_link = 10 ms.", align=J)

figure("fig8_util_thr.png",
       "Figure 8: Utilization versus number of threads, reproducing Figure 13 from Li et al. [1]. Results "
       "shown for q=99% (p=0.01) and q=88% (p=0.12). Sender utilization (green) and broker utilization "
       "(magenta) both decrease with thread count. Broker utilization exceeds sender utilization due to "
       "traffic amplification. System parameters: λ = 30.3 msg/s, μ₁ = μ₂ = 10.0 msg/s/thread, "
       "D_link = 10 ms.")

subheading("5.3", "Convergence and Load Testing")
para("Ensuring simulation convergence is essential for producing reliable estimates. Figure 9 shows the "
     "convergence behavior of key metrics as a function of the number of simulated messages. After an "
     "initial transient period, all metrics stabilize around their analytical values. We discard the first "
     "1,000 messages as warm-up to eliminate transient effects, and run each experiment for at least 10,000 "
     "messages to ensure steady-state estimates with 95% confidence interval widths below 5% of the mean.",
     align=J)

figure("fig9_convergence.png",
       "Figure 9: Convergence test showing stabilization of mean wait time, queue length, and utilization "
       "as the number of simulated messages increases. Metrics converge to analytical values after "
       "approximately 10,000 messages, with the warm-up period of 1,000 messages indicated by the shaded "
       "region.")

para("Figure 10 presents load testing results across arrival rates ranging from low utilization to "
     "near-saturation conditions. As the arrival rate approaches the system’s capacity, both mean and tail "
     "latencies increase sharply, consistent with queueing theory predictions. The M/G/N model with Pareto "
     "service times consistently produces higher latencies than the M/M/N model at all load levels, with "
     "the gap widening as utilization increases. This confirms that the heavy-tail effect is not merely a "
     "high-load phenomenon but is present across the entire operating range, becoming more pronounced under "
     "stress.", align=J)

figure("fig10_load_test.png",
       "Figure 10: Load testing results comparing M/M/N and M/G/N models across arrival rates from 20 to 95 "
       "messages per second. The divergence between models grows with utilization, confirming that "
       "heavy-tailed effects are amplified under high load conditions.")

# ============================ 6 CONCLUSION ============================
heading("6", "Conclusion and Future Work")
para("This paper extended the tandem queue model of Li et al. [1] to address the critical limitation of "
     "exponential service time assumptions in cloud message broker performance modeling. Our simulation "
     "framework, built on Python and SimPy, successfully reproduced all key results from the base paper, "
     "validating the traffic inflation formula Λ₂ = λ/(1 − p) to within 0.2% error and matching M/M/N "
     "analytical predictions within 2% across all metrics.", align=J)
para("The central finding of this work is the quantification of the “reality gap” between M/M/N "
     "predictions and observed performance under Pareto-distributed service times. Standard models "
     "underestimate P99 latency by approximately 45%, with the Gaussian-based P99 approximation yielding "
     "57.5 ms compared to the actual simulation value of 145.8 ms. This underestimation has severe practical "
     "consequences for capacity planning and SLA compliance. We demonstrated that Extreme Value Theory, "
     "specifically the Generalized Pareto Distribution, provides accurate tail risk estimates where Gaussian "
     "methods fail.", align=J)
para("Among the three M/G/N approximation methods evaluated, the Whitt approximation achieved the best "
     "overall accuracy with 5.1% mean wait error and 18.2% P99 error, making it the recommended analytical "
     "method for practitioners who require quick estimates without full simulation. However, for critical "
     "capacity planning decisions involving tail latency guarantees, direct simulation with heavy-tailed "
     "distributions remains essential.", align=J)
para("Several directions for future work emerge from this research. First, incorporating real production "
     "traces from cloud message brokers would validate the Pareto assumption and calibrate the shape "
     "parameter α for specific systems. Second, extending the model to multi-region deployments with "
     "geo-distributed queues would address an increasingly common architectural pattern. Third, integrating "
     "machine learning-based prediction models could enable adaptive capacity planning that responds to "
     "changing workload characteristics in real time. Fourth, connecting the simulation framework to "
     "Kubernetes Horizontal Pod Autoscaler would enable automated scaling decisions based on heavy-tailed "
     "performance models rather than simple utilization thresholds.", align=J)

# ============================ REFERENCES ============================
heading(None, "References")
refs = [
    "[1] J. Li et al., “Modeling message queueing services with reliability guarantee in cloud computing environment using colored Petri nets,” in Proc. IEEE Int. Conf. Cloud Computing, 2015.",
    "[2] A. K. Erlang, “Solution of some problems in the theory of probabilities of significance in automatic telephone exchanges,” Elektroteknikeren, vol. 13, pp. 5–13, 1917.",
    "[3] L. Kleinrock, Queueing Systems, Volume 1: Theory. New York: Wiley-Interscience, 1975.",
    "[4] D. Gross and C. M. Harris, Fundamentals of Queueing Theory, 3rd ed. New York: Wiley, 1998.",
    "[5] J. D. C. Little, “A proof for the queuing formula: L = λW,” Operations Research, vol. 9, no. 3, pp. 383–387, 1961.",
    "[6] M. E. Crovella and A. Bestavros, “Self-similarity in World Wide Web traffic: Evidence and possible causes,” IEEE/ACM Trans. Networking, vol. 5, no. 6, pp. 835–846, 1997.",
    "[7] W. E. Leland, M. S. Taqqu, W. Willinger, and D. V. Wilson, “On the self-similar nature of Ethernet traffic (extended version),” IEEE/ACM Trans. Networking, vol. 2, no. 1, pp. 1–15, 1994.",
    "[8] V. Paxson and S. Floyd, “Wide area traffic: The failure of Poisson modeling,” IEEE/ACM Trans. Networking, vol. 3, no. 3, pp. 226–244, 1995.",
    "[9] J. Dean and L. A. Barroso, “The tail at scale,” Commun. ACM, vol. 56, no. 2, pp. 74–80, 2013.",
    "[10] G. DeCandia et al., “Dynamo: Amazon’s highly available key-value store,” in Proc. ACM SOSP, 2007, pp. 205–220.",
    "[11] Netflix Technology Blog, “Zuul 2: The Netflix journey to asynchronous, non-blocking systems,” 2015.",
    "[12] J. F. C. Kingman, “On queues in heavy traffic,” J. Royal Statistical Society, Series B, vol. 24, no. 2, pp. 383–392, 1962.",
    "[13] W. Whitt, “Approximations for the GI/G/m queue,” Production and Operations Management, vol. 2, no. 2, pp. 114–161, 1993.",
    "[14] A. O. Allen, Probability, Statistics, and Queueing Theory with Computer Science Applications, 2nd ed. San Diego: Academic Press, 1990.",
    "[15] W. G. Marchal, “An approximate formula for waiting time in single server queues,” AIIE Trans., vol. 8, no. 4, pp. 473–474, 1976.",
    "[16] S. Coles, An Introduction to Statistical Modeling of Extreme Values. London: Springer, 2001.",
    "[17] J. Beirlant, Y. Goegebeur, J. Segers, and J. Teugels, Statistics of Extremes: Theory and Applications. Chichester: Wiley, 2004.",
    "[18] S. I. Resnick, Heavy-Tail Phenomena: Probabilistic and Statistical Modeling. New York: Springer, 2007.",
    "[19] M. Harchol-Balter, Performance Modeling and Design of Computer Systems: Queueing Theory in Action. Cambridge: Cambridge Univ. Press, 2013.",
    "[20] J. Nair, A. Wierman, and B. Zwart, “The fundamentals of heavy tails: Properties, emergence, and estimation,” Cambridge Univ. Press, 2022.",
    "[21] Team SimPy, “SimPy: Discrete event simulation for Python,” 2023. [Online]. Available: https://simpy.readthedocs.io/",
]
for idx, ref in enumerate(refs, start=1):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.left_indent = Inches(0.3)
    p.paragraph_format.first_line_indent = Inches(-0.3)
    r = p.add_run(ref)
    r.font.name = "Times New Roman"
    r.font.size = Pt(10)
    add_bookmark(p, f"ref{idx}", 1000 + idx)

out = os.path.join(HERE, "273_paper1_editable.docx")
doc.save(out)
print("saved:", out)
