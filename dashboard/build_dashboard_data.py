#!/usr/bin/env python3
"""
build_dashboard_data.py
------------------------
Consolida, em um unico JSON, todas as metricas usadas no dashboard final
do desafio LH Nautical: KPIs gerais, tendencia mensal, vendas por dia da
semana (Questao 5), ranking de perda por devolucao, clientes de maior
lucro, clientes fieis (Questao 4), previsao de demanda (Questao 6) e
recomendacao de produtos (Questao 7).
"""
import json
import os
from collections import defaultdict

import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

DATA_DIR = "/mnt/project"


def load():
    d = {}
    for name in [
        "orders", "order_items", "customers", "products", "product_variants",
        "categories", "returns", "return_items",
    ]:
        d[name] = pd.read_csv(os.path.join(DATA_DIR, f"{name}.csv"))
    return d


def main():
    d = load()
    orders, order_items = d["orders"], d["order_items"]
    customers, products, variants = d["customers"], d["products"], d["product_variants"]
    categories = d["categories"]
    returns, return_items = d["returns"], d["return_items"]

    orders["placed_at"] = pd.to_datetime(orders["placed_at"])
    out = {}

    # ---------------------------------------------------------------
    # 1) KPIs gerais
    # ---------------------------------------------------------------
    out["kpis"] = {
        "faturamento_total": round(float(orders["total"].sum()), 2),
        "total_pedidos": int(len(orders)),
        "total_clientes": int(customers["id"].nunique()),
        "ticket_medio_geral": round(float(orders["total"].sum() / len(orders)), 2),
        "data_min": str(orders["placed_at"].min().date()),
        "data_max": str(orders["placed_at"].max().date()),
        "faturamento_pos": round(float(orders.loc[orders["channel"] == "pos", "total"].sum()), 2),
        "faturamento_ecommerce": round(float(orders.loc[orders["channel"] == "ecommerce", "total"].sum()), 2),
        "pedidos_pos": int((orders["channel"] == "pos").sum()),
        "pedidos_ecommerce": int((orders["channel"] == "ecommerce").sum()),
    }

    # ---------------------------------------------------------------
    # 2) Faturamento mensal (tendencia) por canal
    # ---------------------------------------------------------------
    orders["mes"] = orders["placed_at"].dt.to_period("M").astype(str)
    mensal = orders.groupby(["mes", "channel"])["total"].sum().unstack(fill_value=0)
    mensal = mensal.sort_index()
    out["tendencia_mensal"] = {
        "meses": mensal.index.tolist(),
        "pos": [round(v, 2) for v in mensal.get("pos", pd.Series(dtype=float)).reindex(mensal.index, fill_value=0).tolist()],
        "ecommerce": [round(v, 2) for v in mensal.get("ecommerce", pd.Series(dtype=float)).reindex(mensal.index, fill_value=0).tolist()],
    }

    # ---------------------------------------------------------------
    # 3) Vendas medias por dia da semana (loja fisica, calendario completo) - Questao 5
    # ---------------------------------------------------------------
    data_min = orders["placed_at"].min().normalize()
    data_max = orders["placed_at"].max().normalize()
    calendario = pd.date_range(data_min, data_max, freq="D")
    vendas_pos_dia = orders.loc[orders["channel"] == "pos"].groupby(
        orders.loc[orders["channel"] == "pos", "placed_at"].dt.date
    )["total"].sum()
    vendas_pos_dia.index = pd.to_datetime(vendas_pos_dia.index)
    serie_completa = vendas_pos_dia.reindex(calendario, fill_value=0)

    dias_pt = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
               "Sexta-feira", "Sábado", "Domingo"]
    media_por_dia = serie_completa.groupby(serie_completa.index.weekday).mean()
    dias_sem_venda = (serie_completa == 0).groupby(serie_completa.index.weekday).sum()
    out["vendas_dia_semana"] = {
        "dias": dias_pt,
        "media_vendas": [round(float(media_por_dia.get(i, 0)), 2) for i in range(7)],
        "dias_sem_venda": [int(dias_sem_venda.get(i, 0)) for i in range(7)],
    }

    # ---------------------------------------------------------------
    # 4) Top categorias por faturamento e por quantidade
    # ---------------------------------------------------------------
    oi = order_items.merge(variants[["id", "product_id"]], left_on="product_variant_id", right_on="id", suffixes=("", "_v"))
    oi = oi.merge(products[["id", "category_id"]], left_on="product_id", right_on="id", suffixes=("", "_p"))
    oi = oi.merge(categories[["id", "name"]], left_on="category_id", right_on="id", suffixes=("", "_c"))
    cat_agg = oi.groupby("name")[["line_total", "quantity"]].sum().sort_values("line_total", ascending=False)
    out["top_categorias"] = {
        "nomes": cat_agg.index.tolist(),
        "faturamento": [round(v, 2) for v in cat_agg["line_total"].tolist()],
        "quantidade": [int(v) for v in cat_agg["quantity"].tolist()],
    }

    # ---------------------------------------------------------------
    # 5) Ranking de prejuizo por produto (devolucoes) - achado adicional
    # ---------------------------------------------------------------
    ri = return_items.merge(order_items[["id", "product_variant_id"]], left_on="order_item_id", right_on="id", suffixes=("", "_oi"))
    ri = ri.merge(variants[["id", "product_id"]], left_on="product_variant_id", right_on="id", suffixes=("", "_v"))
    ri = ri.merge(products[["id", "name"]], left_on="product_id", right_on="id", suffixes=("", "_p"))
    ri["prejuizo"] = ri["quantity"] * ri["unit_refund_amount"]
    prejuizo_produto = ri.groupby("name")["prejuizo"].sum().sort_values(ascending=False).head(10)
    out["prejuizo_por_produto"] = {
        "produtos": prejuizo_produto.index.tolist(),
        "valores": [round(v, 2) for v in prejuizo_produto.tolist()],
    }

    # ---------------------------------------------------------------
    # 6) Clientes com maior lucro acumulado (achado adicional)
    #    lucro_item = (unit_price - cost_price) * quantity
    #    (cost_price atual da variante, usado como aproximacao - nao
    #    ha custo historico registrado por pedido)
    # ---------------------------------------------------------------
    oi_cost = order_items.merge(orders[["id", "customer_id"]], left_on="order_id", right_on="id", suffixes=("", "_o"))
    oi_cost = oi_cost.merge(variants[["id", "cost_price"]], left_on="product_variant_id", right_on="id", suffixes=("", "_v"))
    oi_cost["lucro"] = (oi_cost["unit_price"] - oi_cost["cost_price"]) * oi_cost["quantity"]
    lucro_cliente = oi_cost.groupby("customer_id")["lucro"].sum().sort_values(ascending=False).head(10)
    lucro_cliente_named = lucro_cliente.reset_index().merge(
        customers[["id", "legal_name"]], left_on="customer_id", right_on="id"
    )
    out["clientes_maior_lucro"] = {
        "customer_id": lucro_cliente_named["customer_id"].tolist(),
        "nomes": lucro_cliente_named["legal_name"].tolist(),
        "lucro": [round(v, 2) for v in lucro_cliente_named["lucro"].tolist()],
    }

    # ---------------------------------------------------------------
    # 7) Clientes fieis - Questao 4
    # ---------------------------------------------------------------
    customer_orders = orders.groupby("customer_id").agg(
        faturamento_total=("total", "sum"), frequencia=("id", "count")
    )
    customer_orders["ticket_medio"] = customer_orders["faturamento_total"] / customer_orders["frequencia"]
    diversidade = oi.merge(orders[["id", "customer_id"]], left_on="order_id", right_on="id", suffixes=("", "_o"))
    diversidade = diversidade.groupby("customer_id")["category_id"].nunique()
    metrics = customer_orders.join(diversidade.rename("diversidade_categorias"))
    elite = metrics[metrics["diversidade_categorias"] >= 13].reset_index()
    elite = elite.sort_values(["ticket_medio", "customer_id"], ascending=[False, True]).head(10)
    out["clientes_fieis"] = {
        "customer_id": elite["customer_id"].tolist(),
        "ticket_medio": [round(v, 2) for v in elite["ticket_medio"].tolist()],
        "faturamento_total": [round(v, 2) for v in elite["faturamento_total"].tolist()],
        "diversidade": elite["diversidade_categorias"].tolist(),
    }

    # ---------------------------------------------------------------
    # 8) Previsao de demanda - Questao 6 (Bussola de Bordo 702)
    # ---------------------------------------------------------------
    produto_nome = "Bússola de Bordo 702"
    produto_ids = products.loc[products["name"] == produto_nome, "id"].tolist()
    var_ids = variants.loc[variants["product_id"].isin(produto_ids), "id"].tolist()
    itens_bussola = order_items[order_items["product_variant_id"].isin(var_ids)].merge(
        orders[["id", "placed_at"]], left_on="order_id", right_on="id", suffixes=("", "_o")
    )
    itens_bussola["mes"] = itens_bussola["placed_at"].dt.to_period("M").astype(str)
    vendas_mensais = itens_bussola.groupby("mes")["quantity"].sum()
    idx_completo = pd.period_range(start=vendas_mensais.index.min(), end="2026-03", freq="M").astype(str)
    vendas_mensais = vendas_mensais.reindex(idx_completo, fill_value=0)

    meses_teste = ["2026-01", "2026-02", "2026-03"]
    previsoes = {}
    for mes in meses_teste:
        p = pd.Period(mes, freq="M")
        anteriores = [str(p - i) for i in range(1, 4)]
        previsoes[mes] = float(vendas_mensais.reindex(anteriores).mean())

    hist_meses = [m for m in vendas_mensais.index if m >= "2025-01"]
    out["previsao_demanda"] = {
        "meses_historico": hist_meses,
        "vendas_historico": [int(vendas_mensais[m]) for m in hist_meses],
        "meses_previsao": meses_teste,
        "previsao": [round(previsoes[m], 2) for m in meses_teste],
        "real_previsao": [int(vendas_mensais[m]) for m in meses_teste],
        "mae": round(float(np.mean([abs(previsoes[m] - vendas_mensais[m]) for m in meses_teste])), 2),
        "soma_previsao_arredondada": int(round(sum(previsoes.values()))),
    }

    # ---------------------------------------------------------------
    # 9) Recomendacao - Questao 7 (Motor de Popa 1949)
    # ---------------------------------------------------------------
    itens_rec = order_items.merge(variants[["id", "product_id"]], left_on="product_variant_id", right_on="id", suffixes=("", "_v"))
    itens_rec = itens_rec.merge(orders[["id", "customer_id"]], left_on="order_id", right_on="id", suffixes=("", "_o"))
    pares = itens_rec[["customer_id", "product_id"]].drop_duplicates()
    pares["comprou"] = 1
    matriz = pares.pivot_table(index="customer_id", columns="product_id", values="comprou", fill_value=0)
    sim = cosine_similarity(matriz.T.values)
    sim_df = pd.DataFrame(sim, index=matriz.columns, columns=matriz.columns)

    ref_id = products.loc[products["name"] == "Motor de Popa 1949", "id"].iloc[0]
    similares = sim_df.loc[ref_id].drop(index=ref_id).sort_values(ascending=False).head(5)
    similares_named = similares.reset_index()
    similares_named.columns = ["product_id", "similaridade"]
    similares_named = similares_named.merge(products[["id", "name"]], left_on="product_id", right_on="id")
    out["recomendacao"] = {
        "produto_referencia": "Motor de Popa 1949",
        "produtos": similares_named["name"].tolist(),
        "similaridade": [round(v, 4) for v in similares_named["similaridade"].tolist()],
    }

    with open("/mnt/user-data/outputs/dashboard/dashboard_data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("JSON gerado com sucesso.")
    print(json.dumps(out["kpis"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()