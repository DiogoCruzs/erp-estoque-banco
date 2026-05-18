-- Queries de apoio para o backend
-- Use dentro de transacoes para manter produto e historico sempre consistentes.

-- Listar produtos no formato base do banco
select
    id,
    nome,
    sku,
    saldo_atual,
    estoque_minimo,
    unidade
from produtos
where ativo = true
order by id;

-- Entrada de estoque
-- Parametros esperados:
-- :produto_id
-- :quantidade
-- :origem
--
-- begin;
--
-- select saldo_atual
-- from produtos
-- where id = :produto_id and ativo = true
-- for update;
--
-- update produtos
-- set saldo_atual = saldo_atual + :quantidade
-- where id = :produto_id and ativo = true
-- returning saldo_atual - :quantidade as saldo_anterior,
--           saldo_atual as saldo_posterior;
--
-- insert into movimentacoes_estoque (
--     produto_id,
--     tipo,
--     quantidade,
--     saldo_anterior,
--     saldo_posterior,
--     origem
-- ) values (
--     :produto_id,
--     'entrada',
--     :quantidade,
--     :saldo_anterior,
--     :saldo_posterior,
--     :origem
-- );
--
-- commit;

-- Saida de estoque
-- Antes de atualizar, o backend deve validar se saldo_atual >= :quantidade.
--
-- begin;
--
-- select saldo_atual
-- from produtos
-- where id = :produto_id and ativo = true
-- for update;
--
-- update produtos
-- set saldo_atual = saldo_atual - :quantidade
-- where id = :produto_id
--   and ativo = true
--   and saldo_atual >= :quantidade
-- returning saldo_atual + :quantidade as saldo_anterior,
--           saldo_atual as saldo_posterior;
--
-- insert into movimentacoes_estoque (
--     produto_id,
--     tipo,
--     quantidade,
--     saldo_anterior,
--     saldo_posterior,
--     origem
-- ) values (
--     :produto_id,
--     'saida',
--     :quantidade,
--     :saldo_anterior,
--     :saldo_posterior,
--     :origem
-- );
--
-- commit;

-- Inventario
-- Parametros esperados:
-- :produto_id
-- :saldo_ajustado
-- :justificativa
--
-- begin;
--
-- select saldo_atual
-- from produtos
-- where id = :produto_id and ativo = true
-- for update;
--
-- update produtos
-- set saldo_atual = :saldo_ajustado
-- where id = :produto_id and ativo = true
-- returning abs(saldo_atual - :saldo_anterior) as quantidade,
--           :saldo_anterior as saldo_anterior,
--           saldo_atual as saldo_posterior;
--
-- insert into movimentacoes_estoque (
--     produto_id,
--     tipo,
--     quantidade,
--     saldo_anterior,
--     saldo_posterior,
--     justificativa,
--     origem
-- ) values (
--     :produto_id,
--     'inventario',
--     :quantidade,
--     :saldo_anterior,
--     :saldo_posterior,
--     :justificativa,
--     'inventario'
-- );
--
-- commit;
