"""受注・売上ダッシュボード（Streamlit 版）— Built by Devin."""
import os
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config

st.set_page_config(page_title="[Devin 作成] 受注・売上ダッシュボード", layout="wide")

WAREHOUSE_ID = os.environ["DATABRICKS_WAREHOUSE_ID"]
REGIONS = {"AFRICA": "アフリカ", "AMERICA": "米州", "ASIA": "アジア", "EUROPE": "欧州", "MIDDLE EAST": "中東"}
SEGMENTS = {"BUILDING": "建設", "MACHINERY": "機械", "AUTOMOBILE": "自動車", "HOUSEHOLD": "家庭用品", "FURNITURE": "家具"}
STATUSES = {"F": "出荷済", "O": "未出荷", "P": "一部出荷"}
MIN_DATE, MAX_DATE = date(1992, 1, 1), date(1998, 7, 31)


def case(column, mapping):
    whens = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in mapping.items())
    return f"CASE {column} {whens} END"


ORDERS = f"""
SELECT o.o_orderkey, o.o_orderdate, o.o_totalprice, o.o_orderpriority, o.o_custkey, c.c_name, n.n_name,
       {case('o.o_orderstatus', STATUSES)} AS status,
       {case('c.c_mktsegment', SEGMENTS)} AS segment,
       {case('r.r_name', REGIONS)} AS region
FROM samples.tpch.orders o
JOIN samples.tpch.customer c ON o.o_custkey = c.c_custkey
JOIN samples.tpch.nation n ON c.c_nationkey = n.n_nationkey
JOIN samples.tpch.region r ON n.n_regionkey = r.r_regionkey
WHERE o.o_orderdate BETWEEN :start AND :end
  AND r.r_name IN ({{regions}})
  AND c.c_mktsegment IN ({{segments}})
"""


@st.cache_resource
def connection():
    cfg = Config()
    return sql.connect(server_hostname=cfg.host, http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
                       credentials_provider=lambda: cfg.authenticate)


@st.cache_data(ttl=600, show_spinner=False)
def query(statement: str, params: tuple) -> pd.DataFrame:
    with connection().cursor() as cur:
        cur.execute(statement, dict(params))
        return cur.fetchall_arrow().to_pandas()


def in_list(keys):
    return ", ".join(f"'{k}'" for k in keys)


st.title("受注・売上ダッシュボード（Streamlit 版）")
st.info("このアプリは **Devin（Cognition AI の AI ソフトウェアエンジニア）** が作成しました。"
        "Databricks SQL Warehouse に直接クエリし、`samples.tpch` を可視化しています。")

with st.sidebar:
    st.header("フィルタ")
    period = st.date_input("受注日", (MIN_DATE, MAX_DATE), min_value=MIN_DATE, max_value=MAX_DATE)
    regions = st.multiselect("地域", list(REGIONS), default=list(REGIONS), format_func=REGIONS.get)
    segments = st.multiselect("市場セグメント", list(SEGMENTS), default=list(SEGMENTS), format_func=SEGMENTS.get)
    st.caption("Built by Devin")

if len(period) != 2 or not regions or not segments:
    st.warning("受注日の期間・地域・セグメントを 1 つ以上選択してください。")
    st.stop()

base = ORDERS.format(regions=in_list(regions), segments=in_list(segments))
params = (("start", period[0]), ("end", period[1]))


def agg(select: str, tail: str = "") -> pd.DataFrame:
    return query(f"SELECT {select} FROM ({base}) {tail}", params)


with st.spinner("Databricks からデータを取得中..."):
    kpi = agg("SUM(o_totalprice) AS revenue, COUNT(*) AS orders, COUNT(DISTINCT o_custkey) AS customers")
    monthly = agg("DATE_TRUNC('MONTH', o_orderdate) AS month, region, SUM(o_totalprice) AS revenue", "GROUP BY ALL ORDER BY month")
    by_region = agg("region, SUM(o_totalprice) AS revenue", "GROUP BY ALL ORDER BY revenue DESC")
    by_segment = agg("segment, SUM(o_totalprice) AS revenue", "GROUP BY ALL ORDER BY revenue DESC")
    by_priority = agg("o_orderpriority AS priority, COUNT(*) AS orders", "GROUP BY ALL ORDER BY priority")
    by_status = agg("status, COUNT(*) AS orders", "GROUP BY ALL ORDER BY orders DESC")
    top = agg("c_name AS `顧客名`, n_name AS `国`, region AS `地域`, segment AS `セグメント`, COUNT(*) AS `受注件数`, SUM(o_totalprice) AS `売上 (USD)`",
              "GROUP BY ALL ORDER BY `売上 (USD)` DESC LIMIT 20")
    shipping = query("""
        SELECT l_shipmode AS ship_mode, AVG(CASE WHEN l_receiptdate > l_commitdate THEN 1.0 ELSE 0.0 END) AS late_rate
        FROM samples.tpch.lineitem WHERE l_shipdate BETWEEN :start AND :end GROUP BY ALL ORDER BY late_rate DESC""", params)

k = kpi.iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("総売上 (USD)", f"${float(k.revenue or 0) / 1e9:,.1f}B")
c2.metric("受注件数", f"{int(k.orders):,}")
c3.metric("購入顧客数", f"{int(k.customers):,}")

st.plotly_chart(px.line(monthly, x="month", y="revenue", color="region", title="月次売上推移（地域別）",
                        labels={"month": "受注月", "revenue": "売上 (USD)", "region": "地域"}), use_container_width=True)

left, right = st.columns(2)
left.plotly_chart(px.bar(by_region, x="region", y="revenue", title="地域別売上", text_auto=".3s",
                         labels={"region": "地域", "revenue": "売上 (USD)"}), use_container_width=True)
right.plotly_chart(px.bar(by_segment, x="segment", y="revenue", title="市場セグメント別売上", text_auto=".3s",
                          labels={"segment": "セグメント", "revenue": "売上 (USD)"}), use_container_width=True)
left.plotly_chart(px.pie(by_priority, names="priority", values="orders", title="受注優先度の構成", hole=0.4),
                  use_container_width=True)
right.plotly_chart(px.bar(by_status, x="status", y="orders", title="受注ステータス別件数", text_auto=".3s",
                          labels={"status": "ステータス", "orders": "受注件数"}), use_container_width=True)
fig = px.bar(shipping, x="ship_mode", y="late_rate", title="出荷モード別 納期遅延率", text_auto=".1%",
             labels={"ship_mode": "出荷モード", "late_rate": "遅延率"})
fig.update_yaxes(tickformat=".0%")
left.plotly_chart(fig, use_container_width=True)
right.subheader("売上上位顧客 (Top 20)")
right.dataframe(top, hide_index=True, use_container_width=True, column_config={"売上 (USD)": st.column_config.NumberColumn(format="$%.0f")})

st.divider()
st.caption("作成: Devin（Cognition AI） / Streamlit + Databricks SQL Connector / データ: samples.tpch")
