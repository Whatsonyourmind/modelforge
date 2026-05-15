"""Sheet taxonomy — which gates apply to which sheet."""

from __future__ import annotations

from typing import Literal


SheetClass = Literal["core_output", "simulation", "input", "reference", "audit", "unknown"]


SHEET_TAXONOMY: dict[SheetClass, set[str]] = {
    "core_output": {
        # Cross-template valuation engine sheets — must be fully formulated
        "WACCBuild", "FCFForecast", "Valuation", "Returns",
        "OperatingModel", "DebtSchedule", "Covenants", "CreditOpinion",
        "Waterfall", "EquityWaterfall", "TrancheWaterfall",
        "OperatingPnL", "BalanceSheet", "CashFlowStatement",
        "DSCRBuild", "ProjectCashflows", "ConstructionDraws",
        "BondPricing", "InvestorReturns",
        "ExitBridge", "FairnessSummary",
        "MergerAccretion", "ProForma", "SynergiesBuild",
        "TaxBuild", "DealStructure",
        "RateMatrix", "PaymentSchedule",
        # NPL / structured credit
        "RecoveryWaterfall", "CollectionCurve", "PortfolioReturns",
        "TrancheCashflows",
        # IPO / restructuring
        "ValuationTriangulation", "RecoveryByClass", "PlanFeasibility",
    },
    "simulation": {
        "MonteCarlo", "MonteCarloOutputs", "ScenarioSweep",
        "RiskAnalysis", "RiskSheet",  # NOTE: risk-aggregations are simulation-style
    },
    "input": {
        "Cover", "Sources", "Assumptions", "RawData", "Inputs",
        "ScenarioAssumptions", "OpeningBalanceSheet",
        "DealAssumptions", "TargetFinancials", "AcquirerFinancials",
    },
    "reference": {
        # Reference data with formulas only on aggregation rows
        "ComparableBetas", "RatingShadow", "PrecedentTransactions",
        "TradingComps", "ClaimClasses",
    },
    "audit": {
        # ModelForge meta-sheets (QC, RedFlags, Reproducibility, MOAT)
        "QC", "RedFlags", "Reproducibility", "MOAT",
        "ComplianceCheck", "SensitivityAnalysis",  # sensitivity surfaces partly-derived metrics
    },
}


def classify_sheet(name: str) -> SheetClass:
    """Map a sheet name to its taxonomy class.

    Unknown / new sheets default to ``"core_output"`` to enforce the
    moat by default (opt-out > opt-in for safety).
    """
    for klass, names in SHEET_TAXONOMY.items():
        if name in names:
            return klass
    # Heuristic: anything ending in 'Build', 'Forecast', 'Schedule', 'Returns'
    # → core_output. Anything containing 'MonteCarlo' / 'Risk' → simulation.
    upper = name.upper()
    if any(s in upper for s in ("MONTECARLO", "MONTE_CARLO", "RISK")):
        return "simulation"
    if upper.endswith(("BUILD", "FORECAST", "SCHEDULE", "RETURNS",
                       "WATERFALL", "BRIDGE", "VALUATION")):
        return "core_output"
    if upper in ("RAWDATA", "INPUTS"):
        return "input"
    return "unknown"
