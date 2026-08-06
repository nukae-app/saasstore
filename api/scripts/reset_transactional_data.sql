-- Esborra TOTES les dades transaccionals (compres, vendes, TPV, carrets,
-- peticions, comptabilitat) i deixa nomes dades mestres: catàleg
-- (releases/items/etiquetes), proveïdors, usuaris, configuració i contingut
-- (posts/pàgines/events/traduccions).
--
-- IRREVERSIBLE. No fa cap backup. Pensat per deixar l'entorn "com nou" en
-- fase de proves. Revisar abans de córrer contra producció.
--
-- Ús:
--   ssh -L 5433:recordshop-db.c5c80e4yaiyo.eu-west-1.rds.amazonaws.com:5432 ubuntu@54.76.9.1
--   psql -h localhost -p 5433 -U ultralocal -d ultralocal -f reset_transactional_data.sql
--
-- (OJO: db.txt fa servir "ultralocal_test" al psql d'exemple, però
-- DATABASE_URL de .env apunta a la base "ultralocal". Confirmar quin nom de
-- base és realment producció abans d'executar.)

BEGIN;

-- Devolucions primer: referencien order_items i ventas_externas amb RESTRICT.
DELETE FROM devolucions_venta;
DELETE FROM devolucions_compra;

-- Comptabilitat (moviments/despeses/tancaments de mes).
DELETE FROM moviments_bancaris;
DELETE FROM despeses;
DELETE FROM periodes_comptables;

-- Caixa / TPV.
DELETE FROM caja_movimientos;
DELETE FROM caja_sessions;

-- Newsletter (traces d'enviament; les campanyes en si no són "venda" però
-- sense enviaments no tenen sentit conservar-les soles).
DELETE FROM newsletter_sends;
DELETE FROM newsletter_campaigns;

-- Vendes externes (mostrador/Discogs).
DELETE FROM ventas_externas;

-- Peticions de client.
DELETE FROM peticiones_cliente;

-- Vendes web (pedidos).
DELETE FROM order_items;
DELETE FROM payments;
DELETE FROM orders;

-- Carrets en curs.
DELETE FROM cart_items;
DELETE FROM carts;

-- ERP de compres. historial_compres NO s'esborra: és dada de referència
-- (senyal per al buscador de proveïdor), no una transacció pendent —
-- inclou l'import del CSV ULTRA-CONTROL, que costa de refer.
DELETE FROM solicitud_compra_items;
DELETE FROM solicitudes_compra;
DELETE FROM comanda_items;
DELETE FROM compras;
DELETE FROM comandas;

-- Deixa l'estoc (Item) net: cap còpia reservada/venuda/retirada, totes
-- disponibles. No es toca precio/condicion/coste_adquisicion (són dades de
-- catàleg, no transaccionals).
UPDATE items SET
    status = 'disponible',
    reserved_until = NULL,
    reserved_by_cart_id = NULL,
    reserved_for_peticion_id = NULL,
    compra_id = NULL;

COMMIT;
