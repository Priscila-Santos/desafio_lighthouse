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
├── README.md                          <- este arquivo
├── lh_nautical_csv/                   <- 24 CSVs brutos, fonte de dados do ERP
└── respostas/
    └── questao-2/
        ├── schema_generator.py        <- script que gera o schema.sql
        └── schema.sql                 <- DDL de criação das tabelas (PostgreSQL)
    └── questao-3/ ...                 <- (próximas etapas, conforme forem sendo resolvidas)
```

> Cada questão do desafio tem sua própria pasta em `respostas/`, contendo o(s)
> script(s) usados e os artefatos gerados (SQL, CSVs tratados, notebooks,
> dashboards, etc.).

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
- `--input-dir` / `-i`: pasta com os `.csv` de origem (padrão: `lh_nautical_csv`).
- `--output` / `-o`: caminho do `.sql` de saída (padrão: `schema.sql`).

O script imprime um resumo no terminal ao final da execução (nº de tabelas
processadas, nº de FKs resolvidas automaticamente e quais colunas `*_id`
ficaram sem referência resolvida, para revisão manual).

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
   | 4 | `INTEGER` / `BIGINT` / `NUMERIC(p,0)` | todos são inteiros puros (sem casa decimal); o tamanho decide entre `INTEGER` (cabe em 4 bytes), `BIGINT` (cabe em 8 bytes) ou `NUMERIC` (números maiores, ex. chaves de acesso de NF-e) |
   | 5 | `NUMERIC(p,s)` | mistura de inteiros e decimais, ou só decimais (ex. `"107"` e `"107.000"` na mesma coluna) |
   | 6 | `VARCHAR(n)` / `TEXT` | fallback — texto livre; o tamanho é arredondado para um "bucket" (10, 20, 30, 50, 100, 150, 255, 500) ou `TEXT` se muito longo |

   Coluna com pelo menos um valor vazio no CSV é marcada como `NULL`
   permitido; caso contrário, `NOT NULL`.

3. **Achado de qualidade de dados durante a inferência**: colunas como
   `weight_kg`, `quantity` e `quantity_received` misturam formatação
   inteira (`"107"`) e decimal (`"107.000"`) para a mesma grandeza dentro do
   mesmo arquivo. O script trata isso como `NUMERIC`, unificando os dois
   formatos, em vez de cair (incorretamente) em `VARCHAR`.

4. **Overrides por nome de coluna — identificadores que não devem virar
   número**. Algumas colunas são 100% numéricas no CSV, mas representam
   *códigos*, não quantidades para se fazer conta. Guardá-las como inteiro
   causaria perda de dado ou não faz sentido de negócio:

   | Coluna | Por quê é forçada para `VARCHAR` |
   |---|---|
   | `phone` | valores com **zero à esquerda** (ex. `"06100715800"` em `suppliers.csv`) — vira `INTEGER` e perde o zero, quebrando o número |
   | `cpf`, `tax_id` | mesmo motivo — CPF/CNPJ pode ter zero à esquerda; também não faz sentido "somar" um CPF |
   | `nfe_access_key` | tem **44 dígitos** — maior que um `BIGINT` (máx. ~19 dígitos); guardar como `NUMERIC` gigante seria estranho para um campo que é, na prática, um identificador de texto |
   | `barcode_ean`, `sku`, `ncm_code` | códigos de produto/classificação fiscal — nunca usados em operação aritmética |
   | `cep` / `postal_code`, `zip` | (cobertos por segurança, mesmo já vindo com hífen no CSV) |

   Essa lista fica isolada em uma única variável de configuração no topo do
   script (`OVERRIDE_TEXT_KEYWORDS`), fácil de revisar ou ajustar.

5. **Chave primária**:
   - se o CSV tem coluna `id`, ela é a `PRIMARY KEY`.
   - se não tem (tabelas de associação: `product_suppliers`,
     `variant_attribute_values`, `stock_levels`), a `PRIMARY KEY` composta é
     formada por todas as colunas terminadas em `_id`.

6. **Chaves estrangeiras**: toda coluna `*_id` é comparada com o nome
   (singularizado) dos demais arquivos CSV, para descobrir a tabela
   referenciada automaticamente. Um pequeno dicionário de apelidos resolve
   os poucos nomes que fogem do padrão (`salesperson_id` → `employees`,
   `buyer_id` → `employees`, `exchange_variant_id` → `product_variants`).
   Resultado nesta base: **37 FKs resolvidas automaticamente**, sem
   intervenção manual.

7. **Colunas `*_id` que ficam de fora de propósito** (documentadas em
   comentário no final do `schema.sql`, para revisão manual):
   - `customers.tax_id` e `suppliers.tax_id` — terminam em `_id`, mas não
     são chave estrangeira nenhuma; são identificador fiscal (CPF/CNPJ).
   - `stock_movements.reference_id` — **chave polimórfica**: aponta para
     tabelas diferentes (`orders`, `returns`, `purchase_orders`, etc.)
     dependendo do valor da coluna `reference_table`. Não é possível
     modelar isso como uma `FOREIGN KEY` única em SQL padrão; fica
     sinalizado para tratamento manual (ex.: `CHECK` + trigger, ou manter
     sem FK mesmo, prática comum para chaves polimórficas).

8. **Saída em duas partes**, para não depender de ordenação topológica das
   tabelas:
   - **Parte 1**: todos os `CREATE TABLE` (colunas + `PRIMARY KEY`).
   - **Parte 2**: todos os `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY`,
     emitidos só depois que todas as tabelas já existem.

### Limitações conhecidas (transparência para o Gabriel)
- A inferência de tipo é feita sobre o CSV inteiro, então tabelas muito
  grandes (a maior aqui tem ~147 mil linhas) são lidas por completo — sem
  amostragem. Funciona bem no volume do desafio, mas para bases muito
  maiores valeria trocar por leitura em streaming/amostragem.
- O reconhecimento de chave estrangeira é por convenção de nome
  (`*_id` + singularização), não por análise de integridade referencial
  real (não checamos se os valores de fato existem na tabela referenciada).
  Isso seria um próximo passo natural antes de aplicar o `schema.sql` em
  produção.
- `stock_movements.reference_id` precisa de decisão de modelagem humana
  (chave polimórfica), como explicado acima.

---

## Próximas etapas

- [x] Questão 2 — Schema
- [ ] Tratamento de dados
- [ ] EDA
- [ ] Análise de vendas
- [ ] Análise de clientes
- [ ] Previsão de demanda
- [ ] Sistema de recomendação
- [ ] Dashboard/painel final

*(este README será atualizado conforme cada etapa for concluída)*