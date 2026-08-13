
## Questão 7.3 — Explicação

**1. Como a matriz foi construída?**

Percorri a cadeia `order_items → product_variants → products` (para chegar do item de pedido ao produto, já que o pedido guarda a *variante*/SKU, não o produto direto) e `order_items → orders → customers` (para saber quem comprou). Depois de juntar tudo, fiquei só com os pares únicos `(customer_id, product_id)` — usei `drop_duplicates()` de propósito, porque a regra pedia para ignorar quantidade: não importa se o cliente comprou 1 ou 20 unidades, ou em pedidos diferentes, conta como uma única interação "comprou = 1". Depois é só um `pivot_table` para virar a matriz clientes (linha) × produtos (coluna), preenchendo com 0 onde não há compra.

**2. O que significa a similaridade de cosseno nesse contexto?**

Cada produto vira um vetor binário do tamanho do número de clientes (2.000 posições, cada uma 1 ou 0). A similaridade de cosseno mede o **ângulo** entre dois desses vetores — não a distância bruta, mas o quanto os *padrões* de quem comprou cada produto se sobrepõem. Um valor próximo de 1 significa "praticamente os mesmos clientes compraram os dois produtos"; próximo de 0 significa "quase nenhuma sobreposição de clientela". É por isso que dois produtos comprados pelos mesmos perfis de cliente (mesmo que em quantidades bem diferentes) aparecem como "similares" — a métrica ignora escala, só olha coincidência de presença.

**3. Uma limitação desse método:**

É pura co-ocorrência de compra — não sabe **nada** sobre o produto em si (categoria, preço, função, se faz sentido físico usar os dois juntos). Se dois produtos foram comprados pelos mesmos clientes só por coincidência (ou porque esses clientes compram "de tudo", sem relação real entre os itens), o modelo vai recomendar mesmo sem nenhuma lógica de negócio por trás — é exatamente o que pode ter acontecido aqui: o padrão de compra dos dados sintéticos não necessariamente reproduz o comportamento real esperado (como o combo motor+defensa que a Marina descreveu). Além disso, sofre do problema clássico de **cold start**: um produto novo, sem histórico de vendas, não aparece em nenhum ranking, mesmo que faça todo sentido recomendá-lo.
