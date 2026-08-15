# Desafio LH Nautical — Lighthouse

Repositório com as resoluções do desafio técnico da LH Nautical: um pipeline de
dados que vai da ingestão bruta (CSVs do ERP) até EDA, tratamento de dados,
análises de vendas/clientes, previsão de demanda e sistema de recomendação.

Este README documenta a estrutura do repositório e o raciocínio por trás de
cada entrega — conforme pedido pelo Gabriel Santos (Tech Lead): *"Eu valorizo
mais a organização e a explicação do que o código rodando sem eu entender
nada."*

---

## Estrutura do repositório

```
desafio_lighthouse/
├── README.md
├── lh_nautical_csv/                       <- 24 CSVs brutos, fonte de dados do ERP
└── respostas/
    ├── questao-1/
    │   └── questao1_eda.sql               <- EDA inicial da tabela orders
    ├── questao-2/
    │   ├── schema_generator.py            <- gera o schema.sql a partir dos CSVs
    │   └── schema.sql                     <- DDL de criação das tabelas (PostgreSQL)
    ├── questao-3/
    │   └── load_data.py                   <- carrega os CSVs no PostgreSQL, respeitando o schema
    ├── questao-4/
    │   └── questao4_analise_clientes.sql  <- clientes fiéis (ticket médio + diversidade)
    ├── questao-5/
    │   └── questao5_dimensao_calendario.sql <- calendário completo + vendas por dia da semana
    ├── questao-6/
    │   └── questao6_previsao_demanda.py   <- baseline de previsão (média móvel 3 meses)
    ├── questao-7/
    │   └── questao7_recomendacao.py       <- motor de recomendação (similaridade de cosseno)
    └── dashboard/
        ├── dashboard_lh_nautical.pbix     <- dashboard oficial (Power BI)
        ├── dashboard_lh_nautical.html     <- material complementar (fora do formulário por
        │                                     restrição de formato de upload; guardado aqui)
        └── build_dashboard_data.py        <- script que gera os dados agregados usados no dashboard
```

---

## Questão 1 — EDA (tabela `orders`)

### Contexto
Antes de qualquer modelagem ou decisão, o Sr. Almir quer saber: "posso
confiar nesses dados?" Análise exploratória inicial usando **apenas** a
tabela `orders`, sem nenhuma limpeza ou tratamento — só observação e
agregação.

### Entregável
- `respostas/questao-1/questao1_eda.sql`

### Resultado

| Métrica | Valor |
|---|---:|
| Total de linhas | 48.998 |
| Data mínima (`created_at`) | 2020-01-01 |
| Data máxima (`created_at`) | 2026-12-31 |
| `total` mínimo | R$ 32,62 |
| `total` máximo | R$ 127.262,02 |
| `total` médio | **R$ 28.704,99** |

### Diagnóstico (1.3)
**Os dados são utilizáveis, mas não estão prontos para decisões finais sem
tratamento e sem relacionamento com outras tabelas.**

- **Outliers em `total`**: pelo critério de IQR (1,5×), **452 pedidos
  (~0,9% da base)** ficam fora do intervalo esperado (limite superior ≈
  R$ 82.598), com o máximo chegando a R$ 127.262,02 — mais de 4× a média.
  Isoladamente, `orders` não permite saber se isso é legítimo (ex.: pedido
  corporativo grande) ou erro de lançamento — só dá para validar cruzando
  com `order_items`, conferindo se o valor é consistente com a
  quantidade/preço dos produtos daquele pedido.
- **Qualidade dos dados**: `total` está 100% preenchido, sem nulos,
  negativos ou zeros. As datas (`placed_at`, `created_at`) também não têm
  nulos e são consistentes entre si. `salesperson_id` é nulo em ~49% das
  linhas, mas isso é esperado — a empresa vende tanto por `pos` (loja
  física, com vendedor) quanto `ecommerce` (sem vendedor). O ponto mais
  crítico é temporal: **existem 4.322 pedidos com `created_at` posterior à
  data atual** (até 2026-12-31) — inconsistência que compromete qualquer
  análise de série temporal ou sazonalidade se não for tratada antes.
- **Pronta para análise?** Não isoladamente. Para responder perguntas de
  negócio reais (lucro, margem, produtos mais vendidos, comportamento de
  cliente) é necessário (1) tratamento prévio das datas futuras e
  investigação dos outliers de `total`, e (2) relacionamento com
  `order_items` (validar valores e mix de produtos), `customers`
  (segmentação), `payments` (status financeiro real) e
  `returns`/`return_items` (saber se o pedido foi devolvido, o que afeta o
  `total` líquido). A tabela é confiável como fonte bruta, mas decisões
  estratégicas exigem o pipeline completo de tratamento + join com o
  restante do schema.

---

## Questão 2 — Schema (Engenharia de Dados)

### Contexto
O ERP da LH Nautical só permite extração via CSV (sem acesso direto ao banco).
Antes de qualquer análise, é preciso definir o schema de destino em
PostgreSQL a partir desses 24 arquivos.

### Entregáveis
- `respostas/questao-2/schema_generator.py` — script Python 3 (somente
  biblioteca padrão: `csv`, `os`, `re`, `argparse`) que lê todos os CSVs de um
  diretório e gera um único `schema.sql`.
- `respostas/questao-2/schema.sql` — DDL de criação das 24 tabelas para
  PostgreSQL, já com chaves primárias e estrangeiras.

### Como rodar
```bash
python schema_generator.py --input-dir lh_nautical_csv --output schema.sql
```

### Como o script pensa (passo a passo)

1. **Leitura**: cada CSV é lido por completo (cabeçalho + todas as linhas)
   usando o módulo `csv` puro — sem `pandas` ou qualquer lib externa, por
   restrição do desafio.

2. **Inferência de tipo por coluna, baseada no conteúdo (não no nome)**.
   Para cada coluna, testamos os valores nesta ordem de prioridade, e a
   primeira regra que bate com **100%** dos valores não vazios da coluna
   vence:

   | Ordem | Tipo detectado | Critério |
   |---|---|---|
   | 1 | `BOOLEAN` | todos os valores são `TRUE`/`FALSE` |
   | 2 | `DATE` | todos no formato `AAAA-MM-DD` |
   | 3 | `TIMESTAMP` | todos no formato `AAAA-MM-DD HH:MM:SS` |
   | 4 | `INTEGER` / `BIGINT` / `NUMERIC(p,0)` | todos são inteiros puros (sem casa decimal); o tamanho decide entre `INTEGER`, `BIGINT` ou `NUMERIC` |
   | 5 | `NUMERIC(p,s)` | mistura de inteiros e decimais, ou só decimais |
   | 6 | `VARCHAR(n)` / `TEXT` | fallback — texto livre |

   Coluna com pelo menos um valor vazio no CSV é marcada como `NULL`
   permitido; caso contrário, `NOT NULL`.

3. **Achado de qualidade de dados durante a inferência**: colunas como
   `weight_kg`, `quantity` e `quantity_received` misturam formatação
   inteira (`"107"`) e decimal (`"107.000"`) para a mesma grandeza dentro do
   mesmo arquivo. O script trata isso como `NUMERIC`, unificando os dois
   formatos, em vez de cair (incorretamente) em `VARCHAR`.

4. **Overrides por nome de coluna** — identificadores que não devem virar
   número (`phone`, `cpf`, `tax_id`, `nfe_access_key`, `barcode_ean`, `sku`,
   `ncm_code`, `cep`/`postal_code`), para não perder zero à esquerda nem
   forçar aritmética sobre um código.

5. **Chave primária**: coluna `id` quando existe; nas tabelas de associação
   sem `id` (`product_suppliers`, `variant_attribute_values`,
   `stock_levels`), a PK composta é formada pelas colunas `_id`.

6. **Chaves estrangeiras**: toda coluna `*_id` é comparada com o nome
   (singularizado) dos demais arquivos CSV. Um dicionário de apelidos
   resolve os casos fora do padrão (`salesperson_id` → `employees` etc.).
   Resultado: **37 FKs resolvidas automaticamente**.

7. **Colunas `*_id` fora do padrão, documentadas para revisão manual**:
   `customers.tax_id`/`suppliers.tax_id` (identificador fiscal, não FK) e
   `stock_movements.reference_id` (chave polimórfica — aponta para tabelas
   diferentes dependendo de `reference_table`).

8. **Saída em duas partes**: todos os `CREATE TABLE` primeiro, depois todos
   os `ALTER TABLE ... ADD FOREIGN KEY` — evita depender de ordenação
   topológica das tabelas.

### Limitações conhecidas
- Sem amostragem: lê o CSV inteiro para inferir tipo (funciona bem no
  volume do desafio; para bases maiores, valeria streaming/amostragem).
- FK por convenção de nome, não por checagem real de integridade
  referencial.

---

## Questão 3 — Carregamento

### Contexto
Carregar os 24 CSVs no PostgreSQL, respeitando o schema da Questão 2, sem
nenhum tratamento de dado (sem remoção de nulos, sem correção de caracteres
especiais).

### Entregável
- `respostas/questao-3/load_data.py` — usa `psycopg2`.

### Como rodar
```bash
pip install psycopg2-binary
python load_data.py --csv-dir lh_nautical_csv --schema-file schema.sql --dsn "postgresql://user:senha@host:porta/banco"
```

### Como pensa
1. Lê o `schema.sql` da Questão 2 e separa automaticamente os `CREATE TABLE`
   (sem FK) dos `ALTER TABLE ... ADD FOREIGN KEY`.
2. Cria as tabelas sem FK primeiro — por isso a **ordem de carregamento dos
   CSVs não importa** (inclusive resolve o auto-relacionamento de
   `categories.parent_category_id` sem gambiarra).
3. Carrega cada CSV via `COPY` nativo do PostgreSQL (`cursor.copy_expert`),
   não linha a linha em Python — mais rápido e sem transformação de dado:
   campo vazio vira `NULL` porque é o comportamento *padrão* do formato CSV
   do Postgres, não uma limpeza feita por nós.
4. Só depois de carregar tudo, aplica as `FOREIGN KEY` — se houver
   inconsistência referencial, o erro aparece nesse momento (comportamento
   correto para uma camada bruta).
5. Ao final, roda `SELECT COUNT(*)` por tabela e valida o total.

### Validação (3.2)
Soma de linhas de `customers` + `orders` + `order_items` + `payments`:

| Tabela | Linhas |
|---|---:|
| customers | 2.000 |
| orders | 48.998 |
| order_items | 147.320 |
| payments | 53.546 |
| **Total** | **251.864** |

Confirmado tanto por contagem direta nos CSVs quanto pela execução real do
script contra o banco.

---

## Questão 4 — Análise de Clientes

### Contexto
Identificar os clientes "de elite": ticket médio alto **e** diversidade de
compra em pelo menos 13 categorias distintas.

### Entregável
- `respostas/questao-4/questao4_analise_clientes.sql`

### Cadeia de chaves usada
```
orders.customer_id → customers.id
order_items.order_id → orders.id
order_items.product_variant_id → product_variants.id
product_variants.product_id → products.id
products.category_id → categories.id
```
Ou seja: para saber quais categorias um cliente comprou, é preciso
atravessar 3 joins a partir de `order_items` (`product_variants` →
`products` → `categories`), já que o item de pedido só guarda o ID da
variante, não a categoria diretamente.

### Como pensa
1. `customer_ticket`: soma de `total` e contagem de pedidos por cliente →
   ticket médio = faturamento ÷ frequência.
2. `customer_diversity`: `COUNT(DISTINCT category_id)` por cliente,
   percorrendo a cadeia de chaves acima.
3. Filtro de elite: `diversidade_categorias >= 13`.
4. Ranking: `ORDER BY ticket_medio DESC, customer_id ASC LIMIT 10`.
5. Segunda consulta: soma de `quantity` por categoria, filtrando **apenas**
   pedidos dos 10 clientes do ranking (`WHERE customer_id IN (...)`), para
   não misturar com os quase 2.000 clientes que também atendem ao critério
   de diversidade mas não entraram no top 10.

### Resultado (validado em Python e reproduzido no PostgreSQL)
Top 10 clientes fiéis por ticket médio (todos com diversidade = 14).
Categoria que mais concentra itens entre esses 10 clientes: **Hélices**
(492 unidades).

### Observação documentada
O enunciado não pede exclusão de pedidos por status — a base tem pedidos
`cancelled`/`draft` além de `paid`/`confirmed`. O script usa todos os
pedidos, sem filtro, seguindo a regra ao pé da letra; o ajuste para
considerar só pedidos pagos/confirmados fica comentado no SQL.

---

## Questão 5 — Dimensão de Calendário

### Contexto
O Sr. Almir quer saber o pior dia da semana para vendas nas lojas físicas.
Um cálculo ingênuo (`GROUP BY` direto em `orders`) ignora dias sem nenhuma
venda — que não geram linha na tabela — inflando a média de dias com muitos
"buracos" no calendário.

### Entregável
- `respostas/questao-5/questao5_dimensao_calendario.sql`

### Como pensa
1. **Dimensão de datas**: `generate_series` do PostgreSQL cria uma linha
   para cada dia entre a menor e a maior data de pedido, com o nome do dia
   da semana em português (`CASE EXTRACT(DOW FROM data) ...`).
2. **Vendas diárias**: soma de `total` por dia, filtrando `channel = 'pos'`.
3. **LEFT JOIN do calendário para as vendas** (calendário na esquerda,
   sempre) — todo dia aparece no resultado, com venda real ou `0` via
   `COALESCE`.
4. Média por dia da semana considerando **todos** os dias do período,
   inclusive os sem venda.

### Resultado
**Quinta-feira tem a pior média de vendas** — não domingo, como um cálculo
ingênuo sugeriria. Quinta-feira concentra o maior número de dias sem
nenhuma venda no período (20), o que puxa a média real para baixo.

---

## Questão 6 — Previsão de Demanda

### Contexto
Prever a demanda mensal de "Bússola de Bordo 702" para o 1º trimestre de
2026, com um baseline de média móvel de 3 meses.

### Entregável
- `respostas/questao-6/questao6_previsao_demanda.py` (pandas)

### Achado de dado
Existem **dois `product_id` distintos** (74 e 240) com o nome exato
"Bússola de Bordo 702" — colisão do gerador sintético de nomes, não um
cadastro duplicado proposital. Como o enunciado identifica o produto pelo
nome, os dois foram agregados; documentado no script para revisão.

### Como pensa
1. Dataset unificado: `products` → `product_variants` → `order_items` →
   `orders`, filtrando por nome do produto.
2. Série mensal completa (jan/2020 a mar/2026), com meses sem venda
   preenchidos com 0.
3. Baseline walk-forward: para cada mês a prever, usa a média dos 3 meses
   **imediatamente anteriores**, sempre com valores **reais** (nunca uma
   previsão própria) — evita data leakage e efeito cascata de erro.

### Resultado

| Mês | Previsão | Real | Erro absoluto |
|---|---:|---:|---:|
| Jan/2026 | 38,67 | 79 | 40,33 |
| Fev/2026 | 53,67 | 68 | 14,33 |
| Mar/2026 | 56,33 | 60 | 3,67 |

**MAE = 19,44** · **Soma da previsão do trimestre (arredondada): 149
unidades** (real: 207).

### Conclusão
O baseline subestima justamente janeiro — a virada da alta estação de
verão — porque usa meses de baixa estação (out–dez) para prever o pico.
Limitação principal: média móvel simples não captura sazonalidade.

---

## Questão 7 — Sistema de Recomendação

### Contexto
Recomendar produtos com base em similaridade de comportamento de compra,
usando "Motor de Popa 1949" como item de referência.

### Entregável
- `respostas/questao-7/questao7_recomendacao.py` (pandas, numpy,
  scikit-learn)

### Como pensa
1. Matriz binária cliente × produto (`1` = comprou ao menos uma vez,
   quantidade ignorada de propósito via `drop_duplicates()`).
2. Similaridade de cosseno entre os vetores de produto (transposição da
   matriz: produtos × clientes).
3. Ranking dos 5 produtos mais similares, excluindo o próprio item de
   referência.

### Resultado

| Produto | Similaridade |
|---|---:|
| Motor de Popa 5331 | 0,2566 |
| Cabo Náutico 2105 | 0,2562 |
| Vela Mestra 1913 | 0,2558 |
| Cabo Náutico 9048 | 0,2393 |
| GPS Plotter 6249 | 0,2377 |

### Observação honesta
A narrativa do desafio sugeria uma defensa náutica como par natural do
motor. Os dados não confirmam esse par especificamente — o produto mais
similar foi outro motor. O método está correto; o resultado reflete o que
os dados mostram, não a expectativa da narrativa.

**Limitação do método**: pura co-ocorrência de compra, sem nenhum
conhecimento sobre o produto em si (categoria, função, compatibilidade
física) e sujeito a cold start (produto novo sem histórico não aparece em
nenhum ranking).

---

## Dashboard

### Entregáveis
- `respostas/dashboard/dashboard_lh_nautical.pbix` — dashboard oficial
  (Power BI Desktop), entregue no formulário do desafio.
- `respostas/dashboard/dashboard_lh_nautical.html` — material
  complementar, construído durante a exploração inicial dos dados. Não foi
  anexado no formulário por restrição de formato de upload (aceita apenas
  PDF/Pbix/CSV); guardado aqui como registro do processo.
- `respostas/dashboard/build_dashboard_data.py` — script que gera todos os
  dados agregados usados nas duas versões do dashboard, a partir dos CSVs
  brutos.

### O que o dashboard cobre
KPIs gerais, tendência de faturamento mensal por canal, vendas médias por
dia da semana (Questão 5), faturamento por categoria, ranking de prejuízo
por devolução, clientes de maior lucro acumulado, clientes fiéis (Questão
4), previsão de demanda (Questão 6) e recomendação de produtos (Questão 7)
— cada visual acompanhado de uma leitura de negócio, não só o gráfico bruto.

---

## Checklist

- [x] Questão 1 — EDA
- [x] Questão 2 — Schema
- [x] Questão 3 — Carregamento
- [x] Questão 4 — Análise de Clientes
- [x] Questão 5 — Dimensão de Calendário
- [x] Questão 6 — Previsão de Demanda
- [x] Questão 7 — Sistema de Recomendação
- [x] Dashboard (Power BI + material complementar em HTML)
