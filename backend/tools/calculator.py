"""Financial calculation tools — ratios, growth rates, DCF components."""
from dataclasses import dataclass


@dataclass
class GrowthResult:
    period_from: str
    period_to: str
    value_from: float
    value_to: float
    absolute_change: float
    percent_change: float


def yoy_growth(current: float, prior: float) -> float:
    """Year-over-year growth rate as a decimal (0.05 = 5%)."""
    if prior == 0:
        return 0.0
    return (current - prior) / abs(prior)


def qoq_growth(current: float, prior: float) -> float:
    return yoy_growth(current, prior)


def cagr(beginning: float, ending: float, years: float) -> float:
    """Compound Annual Growth Rate."""
    if beginning <= 0 or years <= 0:
        return 0.0
    return (ending / beginning) ** (1 / years) - 1


def gross_margin(revenue: float, cogs: float) -> float:
    if revenue == 0:
        return 0.0
    return (revenue - cogs) / revenue


def operating_margin(revenue: float, operating_income: float) -> float:
    if revenue == 0:
        return 0.0
    return operating_income / revenue


def net_margin(revenue: float, net_income: float) -> float:
    if revenue == 0:
        return 0.0
    return net_income / revenue


def free_cash_flow(operating_cash_flow: float, capex: float) -> float:
    return operating_cash_flow - capex


def fcf_yield(fcf: float, market_cap: float) -> float:
    if market_cap == 0:
        return 0.0
    return fcf / market_cap


def pe_ratio(stock_price: float, eps: float) -> float:
    if eps == 0:
        return 0.0
    return stock_price / eps


def ev_ebitda(enterprise_value: float, ebitda: float) -> float:
    if ebitda == 0:
        return 0.0
    return enterprise_value / ebitda


def debt_to_equity(total_debt: float, total_equity: float) -> float:
    if total_equity == 0:
        return 0.0
    return total_debt / total_equity


def current_ratio(current_assets: float, current_liabilities: float) -> float:
    if current_liabilities == 0:
        return 0.0
    return current_assets / current_liabilities


def roe(net_income: float, shareholders_equity: float) -> float:
    """Return on Equity."""
    if shareholders_equity == 0:
        return 0.0
    return net_income / shareholders_equity


def roa(net_income: float, total_assets: float) -> float:
    """Return on Assets."""
    if total_assets == 0:
        return 0.0
    return net_income / total_assets


def days_sales_outstanding(accounts_receivable: float, revenue: float, days: int = 90) -> float:
    """DSO = AR / (Revenue / Days)."""
    if revenue == 0:
        return 0.0
    return accounts_receivable / (revenue / days)


def revenue_per_employee(revenue: float, headcount: int) -> float:
    if headcount == 0:
        return 0.0
    return revenue / headcount


def compute_growth_series(values: list[float], periods: list[str]) -> list[GrowthResult]:
    """Compute period-over-period growth for a time series."""
    results = []
    for i in range(1, len(values)):
        v_from = values[i - 1]
        v_to = values[i]
        results.append(GrowthResult(
            period_from=periods[i - 1],
            period_to=periods[i],
            value_from=v_from,
            value_to=v_to,
            absolute_change=v_to - v_from,
            percent_change=yoy_growth(v_to, v_from) * 100,
        ))
    return results


def format_currency(value: float, scale: str = "millions") -> str:
    """Format a number with appropriate scale suffix."""
    multipliers = {"units": 1, "thousands": 1_000, "millions": 1_000_000, "billions": 1_000_000_000}
    raw = value * multipliers.get(scale, 1_000_000)
    if abs(raw) >= 1_000_000_000:
        return f"${raw / 1_000_000_000:.1f}B"
    if abs(raw) >= 1_000_000:
        return f"${raw / 1_000_000:.1f}M"
    if abs(raw) >= 1_000:
        return f"${raw / 1_000:.1f}K"
    return f"${raw:.0f}"
