"""
Small, generically-shared pure functions ported from mockData.ts — used by
students/, finance/, and results/ alike, so they live here rather than in
any one domain app.
"""

from .models import FinanceTerm


def get_previous_term(term: str, year: int) -> tuple[str, int]:
    """
    Port of getPreviousTerm(). Term1 -> (Term3, year-1); Term2 -> (Term1,
    year); Term3 -> (Term2, year). Real calendar-rollback rule used
    throughout Finance/Requirements/trend-tracking — must stay exact.
    """
    if term == FinanceTerm.TERM_1:
        return FinanceTerm.TERM_3, year - 1
    if term == FinanceTerm.TERM_2:
        return FinanceTerm.TERM_1, year
    return FinanceTerm.TERM_2, year
