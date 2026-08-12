
## Questão 4.2 — Explicação

**1. Como cheguei nas categorias mais vendidas (cadeia de chaves)?**

Não existe ligação direta entre `order_items` e `categories` — é preciso atravessar 3 tabelas:
```
order_items.product_variant_id → product_variants.id
product_variants.product_id     → products.id
products.category_id            → categories.id
```
Ou seja: o item de pedido só sabe qual *variante* do produto foi vendida; a variante sabe a qual *produto* pertence; e é só o `products` que carrega o `category_id`. Por isso fiz `order_items JOIN product_variants JOIN products JOIN categories`, e só então agrupei por `category_id` somando `quantity`.

**2. Lógica do filtro de diversidade mínima**

Contei categorias *distintas* por cliente com `COUNT(DISTINCT p.category_id)`, percorrendo a mesma cadeia acima a partir de `orders` (join com `order_items`). O `DISTINCT` é essencial aqui: um cliente pode comprar 10 itens da categoria "Motores" em pedidos diferentes, e isso deve contar como **1** categoria, não 10. Depois de calcular a diversidade por cliente, apliquei `WHERE diversidade_categorias >= 13` como filtro de elite, antes do ranking por ticket médio.

**3. Como garanti que a contagem de itens refletisse só os Top 10**

Guardei o resultado do ranking (já filtrado e limitado a 10, com `ORDER BY ticket_medio DESC, customer_id ASC LIMIT 10`) numa tabela temporária (`top10_clientes_fieis`). A query de quantidade por categoria usa `WHERE o.customer_id IN (SELECT customer_id FROM top10_clientes_fieis)` — assim, qualquer item de pedido de um cliente fora desse grupo de 10 é excluído da soma antes mesmo do `GROUP BY`. Isso evita o erro comum de somar a quantidade de todos os "elegíveis" (os quase 2 mil clientes com diversidade ≥ 13) em vez de só os 10 do ranking final.

**Uma observação importante que documentei no próprio script:** os enunciados não pedem para excluir pedidos por status, e a base tem pedidos `cancelled` e `draft` além de `paid`/`confirmed`. Segui a regra ao pé da letra (soma de `total` sem filtro de status), mas deixei comentado no SQL como ajustar caso a Marina queira considerar só pedidos efetivamente pagos/confirmados no faturamento — é uma decisão de negócio, não técnica, e prefiro deixar explícita a mim do que decidir por conta própria.