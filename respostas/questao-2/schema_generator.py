#!/usr/bin/env python3
"""
schema_generator.py
--------------------
Autor: Time de Dados - LH Nautical
Objetivo (Questao 2): ler todos os arquivos CSV de um diretorio, detectar
automaticamente o schema (nome/tipo de coluna, nulidade, chave primaria e
chaves estrangeiras) e gerar um unico arquivo `schema.sql` com o DDL de
criacao das tabelas para um banco de destino PostgreSQL.

Regras do desafio respeitadas:
- Somente Python 3 puro (bibliotecas padrao: csv, os, re, sys, argparse,
  datetime, collections). Nenhuma lib de terceiros (pandas, etc).
- Le todos os CSVs de um diretorio informado.
- Gera um unico arquivo de saida .sql com o CREATE TABLE de cada CSV.

Como funciona (resumo do raciocinio):
1) Para cada CSV, lemos o cabecalho e TODAS as linhas de dados (o volume do
   desafio - no maximo ~150 mil linhas por arquivo - permite isso em Python
   puro sem problemas de performance).
2) Para cada coluna, inferimos o tipo SQL mais adequado observando o
   CONTEUDO real da coluna (nao o nome), testando nesta ordem:
     BOOLEAN -> DATE -> TIMESTAMP -> INTEGER/BIGINT/NUMERIC (inteiro)
     -> NUMERIC(p,s) (decimal) -> VARCHAR(n)/TEXT (texto)
   A primeira regra que "bate" com 100% dos valores nao vazios da coluna
   vence. Se a coluna tiver ao menos um valor vazio, a coluna e' marcada
   como aceitando NULL.
3) Alem da inferencia por conteudo, forcei uma pequena lista de
   "overrides" por nome de coluna (ex.: telefone, CPF/CNPJ, codigo de
   barras, chave de acesso de NF-e). Esses campos sao 100% numericos no
   CSV, mas sao codigos/identificadores, nao numeros para se fazer conta.
   Guardar como INTEGER faria a base perder zeros a esquerda (ex.:
   telefone "06100715800") e impediria operacoes futuras corretas
   (ex.: chave de acesso de NF-e tem 44 digitos, maior que um BIGINT).
   Por isso, forcei VARCHAR para essas colunas. Essa decisao fica
   documentada e isolada em uma unica variavel de configuracao
   (OVERRIDE_TEXT_KEYWORDS), facil de ajustar.
4) Detectei a chave primaria:
     - se existir uma coluna chamada "id", ela e' a PK (INTEGER/BIGINT).
     - caso contrario (tabelas de associacao, ex.: product_suppliers,
       variant_attribute_values), a PK composta e' formada por todas as
       colunas que terminam em "_id".
5) Detectei chaves estrangeiras: toda coluna terminada em "_id" (exceto
   a propria PK "id") e' comparada com os nomes (singularizados) dos
   demais arquivos CSV para descobrir a tabela referenciada. Um pequeno
   dicionario de apelidos (ALIASES) resolve os poucos casos em que o nome
   da coluna nao e' o nome literal da tabela no singular (ex.:
   "salesperson_id" -> employees, "buyer_id" -> employees,
   "exchange_variant_id" -> product_variants).
6) O SQL final e' emitido em duas partes, para nao depender de ordenacao
   topologica das tabelas:
     PARTE 1 - CREATE TABLE (colunas + PK) para cada CSV, na ordem em que
               os arquivos foram encontrados.
     PARTE 2 - ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY, depois que
               todas as tabelas ja existem.

Uso:
    python3 schema_generator.py --input-dir ./lh_nautical_csv --output schema.sql
"""

import argparse
import csv
import os
import re
import sys
from collections import OrderedDict

# --------------------------------------------------------------------------
# CONFIGURACAO
# --------------------------------------------------------------------------

# Palavras-chave de nome de coluna que, mesmo contendo apenas digitos,
# devem ser tratadas como texto (identificadores/codigos), nunca numero.
# Motivo: preservar zeros a esquerda e evitar que alguem some/subtraia
# um CPF, telefone ou codigo de barras por engano.
OVERRIDE_TEXT_KEYWORDS = [
    "cpf", "cnpj", "tax_id", "phone", "cep", "postal_code", "zip",
    "barcode", "access_key", "ncm_code", "sku",
]

# Apelidos manuais para colunas cuja referencia nao segue o padrao
# "<nome_singular_da_tabela>_id". Mapeia o "miolo" do nome da coluna
# (sem o sufixo "_id") para o nome do arquivo/tabela referenciada.
ALIASES = {
    "salesperson": "employees",
    "buyer": "employees",
    "variant": "product_variants",
}

# Tamanhos "redondos" usados para VARCHAR, evitando um numero de digitos
# muito especifico e feio no DDL.
VARCHAR_BUCKETS = [10, 20, 30, 50, 100, 150, 255, 500]

# Acima deste tamanho de texto, usamos TEXT em vez de VARCHAR(n).
TEXT_THRESHOLD = 500

# --------------------------------------------------------------------------
# REGEX DE DETECCAO DE TIPO
# --------------------------------------------------------------------------

BOOL_VALUES = {"true", "false"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}$")
INTEGER_RE = re.compile(r"^-?\d+$")
# Cobre tanto inteiros quanto decimais - usada para detectar colunas onde o
# ERP grava a mesma grandeza ora como "107" ora como "107.000" (mistura de
# formatos no mesmo campo, comum em sistemas legados/planilhas).
NUMERIC_ANY_RE = re.compile(r"^-?\d+(\.\d+)?$")

# Quando uma coluna esta 100% vazia em todo o arquivo, nao ha dado para
# inferir o tipo. Nesses casos, se o NOME da coluna sugerir uma grandeza
# numerica, usamos NUMERIC em vez de cair no fallback generico de texto -
# fica mais correto semanticamente e evita um ALTER TABLE futuro.
EMPTY_COLUMN_NUMERIC_HINTS = [
    "amount", "price", "cost", "rate", "total", "quantity", "point",
    "weight", "subtotal",
]

INT4_MIN, INT4_MAX = -2147483648, 2147483647
INT8_MIN, INT8_MAX = -9223372036854775808, 9223372036854775807


# --------------------------------------------------------------------------
# LEITURA DOS CSVs
# --------------------------------------------------------------------------

def list_csv_files(input_dir):
    """Retorna a lista ordenada de arquivos .csv de um diretorio."""
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(".csv")]
    files.sort()
    return files


def read_csv(filepath):
    """Le um CSV e retorna (header, colunas) onde colunas e' um dict
    coluna -> lista de valores (strings), na ordem original do arquivo."""
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        columns = OrderedDict((col, []) for col in header)
        for row in reader:
            # Protege contra linhas com numero de colunas diferente do
            # cabecalho (arquivo corrompido/mal formatado).
            if len(row) != len(header):
                row = (row + [""] * len(header))[:len(header)]
            for col, value in zip(header, row):
                columns[col].append(value)
    return header, columns


# --------------------------------------------------------------------------
# INFERENCIA DE TIPO POR COLUNA
# --------------------------------------------------------------------------

def pick_varchar_bucket(max_len):
    for bucket in VARCHAR_BUCKETS:
        if max_len <= bucket:
            return bucket
    return None  # sinaliza que deve usar TEXT


def infer_column_type(col_name, values):
    """Analisa os valores (strings brutas do CSV) de uma coluna e devolve
    (tipo_sql, aceita_null)."""
    non_empty = [v for v in values if v is not None and v.strip() != ""]
    nullable = len(non_empty) < len(values)

    if not non_empty:
        # Coluna 100% vazia em todo o arquivo: sem dado para inferir pelo
        # conteudo. Usamos o nome como ultima pista antes de cair em TEXT.
        if any(hint in col_name.lower() for hint in EMPTY_COLUMN_NUMERIC_HINTS):
            return "NUMERIC(12,2)", True
        return "TEXT", True

    stripped = [v.strip() for v in non_empty]

    # --- override por nome de coluna (identificadores/codigos) ----------
    name_lower = col_name.lower()
    forced_text = any(kw in name_lower for kw in OVERRIDE_TEXT_KEYWORDS)

    # --- BOOLEAN ----------------------------------------------------------
    if not forced_text and {v.lower() for v in stripped} <= BOOL_VALUES:
        return "BOOLEAN", nullable

    # --- DATE ---------------------------------------------------------------
    if not forced_text and all(DATE_RE.match(v) for v in stripped):
        return "DATE", nullable

    # --- TIMESTAMP ----------------------------------------------------------
    if not forced_text and all(TIMESTAMP_RE.match(v) for v in stripped):
        return "TIMESTAMP", nullable

    # --- INTEGER / BIGINT / NUMERIC(p,0) ------------------------------------
    # (todos os valores sao inteiros "puros", sem casa decimal em nenhum)
    if not forced_text and all(INTEGER_RE.match(v) for v in stripped):
        int_values = [int(v) for v in stripped]
        max_digits = max(len(v.lstrip("-")) for v in stripped)
        vmin, vmax = min(int_values), max(int_values)
        if INT4_MIN <= vmin and vmax <= INT4_MAX:
            return "INTEGER", nullable
        if INT8_MIN <= vmin and vmax <= INT8_MAX:
            return "BIGINT", nullable
        return f"NUMERIC({max_digits},0)", nullable

    # --- NUMERIC(p,s) (decimal, incluindo colunas com formato misto) --------
    # Algumas colunas do ERP misturam "107" e "107.000" na mesma coluna
    # (mesma grandeza, formatacao inconsistente). Tratei como NUMERIC
    # sempre que TODOS os valores sao numericos (inteiros e/ou decimais),
    # o que ja cobre o caso 100% decimal tambem.
    if not forced_text and all(NUMERIC_ANY_RE.match(v) for v in stripped):
        max_int_len, max_dec_len = 0, 0
        for v in stripped:
            v_abs = v.lstrip("-")
            if "." in v_abs:
                int_part, dec_part = v_abs.split(".")
            else:
                int_part, dec_part = v_abs, ""
            max_int_len = max(max_int_len, len(int_part))
            max_dec_len = max(max_dec_len, len(dec_part))
        scale = max_dec_len
        precision = max_int_len + max_dec_len + 2  # margem de seguranca
        return f"NUMERIC({precision},{scale})", nullable

    # --- TEXTO (VARCHAR/TEXT) -----------------------------------------------
    max_len = max(len(v) for v in stripped)
    if max_len > TEXT_THRESHOLD:
        return "TEXT", nullable
    bucket = pick_varchar_bucket(max_len)
    if bucket is None:
        return "TEXT", nullable
    return f"VARCHAR({bucket})", nullable


# --------------------------------------------------------------------------
# CHAVES PRIMARIAS E ESTRANGEIRAS
# --------------------------------------------------------------------------

def singularize(word):
    """Singulariza um nome de tabela em ingles de forma simples (regras
    cobrem os casos observados nos arquivos do desafio)."""
    if word.endswith(("sses", "ches", "shes", "xes")):
        return word[:-2]
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("s"):
        return word[:-1]
    return word


def build_table_singulars(table_names):
    """Mapa singular -> nome_real_da_tabela, para resolucao de FKs."""
    mapping = {}
    for table in table_names:
        mapping[singularize(table)] = table
    return mapping


def resolve_foreign_key(column_name, table_singulars, aliases):
    """Dado o nome de uma coluna terminada em "_id", tenta descobrir a
    tabela referenciada. Retorna o nome da tabela ou None se nao resolver
    (nesse caso, nenhuma FK e' criada para a coluna, e um comentario e'
    emitido no SQL para revisao manual)."""
    if column_name == "id" or not column_name.endswith("_id"):
        return None
    base = column_name[:-3]  # remove sufixo "_id"

    # 1) correspondencia exata com o singular de alguma tabela
    if base in table_singulars:
        return table_singulars[base]

    # 2) correspondencia exata com um apelido manual
    if base in aliases:
        return aliases[base]

    # 3) o "miolo" termina com "_<singular_da_tabela>" (ex.: primary_location)
    for sing in sorted(table_singulars, key=len, reverse=True):
        if base.endswith("_" + sing):
            return table_singulars[sing]

    # 4) o "miolo" termina com "_<apelido>" (ex.: exchange_variant)
    for alias, table in aliases.items():
        if base.endswith("_" + alias):
            return table

    return None


# --------------------------------------------------------------------------
# GERACAO DE SQL
# --------------------------------------------------------------------------

def quote_ident(name):
    """Identificador seguro para PostgreSQL (minusculo, sem necessidade de
    aspas na pratica, mas mantemos a funcao central caso o padrao mude)."""
    return name


def build_table_ddl(table_name, header, col_types, pk_columns):
    lines = [f"CREATE TABLE {quote_ident(table_name)} ("]
    col_defs = []
    for col in header:
        sql_type, nullable = col_types[col]
        null_clause = "" if nullable else " NOT NULL"
        col_defs.append(f"    {quote_ident(col)} {sql_type}{null_clause}")

    if pk_columns:
        pk_clause = ", ".join(quote_ident(c) for c in pk_columns)
        col_defs.append(f"    PRIMARY KEY ({pk_clause})")

    lines.append(",\n".join(col_defs))
    lines.append(");")
    return "\n".join(lines)


def build_foreign_keys_ddl(table_name, header, table_singulars, aliases,
                            pk_columns, unresolved_log):
    """Gera as instrucoes ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY
    para as colunas "_id" da tabela (exceto a propria PK simples "id")."""
    statements = []
    for col in header:
        if col == "id":
            continue
        if not col.endswith("_id"):
            continue
        ref_table = resolve_foreign_key(col, table_singulars, aliases)
        if ref_table is None:
            unresolved_log.append((table_name, col))
            continue
        constraint_name = f"fk_{table_name}_{col}"
        statements.append(
            f"ALTER TABLE {quote_ident(table_name)} "
            f"ADD CONSTRAINT {constraint_name} "
            f"FOREIGN KEY ({quote_ident(col)}) "
            f"REFERENCES {quote_ident(ref_table)} (id);"
        )
    return statements


def generate_schema(input_dir, output_path):
    csv_files = list_csv_files(input_dir)
    if not csv_files:
        print(f"Nenhum arquivo .csv encontrado em: {input_dir}", file=sys.stderr)
        sys.exit(1)

    table_names = [os.path.splitext(f)[0] for f in csv_files]
    table_singulars = build_table_singulars(table_names)

    create_statements = []
    alter_statements = []
    unresolved_log = []

    for csv_file, table_name in zip(csv_files, table_names):
        filepath = os.path.join(input_dir, csv_file)
        header, columns = read_csv(filepath)

        # 1) inferir tipo de cada coluna a partir do conteudo
        col_types = {}
        for col in header:
            col_types[col] = infer_column_type(col, columns[col])

        # 2) chave primaria
        if "id" in header:
            pk_columns = ["id"]
            # PK nunca deve aceitar NULL, garantimos aqui mesmo que os
            # dados nao tenham vazios (defensivo).
            sql_type, _ = col_types["id"]
            col_types["id"] = (sql_type, False)
        else:
            pk_columns = [c for c in header if c.endswith("_id")]
            for c in pk_columns:
                sql_type, _ = col_types[c]
                col_types[c] = (sql_type, False)

        create_statements.append(
            f"-- Tabela gerada a partir de: {csv_file}\n"
            + build_table_ddl(table_name, header, col_types, pk_columns)
        )

        # 3) chaves estrangeiras (emitidas em bloco separado no final)
        fks = build_foreign_keys_ddl(
            table_name, header, table_singulars, ALIASES, pk_columns,
            unresolved_log,
        )
        alter_statements.extend(fks)

    # ------------------------------------------------------------------
    # Monta o arquivo final
    # ------------------------------------------------------------------
    header_comment = (
        "-- ============================================================\n"
        "-- schema.sql\n"
        "-- Gerado automaticamente por schema_generator.py\n"
        "-- Fonte: arquivos CSV do ERP da LH Nautical\n"
        "-- Banco de destino: PostgreSQL\n"
        "--\n"
        "-- Estrutura do arquivo:\n"
        "--   1) CREATE TABLE para cada CSV (colunas + PRIMARY KEY)\n"
        "--   2) ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY\n"
        "--      (emitidas depois de todas as tabelas existirem, para nao\n"
        "--       depender de ordem topologica de criacao)\n"
        "-- ============================================================\n"
    )

    parts = [header_comment]
    parts.append("-- ================= PARTE 1: TABELAS =================\n")
    parts.append("\n\n".join(create_statements))
    parts.append("\n\n-- ============ PARTE 2: CHAVES ESTRANGEIRAS ============\n")
    if alter_statements:
        parts.append("\n".join(alter_statements))
    else:
        parts.append("-- Nenhuma chave estrangeira foi resolvida.")

    if unresolved_log:
        parts.append(
            "\n\n-- ============ COLUNAS *_id SEM FK RESOLVIDA ============\n"
            "-- Revisar manualmente (ex.: chaves polimorficas como\n"
            "-- stock_movements.reference_id, que aponta para tabelas\n"
            "-- diferentes dependendo do valor de reference_table):"
        )
        for table_name, col in unresolved_log:
            parts.append(f"-- {table_name}.{col}")

    final_sql = "\n".join(parts) + "\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_sql)

    # Resumo no console, para conferencia rapida
    print(f"{len(csv_files)} tabelas processadas a partir de: {input_dir}")
    print(f"{len(alter_statements)} chaves estrangeiras resolvidas automaticamente.")
    if unresolved_log:
        print(f"{len(unresolved_log)} colunas *_id nao resolvidas (ver comentarios no final do schema.sql):")
        for table_name, col in unresolved_log:
            print(f"  - {table_name}.{col}")
    print(f"Arquivo gerado: {output_path}")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Gera um schema.sql (PostgreSQL) a partir de uma pasta de CSVs."
    )
    parser.add_argument(
        "--input-dir", "-i", default="lh_nautical_csv",
        help="Diretorio contendo os arquivos .csv (padrao: lh_nautical_csv)",
    )
    parser.add_argument(
        "--output", "-o", default="schema.sql",
        help="Caminho do arquivo .sql de saida (padrao: schema.sql)",
    )
    args = parser.parse_args()
    generate_schema(args.input_dir, args.output)


if __name__ == "__main__":
    main()