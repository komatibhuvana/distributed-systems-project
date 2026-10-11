"""
Analytical Routes
Endpoints for analytical calculations (M/M/N, M/G/N formulas)
Instant results without running simulations
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import sys
import os
# Add project root to path
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
sys.path.append(project_root)

from src.analysis.analytical import MMNAnalytical, MGNAnalytical, TandemQueueAnalytical
from backend.api.models.analytical_models import (
    MMNAnalyticalRequest,
    MGNAnalyticalRequest,
    TandemAnalyticalRequest,
    AnalyticalResponse
)

router = APIRouter()


@router.post("/mmn", response_model=AnalyticalResponse)
async def calculate_mmn(request: MMNAnalyticalRequest):
    """
    Calculate M/M/N queue metrics analytically

    Returns all metrics instantly using Erlang-C and queueing formulas:
    - Utilization (ρ)
    - Erlang-C (probability of queueing)
    - Mean waiting time (Wq)
    - Mean queue length (Lq)
    - Mean response time (R)
    - Mean system size (L)
    """
    try:
        # Create analytical model
        analytical = MMNAnalytical(
            arrival_rate=request.arrival_rate,
            num_threads=request.num_threads,
            service_rate=request.service_rate
        )

        # Calculate all metrics
        metrics = analytical.all_metrics()

        return AnalyticalResponse(
            model_type="M/M/N",
            config={
                "arrival_rate": request.arrival_rate,
                "num_threads": request.num_threads,
                "service_rate": request.service_rate
            },
            metrics=metrics,
            formulas_used=[
                "Eq. 1: Utilization ρ = λ/(N·μ)",
                "Eq. 2: Erlang-C formula",
                "Eq. 4: Mean queue length Lq",
                "Eq. 5: Mean waiting time Wq (Little's Law)"
            ]
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mgn", response_model=AnalyticalResponse)
async def calculate_mgn(request: MGNAnalyticalRequest):
    """
    Calculate M/G/N queue metrics analytically

    Uses Pollaczek-Khinchin approximation for heavy-tailed distributions:
    - Coefficient of Variation (C²)
    - Approximate mean waiting time
    - Approximate queue length
    """
    try:
        # Create analytical model
        analytical = MGNAnalytical(
            arrival_rate=request.arrival_rate,
            num_threads=request.num_threads,
            mean_service=request.mean_service,
            variance_service=request.variance_service
        )

        # Calculate metrics
        metrics = analytical.all_metrics()

        return AnalyticalResponse(
            model_type="M/G/N",
            config={
                "arrival_rate": request.arrival_rate,
                "num_threads": request.num_threads,
                "mean_service": request.mean_service,
                "variance_service": request.variance_service
            },
            metrics=metrics,
            formulas_used=[
                "Eq. 9: Coefficient of Variation C²",
                "Eq. 10: M/G/N waiting time approximation (Kingman/Whitt)",
                "Heavy-tailed distribution adjustment"
            ]
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tandem", response_model=AnalyticalResponse)
async def calculate_tandem(request: TandemAnalyticalRequest):
    """
    Calculate Tandem queue (two-stage) metrics analytically

    Critical insight: Stage 2 sees amplified traffic due to retransmissions
    Λ₂ = λ/(1-p) where p is failure probability
    """
    try:
        # Create analytical model
        analytical = TandemQueueAnalytical(
            lambda_arrival=request.arrival_rate,
            n1=request.n1,
            mu1=request.mu1,
            n2=request.n2,
            mu2=request.mu2,
            network_delay=request.network_delay,
            failure_prob=request.failure_prob
        )

        # Calculate all metrics
        stage1_wq = analytical.stage1_waiting_time()
        stage2_wq = analytical.stage2_waiting_time()
        total_latency = analytical.total_message_delivery_time()
        network_time = analytical.network_transmission_time()

        # Stage 2 effective arrival rate
        lambda2 = request.arrival_rate / (1 - request.failure_prob)

        metrics = {
            "stage1_waiting_time": stage1_wq,
            "stage1_utilization": request.arrival_rate / (request.n1 * request.mu1),
            "stage2_waiting_time": stage2_wq,
            "stage2_effective_arrival": lambda2,
            "stage2_utilization": lambda2 / (request.n2 * request.mu2),
            "network_time": network_time,
            "total_latency": total_latency,
            "load_amplification": lambda2 / request.arrival_rate
        }

        return AnalyticalResponse(
            model_type="Tandem",
            config={
                "arrival_rate": request.arrival_rate,
                "n1": request.n1,
                "mu1": request.mu1,
                "n2": request.n2,
                "mu2": request.mu2,
                "network_delay": request.network_delay,
                "failure_prob": request.failure_prob
            },
            metrics=metrics,
            formulas_used=[
                "Stage 2 arrival: Λ₂ = λ/(1-p)",
                "Network time: (2+p)·D",
                "Total latency: W₁ + S₁ + (2+p)·D + W₂ + S₂",
                "Li et al. (2015) tandem model"
            ]
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_simulation_vs_analytical(
    simulation_results: Dict[str, Any],
    analytical_config: Dict[str, Any]
):
    """
    Compare simulation results with analytical predictions

    Returns:
    - Side-by-side metrics comparison
    - Percentage errors
    - Validation status (< 15% error is acceptable)
    """
    try:
        model_type = analytical_config.get("model_type", "M/M/N")

        if model_type == "M/M/N":
            analytical = MMNAnalytical(
                arrival_rate=analytical_config["arrival_rate"],
                num_threads=analytical_config["num_threads"],
                service_rate=analytical_config["service_rate"]
            )
            analytical_metrics = analytical.all_metrics()
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported model type: {model_type}")

        # Calculate errors
        comparison = {}
        for key in ["mean_waiting_time", "mean_queue_length", "mean_response_time"]:
            if key in simulation_results and key in analytical_metrics:
                sim_val = simulation_results[key]
                ana_val = analytical_metrics[key]
                error = abs(sim_val - ana_val) / ana_val * 100 if ana_val > 0 else 0

                comparison[key] = {
                    "simulation": sim_val,
                    "analytical": ana_val,
                    "error_percent": error,
                    "valid": error < 15.0  # < 15% is acceptable
                }

        return {
            "model_type": model_type,
            "comparison": comparison,
            "overall_valid": all(v["valid"] for v in comparison.values())
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/formulas")
async def get_formulas():
    """
    Get all 15 analytical formulas used in the project

    Returns LaTeX-formatted equations for display
    """
    return {
        "mmn_formulas": {
            "eq1": {"name": "Utilization", "latex": r"\rho = \frac{\lambda}{N \cdot \mu}"},
            "eq2": {"name": "Erlang-C", "latex": r"C(N,a) = \frac{\frac{a^N}{N!} \cdot \frac{N}{N-a}}{P_0^{-1}}"},
            "eq3": {"name": "Mean Queue Length", "latex": r"L_q = C(N,a) \cdot \frac{\rho}{1-\rho}"},
            "eq4": {"name": "Mean Waiting Time", "latex": r"W_q = \frac{L_q}{\lambda}"},
            "eq5": {"name": "Mean Response Time", "latex": r"R = W_q + \frac{1}{\mu}"}
        },
        "mgn_formulas": {
            "eq6": {"name": "Pareto PDF", "latex": r"f(t) = \frac{\alpha \cdot k^\alpha}{t^{\alpha+1}}"},
            "eq7": {"name": "Pareto Mean", "latex": r"E[S] = \frac{\alpha \cdot k}{\alpha - 1}"},
            "eq8": {"name": "Pareto Variance", "latex": r"Var(S) = \frac{\alpha \cdot k^2}{(\alpha-1)^2(\alpha-2)}"},
            "eq9": {"name": "Coefficient of Variation", "latex": r"C^2 = \frac{1}{\alpha(\alpha-2)}"},
            "eq10": {"name": "M/G/N Waiting Time", "latex": r"W_q \approx C(N,a) \cdot \frac{\rho}{1-\rho} \cdot \frac{E[S]}{2} \cdot (1+C^2)"}
        },
        "tandem_formulas": {
            "stage2_arrival": {"latex": r"\Lambda_2 = \frac{\lambda}{1-p}"},
            "network_time": {"latex": r"T_{net} = (2+p) \cdot D"},
            "total_latency": {"latex": r"T_{total} = W_1 + S_1 + T_{net} + W_2 + S_2"}
        }
    }
