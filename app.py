import streamlit as st
import pandas as pd
import numpy as np

from api import appraisal


USER_AGENT = "https://github.com/thebravyone/bravy-broker"

MARKETS = [
    "K7D-II",
    "P-ZMZV",
    "1DQ1-A",
    "O4T-Z5",
    "F7C-H0",
    "Jita",
    "Amarr",
    "Dodixie",
    "Hek",
    "Rens",
]

DEFAULT_MARKETS = [
    "K7D-II",
    "P-ZMZV",
    "1DQ1-A",
    "Jita",
]

MAIN_HUB = "Jita"  # Used for price comparison


def type_id_to_icon_url(type_ids: pd.Series) -> pd.Series:
    return "https://images.evetech.net/types/" + type_ids.astype(str) + "/icon/?size=32"


def format_with_units(num):
    units = [
        "",
        "k",
        "m",
        "b",
        "t",
    ]  # Define units (K for thousands, M for millions, etc.)
    for unit in units:
        if abs(num) < 1000:
            return "{:.2f}{} ISK".format(num, unit)
        num /= 1000


@st.cache_data(ttl=3600, show_spinner=False)
def load_data(market_list: list[str], raw_textarea: str) -> pd.DataFrame | None:
    appraisals = []
    _market_list = market_list.copy()

    if MAIN_HUB not in market_list:
        _market_list.append(MAIN_HUB)

    for market in _market_list:
        appraisals.append(appraisal.get_appraisal(market, raw_textarea, USER_AGENT))

    if appraisals:
        return pd.concat(appraisals)

    return None


def parse_and_filter_data(data: pd.DataFrame, market_list: list[str]):
    req_cols = [
        "typeName",
        "typeID",
        "typeVolume",
        "quantity",
        "prices.sell.min",
        "market_name",
    ]

    parsed_data = data[req_cols].copy()

    parsed_data.rename(
        inplace=True,
        columns={
            "typeName": "type_name",
            "typeID": "type_id",
            "typeVolume": "type_volume",
            "quantity": "quantity",
            "prices.sell.min": "sell_price",
            "market_name": "market_name",
        },
    )

    jita_data = parsed_data[parsed_data["market_name"] == MAIN_HUB].copy()

    # Filters only interested hubs
    filtered_data = parsed_data[parsed_data["market_name"].isin(market_list)]

    # Filters only best prices
    filtered_data["min_sell_price"] = filtered_data.groupby("type_id")[
        "sell_price"
    ].transform("min")

    filtered_data = filtered_data[
        filtered_data["sell_price"] == filtered_data["min_sell_price"]
    ]

    # Filters hubs based on priority order from MARKETS list
    filtered_data = filtered_data.sort_values(
        by="market_name",
        key=lambda x: x.map({market: i for i, market in enumerate(MARKETS)}),
    )

    filtered_data = filtered_data.drop_duplicates(subset="type_id", keep="first")

    # Create Icons
    filtered_data["icon"] = type_id_to_icon_url(filtered_data["type_id"])

    # Create totals per item
    filtered_data["value"] = filtered_data["sell_price"] * filtered_data["quantity"]
    filtered_data["volume"] = filtered_data["type_volume"] * filtered_data["quantity"]

    jita_data["value"] = jita_data["sell_price"] * jita_data["quantity"]
    jita_data["volume"] = jita_data["type_volume"] * jita_data["quantity"]

    # Simplifies columns
    jita_data = jita_data[["type_id", "sell_price", "value"]]
    del filtered_data["min_sell_price"]

    # Join Jita Price
    merged_data = pd.merge(
        filtered_data, jita_data, on="type_id", how="left", suffixes=["", "_jita"]
    )

    merged_data["var_sell_price"] = np.where(
        merged_data["sell_price_jita"] > 0,
        merged_data["sell_price"] / merged_data["sell_price_jita"] - 1,
        0,
    )

    merged_data["var_sell_price_val"] = merged_data["value"] - merged_data["value_jita"]

    return merged_data


st.set_page_config(
    page_title="Bravy Broker SA",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

market_list = []
raw_textarea = ""

total_value = 0
saved_percentage = 0

# Sidebar
with st.sidebar:
    st.title("🏦 Bravy Broker SA")
    st.markdown(
        "Nós te ajudamos a encontrar os :green[**melhores preços**] 💸 entre :red[**Jita**] e as :red[**hubs null-sec**] próximas à :blue[**Brave Collective**]."
    )

    with st.form("appraisal_form", border=False):
        raw_textarea = st.text_area("Cole aqui o que deseja comprar:")
        market_list = st.multiselect(
            label="Selecione os Market Hubs",
            placeholder="Escolha ao menos uma Hub",
            options=MARKETS,
            default=DEFAULT_MARKETS,
            key="selected_markets",
        )

        st.form_submit_button("Submeter", use_container_width=True)

# Top Bar
metrics_col, chart_col = st.columns([0.2, 0.8])

# Render Data
if raw_textarea != "":
    with st.spinner("Avaliando Preços..."):
        data = load_data(market_list, raw_textarea)

    if isinstance(data, pd.DataFrame) and not data.empty:
        parsed_data = parse_and_filter_data(data, market_list)

        total_value = parsed_data["value"].sum()
        total_value_jita = parsed_data["value_jita"].sum()

        if total_value_jita > 0:
            saved_percentage = total_value / total_value_jita - 1
        else:
            saved_percentage = 0

        metrics_col.metric(
            label="Valor Total",
            value=format_with_units(total_value),
            delta="{:,.1%} vs Jita".format(saved_percentage),
            delta_color="inverse" if saved_percentage < 0 else "off",
        )

        hub_data = parsed_data.groupby("market_name", as_index=False).agg(
            {"volume": "sum", "value": "sum"}
        )

        formatted_data = parsed_data.style.format(
            {
                "sell_price": lambda x: "{:,.2f} ISK".format(x),
                "type_volume": lambda x: "{:,.2f} m³".format(x),
                "value": lambda x: "{:,.2f} ISK".format(x),
                "volume": lambda x: "{:,.2f} m³".format(x),
                "var_sell_price": lambda x: "{:,.1%}".format(x),
                "var_sell_price_val": lambda x: "{:,.2f} ISK".format(x),
            },
            thousands=".",
            decimal=",",
        )

        hub_data = hub_data.style.format(
            {
                "value": lambda x: "{:,.2f} ISK".format(x),
                "volume": lambda x: "{:,.2f} m³".format(x),
            },
            thousands=".",
            decimal=",",
        )

        st.dataframe(
            formatted_data,
            hide_index=True,
            column_order=[
                "icon",
                "type_name",
                "quantity",
                "market_name",
                "type_volume",
                "sell_price",
                "volume",
                "value",
                "var_sell_price",
                "var_sell_price_val",
            ],
            column_config={
                "icon": st.column_config.ImageColumn(label="Ícone"),
                "type_name": "Item",
                "quantity": "Quantidade",
                "market_name": "Market Hub",
                "sell_price": "Preço Unitário",
                "type_volume": "Volume Unitário",
                "value": "Preço Total",
                "volume": "Volume Total",
                "var_sell_price": "Preço vs Jita [%]",
                "var_sell_price_val": "Preço vs Jita [ISK]",
            },
        )

        st.dataframe(
            hub_data,
            hide_index=True,
            column_config={
                "market_name": "Market Hub",
                "value": "Valor Total",
                "volume": "Volume Total",
            },
        )
    else:
        st.markdown(
            """
            ### ⚠️ Não há nenhum dado para mostrar.

            1) Verifique o texto colado e garanta que não há nenhum erro de digitação. De preferência, copie e cole diretamente do EVE.
            2) É possível que não haja nenhuma ordem nos mercados escolhidos que atenda aos filtros ou itens informados.
            """
        )

else:
    st.markdown("Comece preenchendo as informações na barra ao lado.")
