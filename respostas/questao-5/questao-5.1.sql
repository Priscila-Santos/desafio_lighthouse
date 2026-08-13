-- ============================================================
-- Questao 5 - Dimensao de Calendario
-- Pergunta do Sr. Almir: qual dia da semana tem a PIOR media de
-- vendas nas lojas fisicas (channel = 'pos')?
--
-- O erro do estagiario: ele agrupou direto a tabela orders por dia
-- da semana. Como um dia sem nenhuma venda simplesmente NAO GERA
-- LINHA em orders, esse dia "some" da conta - ele nao entra nem na
-- soma (correto, contribuiria 0) nem no COUNT usado para tirar a
-- media (incorreto: deveria contar como um dia a mais no
-- denominador). Isso infla a media de qualquer dia da semana que
-- tenha varios dias parados, e foi exatamente o caso do Domingo no
-- calculo dele.
--
-- A correcao exige um CALENDARIO (dimensao de datas) com TODOS os
-- dias do periodo, independente de ter venda ou nao, e um LEFT JOIN
-- de orders para dentro desse calendario (nunca o contrario).
-- ============================================================


-- ------------------------------------------------------------
-- PASSO 1: Dimensao de datas (calendario)
-- Periodo: da menor ate a maior data de venda presente no arquivo
-- de pedidos (orders.placed_at), cobrindo TODOS os dias corridos,
-- inclusive fins de semana - conforme a premissa "a loja esteve
-- aberta em todos os dias do periodo".
-- ------------------------------------------------------------
DROP TABLE IF EXISTS dim_calendario;
CREATE TEMP TABLE dim_calendario AS
WITH periodo AS (
    SELECT
        MIN(placed_at::date) AS data_inicio,
        MAX(placed_at::date) AS data_fim
    FROM orders
)
SELECT
    dia::date AS data,
    -- EXTRACT(DOW ...) no Postgres retorna 0=Domingo ... 6=Sabado.
    -- Mapeamos para o nome do dia em portugues:
    CASE EXTRACT(DOW FROM dia)
        WHEN 0 THEN 'Domingo'
        WHEN 1 THEN 'Segunda-feira'
        WHEN 2 THEN 'Terça-feira'
        WHEN 3 THEN 'Quarta-feira'
        WHEN 4 THEN 'Quinta-feira'
        WHEN 5 THEN 'Sexta-feira'
        WHEN 6 THEN 'Sábado'
    END AS dia_semana,
    -- ordem de exibicao comecando na Segunda-feira (mais intuitivo
    -- para leitura do que comecar no Domingo, que e' o padrao do
    -- EXTRACT(DOW)):
    CASE EXTRACT(DOW FROM dia)
        WHEN 0 THEN 7
        WHEN 1 THEN 1
        WHEN 2 THEN 2
        WHEN 3 THEN 3
        WHEN 4 THEN 4
        WHEN 5 THEN 5
        WHEN 6 THEN 6
    END AS dia_semana_ordem
FROM periodo, generate_series(periodo.data_inicio, periodo.data_fim, interval '1 day') AS dia;


-- ------------------------------------------------------------
-- PASSO 2: Vendas diarias das lojas fisicas (channel = 'pos')
-- "Vendas diarias" = soma do valor da venda (orders.total) por dia.
-- ------------------------------------------------------------
DROP TABLE IF EXISTS vendas_diarias_pos;
CREATE TEMP TABLE vendas_diarias_pos AS
SELECT
    placed_at::date AS data,
    SUM(total)       AS valor_venda
FROM orders
WHERE channel = 'pos'
GROUP BY placed_at::date;


-- ------------------------------------------------------------
-- PASSO 3: LEFT JOIN do calendario com as vendas diarias.
-- O calendario e' a tabela "base" (esquerda) - todo dia do periodo
-- aparece no resultado, tenha tido venda ou nao. Dia sem
-- correspondencia em vendas_diarias_pos entra com NULL, que
-- convertemos para 0 com COALESCE.
-- ------------------------------------------------------------
DROP TABLE IF EXISTS calendario_vendas;
CREATE TEMP TABLE calendario_vendas AS
SELECT
    c.data,
    c.dia_semana,
    c.dia_semana_ordem,
    COALESCE(v.valor_venda, 0) AS valor_venda
FROM dim_calendario c
LEFT JOIN vendas_diarias_pos v ON v.data = c.data;


-- ------------------------------------------------------------
-- QUESTAO 5.1 - RESULTADO: media de vendas por dia da semana,
-- considerando TODOS os dias do calendario (inclusive os dias sem
-- venda, que entram como 0 no numerador e como +1 no denominador
-- do AVG). Ordenado do PIOR para o MELHOR dia, para responder
-- direto a pergunta do Sr. Almir.
-- ------------------------------------------------------------
SELECT
    dia_semana,
    COUNT(*)                       AS qtd_dias_no_periodo,
    SUM(valor_venda)               AS soma_vendas,
    ROUND(AVG(valor_venda), 2)     AS media_vendas_por_dia
FROM calendario_vendas
GROUP BY dia_semana, dia_semana_ordem
ORDER BY media_vendas_por_dia ASC;   -- pior dia primeiro
