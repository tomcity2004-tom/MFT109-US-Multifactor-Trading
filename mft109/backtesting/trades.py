"""Observe executed unit changes; never alter holdings, costs or portfolio returns."""

import math

import numpy as np
import pandas as pd

from mft109.trade_log import TRADE_COLUMNS, validate_trade_log


def rebalance_trades(*, execution_date, formation_date, before, after, prices,
                     transaction_cost_usd, portfolio_value_usd) -> list[dict]:
    """Log fractional adjusted-price units, including retained-name rebalancing.

    Ignore only unit changes within 32 machine epsilons of the larger holding
    (floor 1 unit). No rounding is applied to real trades. Allocate the already
    charged rebalance cost pro rata to gross stock notional, with the residual
    on the largest trade. This attribution is NOT a second fee calculation.
    Portfolio value is the post-cost execution-day closing value.
    """
    rows = []
    for ticker in sorted(set(before) | set(after)):
        pre, post = float(before.get(ticker, 0)), float(after.get(ticker, 0))
        delta = post - pre
        if abs(delta) <= 32 * np.finfo(float).eps * max(1., abs(pre), abs(post)):
            continue
        side = "BUY" if delta > 0 else "SELL"
        kind = ("NEW_ENTRY" if pre == 0 else "INCREASE") if delta > 0 else (
            "FULL_EXIT" if post == 0 else "DECREASE")
        price = float(prices[ticker])
        rows.append(dict(execution_date=execution_date, formation_date=formation_date,
                         ticker=ticker, side=side, trade_type=kind,
                         adjusted_execution_price=price, quantity=abs(delta),
                         gross_trade_value_usd=abs(delta) * price,
                         pre_trade_units=pre, post_trade_units=post,
                         transaction_cost_usd=0., portfolio_value_usd=portfolio_value_usd))
    if rows:
        total = math.fsum(row["gross_trade_value_usd"] for row in rows)
        largest = max(range(len(rows)), key=lambda i: rows[i]["gross_trade_value_usd"])
        for i, row in enumerate(rows):
            if i != largest:
                row["transaction_cost_usd"] = transaction_cost_usd * row["gross_trade_value_usd"] / total
        rows[largest]["transaction_cost_usd"] = transaction_cost_usd - math.fsum(
            row["transaction_cost_usd"] for i, row in enumerate(rows) if i != largest)
    return rows


def empty_trade_log() -> pd.DataFrame:
    """Header-only result is valid when no stock trades took place."""
    return pd.DataFrame(columns=TRADE_COLUMNS)


def reconcile_trade_log(result) -> None:
    """Check each executed rebalance against actual before/after holdings and cash."""
    from mft109.portfolio import CASH_ASSET

    validate_trade_log(result.trade_log)
    holdings = {date: table.set_index('ticker') for date, table in result.holdings.groupby('date')}
    dates = sorted(holdings)
    previous = {date: holdings[dates[i-1]] if i else None for i, date in enumerate(dates)}
    executed = result.rebalance_audit.loc[result.rebalance_audit.status.eq('executed')]
    if not result.trade_log.execution_date.isin(executed.execution_date).all():
        raise ValueError('Trade outside an executed rebalance')
    for event in executed.itertuples(index=False):
        rows = result.trade_log.loc[result.trade_log.execution_date.eq(event.execution_date)]
        before, after = previous[event.execution_date], holdings[event.execution_date]
        pre = {} if before is None else before.units.drop(CASH_ASSET).to_dict()
        post = after.units.drop(CASH_ASSET).to_dict()
        logged = rows.set_index('ticker')
        for ticker in set(pre) | set(post):
            a, b = pre.get(ticker, 0.), post.get(ticker, 0.)
            tolerance = 32 * np.finfo(float).eps * max(1., abs(a), abs(b))
            if abs(b-a) > tolerance:
                if ticker not in logged.index:
                    raise ValueError('Missing executed unit change')
                row = logged.loc[ticker]
                if (row.pre_trade_units != a or row.post_trade_units != b
                        or row.formation_date != event.formation_date):
                    raise ValueError('Trade does not reconcile to holdings/formation')
            elif ticker in logged.index:
                raise ValueError('Spurious numerical-noise trade')
        if not set(logged.index).issubset(set(pre) | set(post)):
            raise ValueError('Trade with no position change')
        if (not math.isclose(rows.transaction_cost_usd.sum(), event.transaction_cost_usd,
                             rel_tol=1e-12, abs_tol=1e-8)
                or not rows.portfolio_value_usd.eq(event.post_value_usd).all()):
            raise ValueError('Trade cost/value does not reconcile to audit')
        pre_cash = event.pre_value_usd if before is None else before.at[CASH_ASSET, 'units']
        signed = rows.gross_trade_value_usd.where(rows.side.eq('SELL'), -rows.gross_trade_value_usd)
        expected_cash = pre_cash + signed.sum() - event.transaction_cost_usd
        if not math.isclose(expected_cash, after.at[CASH_ASSET, 'units'], abs_tol=1e-7, rel_tol=1e-12):
            raise ValueError('Trade cash flow does not reconcile')
