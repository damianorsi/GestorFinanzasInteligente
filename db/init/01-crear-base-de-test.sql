-- Base separada para la suite de tests.
--
-- Los tests truncan todas las tablas entre casos, así que NO pueden correr
-- contra la base de desarrollo. Este script se ejecuta una única vez, cuando
-- el volumen de MySQL se inicializa vacío.
--
-- El nombre del usuario está fijo porque el entrypoint de la imagen de MySQL
-- no interpola variables dentro de los scripts de init. Coincide con
-- MYSQL_USER de .env.example.

CREATE DATABASE IF NOT EXISTS `finanzas_test`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

GRANT ALL PRIVILEGES ON `finanzas_test`.* TO 'finanzas'@'%';
FLUSH PRIVILEGES;
