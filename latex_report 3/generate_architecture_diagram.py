"""
Generate a multi-stage network diagram similar to Rubesh Anand paper
for Cloud Message Queue Tandem System
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Circle, FancyArrowPatch, Ellipse
import numpy as np

# Create figure
fig, ax = plt.subplots(1, 1, figsize=(14, 10))
ax.set_xlim(0, 14)
ax.set_ylim(0, 10)
ax.set_aspect('equal')
ax.axis('off')

# Colors
producer_color = '#E8F4FD'  # Light blue
queue_color = '#FFF3E0'     # Light orange
server_color = '#E8F5E9'    # Light green
failed_color = '#FFEBEE'    # Light red
consumer_color = '#F3E5F5'  # Light purple

# ===== Stage Labels =====
ax.text(1.5, 0.3, '1st Stage\n(Producers)', ha='center', fontsize=11, fontweight='bold')
ax.text(4.5, 0.3, '2nd Stage\n(Queue 1)', ha='center', fontsize=11, fontweight='bold')
ax.text(7.5, 0.3, '3rd Stage\n(Queue 2)', ha='center', fontsize=11, fontweight='bold')
ax.text(10.5, 0.3, '4th Stage\n(Consumers)', ha='center', fontsize=11, fontweight='bold')
ax.text(13, 0.3, 'nth Stage\n(Output)', ha='center', fontsize=11, fontweight='bold')

# ===== Draw Producers (Stage 1) =====
producer_positions = [8, 6.5, 5, 3.5, 2]
for i, y in enumerate(producer_positions):
    circle = Circle((1.5, y), 0.4, facecolor=producer_color, edgecolor='black', linewidth=1.5)
    ax.add_patch(circle)
    ax.text(1.5, y, f'P{i+1}', ha='center', va='center', fontsize=9, fontweight='bold')

# Draw arrival arrows (lambda)
for y in producer_positions:
    ax.annotate('', xy=(1.1, y), xytext=(0.3, y),
                arrowprops=dict(arrowstyle='->', color='darkgreen', lw=1.5))
ax.text(0.1, 5, 'λ', fontsize=14, fontweight='bold', color='darkgreen')

# ===== Draw Queue 1 Servers (Stage 2) =====
# Draw enclosing ellipse for Queue 1
ellipse1 = Ellipse((4.5, 5), 2.2, 7, facecolor='#FAFAFA', edgecolor='gray', 
                    linewidth=1, linestyle='--', alpha=0.5)
ax.add_patch(ellipse1)
ax.text(4.5, 8.8, 'Queue 1\n(N₁=10)', ha='center', fontsize=10, fontweight='bold', color='#1565C0')

queue1_positions = [7.5, 6.3, 5.1, 3.9, 2.7]
queue1_colors = [queue_color, queue_color, failed_color, queue_color, queue_color]
for i, (y, color) in enumerate(zip(queue1_positions, queue1_colors)):
    circle = Circle((4.5, y), 0.35, facecolor=color, edgecolor='black', linewidth=1.5)
    ax.add_patch(circle)
    label = 'μ₁' if color == queue_color else 'F'
    ax.text(4.5, y, label, ha='center', va='center', fontsize=8, fontweight='bold')

# Arrows from producers to Queue 1
for py in producer_positions:
    for qy in queue1_positions:
        if abs(py - qy) < 2:
            ax.annotate('', xy=(4.1, qy), xytext=(1.9, py),
                        arrowprops=dict(arrowstyle='->', color='gray', lw=0.8, alpha=0.6))

# ===== Draw Queue 2 Servers (Stage 3) =====
# Draw enclosing ellipse for Queue 2
ellipse2 = Ellipse((7.5, 5), 2.2, 7, facecolor='#FAFAFA', edgecolor='gray', 
                    linewidth=1, linestyle='--', alpha=0.5)
ax.add_patch(ellipse2)
ax.text(7.5, 8.8, 'Queue 2\n(N₂=8)', ha='center', fontsize=10, fontweight='bold', color='#1565C0')

queue2_positions = [7.5, 6.3, 5.1, 3.9, 2.7]
queue2_colors = [server_color, server_color, server_color, failed_color, server_color]
for i, (y, color) in enumerate(zip(queue2_positions, queue2_colors)):
    circle = Circle((7.5, y), 0.35, facecolor=color, edgecolor='black', linewidth=1.5)
    ax.add_patch(circle)
    label = 'μ₂' if color == server_color else 'F'
    ax.text(7.5, y, label, ha='center', va='center', fontsize=8, fontweight='bold')

# Arrows from Queue 1 to Queue 2
for q1y in queue1_positions:
    for q2y in queue2_positions:
        if abs(q1y - q2y) < 1.5:
            ax.annotate('', xy=(7.1, q2y), xytext=(4.9, q1y),
                        arrowprops=dict(arrowstyle='->', color='#1976D2', lw=1, alpha=0.7))

# ===== Draw Consumers (Stage 4) =====
consumer_positions = [7.5, 6.3, 5.1, 3.9, 2.7]
for i, y in enumerate(consumer_positions):
    circle = Circle((10.5, y), 0.35, facecolor=consumer_color, edgecolor='black', linewidth=1.5)
    ax.add_patch(circle)
    ax.text(10.5, y, f'C{i+1}', ha='center', va='center', fontsize=8, fontweight='bold')

# Arrows from Queue 2 to Consumers
for q2y in queue2_positions:
    for cy in consumer_positions:
        if abs(q2y - cy) < 1.2:
            ax.annotate('', xy=(10.1, cy), xytext=(7.9, q2y),
                        arrowprops=dict(arrowstyle='->', color='#388E3C', lw=1, alpha=0.7))

# ===== Draw nth Stage (Output) =====
output_y_positions = np.linspace(7.8, 2.2, 8)
for y in output_y_positions:
    circle = Circle((13, y), 0.2, facecolor='white', edgecolor='black', linewidth=1)
    ax.add_patch(circle)

# Arrows to output
for cy in consumer_positions[:3]:
    ax.annotate('', xy=(12.7, cy + 0.5), xytext=(10.9, cy),
                arrowprops=dict(arrowstyle='->', color='gray', lw=0.8, alpha=0.6))

# ===== Draw Retry/Failure Loop =====
# Curved arrow for retransmission from Queue 2 back to Queue 1
style = "Simple, tail_width=0.5, head_width=4, head_length=8"
kw = dict(arrowstyle=style, color='red', lw=1.5)

# Draw retry path
ax.annotate('', xy=(4.5, 1.3), xytext=(7.5, 1.3),
            arrowprops=dict(arrowstyle='<-', color='red', lw=2,
                           connectionstyle='arc3,rad=0.3'))
ax.text(6, 0.8, 'Retry (p=0.1)', ha='center', fontsize=10, fontweight='bold', color='red')

# ===== Traffic Inflation Annotation =====
ax.annotate('', xy=(5.5, 9.3), xytext=(3.5, 9.3),
            arrowprops=dict(arrowstyle='->', color='darkblue', lw=2))
ax.text(4.5, 9.6, 'Λ₂ = λ/(1-p)', ha='center', fontsize=11, fontweight='bold', color='darkblue')

# ===== Vertical dotted lines between stages =====
for x in [2.8, 5.8, 8.8, 11.8]:
    ax.plot([x, x], [1, 9], 'k--', alpha=0.3, linewidth=1)

# ===== Legend =====
legend_elements = [
    mpatches.Patch(facecolor=producer_color, edgecolor='black', label='Producer (Message Source)'),
    mpatches.Patch(facecolor=queue_color, edgecolor='black', label='Queue Server (Working)'),
    mpatches.Patch(facecolor=server_color, edgecolor='black', label='Server (Processing)'),
    mpatches.Patch(facecolor=failed_color, edgecolor='black', label='Failed/Retry Node'),
    mpatches.Patch(facecolor=consumer_color, edgecolor='black', label='Consumer (Message Sink)'),
]
ax.legend(handles=legend_elements, loc='upper left', fontsize=9, 
          framealpha=0.9, bbox_to_anchor=(0.02, 0.98))

# ===== Title =====
ax.set_title('Cloud Message Queue Tandem System Architecture\n(Multi-Stage Message Processing with Retry Mechanism)', 
             fontsize=14, fontweight='bold', pad=20)

# ===== Add equations box =====
textstr = '\n'.join([
    'Key Parameters:',
    'λ = 80 msg/s (arrival rate)',
    'μ₁ = 10 msg/s (Stage 1 service)',
    'μ₂ = 12 msg/s (Stage 2 service)',
    'N₁ = 10, N₂ = 8 (servers)',
    'p = 0.1 (failure probability)',
    'Λ₂ = λ/(1-p) = 88.89 msg/s'
])
props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
ax.text(0.98, 0.35, textstr, transform=ax.transAxes, fontsize=9,
        verticalalignment='top', horizontalalignment='right', bbox=props)

plt.tight_layout()
plt.savefig('images/tandem_queue_architecture.png', dpi=300, bbox_inches='tight', 
            facecolor='white', edgecolor='none')
plt.savefig('images/tandem_queue_architecture.pdf', bbox_inches='tight', 
            facecolor='white', edgecolor='none')
print("Saved: images/tandem_queue_architecture.png")
print("Saved: images/tandem_queue_architecture.pdf")
plt.show()
