CREATE DATABASE IF NOT EXISTS shop;

DROP TABLE IF EXISTS shop.products;

CREATE TABLE shop.products (
    id INT AUTO_INCREMENT PRIMARY KEY, 
    name VARCHAR(50), 
    brand VARCHAR(30),
    category VARCHAR(30),
    stock INT, 
    price INT
);

-- 가격과 재고를 랜덤하게 설정
INSERT INTO shop.products (name, brand, category, stock, price) VALUES ('MacBook Pro', 'Apple', 'PC', 12, 3200000);
INSERT INTO shop.products (name, brand, category, stock, price) VALUES ('MacBook Air', 'Apple', 'PC', 3, 1850000);
INSERT INTO shop.products (name, brand, category, stock, price) VALUES ('iPhone 15', 'Apple', 'Smartphone', 25, 1450000);
INSERT INTO shop.products (name, brand, category, stock, price) VALUES ('iPhone 14', 'Apple', 'Smartphone', 8, 1150000);
INSERT INTO shop.products (name, brand, category, stock, price) VALUES ('iPhone 13', 'Apple', 'Smartphone', 0, 950000);
INSERT INTO shop.products (name, brand, category, stock, price) VALUES ('Galaxy S24', 'Samsung', 'Smartphone', 42, 1300000);
INSERT INTO shop.products (name, brand, category, stock, price) VALUES ('Galaxy S23', 'Samsung', 'Smartphone', 15, 980000);
INSERT INTO shop.products (name, brand, category, stock, price) VALUES ('Galaxy S22', 'Samsung', 'Smartphone', 0, 750000);
INSERT INTO shop.products (name, brand, category, stock, price) VALUES ('Galaxy Book S9', 'Samsung', 'PC', 7, 2100000);

