## Questão 1.3 — Interpretação

Com base na análise exploratória da tabela `orders`, meu diagnóstico é: **os dados são utilizáveis, mas não estão prontos para decisões finais sem tratamento e sem relacionamento com outras tabelas.**

**Outliers em "total"**
Aplicando o critério de IQR (1,5×), identifiquei **452 pedidos (~0,9% da base)** fora do intervalo esperado (limite superior ≈ R$ 82.598), com o valor máximo chegando a R$ 127.262,02 — mais de 4x a média. Isoladamente, a tabela `orders` não permite saber se isso é legítimo (ex: pedido corporativo grande) ou erro de lançamento, pois não temos os itens do pedido. Isso só pode ser validado cruzando com `order_items`, para conferir se o valor alto é consistente com a quantidade/preço dos produtos vendidos naquele pedido.

**Qualidade dos dados**
A coluna `total` está 100% preenchida, sem nulos, negativos ou zeros — bom sinal. As datas (`placed_at`, `created_at`) também não têm nulos e são consistentes entre si. O único ponto de atenção direto na tabela é `salesperson_id`, nulo em ~49% das linhas — mas isso provavelmente é esperado, já que a empresa vende tanto por `pos` (loja física, com vendedor) quanto `ecommerce` (sem vendedor). O ponto mais crítico, porém, é temporal: **existem 4.322 pedidos com `created_at` posterior à data atual (até 2026-12-31)** — uma inconsistência que compromete qualquer análise de série temporal, sazonalidade ou performance recente se não for tratada antes.

**A tabela está pronta para análise?**
Não isoladamente. `orders` sozinha só permite uma leitura superficial — para responder perguntas de negócio reais (lucro, margem, produtos mais vendidos, comportamento de cliente) é necessário:
1. **Tratamento prévio**: decidir o que fazer com as datas futuras e investigar os outliers de `total`;
2. **Relacionamento com outras tabelas**: `order_items` (para validar os valores e entender o mix de produtos), `customers` (para segmentação), `payments` (para status financeiro real do pedido) e `returns`/`return_items` (para saber se o pedido foi total ou parcialmente devolvido, o que afeta o "total" líquido).

Ou seja: a tabela é confiável como fonte bruta, mas **decisões estratégicas** exigem o pipeline completo de tratamento + join com o restante do schema.