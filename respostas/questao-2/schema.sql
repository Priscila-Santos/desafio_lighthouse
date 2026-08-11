-- ============================================================
-- schema.sql
-- Gerado automaticamente por schema_generator.py
-- Fonte: arquivos CSV do ERP da LH Nautical
-- Banco de destino: PostgreSQL
--
-- Estrutura do arquivo:
--   1) CREATE TABLE para cada CSV (colunas + PRIMARY KEY)
--   2) ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY
--      (emitidas depois de todas as tabelas existirem, para nao
--       depender de ordem topologica de criacao)
-- ============================================================

-- ================= PARTE 1: TABELAS =================

-- Tabela gerada a partir de: addresses.csv
CREATE TABLE addresses (
    id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    address_type VARCHAR(10) NOT NULL,
    postal_code VARCHAR(10) NOT NULL,
    street VARCHAR(50) NOT NULL,
    number INTEGER NOT NULL,
    complement VARCHAR(10),
    district VARCHAR(50) NOT NULL,
    city VARCHAR(30) NOT NULL,
    state VARCHAR(10) NOT NULL,
    country VARCHAR(10) NOT NULL,
    is_primary BOOLEAN NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: attributes.csv
CREATE TABLE attributes (
    id INTEGER NOT NULL,
    name VARCHAR(10) NOT NULL,
    data_type VARCHAR(10) NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: brands.csv
CREATE TABLE brands (
    id INTEGER NOT NULL,
    name VARCHAR(20) NOT NULL,
    country VARCHAR(10),
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: categories.csv
CREATE TABLE categories (
    id INTEGER NOT NULL,
    name VARCHAR(20) NOT NULL,
    slug VARCHAR(20) NOT NULL,
    parent_category_id INTEGER,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: customers.csv
CREATE TABLE customers (
    id INTEGER NOT NULL,
    person_type VARCHAR(10) NOT NULL,
    legal_name VARCHAR(50) NOT NULL,
    trade_name VARCHAR(30),
    tax_id VARCHAR(20) NOT NULL,
    state_registration VARCHAR(10),
    email VARCHAR(50),
    phone VARCHAR(20),
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: employees.csv
CREATE TABLE employees (
    id INTEGER NOT NULL,
    full_name VARCHAR(30) NOT NULL,
    cpf VARCHAR(20) NOT NULL,
    email VARCHAR(50) NOT NULL,
    role VARCHAR(20) NOT NULL,
    primary_location_id INTEGER NOT NULL,
    hire_date DATE NOT NULL,
    termination_date DATE,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: fiscal_invoices.csv
CREATE TABLE fiscal_invoices (
    id INTEGER NOT NULL,
    order_id INTEGER NOT NULL,
    nfe_number VARCHAR(20) NOT NULL,
    nfe_access_key VARCHAR(50) NOT NULL,
    series INTEGER NOT NULL,
    issued_at TIMESTAMP NOT NULL,
    status VARCHAR(10) NOT NULL,
    total_amount NUMERIC(10,2) NOT NULL,
    xml_storage_uri VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: goods_receipt_items.csv
CREATE TABLE goods_receipt_items (
    id INTEGER NOT NULL,
    goods_receipt_id INTEGER NOT NULL,
    purchase_order_item_id INTEGER NOT NULL,
    quantity_received NUMERIC(7,3) NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: goods_receipts.csv
CREATE TABLE goods_receipts (
    id INTEGER NOT NULL,
    purchase_order_id INTEGER NOT NULL,
    received_by_employee_id INTEGER NOT NULL,
    received_at TIMESTAMP NOT NULL,
    notes VARCHAR(20),
    created_at TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: locations.csv
CREATE TABLE locations (
    id INTEGER NOT NULL,
    name VARCHAR(20) NOT NULL,
    location_type VARCHAR(10) NOT NULL,
    postal_code VARCHAR(10) NOT NULL,
    street VARCHAR(30) NOT NULL,
    number INTEGER NOT NULL,
    complement VARCHAR(10),
    district VARCHAR(30) NOT NULL,
    city VARCHAR(20) NOT NULL,
    state VARCHAR(10) NOT NULL,
    country VARCHAR(10) NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: order_items.csv
CREATE TABLE order_items (
    id INTEGER NOT NULL,
    order_id INTEGER NOT NULL,
    product_variant_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(8,2) NOT NULL,
    icms_rate NUMERIC(6,2) NOT NULL,
    ipi_rate NUMERIC(6,2) NOT NULL,
    line_total NUMERIC(9,2) NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: orders.csv
CREATE TABLE orders (
    id INTEGER NOT NULL,
    order_number VARCHAR(10) NOT NULL,
    channel VARCHAR(10) NOT NULL,
    customer_id INTEGER NOT NULL,
    salesperson_id INTEGER,
    location_id INTEGER NOT NULL,
    status VARCHAR(10) NOT NULL,
    subtotal NUMERIC(10,2) NOT NULL,
    discount_amount NUMERIC(9,2) NOT NULL,
    total NUMERIC(10,2) NOT NULL,
    placed_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: payments.csv
CREATE TABLE payments (
    id INTEGER NOT NULL,
    order_id INTEGER NOT NULL,
    method VARCHAR(20) NOT NULL,
    installments INTEGER NOT NULL,
    amount NUMERIC(10,2) NOT NULL,
    status VARCHAR(10) NOT NULL,
    paid_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: product_suppliers.csv
CREATE TABLE product_suppliers (
    product_variant_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    supplier_sku VARCHAR(20),
    last_quoted_cost NUMERIC(8,2) NOT NULL,
    lead_time_days INTEGER NOT NULL,
    is_preferred BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (product_variant_id, supplier_id)
);

-- Tabela gerada a partir de: product_variants.csv
CREATE TABLE product_variants (
    id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    sku VARCHAR(10) NOT NULL,
    barcode_ean VARCHAR(20),
    sale_price NUMERIC(8,2) NOT NULL,
    cost_price NUMERIC(8,2) NOT NULL,
    weight_kg NUMERIC(7,3) NOT NULL,
    icms_rate NUMERIC(6,2) NOT NULL,
    ipi_rate NUMERIC(6,2) NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: products.csv
CREATE TABLE products (
    id INTEGER NOT NULL,
    name VARCHAR(30) NOT NULL,
    description VARCHAR(50),
    brand_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    ncm_code VARCHAR(10) NOT NULL,
    unit_of_measure VARCHAR(10) NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: purchase_order_items.csv
CREATE TABLE purchase_order_items (
    id INTEGER NOT NULL,
    purchase_order_id INTEGER NOT NULL,
    product_variant_id INTEGER NOT NULL,
    quantity_ordered INTEGER NOT NULL,
    unit_cost NUMERIC(8,2) NOT NULL,
    line_total NUMERIC(10,2) NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: purchase_orders.csv
CREATE TABLE purchase_orders (
    id INTEGER NOT NULL,
    po_number VARCHAR(10) NOT NULL,
    supplier_id INTEGER NOT NULL,
    buyer_id INTEGER NOT NULL,
    destination_location_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    subtotal NUMERIC(10,2) NOT NULL,
    total NUMERIC(10,2) NOT NULL,
    placed_at TIMESTAMP NOT NULL,
    expected_delivery_at DATE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: return_items.csv
CREATE TABLE return_items (
    id INTEGER NOT NULL,
    return_id INTEGER NOT NULL,
    order_item_id INTEGER NOT NULL,
    quantity NUMERIC(7,3) NOT NULL,
    action VARCHAR(10) NOT NULL,
    exchange_variant_id INTEGER,
    unit_refund_amount NUMERIC(8,2) NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: returns.csv
CREATE TABLE returns (
    id INTEGER NOT NULL,
    return_number VARCHAR(10) NOT NULL,
    order_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    received_at_location_id INTEGER NOT NULL,
    status VARCHAR(10) NOT NULL,
    reason VARCHAR(50),
    total_refund_amount NUMERIC(9,2) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: stock_levels.csv
CREATE TABLE stock_levels (
    product_variant_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    quantity_on_hand NUMERIC(7,3) NOT NULL,
    reorder_point NUMERIC(12,2),
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (product_variant_id, location_id)
);

-- Tabela gerada a partir de: stock_movements.csv
CREATE TABLE stock_movements (
    id INTEGER NOT NULL,
    product_variant_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    movement_type VARCHAR(20) NOT NULL,
    quantity NUMERIC(8,3) NOT NULL,
    reference_table VARCHAR(20),
    reference_id INTEGER,
    employee_id INTEGER,
    notes VARCHAR(50),
    occurred_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: suppliers.csv
CREATE TABLE suppliers (
    id INTEGER NOT NULL,
    legal_name VARCHAR(30) NOT NULL,
    trade_name VARCHAR(20),
    country VARCHAR(10) NOT NULL,
    tax_id VARCHAR(20) NOT NULL,
    tax_id_type VARCHAR(10) NOT NULL,
    email VARCHAR(30) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    contact_name VARCHAR(30) NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
);

-- Tabela gerada a partir de: variant_attribute_values.csv
CREATE TABLE variant_attribute_values (
    product_variant_id INTEGER NOT NULL,
    attribute_id INTEGER NOT NULL,
    value VARCHAR(20) NOT NULL,
    PRIMARY KEY (product_variant_id, attribute_id)
);


-- ============ PARTE 2: CHAVES ESTRANGEIRAS ============

ALTER TABLE addresses ADD CONSTRAINT fk_addresses_customer_id FOREIGN KEY (customer_id) REFERENCES customers (id);
ALTER TABLE categories ADD CONSTRAINT fk_categories_parent_category_id FOREIGN KEY (parent_category_id) REFERENCES categories (id);
ALTER TABLE employees ADD CONSTRAINT fk_employees_primary_location_id FOREIGN KEY (primary_location_id) REFERENCES locations (id);
ALTER TABLE fiscal_invoices ADD CONSTRAINT fk_fiscal_invoices_order_id FOREIGN KEY (order_id) REFERENCES orders (id);
ALTER TABLE goods_receipt_items ADD CONSTRAINT fk_goods_receipt_items_goods_receipt_id FOREIGN KEY (goods_receipt_id) REFERENCES goods_receipts (id);
ALTER TABLE goods_receipt_items ADD CONSTRAINT fk_goods_receipt_items_purchase_order_item_id FOREIGN KEY (purchase_order_item_id) REFERENCES purchase_order_items (id);
ALTER TABLE goods_receipts ADD CONSTRAINT fk_goods_receipts_purchase_order_id FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders (id);
ALTER TABLE goods_receipts ADD CONSTRAINT fk_goods_receipts_received_by_employee_id FOREIGN KEY (received_by_employee_id) REFERENCES employees (id);
ALTER TABLE order_items ADD CONSTRAINT fk_order_items_order_id FOREIGN KEY (order_id) REFERENCES orders (id);
ALTER TABLE order_items ADD CONSTRAINT fk_order_items_product_variant_id FOREIGN KEY (product_variant_id) REFERENCES product_variants (id);
ALTER TABLE orders ADD CONSTRAINT fk_orders_customer_id FOREIGN KEY (customer_id) REFERENCES customers (id);
ALTER TABLE orders ADD CONSTRAINT fk_orders_salesperson_id FOREIGN KEY (salesperson_id) REFERENCES employees (id);
ALTER TABLE orders ADD CONSTRAINT fk_orders_location_id FOREIGN KEY (location_id) REFERENCES locations (id);
ALTER TABLE payments ADD CONSTRAINT fk_payments_order_id FOREIGN KEY (order_id) REFERENCES orders (id);
ALTER TABLE product_suppliers ADD CONSTRAINT fk_product_suppliers_product_variant_id FOREIGN KEY (product_variant_id) REFERENCES product_variants (id);
ALTER TABLE product_suppliers ADD CONSTRAINT fk_product_suppliers_supplier_id FOREIGN KEY (supplier_id) REFERENCES suppliers (id);
ALTER TABLE product_variants ADD CONSTRAINT fk_product_variants_product_id FOREIGN KEY (product_id) REFERENCES products (id);
ALTER TABLE products ADD CONSTRAINT fk_products_brand_id FOREIGN KEY (brand_id) REFERENCES brands (id);
ALTER TABLE products ADD CONSTRAINT fk_products_category_id FOREIGN KEY (category_id) REFERENCES categories (id);
ALTER TABLE purchase_order_items ADD CONSTRAINT fk_purchase_order_items_purchase_order_id FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders (id);
ALTER TABLE purchase_order_items ADD CONSTRAINT fk_purchase_order_items_product_variant_id FOREIGN KEY (product_variant_id) REFERENCES product_variants (id);
ALTER TABLE purchase_orders ADD CONSTRAINT fk_purchase_orders_supplier_id FOREIGN KEY (supplier_id) REFERENCES suppliers (id);
ALTER TABLE purchase_orders ADD CONSTRAINT fk_purchase_orders_buyer_id FOREIGN KEY (buyer_id) REFERENCES employees (id);
ALTER TABLE purchase_orders ADD CONSTRAINT fk_purchase_orders_destination_location_id FOREIGN KEY (destination_location_id) REFERENCES locations (id);
ALTER TABLE return_items ADD CONSTRAINT fk_return_items_return_id FOREIGN KEY (return_id) REFERENCES returns (id);
ALTER TABLE return_items ADD CONSTRAINT fk_return_items_order_item_id FOREIGN KEY (order_item_id) REFERENCES order_items (id);
ALTER TABLE return_items ADD CONSTRAINT fk_return_items_exchange_variant_id FOREIGN KEY (exchange_variant_id) REFERENCES product_variants (id);
ALTER TABLE returns ADD CONSTRAINT fk_returns_order_id FOREIGN KEY (order_id) REFERENCES orders (id);
ALTER TABLE returns ADD CONSTRAINT fk_returns_customer_id FOREIGN KEY (customer_id) REFERENCES customers (id);
ALTER TABLE returns ADD CONSTRAINT fk_returns_received_at_location_id FOREIGN KEY (received_at_location_id) REFERENCES locations (id);
ALTER TABLE stock_levels ADD CONSTRAINT fk_stock_levels_product_variant_id FOREIGN KEY (product_variant_id) REFERENCES product_variants (id);
ALTER TABLE stock_levels ADD CONSTRAINT fk_stock_levels_location_id FOREIGN KEY (location_id) REFERENCES locations (id);
ALTER TABLE stock_movements ADD CONSTRAINT fk_stock_movements_product_variant_id FOREIGN KEY (product_variant_id) REFERENCES product_variants (id);
ALTER TABLE stock_movements ADD CONSTRAINT fk_stock_movements_location_id FOREIGN KEY (location_id) REFERENCES locations (id);
ALTER TABLE stock_movements ADD CONSTRAINT fk_stock_movements_employee_id FOREIGN KEY (employee_id) REFERENCES employees (id);
ALTER TABLE variant_attribute_values ADD CONSTRAINT fk_variant_attribute_values_product_variant_id FOREIGN KEY (product_variant_id) REFERENCES product_variants (id);
ALTER TABLE variant_attribute_values ADD CONSTRAINT fk_variant_attribute_values_attribute_id FOREIGN KEY (attribute_id) REFERENCES attributes (id);


-- ============ COLUNAS *_id SEM FK RESOLVIDA ============
-- Revisar manualmente (ex.: chaves polimorficas como
-- stock_movements.reference_id, que aponta para tabelas
-- diferentes dependendo do valor de reference_table):
-- customers.tax_id
-- stock_movements.reference_id
-- suppliers.tax_id
