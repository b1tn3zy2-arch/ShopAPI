-- ============================================================
-- ShopAPI — тестовые данные
-- Запуск: mysql -u root -p < sql/seed.sql
-- Порядок: schema.sql -> functions.sql -> procedures.sql -> seed.sql
-- ============================================================

USE shop_django;

SET NAMES utf8mb4;

INSERT INTO categories (name) VALUES
('Электроника'),
('Книги'),
('Одежда');

INSERT INTO products (name, category_id, price, stock) VALUES
('Смартфон',       1, 29990.00, 15),
('Ноутбук',        1, 75990.00, 7),
('Роман «1984»',   2,   890.00, 40),
('Футболка',       3,  1500.00, 25);

INSERT INTO customers (first_name, last_name, email, age) VALUES
('Иван',  'Иванов',  'ivanov@example.com',  25),
('Анна',  'Петрова', 'petrova@example.com', 62),
('Пётр',  'Сидоров', 'sidorov@example.com', 17);

-- Демонстрационный заказ: позиции + корректный итог.
-- Остатки списываются вручную, чтобы seed оставался идемпотентным.
INSERT INTO orders (order_id, customer_id, created_at, total) VALUES
(1, 1, NOW(), 38880.00);

INSERT INTO order_items (order_id, product_id, quantity, price) VALUES
(1, 1, 1, 29990.00),
(1, 3, 10, 890.00);

UPDATE products SET stock = stock - 1  WHERE product_id = 1;
UPDATE products SET stock = stock - 10 WHERE product_id = 3;