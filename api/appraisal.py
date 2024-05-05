import pandas as pd
import requests

GOONPRAISAL_URL = "https://appraise.gnf.lt/appraisal.json"

MARKET_DICT = {
    "Jita": "jita",
    "Amarr": "amarr",
    "Dodixie": "dodixie",
    "Hek": "hek",
    "Rens": "rens",
}

UNWANTED_STRATEGIES = ["orders_universe", "ccp"]


# get prices from https://appraise.gnf.lt/
def get_appraisal(
    market: str, raw_textarea: str, user_agent: str
) -> pd.DataFrame | None:

    if market in MARKET_DICT:
        _market = MARKET_DICT[market]
    else:
        _market = market

    params = {
        "market": _market,
        "raw_textarea": raw_textarea,
        "persist": "no",
    }

    headers = {
        "User-Agent": user_agent,
    }

    response = requests.post(
        GOONPRAISAL_URL,
        params=params,
        headers=headers,
    )

    if response.status_code != 200:
        return

    data = response.json()["appraisal"]

    appraisal = pd.json_normalize(
        data,
        record_path=["items"],
        meta=["market_name"],
    )

    # "orders_universe" or "ccp" are fallbacks for when there are no matching orders in this market
    # we don't want this
    appraisal = appraisal[~(appraisal["prices.strategy"].isin(UNWANTED_STRATEGIES))]

    if market in MARKET_DICT:
        appraisal["market_name"] = market

    return appraisal
