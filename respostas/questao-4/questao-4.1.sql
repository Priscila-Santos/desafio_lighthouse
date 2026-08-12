-- ============================================================
-- Questao 4 - Analise de Clientes (clientes "fieis")
--
-- Cadeia de chaves usada em todo o script (do cliente ate a categoria):
--   orders.customer_id       -> customers.id
--   orders.id                -> order_items.order_id
--   order_items.product_variant_id -> product_variants.id
--   product_variants.product_id    -> products.id
--   products.category_id           -> categories.id
--
-- Ou seja: para saber QUAIS categorias um cliente comprou, eh preciso
-- passar por 3 joins a partir de order_items:
--   order_items -> product_variants -> products -> categories
-- (o order_item so guarda o ID da variante do produto, nao a categoria
-- diretamente; a categoria mora em products, e o order_item se conecta a
-- products atraves de product_variants).
--
-- Observacao/premissa assumida: as regras de negocio fornecidas nao
-- mencionam exclusao de pedidos por status (existem os status 'paid',
-- 'confirmed', 'draft' e 'cancelled' na base). Como o enunciado define
-- Faturamento Total como "soma da coluna total por cliente" sem
-- ressalva, este script usa TODOS os pedidos, de qualquer status. Se a
-- area de negocio quiser excluir pedidos 'cancelled'/'draft' do
-- faturamento e da frequencia, basta adicionar
-- "WHERE status NOT IN ('cancelled','draft')" no CTE customer_orders
-- (e replicar o mesmo filtro nos demais CTEs que usam orders/order_items,
-- para manter a base de clientes consistente entre as metricas).
-- ============================================================


-- ------------------------------------------------------------
-- PASSO 1: Faturamento, Frequencia e Ticket Medio por cliente
-- ------------------------------------------------------------
DROP TABLE IF EXISTS customer_ticket;
CREATE TEMP TABLE customer_ticket AS
SELECT
    o.customer_id,
    SUM(o.total)               AS faturamento_total,
    COUNT(o.id)                AS frequencia,
    SUM(o.total) / COUNT(o.id) AS ticket_medio
FROM orders o
GROUP BY o.customer_id;


-- ------------------------------------------------------------
-- PASSO 2: Diversidade de categorias por cliente
--   COUNT(DISTINCT category_id) percorrendo a cadeia de chaves:
--   orders -> order_items -> product_variants -> products -> categories
-- ------------------------------------------------------------
DROP TABLE IF EXISTS customer_diversity;
CREATE TEMP TABLE customer_diversity AS
SELECT
    o.customer_id,
    COUNT(DISTINCT p.category_id) AS diversidade_categorias
FROM orders o
JOIN order_items oi        ON oi.order_id = o.id
JOIN product_variants pv   ON pv.id = oi.product_variant_id
JOIN products p            ON p.id = pv.product_id
GROUP BY o.customer_id;


-- ------------------------------------------------------------
-- PASSO 3: Junta as duas metricas, aplica o filtro de elite
-- (diversidade >= 13) e seleciona o Top 10 por Ticket Medio,
-- com desempate por customer_id crescente.
-- ------------------------------------------------------------
DROP TABLE IF EXISTS top10_clientes_fieis;
CREATE TEMP TABLE top10_clientes_fieis AS
SELECT
    ct.customer_id,
    ct.faturamento_total,
    ct.frequencia,
    ct.ticket_medio,
    cd.diversidade_categorias
FROM customer_ticket ct
JOIN customer_diversity cd ON cd.customer_id = ct.customer_id
WHERE cd.diversidade_categorias >= 13
ORDER BY ct.ticket_medio DESC, ct.customer_id ASC
LIMIT 10;


-- ------------------------------------------------------------
-- QUESTAO 4.1 - RESULTADO 1: Ticket Medio, Diversidade e o
-- ranking dos 10 clientes fieis.
-- ------------------------------------------------------------
SELECT
    customer_id,
    faturamento_total,
    frequencia,
    ROUND(ticket_medio, 2)      AS ticket_medio,
    diversidade_categorias
FROM top10_clientes_fieis
ORDER BY ticket_medio DESC, customer_id ASC;


-- ------------------------------------------------------------
-- QUESTAO 4.1 - RESULTADO 2: entre os 10 clientes acima, qual
-- categoria concentra a maior quantidade total de itens
-- comprados (SUM(quantity)).
--
-- O filtro "WHERE o.customer_id IN (SELECT customer_id FROM
-- top10_clientes_fieis)" garante que a soma de quantidade so'
-- considera pedidos desses 10 clientes - nenhum item de outro
-- cliente entra na conta.
-- ------------------------------------------------------------
SELECT
    p.category_id,
    c.name                 AS category_name,
    SUM(oi.quantity)       AS quantidade_total
FROM orders o
JOIN order_items oi        ON oi.order_id = o.id
JOIN product_variants pv   ON pv.id = oi.product_variant_id
JOIN products p            ON p.id = pv.product_id
JOIN categories c          ON c.id = p.category_id
WHERE o.customer_id IN (SELECT customer_id FROM top10_clientes_fieis)
GROUP BY p.category_id, c.name
ORDER BY quantidade_total DESC;
