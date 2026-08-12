SELECT
    (SELECT COUNT(*) FROM customers)   AS total_customers,
    (SELECT COUNT(*) FROM orders)      AS total_orders,
    (SELECT COUNT(*) FROM order_items) AS total_order_items,
    (SELECT COUNT(*) FROM payments)    AS total_payments,
    (SELECT COUNT(*) FROM customers) +
    (SELECT COUNT(*) FROM orders) +
    (SELECT COUNT(*) FROM order_items) +
    (SELECT COUNT(*) FROM payments)    AS total_geral;

-- outra versão da mesma consulta, utilizando UNION ALL para retornar os resultados em linhas separadas

SELECT 'customers' AS tabela, COUNT(*) AS total FROM customers
UNION ALL
SELECT 'orders', COUNT(*) FROM orders
UNION ALL
SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL
SELECT 'payments', COUNT(*) FROM payments;