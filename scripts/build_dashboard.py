"""Generate serialized Lakeview (AI/BI) dashboard JSON for samples.tpch."""
import json, pathlib

OUT = pathlib.Path(__file__).resolve().parent.parent / "src" / "dashboards" / "tpch_sales.lvdash.json"
REGION_JA = "CASE r.r_name WHEN 'AFRICA' THEN 'アフリカ' WHEN 'AMERICA' THEN '米州' WHEN 'ASIA' THEN 'アジア' WHEN 'EUROPE' THEN '欧州' WHEN 'MIDDLE EAST' THEN '中東' END"
SEGMENT_JA = "CASE c.c_mktsegment WHEN 'BUILDING' THEN '建設' WHEN 'MACHINERY' THEN '機械' WHEN 'AUTOMOBILE' THEN '自動車' WHEN 'HOUSEHOLD' THEN '家庭用品' WHEN 'FURNITURE' THEN '家具' END"

DATASETS = {
    "orders": ("受注明細（顧客・地域付き）", f"""
SELECT
  o.o_orderkey AS order_key,
  o.o_orderdate AS order_date,
  o.o_totalprice AS total_price,
  CASE o.o_orderstatus WHEN 'F' THEN '出荷済' WHEN 'O' THEN '未出荷' WHEN 'P' THEN '一部出荷' END AS order_status,
  o.o_orderpriority AS order_priority,
  o.o_custkey AS customer_key,
  {SEGMENT_JA} AS segment,
  n.n_name AS nation,
  {REGION_JA} AS region
FROM samples.tpch.orders o
JOIN samples.tpch.customer c ON o.o_custkey = c.c_custkey
JOIN samples.tpch.nation n ON c.c_nationkey = n.n_nationkey
JOIN samples.tpch.region r ON n.n_regionkey = r.r_regionkey
WHERE o.o_orderdate < DATE'1998-08-01'
"""),
    "shipping": ("出荷モード別 月次実績", """
SELECT
  date_trunc('MONTH', l_shipdate) AS ship_month,
  l_shipmode AS ship_mode,
  count(*) AS line_count,
  sum(l_extendedprice * (1 - l_discount)) AS net_revenue,
  sum(CASE WHEN l_receiptdate > l_commitdate THEN 1 ELSE 0 END) AS late_count
FROM samples.tpch.lineitem
WHERE l_shipdate < DATE'1998-08-01'
GROUP BY ALL
"""),
    "top_customers": ("顧客別売上", f"""
SELECT
  c.c_name AS customer_name,
  n.n_name AS nation,
  {REGION_JA} AS region,
  {SEGMENT_JA} AS segment,
  count(*) AS order_count,
  sum(o.o_totalprice) AS revenue
FROM samples.tpch.orders o
JOIN samples.tpch.customer c ON o.o_custkey = c.c_custkey
JOIN samples.tpch.nation n ON c.c_nationkey = n.n_nationkey
JOIN samples.tpch.region r ON n.n_regionkey = r.r_regionkey
WHERE o.o_orderdate < DATE'1998-08-01'
GROUP BY ALL
ORDER BY revenue DESC
LIMIT 100
"""),
}


def field(name, expr=None):
    return {"name": name, "expression": expr or f"`{name}`"}


def chart(name, title, dataset, wtype, fields, encodings, version=3, disaggregated=False):
    return {
        "name": name,
        "queries": [{"name": "main_query", "query": {"datasetName": dataset, "fields": fields, "disaggregated": disaggregated}}],
        "spec": {"version": version, "widgetType": wtype, "encodings": encodings,
                 "frame": {"showTitle": True, "title": title}},
    }


def enc(field_name, display, scale, **extra):
    return {"fieldName": field_name, "displayName": display, "scale": {"type": scale}, **extra}


def filter_widget(name, title, wtype, column, datasets):
    queries = [{
        "name": f"filter_{name}_{ds}",
        "query": {"datasetName": ds, "fields": [field(column), field(f"{column}_associativity", "COUNT_IF(`associative_filter_predicate_group`)")], "disaggregated": False},
    } for ds in datasets]
    return {
        "name": name,
        "queries": queries,
        "spec": {"version": 2, "widgetType": wtype,
                 "encodings": {"fields": [{"fieldName": column, "displayName": title, "queryName": q["name"]} for q in queries]},
                 "frame": {"showTitle": True, "title": title}},
    }


def counter(name, title, dataset, fname, expr):
    return chart(name, title, dataset, "counter", [field(fname, expr)],
                 {"value": {"fieldName": fname, "displayName": title}}, version=2)


def pos(x, y, w, h):
    return {"x": x, "y": y, "width": w, "height": h}


layout = [
    ({"name": "title", "multilineTextboxSpec": {"lines": [
        "# 受注・売上ダッシュボード（サンプル） — Built by Devin\n",
        "**このダッシュボードは Devin（Cognition AI の AI ソフトウェアエンジニア）が Databricks API 経由で自動作成しました。**\n",
        "\n",
        "Databricks 組み込みサンプル `samples.tpch`（1992/01〜1998/07 の受注 約 750 万件）を可視化しています。",
    ]}}, pos(0, 0, 6, 2)),
    (filter_widget("f_date", "受注日", "filter-date-range-picker", "order_date", ["orders"]), pos(0, 2, 2, 1)),
    (filter_widget("f_region", "地域", "filter-multi-select", "region", ["orders", "top_customers"]), pos(2, 2, 2, 1)),
    (filter_widget("f_segment", "市場セグメント", "filter-multi-select", "segment", ["orders", "top_customers"]), pos(4, 2, 2, 1)),
    (counter("c_revenue", "総売上 (USD)", "orders", "sum(total_price)", "SUM(`total_price`)"), pos(0, 3, 2, 2)),
    (counter("c_orders", "受注件数", "orders", "count(order_key)", "COUNT(`order_key`)"), pos(2, 3, 2, 2)),
    (counter("c_customers", "購入顧客数", "orders", "countdistinct(customer_key)", "COUNT(DISTINCT `customer_key`)"), pos(4, 3, 2, 2)),
    (chart("monthly_revenue", "月次売上推移（地域別）", "orders", "line",
           [field("monthly(order_date)", 'DATE_TRUNC("MONTH", `order_date`)'), field("region"), field("sum(total_price)", "SUM(`total_price`)")],
           {"x": enc("monthly(order_date)", "受注月", "temporal"),
            "y": enc("sum(total_price)", "売上 (USD)", "quantitative"),
            "color": enc("region", "地域", "categorical")}), pos(0, 5, 6, 6)),
    (chart("revenue_by_region", "地域別売上", "orders", "bar",
           [field("region"), field("sum(total_price)", "SUM(`total_price`)")],
           {"x": enc("region", "地域", "categorical"),
            "y": enc("sum(total_price)", "売上 (USD)", "quantitative"),
            "label": {"show": True}}), pos(0, 11, 3, 6)),
    (chart("revenue_by_segment", "市場セグメント別売上", "orders", "bar",
           [field("segment"), field("sum(total_price)", "SUM(`total_price`)")],
           {"x": enc("segment", "セグメント", "categorical"),
            "y": enc("sum(total_price)", "売上 (USD)", "quantitative"),
            "label": {"show": True}}), pos(3, 11, 3, 6)),
    (chart("orders_by_priority", "受注優先度の構成", "orders", "pie",
           [field("order_priority"), field("count(order_key)", "COUNT(`order_key`)")],
           {"angle": enc("count(order_key)", "受注件数", "quantitative"),
            "color": enc("order_priority", "優先度", "categorical"),
            "label": {"show": True}}), pos(0, 17, 3, 6)),
    (chart("orders_by_status", "受注ステータス別件数", "orders", "bar",
           [field("order_status"), field("count(order_key)", "COUNT(`order_key`)")],
           {"x": enc("order_status", "ステータス", "categorical"),
            "y": enc("count(order_key)", "受注件数", "quantitative"),
            "label": {"show": True}}), pos(3, 17, 3, 6)),
    (chart("late_rate_by_mode", "出荷モード別 納期遅延率", "shipping", "bar",
           [field("ship_mode"), field("late_rate", "SUM(`late_count`) / SUM(`line_count`)")],
           {"x": enc("ship_mode", "出荷モード", "categorical"),
            "y": enc("late_rate", "遅延率", "quantitative", format={"type": "number-percent", "decimalPlaces": {"type": "exact", "places": 1}}),
            "label": {"show": True}}), pos(0, 23, 3, 7)),
    (chart("top_customers_table", "売上上位顧客", "top_customers", "table",
           [field(c) for c in ["customer_name", "nation", "region", "segment", "order_count", "revenue"]],
           {"columns": [{"fieldName": f, "displayName": d} for f, d in [
               ("customer_name", "顧客名"), ("nation", "国"), ("region", "地域"),
               ("segment", "セグメント"), ("order_count", "受注件数"), ("revenue", "売上 (USD)")]]},
           version=2, disaggregated=True), pos(3, 23, 3, 7)),
    ({"name": "footer", "multilineTextboxSpec": {"lines": [
        "---\n",
        "作成: **Devin**（Cognition AI） / データセット・SQL・レイアウト定義はすべて Devin が生成し、Lakeview API でデプロイしています。",
    ]}}, pos(0, 30, 6, 1)),
]

dashboard = {
    "datasets": [{"name": k, "displayName": v[0], "queryLines": [l + "\n" for l in v[1].strip().splitlines()]} for k, v in DATASETS.items()],
    "pages": [{"name": "overview", "displayName": "概要", "pageType": "PAGE_TYPE_CANVAS",
               "layout": [{"widget": w, "position": p} for w, p in layout]}],
}

if __name__ == "__main__":
    OUT.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n")
    print("wrote", OUT)
