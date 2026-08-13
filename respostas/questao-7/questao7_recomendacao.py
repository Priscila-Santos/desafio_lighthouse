#!/usr/bin/env python3
"""
questao7_recomendacao.py
--------------------------
Autor: Time de Dados - LH Nautical
Objetivo (Questao 7): montar uma vitrine "Quem comprou isso, tambem
levou..." usando um motor de recomendacao item-a-item (item-based
collaborative filtering), baseado em similaridade de cosseno sobre uma
matriz binaria Usuario x Produto.

Bibliotecas: pandas, numpy, scikit-learn (cosine_similarity).

Uso:
    python3 questao7_recomendacao.py --data-dir lh_nautical_csv
"""

import argparse
import os



import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity


PRODUTO_REFERENCIA = "Motor de Popa 1949"
TOP_N = 5


# --------------------------------------------------------------------------
# PASSO 1: matriz de interacao Usuario x Produto (binaria)
# --------------------------------------------------------------------------

def build_interaction_matrix(data_dir):
    """Constroi a matriz binaria cliente x produto:
        1 -> o cliente comprou o produto pelo menos uma vez
        0 -> caso contrario (quantidade e' ignorada de proposito)

    Cadeia de chaves percorrida (produto e' o nivel de agregacao, nao a
    variante/SKU - a pergunta e' "quais produtos sao comprados juntos",
    nao "quais SKUs exatos"):
        order_items.product_variant_id -> product_variants.id
        product_variants.product_id    -> products.id
        order_items.order_id           -> orders.id
        orders.customer_id             -> customers.id
    """
    products = pd.read_csv(os.path.join(data_dir, "products.csv"))
    variants = pd.read_csv(os.path.join(data_dir, "product_variants.csv"))
    orders = pd.read_csv(os.path.join(data_dir, "orders.csv"))
    order_items = pd.read_csv(os.path.join(data_dir, "order_items.csv"))

    # order_items -> variante -> produto
    itens = order_items.merge(
        variants[["id", "product_id"]],
        left_on="product_variant_id", right_on="id",
        suffixes=("", "_variant"),
    )
    # + pedido -> cliente
    itens = itens.merge(
        orders[["id", "customer_id"]],
        left_on="order_id", right_on="id",
        suffixes=("", "_order"),
    )

    # pares (cliente, produto) unicos = presenca de compra, quantidade
    # e' ignorada de proposito (drop_duplicates faz exatamente isso: nao
    # importa se o cliente comprou 1 ou 50 unidades, ou em pedidos
    # diferentes - conta como uma unica interacao "comprou").
    pares_cliente_produto = itens[["customer_id", "product_id"]].drop_duplicates()
    pares_cliente_produto["comprou"] = 1

    matriz = pares_cliente_produto.pivot_table(
        index="customer_id",
        columns="product_id",
        values="comprou",
        fill_value=0,
    )

    return matriz, products


# --------------------------------------------------------------------------
# PASSO 2: similaridade de cosseno produto x produto
# --------------------------------------------------------------------------

def compute_item_similarity(matriz_usuario_produto):
    """A similaridade e' calculada entre PRODUTOS, com base nos CLIENTES
    que compraram cada um - por isso transpomos a matriz (produtos nas
    linhas, clientes nas colunas) antes de chamar cosine_similarity.
    Cada produto vira um vetor binario de tamanho = numero de clientes;
    cosine_similarity mede o angulo entre esses vetores."""
    matriz_produto_usuario = matriz_usuario_produto.T  # produtos x clientes

    sim_array = cosine_similarity(matriz_produto_usuario.values)
    sim_df = pd.DataFrame(
        sim_array,
        index=matriz_produto_usuario.index,
        columns=matriz_produto_usuario.index,
    )
    return sim_df


# --------------------------------------------------------------------------
# PASSO 3: ranking dos produtos mais similares ao item de referencia
# --------------------------------------------------------------------------

def rank_similar_products(sim_df, products, produto_nome_referencia, top_n=5):
    produto_id_ref = products.loc[
        products["name"] == produto_nome_referencia, "id"
    ]
    if produto_id_ref.empty:
        raise ValueError(f"Produto '{produto_nome_referencia}' nao encontrado.")
    produto_id_ref = produto_id_ref.iloc[0]

    if produto_id_ref not in sim_df.index:
        raise ValueError(
            f"Produto '{produto_nome_referencia}' (id={produto_id_ref}) "
            f"nao possui nenhuma venda registrada - impossivel calcular similaridade."
        )

    similares = sim_df.loc[produto_id_ref].drop(index=produto_id_ref)  # remove o proprio item
    similares = similares.sort_values(ascending=False).head(top_n)

    ranking = similares.reset_index()
    ranking.columns = ["product_id", "similaridade_cosseno"]
    ranking = ranking.merge(products[["id", "name"]], left_on="product_id", right_on="id")
    ranking = ranking[["product_id", "name", "similaridade_cosseno"]]
    ranking["similaridade_cosseno"] = ranking["similaridade_cosseno"].round(4)

    return produto_id_ref, ranking


# --------------------------------------------------------------------------
# ORQUESTRACAO
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Motor de recomendacao item-a-item (similaridade de cosseno)."
    )
    parser.add_argument("--data-dir", "-d", default="lh_nautical_csv")
    args = parser.parse_args()

    matriz, products = build_interaction_matrix(args.data_dir)
    print(f"Matriz Usuario x Produto: {matriz.shape[0]} clientes x {matriz.shape[1]} produtos")
    print(f"Densidade da matriz (proporcao de 1's): {matriz.values.mean():.4%}")

    sim_df = compute_item_similarity(matriz)

    produto_id_ref, ranking = rank_similar_products(
        sim_df, products, PRODUTO_REFERENCIA, top_n=TOP_N
    )

    print(f"\nProduto de referencia: '{PRODUTO_REFERENCIA}' (product_id={produto_id_ref})")
    print(f"\nTop {TOP_N} produtos mais similares ('Quem comprou isso, tambem levou...'):")
    print(ranking.to_string(index=False))

    print(f"\n[Questao 7.2] Produto com MAIOR similaridade: '{ranking.iloc[0]['name']}' "
          f"(similaridade = {ranking.iloc[0]['similaridade_cosseno']})")


if __name__ == "__main__":
    main()