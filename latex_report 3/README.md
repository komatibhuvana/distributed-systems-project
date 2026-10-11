# LaTeX Report for CMPE 273 Project

## How to Use in Overleaf

### Option 1: Upload as ZIP (Recommended)

1. **Create a ZIP file:**
   ```bash
   cd /path/to/distributed-systems-project/latex_report
   zip -r cmpe273_report.zip .
   ```

2. **Upload to Overleaf:**
   - Go to [Overleaf](https://www.overleaf.com)
   - Click "New Project" → "Upload Project"
   - Upload the `cmpe273_report.zip` file
   - Overleaf will automatically extract and set up the project

3. **Compile:**
   - Click "Recompile" button
   - The PDF will be generated automatically

### Option 2: Manual Upload

1. **Create a new Overleaf project:**
   - Go to Overleaf → "New Project" → "Blank Project"
   - Name it "CMPE273_Project_Report"

2. **Upload files:**
   - Upload `main.tex` (the main LaTeX file)
   - Create a folder called `images`
   - Upload all PNG files from the `images/` folder

3. **Compile:**
   - Click "Recompile"

## File Structure

```
latex_report/
├── main.tex                    # Main LaTeX document
├── images/                     # All figures
│   ├── reality_gap.png         # Title page figure
│   ├── mmn_validation.png      # M/M/N validation
│   ├── figure11_comparison.png # Delivery time comparison
│   ├── figure12_comparison.png # Queue length validation
│   ├── figure13_comparison.png # Utilization validation
│   ├── figure14_reproduction.png # Service time trend
│   ├── figure15_reproduction.png # Arrival rate trend
│   ├── mgn_heavy_tail.png      # Heavy tail distribution
│   ├── tail_risk.png           # P99 tail risk
│   ├── convergence_test.png    # Convergence analysis
│   ├── convergence_check.png   # Additional convergence
│   ├── mitigation_scaling.png  # Server scaling
│   ├── erlang_efficiency.png   # Erlang-k efficiency
│   ├── warmup_validation.png   # Warmup validation
│   ├── plot_1_mmn_validation.png
│   ├── plot_2_heavy_tail_impact.png
│   ├── plot_3_threading_comparison.png
│   ├── plot_4_load_testing.png
│   └── plot_5_confidence_intervals.png
└── README.md                   # This file
```

## LaTeX Packages Used

The document uses standard LaTeX packages that are pre-installed on Overleaf:

- `graphicx` - For images
- `amsmath`, `amssymb` - For mathematical equations
- `hyperref` - For clickable links
- `booktabs` - For professional tables
- `listings` - For code listings
- `algorithm`, `algpseudocode` - For algorithm pseudocode
- `fancyhdr` - For headers/footers
- `natbib` - For bibliography

## Quick Commands

Create ZIP for Overleaf:
```bash
cd /Users/bhuvana/Desktop/Masters/CMPE\ 273/Project/distributed-systems-project/latex_report
zip -r cmpe273_report.zip main.tex images/ README.md
```

## Customization

### Change Authors
Edit line 62 in `main.tex`:
```latex
{\Large\textbf{Authors:} Himanshu Jain, Bhuvana Komati\par}
```

### Change Date
Edit line 67 in `main.tex`:
```latex
{\large\textbf{Date:} December 12, 2025\par}
```

### Add New Figures
1. Add PNG to `images/` folder
2. Reference in main.tex:
```latex
\begin{figure}[H]
    \centering
    \includegraphics[width=0.8\textwidth]{images/your_image.png}
    \caption{Your caption here}
    \label{fig:your_label}
\end{figure}
```

## Troubleshooting

### Images not showing
- Make sure all images are in the `images/` folder
- Check file names match exactly (case-sensitive)

### Compilation errors
- Use "Logs and output files" in Overleaf to see detailed errors
- Common fix: Clear cache and recompile

### Bibliography issues
- The document uses `thebibliography` (inline references)
- No external .bib file needed

## Output

The compiled PDF will include:
- Title page with cover image
- Auto-generated Table of Contents
- Auto-generated List of Figures
- All 16 sections with embedded figures
- References section
- Comprehensive Appendix

---

**Report for:** CMPE 273 - Enterprise Distributed Systems  
**Institution:** San Jose State University  
**Authors:** Himanshu Jain, Bhuvana Komati
