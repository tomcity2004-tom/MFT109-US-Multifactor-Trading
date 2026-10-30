"""Consistent bilingual framing; language is durable session state, not model state."""

import streamlit as st
from mft109.config import BASELINE
from dashboard.components.i18n import LANGUAGES, t


def _save_language() -> None:
    st.session_state["dashboard_language"] = next(code for code, label in LANGUAGES.items() if label == st.session_state["_language_choice"])


def language_selector() -> str:
    language = st.session_state.get("dashboard_language", "en")
    # Separate durable state from widget state, which Streamlit may clean on navigation.
    st.session_state["_language_choice"] = LANGUAGES[language]
    st.sidebar.selectbox("Language / 語言", list(LANGUAGES.values()),
                         key="_language_choice", on_change=_save_language)
    return language


def configure(title: str) -> str:
    language = st.session_state.get("dashboard_language", "en")
    st.set_page_config(page_title=t("MFT109 Multi-Factor Trading", language), layout="wide")
    language = language_selector()
    st.sidebar.title("MFT109")
    st.sidebar.caption(t("Financial Algorithmic Trading", language))
    st.sidebar.markdown(t("**U.S. multi-factor stock selection**\n\n2016–2025 · SPY benchmark\n\n4 factors · Top 20 · Monthly", language))
    st.sidebar.divider()
    st.sidebar.caption(t("Fixed current S&P 500 snapshot. Survivorship bias applies. Academic research; not investment advice.", language))
    st.title(t(title, language))
    st.caption(t("S&P 500 Multi-Factor Stock Selection Backtest · 2016–2025", language))
    return language


def limitations(language: str = "en") -> None:
    st.subheader(t("Methodology and limitations", language))
    messages = [
        t("A fixed snapshot of **current S&P 500 constituents** is used throughout history, introducing **survivorship bias**.", language),
        t("Yahoo Finance historical data may be revised; this dashboard uses the reviewed data version.", language),
        t("Next-session adjusted-close execution is a simplified academic convention.", language),
        t("Transaction costs are {bps} bps × actual cash-inclusive turnover.", language, bps=f"{BASELINE.transaction_cost_rate * 10000:g}"),
        t("Historical results and sensitivity comparisons are not evidence of future superiority.", language),
        t("This academic backtest is **not investment advice**.", language),
    ]
    st.markdown("\n".join(f"- {message}" for message in messages))


def _save_choice(key: str, identifiers: dict[str, str]) -> None:
    st.session_state[f"choice_{key}"] = identifiers[st.session_state[key]]


def translated_choice(label: str, choices: dict[str, str], key: str, language: str) -> str:
    """Preserve a display choice's identifier when its translated label changes."""
    selected = st.session_state.get(f"choice_{key}", next(iter(choices)))
    labels = {identifier: t(text, language) for identifier, text in choices.items()}
    identifiers = {text: identifier for identifier, text in labels.items()}
    st.session_state[key] = labels[selected]
    value = st.selectbox(t(label, language), list(identifiers), key=key,
                         on_change=_save_choice, args=(key, identifiers))
    return identifiers[value]
