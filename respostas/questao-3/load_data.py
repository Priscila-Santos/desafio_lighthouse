#!/usr/bin/env python3
"""
load_data.py
------------
Autor: Time de Dados - LH Nautical
Objetivo (Questao 3): carregar todos os CSVs brutos no banco PostgreSQL,
respeitando o schema criado na Questao 2 (schema.sql), SEM nenhum
tratamento de dado (sem remover nulos, sem corrigir caracteres especiais,
sem normalizar nada). E' uma carga "as-is" para uma camada bruta (raw),
que sera tratada em etapas posteriores do pipeline.

Bibliotecas usadas:
    - psycopg2 (driver PostgreSQL para Python). Instalar com:
          pip install psycopg2-binary

Estrategia de carga (resumo do raciocinio):
    1) O schema.sql gerado na Questao 2 tem DUAS partes:
         PARTE 1 - CREATE TABLE (colunas + PRIMARY KEY), sem FK.
         PARTE 2 - ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY.
       Esse script LE o schema.sql e separa essas duas partes
       automaticamente (por prefixo do comando: CREATE TABLE vs ALTER
       TABLE).
    2) Executa a PARTE 1 primeiro -> cria todas as tabelas, ainda sem FK.
    3) Carrega os 24 CSVs usando o comando nativo do PostgreSQL "COPY",
       via psycopg2 (cursor.copy_expert). O COPY em formato CSV:
         - le o cabecalho do CSV e ignora (HEADER true);
         - trata campo vazio nao citado como NULL automaticamente (e' o
           comportamento padrao do formato CSV do proprio Postgres, nao
           uma limpeza feita por nos);
         - preserva acentos, caracteres especiais e qualquer sujeira do
           dado original, pois nao aplicamos nenhuma transformacao no
           conteudo - so passamos o arquivo adiante para o banco.
       Como a PARTE 2 (FKs) ainda nao foi aplicada nesse ponto, a ORDEM de
       carregamento dos arquivos NAO IMPORTA (nao ha constraint de FK para
       violar ainda) - inclusive resolve o caso de auto-relacionamento em
       categories.parent_category_id sem nenhum truque extra.
    4) Depois que TODOS os CSVs foram carregados, executa a PARTE 2
       (ALTER TABLE ... ADD FOREIGN KEY). Se algum dado estiver
       inconsistente (uma FK apontando para um ID que nao existe), o
       banco vai acusar o erro exatamente aqui - o que e' o comportamento
       correto para uma camada bruta: carregar tudo, e deixar o banco
       apontar inconsistencias de integridade referencial para tratamento
       posterior (nao escondemos o problema).
    5) Ao final, roda um SELECT COUNT(*) em cada tabela e imprime um
       resumo de validacao, incluindo a soma de linhas de
       customers + orders + order_items + payments (Questao 3.2).

Uso:
    python3 load_data.py \\
        --csv-dir ./lh_nautical_csv \\
        --schema-file ../questao-2/schema.sql \\
        --dsn "postgresql://user:senha@localhost:5432/lh_nautical"

    Alternativamente, a connection string pode vir da variavel de ambiente
    DATABASE_URL, e as credenciais tambem podem ser passadas via as
    variaveis padrao do libpq (PGHOST, PGPORT, PGDATABASE, PGUSER,
    PGPASSWORD), sem precisar de --dsn.

    Use --dry-run para validar o plano de carga (parsing do schema.sql,
    leitura dos CSVs, ordem de execucao) SEM se conectar a nenhum banco -
    util para revisar o que o script vai fazer antes de rodar de verdade.
"""

import argparse
import csv
import os
import re
import sys

try:
    import psycopg2
except ImportError:
    psycopg2 = None  # so' e' necessario de fato fora do modo --dry-run


# --------------------------------------------------------------------------
# LEITURA E PARSING DO schema.sql
# --------------------------------------------------------------------------

def parse_schema_sql(schema_path):
    """Le o schema.sql gerado na Questao 2 e separa os comandos em duas
    listas: CREATE TABLE (sem FK) e ALTER TABLE (FKs). O parsing e'
    propositalmente simples (split por ';' + prefixo do comando), pois o
    schema.sql e' sempre gerado pelo nosso proprio schema_generator.py,
    com formatacao previsivel."""
    with open(schema_path, "r", encoding="utf-8") as f:
        content = f.read()

    statements = []
    for raw_stmt in content.split(";"):
        stmt = raw_stmt.strip()
        if not stmt:
            continue
        # remove linhas de comentario dentro do statement (ex.: a linha
        # "-- Tabela gerada a partir de: X.csv" que antecede cada
        # CREATE TABLE), mantendo so' o SQL de fato. Importante: nao
        # descartamos o chunk so' porque a PRIMEIRA linha e' comentario -
        # isso e' o caso de TODO CREATE TABLE gerado pela Questao 2.
        lines = [ln for ln in stmt.splitlines() if not ln.strip().startswith("--")]
        clean_stmt = "\n".join(lines).strip()
        if clean_stmt:
            statements.append(clean_stmt + ";")

    create_statements = [s for s in statements if s.upper().startswith("CREATE TABLE")]
    alter_statements = [s for s in statements if s.upper().startswith("ALTER TABLE")]

    return create_statements, alter_statements


def extract_table_name(create_statement):
    """Extrai o nome da tabela de um comando 'CREATE TABLE nome (...)'."""
    match = re.match(r"CREATE TABLE\s+(\w+)\s*\(", create_statement, re.IGNORECASE)
    if not match:
        raise ValueError(f"Nao foi possivel identificar o nome da tabela em: {create_statement[:60]}")
    return match.group(1)


# --------------------------------------------------------------------------
# LOCALIZACAO DOS CSVs
# --------------------------------------------------------------------------

def find_csv_for_table(csv_dir, table_name):
    """Cada tabela tem o mesmo nome do arquivo CSV que a originou
    (convencao usada pelo schema_generator.py da Questao 2)."""
    path = os.path.join(csv_dir, f"{table_name}.csv")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"CSV nao encontrado para a tabela '{table_name}': {path}")
    return path


def count_csv_rows(csv_path):
    """Conta linhas de dados (exclui cabecalho) - usado so' para o log do
    --dry-run e para conferencia visual, o COPY do Postgres nao depende
    disso."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        return sum(1 for _ in reader)


# --------------------------------------------------------------------------
# CARGA NO POSTGRESQL
# --------------------------------------------------------------------------

def run_ddl_statements(cur, statements, label):
    for stmt in statements:
        cur.execute(stmt)
    print(f"[OK] {len(statements)} comando(s) de {label} executado(s).")


def drop_tables_if_exists(cur, table_names):
    """Torna a carga idempotente: permite rodar o script varias vezes
    sem erro de 'tabela ja existe'. So' remove as tabelas do proprio
    schema (nao mexe em nada fora da lista gerada pela Questao 2)."""
    for table in reversed(table_names):  # ordem reversa por seguranca
        cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
    print(f"[OK] {len(table_names)} tabela(s) removida(s) (se existiam) antes da recriacao.")


def copy_csv_into_table(cur, csv_path, table_name):
    """Carrega um CSV inteiro na tabela via COPY nativo do PostgreSQL.
    Sem nenhuma transformacao de dado: o que esta no CSV vai para o banco
    exatamente como esta (inclusive campo vazio -> NULL, que e' o
    comportamento padrao do formato CSV, nao uma limpeza feita por nos)."""
    copy_sql = (
        f"COPY {table_name} FROM STDIN WITH ("
        f"FORMAT csv, HEADER true, DELIMITER ',', ENCODING 'UTF8')"
    )
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        cur.copy_expert(copy_sql, f)


def load_all_csvs(cur, csv_dir, table_names):
    for table in table_names:
        csv_path = find_csv_for_table(csv_dir, table)
        copy_csv_into_table(cur, csv_path, table)
        print(f"  - {table}.csv carregado em '{table}'.")


def validate_row_counts(cur, table_names):
    """Roda um SELECT COUNT(*) em cada tabela carregada e imprime um
    resumo, incluindo a soma pedida na Questao 3.2."""
    counts = {}
    for table in table_names:
        cur.execute(f"SELECT COUNT(*) FROM {table};")
        counts[table] = cur.fetchone()[0]

    print("\nResumo de linhas carregadas por tabela:")
    for table in table_names:
        print(f"  {table:<28} {counts[table]:>10}")

    validation_tables = ["customers", "orders", "order_items", "payments"]
    if all(t in counts for t in validation_tables):
        total = sum(counts[t] for t in validation_tables)
        print("\n[Questao 3.2] Soma de linhas (customers + orders + order_items + payments):")
        for t in validation_tables:
            print(f"  {t:<28} {counts[t]:>10}")
        print(f"  {'TOTAL':<28} {total:>10}")

    return counts


# --------------------------------------------------------------------------
# ORQUESTRACAO
# --------------------------------------------------------------------------

def build_connection(dsn):
    if psycopg2 is None:
        raise RuntimeError(
            "psycopg2 nao esta instalado. Rode: pip install psycopg2-binary"
        )
    # dsn vazio -> psycopg2/libpq usa as variaveis de ambiente padrao
    # (PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD)
    return psycopg2.connect(dsn) if dsn else psycopg2.connect("")


def run(csv_dir, schema_file, dsn, dry_run, reset):
    create_statements, alter_statements = parse_schema_sql(schema_file)
    table_names = [extract_table_name(s) for s in create_statements]

    print(f"Schema lido de: {schema_file}")
    print(f"  {len(create_statements)} tabela(s) a criar.")
    print(f"  {len(alter_statements)} chave(s) estrangeira(s) a aplicar apos a carga.")
    print(f"Diretorio de CSVs: {csv_dir}")

    if dry_run:
        print("\n--- MODO DRY-RUN: nada sera executado no banco ---")
        total_rows = 0
        for table in table_names:
            csv_path = find_csv_for_table(csv_dir, table)
            n_rows = count_csv_rows(csv_path)
            total_rows += n_rows
            print(f"  {table:<28} <- {os.path.basename(csv_path):<32} {n_rows:>10} linhas")
        print(f"\nTotal de linhas em todos os CSVs: {total_rows}")
        print("Plano de execucao validado com sucesso (sem conexao ao banco).")
        return

    conn = build_connection(dsn)
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            if reset:
                drop_tables_if_exists(cur, table_names)

            run_ddl_statements(cur, create_statements, "criacao de tabela (PARTE 1)")

            print(f"\nCarregando {len(table_names)} arquivo(s) CSV via COPY...")
            load_all_csvs(cur, csv_dir, table_names)

            run_ddl_statements(cur, alter_statements, "chave estrangeira (PARTE 2)")

            validate_row_counts(cur, table_names)

        conn.commit()
        print("\n[OK] Carga concluida e commitada com sucesso.")
    except Exception:
        conn.rollback()
        print("\n[ERRO] Carga revertida (rollback). Nenhum dado foi persistido.", file=sys.stderr)
        raise
    finally:
        conn.close()


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Carrega os CSVs da LH Nautical no PostgreSQL, respeitando o schema.sql da Questao 2."
    )
    parser.add_argument(
        "--csv-dir", "-c", default="lh_nautical_csv",
        help="Diretorio com os arquivos .csv de origem (padrao: lh_nautical_csv)",
    )
    parser.add_argument(
        "--schema-file", "-s", default="schema.sql",
        help="Caminho do schema.sql gerado na Questao 2 (padrao: schema.sql)",
    )
    parser.add_argument(
        "--dsn", default=os.environ.get("DATABASE_URL", ""),
        help=(
            "Connection string do PostgreSQL, ex.: "
            "postgresql://user:senha@host:5432/banco. "
            "Se omitido, usa a env var DATABASE_URL ou, na ausencia dela, "
            "as variaveis padrao do libpq (PGHOST, PGUSER, etc.)."
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Valida o plano de carga (schema.sql + CSVs) sem conectar a nenhum banco.",
    )
    parser.add_argument(
        "--no-reset", dest="reset", action="store_false",
        help="Nao remove tabelas existentes antes de recriar (por padrao, o script recria do zero).",
    )
    args = parser.parse_args()

    run(
        csv_dir=args.csv_dir,
        schema_file=args.schema_file,
        dsn=args.dsn,
        dry_run=args.dry_run,
        reset=args.reset,
    )


if __name__ == "__main__":
    main()