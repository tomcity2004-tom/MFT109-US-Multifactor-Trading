"""Display and download engine-derived trades; filters never rerun the strategy."""

from pathlib import Path
import sys

_REPOSITORY_ROOT = str(Path(__file__).resolve().parents[2])
if _REPOSITORY_ROOT not in sys.path:
    sys.path.insert(0, _REPOSITORY_ROOT)

import streamlit as st

from dashboard.components.formatting import number
from dashboard.components.i18n import t
from dashboard.components.layout import configure
from dashboard.components.loaders import cached_trades
from mft109.visualization.dashboard_data import DashboardDataError
from mft109.visualization.trade_history import filter_trades, trade_signature


COLUMN_LABELS = {
    'execution_date': 'Execution date', 'formation_date': 'Formation date',
    'ticker': 'Ticker', 'side': 'Side', 'trade_type': 'Trade type',
    'adjusted_execution_price': 'Adjusted execution price (USD)', 'quantity': 'Quantity',
    'gross_trade_value_usd': 'Gross trade value (USD)', 'pre_trade_units': 'Pre-trade units',
    'post_trade_units': 'Post-trade units', 'transaction_cost_usd': 'Allocated cost (USD)',
    'portfolio_value_usd': 'Portfolio value (USD)',
}


def main() -> None:
    language = configure('Trade History')
    st.caption(t('Academic simulated trades at adjusted close, not actual market fills. Fractional units are adjusted-price units.', language))
    st.caption(t('Costs allocate the already charged rebalance fee by gross trade value; they are not additional charges. Portfolio value is after costs.', language))
    try:
        trades = cached_trades(trade_signature())
    except DashboardDataError as error:
        st.warning(t('Trade history is unavailable. Restore the tracked trade artifacts or run the offline official export with approved price caches.', language))
        with st.expander(t('Technical diagnostic (original message)', language)):
            st.code(str(error))
        return
    filtered = trades
    if not trades.empty:
        start, end = trades.execution_date.min().date(), trades.execution_date.max().date()
        dates = st.date_input(t('Execution date range', language), value=(start, end),
                              min_value=start, max_value=end, key='trade_date_range')
        tickers = st.multiselect(t('Ticker filter (empty = all)', language), sorted(trades.ticker.unique()),
                                key='trade_tickers')
        sides = st.multiselect(t('Side filter (empty = all)', language), ['BUY', 'SELL'],
                              format_func=lambda value: t(value, language), key='trade_sides')
        if len(dates) != 2:
            st.info(t('Choose both a start and an end date.', language))
            return
        filtered = filter_trades(trades, start=dates[0], end=dates[1], tickers=tickers, sides=sides)
    counts = st.columns(4)
    counts[0].metric(t('Trade count', language), len(filtered))
    counts[1].metric(t('Buy count', language), int(filtered.side.eq('BUY').sum()))
    counts[2].metric(t('Sell count', language), int(filtered.side.eq('SELL').sum()))
    counts[3].metric(t('Total gross trade value', language), number(filtered.gross_trade_value_usd.sum(), 'currency'))
    if filtered.empty:
        st.info(t('No trades match the current selection.', language))
    display = filtered.copy()
    for column in ('side', 'trade_type'):
        display[column] = display[column].map(lambda value: t(value, language))
    labels = {key: t(value, language) for key, value in COLUMN_LABELS.items()}
    config = {labels[c]: st.column_config.NumberColumn(format='%.6f') for c in
              ('quantity', 'pre_trade_units', 'post_trade_units', 'adjusted_execution_price')}
    config.update({labels[c]: st.column_config.NumberColumn(format='$%.2f') for c in
                   ('gross_trade_value_usd', 'transaction_cost_usd', 'portfolio_value_usd')})
    config.update({labels[c]: st.column_config.DateColumn(format='YYYY-MM-DD') for c in
                   ('execution_date', 'formation_date')})
    st.dataframe(display.rename(columns=labels), column_config=config, hide_index=True, width='stretch')
    st.download_button(t('Download filtered trades CSV', language),
                       data=filtered.to_csv(index=False, date_format='%Y-%m-%d').encode('utf-8'),
                       file_name='trade_log.csv', mime='text/csv', key='download_trade_log')
    st.caption(t('Summary and CSV reflect the filters. CSV keeps original field names, identifiers and full numeric precision.', language))


if __name__ == '__main__':
    main()
