-- ====================================================================
-- Savyant Systems: Sales Order & Inventory Management System
-- Database Schema Definition (MySQL 8.0+)
-- Complies with Part 3 Database Design Specifications
-- ====================================================================

DROP DATABASE IF EXISTS savyant_sales_db;
CREATE DATABASE savyant_sales_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE savyant_sales_db;

-- --------------------------------------------------------------------
-- 1. Entity: User
-- Minimum fields: ID, name, unique email, password hash, role
-- --------------------------------------------------------------------
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'sales') NOT NULL DEFAULT 'sales',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_email (email),
    INDEX idx_user_role (role)
) ENGINE=InnoDB;

-- --------------------------------------------------------------------
-- 2. Entity: Customer
-- Minimum fields: ID, name, email, mobile, city, active/inactive status
-- --------------------------------------------------------------------
CREATE TABLE customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL,
    mobile VARCHAR(20) NOT NULL,
    city VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_customer_name (name),
    INDEX idx_customer_email (email),
    INDEX idx_customer_mobile (mobile),
    INDEX idx_customer_status (is_active)
) ENGINE=InnoDB;

-- --------------------------------------------------------------------
-- 3. Entity: Product
-- Minimum fields: ID, unique product code, name, category, price, stock quantity, active/inactive status
-- Money: DECIMAL(12, 2)
-- Constraints: Price >= 0, Stock >= 0
-- --------------------------------------------------------------------
CREATE TABLE products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    category VARCHAR(100) NOT NULL,
    price DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    stock_quantity INT NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT chk_product_price_non_negative CHECK (price >= 0.00),
    CONSTRAINT chk_product_stock_non_negative CHECK (stock_quantity >= 0),
    INDEX idx_product_code (product_code),
    INDEX idx_product_name (name),
    INDEX idx_product_category (category),
    INDEX idx_product_status (is_active)
) ENGINE=InnoDB;

-- --------------------------------------------------------------------
-- 4. Entity: Sales Order
-- Minimum fields: ID, unique order number, customer, order date, status, discount percentage,
-- subtotal, discount amount, grand total, created by
-- Constraints: Discount percentage between 0 and 20
-- --------------------------------------------------------------------
CREATE TABLE sales_orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_number VARCHAR(50) NOT NULL UNIQUE,
    customer_id INT NOT NULL,
    order_date DATE NOT NULL,
    status ENUM('draft', 'confirmed', 'cancelled') NOT NULL DEFAULT 'draft',
    discount_percentage DECIMAL(5, 2) NOT NULL DEFAULT 0.00,
    subtotal DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    discount_amount DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    grand_total DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    created_by_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_sales_order_customer FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT,
    CONSTRAINT fk_sales_order_created_by FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT chk_discount_percentage_range CHECK (discount_percentage >= 0.00 AND discount_percentage <= 20.00),
    INDEX idx_order_number (order_number),
    INDEX idx_order_date_status (order_date, status),
    INDEX idx_order_customer (customer_id),
    INDEX idx_order_created_by (created_by_id)
) ENGINE=InnoDB;

-- --------------------------------------------------------------------
-- 5. Entity: Sales Order Item
-- Minimum fields: ID, sales order, product, quantity, rate, amount
-- Constraints: quantity >= 1, rate >= 0.00, unique(order, product)
-- --------------------------------------------------------------------
CREATE TABLE sales_order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sales_order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    rate DECIMAL(12, 2) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    CONSTRAINT fk_order_item_sales_order FOREIGN KEY (sales_order_id) REFERENCES sales_orders(id) ON DELETE CASCADE,
    CONSTRAINT fk_order_item_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
    CONSTRAINT chk_item_quantity_positive CHECK (quantity >= 1),
    CONSTRAINT chk_item_rate_non_negative CHECK (rate >= 0.00),
    CONSTRAINT uq_order_product UNIQUE (sales_order_id, product_id),
    INDEX idx_order_items_product (product_id)
) ENGINE=InnoDB;

-- --------------------------------------------------------------------
-- 6. Entity: Stock Movement
-- Minimum fields: ID, product, movement type, quantity change, related order, reason, created by, timestamp
-- --------------------------------------------------------------------
CREATE TABLE stock_movements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    movement_type ENUM('OPENING_STOCK', 'ADJUSTMENT', 'ORDER_CONFIRM', 'ORDER_CANCEL') NOT NULL,
    quantity_change INT NOT NULL,
    related_order_id INT NULL,
    reason TEXT NOT NULL,
    created_by_id INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_stock_movement_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_movement_order FOREIGN KEY (related_order_id) REFERENCES sales_orders(id) ON DELETE SET NULL,
    CONSTRAINT fk_stock_movement_user FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE RESTRICT,
    INDEX idx_stock_product_time (product_id, timestamp),
    INDEX idx_stock_type_time (movement_type, timestamp)
) ENGINE=InnoDB;

-- ====================================================================
-- Sample Data Inserts
-- ====================================================================

-- Users (Passwords hashed using PBKDF2 / SHA256 for standard Django authentication)
INSERT INTO users (id, name, email, password_hash, role) VALUES
(1, 'System Administrator', 'admin@savyant.com', 'pbkdf2_sha256$870000$dummy$hash...', 'admin'),
(2, 'Rahul Sharma', 'sales1@savyant.com', 'pbkdf2_sha256$870000$dummy$hash...', 'sales'),
(3, 'Priya Patel', 'sales2@savyant.com', 'pbkdf2_sha256$870000$dummy$hash...', 'sales');

-- Customers
INSERT INTO customers (id, name, email, mobile, city, is_active) VALUES
(1, 'Apex Enterprises', 'contact@apex.com', '+91-9876543210', 'Mumbai', TRUE),
(2, 'Bharat Tech Traders', 'sales@bharattech.in', '+91-9876543211', 'Delhi', TRUE),
(3, 'Crestline Solutions', 'info@crestline.org', '+91-9876543212', 'Bengaluru', TRUE),
(4, 'Delta Hardware Store', 'orders@deltahw.com', '+91-9876543213', 'Pune', TRUE),
(5, 'Echo Digital Corp', 'support@echodigital.in', '+91-9876543214', 'Hyderabad', FALSE),
(6, 'Never Ordered Corp', 'never@ordered.com', '+91-9876543215', 'Kolkata', TRUE);

-- Products
INSERT INTO products (id, product_code, name, category, price, stock_quantity, is_active) VALUES
(1, 'PRD-001', 'Mechanical Keyboard', 'Accessories', 1500.00, 33, TRUE),
(2, 'PRD-002', 'Optical Mouse', 'Accessories', 500.00, 57, TRUE),
(3, 'PRD-003', 'USB-C Multiport Hub', 'Cables & Adapters', 1200.00, 18, TRUE),
(4, 'PRD-004', '27-inch IPS Monitor', 'Displays', 18500.00, 7, TRUE),
(5, 'PRD-005', 'Wireless Noise-Canceling Headset', 'Audio', 3200.00, 5, TRUE),
(6, 'PRD-006', 'Desk Mat XL', 'Accessories', 650.00, 45, TRUE),
(7, 'PRD-007', 'Legacy VGA Cable', 'Cables & Adapters', 200.00, 0, FALSE);

-- Sales Orders
INSERT INTO sales_orders (id, order_number, customer_id, order_date, status, discount_percentage, subtotal, discount_amount, grand_total, created_by_id) VALUES
(1, 'SO-20261109-0001', 1, '2026-11-09', 'confirmed', 10.00, 4500.00, 450.00, 4050.00, 2),
(2, 'SO-20261109-0002', 2, '2026-11-09', 'confirmed', 5.00, 20900.00, 1045.00, 19855.00, 3),
(3, 'SO-20261109-0003', 3, '2026-11-09', 'draft', 0.00, 4250.00, 0.00, 4250.00, 2);

-- Order Items
INSERT INTO sales_order_items (id, sales_order_id, product_id, quantity, rate, amount) VALUES
(1, 1, 1, 2, 1500.00, 3000.00),
(2, 1, 2, 3, 500.00, 1500.00),
(3, 2, 4, 1, 18500.00, 18500.00),
(4, 2, 3, 2, 1200.00, 2400.00),
(5, 3, 6, 5, 650.00, 3250.00),
(6, 3, 2, 2, 500.00, 1000.00);

-- Stock Movements
INSERT INTO stock_movements (id, product_id, movement_type, quantity_change, related_order_id, reason, created_by_id) VALUES
(1, 1, 'OPENING_STOCK', 35, NULL, 'Initial Opening Stock', 1),
(2, 2, 'OPENING_STOCK', 60, NULL, 'Initial Opening Stock', 1),
(3, 1, 'ORDER_CONFIRM', -2, 1, 'Order SO-20261109-0001 confirmed', 2),
(4, 2, 'ORDER_CONFIRM', -3, 1, 'Order SO-20261109-0001 confirmed', 2),
(5, 4, 'ORDER_CONFIRM', -1, 2, 'Order SO-20261109-0002 confirmed', 3),
(6, 3, 'ORDER_CONFIRM', -2, 2, 'Order SO-20261109-0002 confirmed', 3);
