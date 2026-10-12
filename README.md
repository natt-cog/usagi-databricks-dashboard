# usagi-databricks-dashboard

> このリポジトリは **Devin（Cognition AI の AI ソフトウェアエンジニア）** が作成しました。

Databricks の組み込みサンプルデータ `samples.tpch`（1992/01〜1998/07 の受注 約 750 万件）を可視化するサンプルです。
[Databricks Asset Bundles](https://docs.databricks.com/aws/ja/dev-tools/bundles/) で、次の 2 つをコードとして管理・デプロイします。

| リソース | 種類 | 内容 |
| --- | --- | --- |
| `tpch_sales` | AI/BI ダッシュボード（Lakeview） | KPI・月次推移・地域/セグメント別売上・出荷遅延率・上位顧客 |
| `tpch_streamlit` | Databricks Apps（Streamlit） | 同じ内容を SQL Warehouse に直接クエリして描画する Python アプリ |

## 構成

```
databricks.yml                      # バンドル定義（ターゲット・変数）
resources/
  tpch_sales.dashboard.yml          # AI/BI ダッシュボード
  tpch_streamlit.app.yml            # Databricks Apps
src/
  dashboards/tpch_sales.lvdash.json # ダッシュボード定義（scripts/build_dashboard.py で生成）
  app/                              # Streamlit アプリ（app.py / app.yaml / requirements.txt）
scripts/build_dashboard.py          # ダッシュボード定義 JSON の生成スクリプト
```

## 前提

- [Databricks CLI](https://docs.databricks.com/aws/ja/dev-tools/cli/install) （v1.20.0 で動作確認）
- 環境変数 `DATABRICKS_HOST`（ワークスペース URL）と `DATABRICKS_TOKEN`（PAT）
- ワークスペースに SQL Warehouse「Serverless Starter Warehouse」があること（別名の場合は `databricks.yml` の `warehouse_id` を変更）

## デプロイ

```bash
databricks bundle validate
databricks bundle deploy          # ダッシュボードとアプリを作成・更新（ダッシュボードは公開まで実行）
databricks bundle run tpch_streamlit   # アプリのソースをデプロイして起動
databricks bundle summary         # URL を確認
```

## ダッシュボードの変更

`scripts/build_dashboard.py` を編集して JSON を再生成し、デプロイします。

```bash
python3 scripts/build_dashboard.py
databricks bundle deploy
```

## Streamlit アプリをローカルで動かす

```bash
pip install streamlit -r src/app/requirements.txt
export DATABRICKS_WAREHOUSE_ID=<SQL Warehouse ID>
cd src/app && python3 -m streamlit run app.py
```

## 注意

- `samples.tpch` は均等分布のベンチマークデータのため、地域別・セグメント別のグラフはほぼ同じ値になります。
- Databricks Apps は起動中コンピュート課金が発生します。不要なときは `databricks apps stop devin-tpch-dashboard` で停止してください。
