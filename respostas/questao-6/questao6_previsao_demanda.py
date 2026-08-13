#!/usr/bin/env python3
"""
questao6_previsao_demanda.py
------------------------------
Autor: Time de Dados - LH Nautical
Objetivo (Questao 6): construir um dataset unificado de vendas mensais
para o produto "Bussola de Bordo 702" e um modelo baseline de previsao
de demanda (media movel dos ultimos 3 meses), avaliando o desempenho no
primeiro trimestre de 2026 com a metrica MAE - Mean Absolute Error.


Uso:
    python3 questao6_previsao_demanda.py --data-dir lh_nautical_csv
"""

import argparse
import os
import pandas as pd


PRODUTO_ALVO = "Bússola de Bordo 702"
DATA_CORTE_TREINO = "2025-12"     # ultimo mes do periodo de treino (AAAA-MM)
MESES_TESTE = ["2026-01", "2026-02", "2026-03"]


# --------------------------------------------------------------------------
# PASSO 1: dataset unificado
# --------------------------------------------------------------------------

def build_unified_dataset(data_dir):
    """Junta products -> product_variants -> order_items -> orders para
    obter, linha a linha, cada item vendido do produto alvo com sua data
    de pedido e quantidade. Essa e' a base para a agregacao mensal."""

    products = pd.read_csv(os.path.join(data_dir, "products.csv"))
    variants = pd.read_csv(os.path.join(data_dir, "product_variants.csv"))
    orders = pd.read_csv(os.path.join(data_dir, "orders.csv"))
    order_items = pd.read_csv(os.path.join(data_dir, "order_items.csv"))

    # --- filtro do produto alvo -------------------------------------------
    # Filtrei por NOME (nao por ID) porque foi assim que o enunciado
    # identificou o produto: "considere apenas o produto: 'Bussola de
    # Bordo 702'". Ao filtrar por nome descobri um achado de qualidade
    # de dados importante: existem DOIS product_id distintos com esse
    # EXATO nome no catalogo (ids 74 e 240) - aparentemente uma colisao
    # do gerador sintetico de nomes ("Bussola de Bordo" + numero
    # aleatorio), e nao um erro de cadastro duplicado proposital. Como o
    # enunciado se refere ao produto pelo NOME comercial, mantive as
    # duas ocorrencias agregadas como "o produto Bussola de Bordo 702" -
    # e deixei isso documentado aqui e na resposta da Questao 6.3 para
    # o Gabriel decidir se prefere tratar como itens distintos.
    produto_ids = products.loc[products["name"] == PRODUTO_ALVO, "id"].tolist()
    if not produto_ids:
        raise ValueError(f"Produto '{PRODUTO_ALVO}' nao encontrado em products.csv")

    variant_ids = variants.loc[variants["product_id"].isin(produto_ids), "id"].tolist()

    # --- join: order_items (do produto alvo) + orders (para a data) -------
    itens_produto = order_items[order_items["product_variant_id"].isin(variant_ids)].copy()
    itens_produto = itens_produto.merge(
        orders[["id", "placed_at"]],
        left_on="order_id", right_on="id", suffixes=("_item", "_order"),
    )

    itens_produto["placed_at"] = pd.to_datetime(itens_produto["placed_at"])
    itens_produto["mes"] = itens_produto["placed_at"].dt.to_period("M").astype(str)

    return itens_produto, produto_ids


# --------------------------------------------------------------------------
# PASSO 2: serie mensal completa (preenchendo meses sem venda com 0)
# --------------------------------------------------------------------------

def build_monthly_series(itens_produto):
    """Agrega SUM(quantity) por mes e garante que TODO mes do periodo
    apareca na serie (mesmo sem venda = 0) - sem isso, a media movel de
    3 meses ficaria errada em qualquer janela que atravesse um mes sem
    registro (o mesmo problema de fundo da Questao 5, agora em base
    mensal)."""
    vendas_mensais = (
        itens_produto.groupby("mes")["quantity"].sum().sort_index()
    )

    # calendario mensal completo: do primeiro mes com dado ate o fim do
    # periodo de teste (2026-03), para nao perder nenhum mes "buraco".
    idx_completo = pd.period_range(
        start=vendas_mensais.index.min(), end="2026-03", freq="M"
    ).astype(str)
    vendas_mensais = vendas_mensais.reindex(idx_completo, fill_value=0)
    vendas_mensais.index.name = "mes"
    vendas_mensais.name = "quantidade_vendida"
    return vendas_mensais


# --------------------------------------------------------------------------
# PASSO 3: baseline - media movel dos ultimos 3 meses (walk-forward)
# --------------------------------------------------------------------------

def forecast_moving_average(vendas_mensais, meses_para_prever, janela=3):
    """Para cada mes a prever, calcula a media dos 'janela' meses
    IMEDIATAMENTE ANTERIORES, usando sempre valores REAIS (nunca uma
    previsao proapria) - e' assim que se evita vazamento de dado (data
    leakage) e o efeito cascata de erro se propagando entre meses.

    Ex.: para prever Fev/2026, usamos Nov/2025, Dez/2025 e Jan/2026 REAL
    (o valor real de Jan/2026 ja esta disponivel no momento em que
    fevereiro esta para ser previsto - e' um esquema valido de previsao
    'passo a passo' / walk-forward, comum em series temporais)."""
    previsoes = {}
    for mes in meses_para_prever:
        periodo_alvo = pd.Period(mes, freq="M")
        meses_anteriores = [
            str(periodo_alvo - i) for i in range(1, janela + 1)
        ]  # janela imediatamente anterior ao mes alvo
        valores = vendas_mensais.reindex(meses_anteriores)
        previsoes[mes] = valores.mean()
    return pd.Series(previsoes, name="previsao")


# --------------------------------------------------------------------------
# PASSO 4: avaliacao com MAE
# --------------------------------------------------------------------------

def compute_mae(previsoes, vendas_mensais):
    reais = vendas_mensais.reindex(previsoes.index)
    erros_absolutos = (previsoes - reais).abs()
    mae = erros_absolutos.mean()
    return reais, erros_absolutos, mae


# --------------------------------------------------------------------------
# ORQUESTRACAO / RELATORIO
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Previsao de demanda (baseline media movel 3 meses) para Bussola de Bordo 702."
    )
    parser.add_argument("--data-dir", "-d", default="lh_nautical_csv")
    args = parser.parse_args()

    itens_produto, produto_ids = build_unified_dataset(args.data_dir)
    print(f"Produto '{PRODUTO_ALVO}' -> product_id(s) encontrados: {produto_ids}")
    print(f"Total de itens vendidos (linhas de order_items) do produto: {len(itens_produto)}")

    vendas_mensais = build_monthly_series(itens_produto)
    print("\nSerie mensal de vendas (treino ate", DATA_CORTE_TREINO, "):")
    print(vendas_mensais[vendas_mensais.index <= DATA_CORTE_TREINO].to_string())

    previsoes = forecast_moving_average(vendas_mensais, MESES_TESTE, janela=3)
    reais, erros, mae = compute_mae(previsoes, vendas_mensais)

    print("\nPrevisao vs Real - 1o trimestre de 2026:")
    resultado = pd.DataFrame({
        "previsao": previsoes.round(2),
        "real": reais,
        "erro_absoluto": erros.round(2),
    })
    print(resultado.to_string())

    soma_previsao = round(previsoes.sum())
    print(f"\n[Questao 6.2] Soma da previsao (1o trimestre 2026, arredondada): {soma_previsao}")
    print(f"[Questao 6] MAE (Mean Absolute Error) no periodo de teste: {mae:.2f}")


if __name__ == "__main__":
    main()