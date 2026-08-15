-- Questão 1.1 - EDA da tabela orders (SQL)
-- Sem tratamento/limpeza de dados, apenas observação e agregação, conforme premissas da Questão 1.

SELECT
    COUNT(*)              AS total_linhas,
    MIN(created_at)        AS data_minima,
    MAX(created_at)        AS data_maxima,
    MIN(total)              AS total_minimo,
    MAX(total)              AS total_maximo,
    AVG(total)              AS total_medio
FROM orders;
