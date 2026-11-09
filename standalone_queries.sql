-- ====================================================================
-- Savyant Systems: Sales Order & Inventory Management System
-- Part 9: Standalone SQL Queries
-- Database Engine: MySQL 8.0+
-- ====================================================================

-- --------------------------------------------------------------------
-- Query 1: Top three customers by Confirmed order grand total
-- Explanation: Groups by customer, filters strictly for Confirmed orders,
-- sums the final order grand_total (after discount), and takes top 3.
-- --------------------------------------------------------------------
SELECT 
    c.id AS customer_id,
    c.name AS customer_name,
    c.email AS customer_email,
    COUNT(so.id) AS confirmed_orders_count,
    ROUND(SUM(so.grand_total), 2) AS total_confirmed_sales
FROM 
    customers c
INNER JOIN 
    sales_orders so ON c.id = so.customer_id
WHERE 
    so.status = 'confirmed'
GROUP BY 
    c.id, c.name, c.email
ORDER BY 
    total_confirmed_sales DESC
LIMIT 3;


-- --------------------------------------------------------------------
-- Query 2: Top three products by quantity sold in Confirmed orders
-- Explanation: Joins order items with confirmed orders, aggregates total
-- units sold per product, and orders descending, limiting to 3.
-- --------------------------------------------------------------------
SELECT 
    p.id AS product_id,
    p.product_code,
    p.name AS product_name,
    p.category,
    SUM(soi.quantity) AS total_quantity_sold,
    ROUND(SUM(soi.amount), 2) AS gross_sales_value
FROM 
    products p
INNER JOIN 
    sales_order_items soi ON p.id = soi.product_id
INNER JOIN 
    sales_orders so ON soi.sales_order_id = so.id
WHERE 
    so.status = 'confirmed'
GROUP BY 
    p.id, p.product_code, p.name, p.category
ORDER BY 
    total_quantity_sold DESC
LIMIT 3;


-- --------------------------------------------------------------------
-- Query 3: Customers who have never placed any order
-- Explanation: Uses LEFT JOIN from customers to sales_orders and filters
-- where sales_orders.id IS NULL (or alternatively NOT EXISTS).
-- Returns all registered customers who have 0 orders in the system.
-- --------------------------------------------------------------------
SELECT 
    c.id AS customer_id,
    c.name AS customer_name,
    c.email,
    c.mobile,
    c.city,
    c.is_active
FROM 
    customers c
LEFT JOIN 
    sales_orders so ON c.id = so.customer_id
WHERE 
    so.id IS NULL
ORDER BY 
    c.name ASC;


-- --------------------------------------------------------------------
-- Query 4: Month-wise Confirmed sales totals, grouped by year and month
-- Explanation: Extracts YEAR and MONTH from order_date, restricts to Confirmed
-- status, and aggregates total order count, gross subtotal, total discount,
-- and net grand total.
-- --------------------------------------------------------------------
SELECT 
    YEAR(so.order_date) AS sales_year,
    MONTH(so.order_date) AS sales_month,
    DATE_FORMAT(so.order_date, '%Y-%m') AS year_month,
    COUNT(so.id) AS confirmed_order_count,
    ROUND(SUM(so.subtotal), 2) AS total_subtotal,
    ROUND(SUM(so.discount_amount), 2) AS total_discount_given,
    ROUND(SUM(so.grand_total), 2) AS total_confirmed_revenue
FROM 
    sales_orders so
WHERE 
    so.status = 'confirmed'
GROUP BY 
    YEAR(so.order_date),
    MONTH(so.order_date),
    DATE_FORMAT(so.order_date, '%Y-%m')
ORDER BY 
    sales_year DESC,
    sales_month DESC;


-- --------------------------------------------------------------------
-- Query 5: Products below a supplied stock threshold (e.g. threshold = 10)
-- Explanation: Parameterized stock query filtering active products whose
-- current stock_quantity is strictly less than the given threshold.
-- (Replace :threshold with desired parameter value, default 10)
-- --------------------------------------------------------------------
SET @stock_threshold = 10;

SELECT 
    p.id AS product_id,
    p.product_code,
    p.name AS product_name,
    p.category,
    p.price,
    p.stock_quantity,
    p.is_active
FROM 
    products p
WHERE 
    p.stock_quantity < @stock_threshold
    AND p.is_active = TRUE
ORDER BY 
    p.stock_quantity ASC;
