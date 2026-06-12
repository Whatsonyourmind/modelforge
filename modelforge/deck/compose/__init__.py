"""Deal-deck composers — turn structured deal data into presentation IR.

Callers build a typed facts payload (the ``*Facts`` pydantic models in this
package) and call the matching ``compose_<type>`` function to get a fully
validated ``Presentation`` IR, which can then be rendered to a .pptx binary
via the rendering pipeline (``modelforge.deck.rendering``). This is a pure
library API — no network service is involved.

Available composers:

- ``compose_ic_memo`` — 12-slide investment committee memo
- ``compose_teaser`` — 6-slide anonymized deal teaser
- ``compose_lp_quarterly`` — 9-slide LP quarterly fund report
- ``compose_exit_memo`` — 8-slide exit recommendation deck
- ``compose_pitch_deck`` — 13-slide startup pitch deck
- ``compose_portfolio_review`` — 11-slide internal GP portfolio review
- ``compose_board_update`` — 9-slide portfolio-company board update
"""
from __future__ import annotations

from modelforge.deck.compose.board_update import (
    BoardAsk,
    BoardUpdateFacts,
    FinancialRow,
    KpiScorecardEntry,
    compose_board_update,
)
from modelforge.deck.compose.exit_memo import (
    BuyerCandidate,
    ExitMemoFacts,
    ExitMilestone,
    compose_exit_memo,
)
from modelforge.deck.compose.ic_memo import (
    ComparableTransaction,
    DealFacts,
    compose_ic_memo,
)
from modelforge.deck.compose.lp_quarterly import (
    LPQuarterlyFacts,
    PortfolioHolding,
    PortfolioMover,
    compose_lp_quarterly,
)
from modelforge.deck.compose.pitch_deck import (
    CompetitorRow,
    PitchDeckFacts,
    TeamMember,
    compose_pitch_deck,
)
from modelforge.deck.compose.portfolio_review import (
    ExitRecord,
    IcAsk,
    PortfolioCompany,
    PortfolioReviewFacts,
    TopPerformer,
    ValueCreationAction,
    WatchlistItem,
    compose_portfolio_review,
)
from modelforge.deck.compose.teaser import (
    ProcessMilestone,
    TeaserFacts,
    compose_teaser,
)

__all__ = [
    # IC memo
    "ComparableTransaction",
    "DealFacts",
    "compose_ic_memo",
    # Teaser
    "ProcessMilestone",
    "TeaserFacts",
    "compose_teaser",
    # LP quarterly
    "LPQuarterlyFacts",
    "PortfolioHolding",
    "PortfolioMover",
    "compose_lp_quarterly",
    # Exit memo
    "BuyerCandidate",
    "ExitMemoFacts",
    "ExitMilestone",
    "compose_exit_memo",
    # Pitch deck
    "CompetitorRow",
    "PitchDeckFacts",
    "TeamMember",
    "compose_pitch_deck",
    # Portfolio review
    "ExitRecord",
    "IcAsk",
    "PortfolioCompany",
    "PortfolioReviewFacts",
    "TopPerformer",
    "ValueCreationAction",
    "WatchlistItem",
    "compose_portfolio_review",
    # Board update
    "BoardAsk",
    "BoardUpdateFacts",
    "FinancialRow",
    "KpiScorecardEntry",
    "compose_board_update",
]
