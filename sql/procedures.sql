-- ============================================================
-- ShopAPI — хранимые процедуры (7 основных + 6 вспомогательных)
-- Запуск: mysql -u root -p < sql/procedures.sql
--
-- OUT-параметры: sp_product_add, sp_order_create, sp_order_add_item.
-- Из Python они читаются через сессионные переменные @_out_N —
-- MySQL не принимает литералы/плейсхолдеры на месте OUT (ошибка 1414).
-- ============================================================

USE shop_django;

DELIMITER //

-- ---------- Задание 1: список товаров ----------
DROP PROCEDURE IF EXISTS sp_products_list//
CREATE PROCEDURE sp_products_list ()
BEGIN
    SELECT p.product_id, p.name, c.name AS category, p.price, p.stock
      FROM products p
      JOIN categories c ON c.category_id = p.category_id
     ORDER BY p.name;
END //

-- ---------- Задание 2: добавить товар (OUT p_new_id) ----------
DROP PROCEDURE IF EXISTS sp_product_add//
CREATE PROCEDURE sp_product_add (
    IN p_name VARCHAR(100),
    IN p_category_id INT,
    IN p_price DECIMAL(10,2),
    IN p_stock INT,
    OUT p_new_id INT
)
BEGIN
    INSERT INTO products (name, category_id, price, stock)
    VALUES (p_name, p_category_id, p_price, p_stock);
    SET p_new_id = LAST_INSERT_ID();
END //

-- ---------- Задание 3: обновить цену ----------
DROP PROCEDURE IF EXISTS sp_product_update_price//
CREATE PROCEDURE sp_product_update_price (
    IN p_product_id INT,
    IN p_new_price DECIMAL(10,2)
)
BEGIN
    UPDATE products SET price = p_new_price WHERE product_id = p_product_id;
END //

-- ---------- Задание 4a: создать пустой заказ (OUT p_order_id) ----------
DROP PROCEDURE IF EXISTS sp_order_create//
CREATE PROCEDURE sp_order_create (
    IN p_customer_id INT,
    OUT p_order_id INT
)
BEGIN
    INSERT INTO orders (customer_id, created_at, total)
    VALUES (p_customer_id, NOW(), 0);
    SET p_order_id = LAST_INSERT_ID();
END //

-- ---------- Задание 4b: добавить позицию (OUT p_success, OUT p_message) ----------
-- Транзакция + SELECT ... FOR UPDATE защищают от двойного списания остатка.
DROP PROCEDURE IF EXISTS sp_order_add_item//
CREATE PROCEDURE sp_order_add_item (
    IN p_order_id INT,
    IN p_product_id INT,
    IN p_quantity INT,
    OUT p_success TINYINT,
    OUT p_message VARCHAR(255)
)
BEGIN
    DECLARE v_stock INT;
    DECLARE v_price DECIMAL(10,2);
    DECLARE v_order_exists INT DEFAULT 0;

    -- EXIT HANDLER: любое исключение внутри процедуры откатывает
    -- транзакцию и возвращает ошибку через OUT-параметры.
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_success = 0;
        SET p_message = 'Ошибка при добавлении позиции';
    END;

    SET p_success = 0;
    SET p_message = '';

    IF p_quantity IS NULL OR p_quantity <= 0 THEN
        SET p_message = 'Количество должно быть больше нуля';
    ELSE
        START TRANSACTION;

        -- Блокируем строку товара до конца транзакции: параллельный заказ
        -- не сможет прочитать тот же остаток и списать его второй раз.
        SELECT stock, price INTO v_stock, v_price
          FROM products WHERE product_id = p_product_id FOR UPDATE;

        SELECT COUNT(*) INTO v_order_exists
          FROM orders WHERE order_id = p_order_id;

        IF v_stock IS NULL THEN
            SET p_message = 'Товар не найден';
            ROLLBACK;
        ELSEIF v_order_exists = 0 THEN
            SET p_message = 'Заказ не найден';
            ROLLBACK;
        ELSEIF v_stock < p_quantity THEN
            SET p_message = CONCAT('Недостаточно товара. Доступно: ', v_stock);
            ROLLBACK;
        ELSE
            INSERT INTO order_items (order_id, product_id, quantity, price)
            VALUES (p_order_id, p_product_id, p_quantity, v_price)
            ON DUPLICATE KEY UPDATE quantity = quantity + p_quantity;

            UPDATE products SET stock = stock - p_quantity
             WHERE product_id = p_product_id;

            UPDATE orders o
               SET total = (SELECT SUM(quantity * price)
                              FROM order_items WHERE order_id = p_order_id)
             WHERE o.order_id = p_order_id;

            SET p_success = 1;
            SET p_message = 'OK';
            COMMIT;
        END IF;
    END IF;
END //

-- ---------- Задание 5: заказы клиента ----------
DROP PROCEDURE IF EXISTS sp_customer_orders//
CREATE PROCEDURE sp_customer_orders (IN p_customer_id INT)
BEGIN
    SELECT o.order_id, o.created_at, o.total,
           fn_customer_avg_check(o.customer_id) AS avg_check
      FROM orders o
     WHERE o.customer_id = p_customer_id
     ORDER BY o.created_at DESC, o.order_id DESC;
END //

-- ---------- Задание 6: статистика по категориям ----------
DROP PROCEDURE IF EXISTS sp_category_stats//
CREATE PROCEDURE sp_category_stats ()
BEGIN
    SELECT c.name AS category,
           COUNT(DISTINCT p.product_id) AS products_count,
           IFNULL(SUM(oi.quantity), 0)  AS sold_units,
           IFNULL(SUM(oi.quantity * oi.price), 0) AS revenue
      FROM categories c
      LEFT JOIN products    p  ON p.category_id  = c.category_id
      LEFT JOIN order_items oi ON oi.product_id = p.product_id
     GROUP BY c.category_id, c.name
     ORDER BY revenue DESC;
END //

-- ---------- Вспомогательные: справочники для выпадающих списков ----------
DROP PROCEDURE IF EXISTS sp_categories_list//
CREATE PROCEDURE sp_categories_list ()
BEGIN
    SELECT category_id, name FROM categories ORDER BY name;
END //

DROP PROCEDURE IF EXISTS sp_customers_list//
CREATE PROCEDURE sp_customers_list ()
BEGIN
    SELECT customer_id, first_name, last_name, email, age
      FROM customers ORDER BY last_name, first_name;
END //

DROP PROCEDURE IF EXISTS sp_customer_get//
CREATE PROCEDURE sp_customer_get (IN p_customer_id INT)
BEGIN
    SELECT customer_id, first_name, last_name, email, age
      FROM customers WHERE customer_id = p_customer_id;
END //

-- ---------- Вспомогательные: карточки товара и заказа ----------
DROP PROCEDURE IF EXISTS sp_product_get//
CREATE PROCEDURE sp_product_get (IN p_product_id INT)
BEGIN
    SELECT product_id, name, category_id, price, stock
      FROM products WHERE product_id = p_product_id;
END //

DROP PROCEDURE IF EXISTS sp_order_get//
CREATE PROCEDURE sp_order_get (IN p_order_id INT)
BEGIN
    SELECT o.order_id, o.customer_id,
           CONCAT(c.first_name, ' ', c.last_name) AS customer_name,
           o.created_at, o.total
      FROM orders o
      JOIN customers c ON c.customer_id = o.customer_id
     WHERE o.order_id = p_order_id;
END //

DROP PROCEDURE IF EXISTS sp_order_items//
CREATE PROCEDURE sp_order_items (IN p_order_id INT)
BEGIN
    SELECT oi.product_id, p.name, oi.quantity, oi.price,
           oi.quantity * oi.price AS subtotal
      FROM order_items oi
      JOIN products p ON p.product_id = oi.product_id
     WHERE oi.order_id = p_order_id
     ORDER BY p.name;
END //

DELIMITER ;