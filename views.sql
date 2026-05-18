-- View para alertas de estoque baixo
-- Ajuda o backend a implementar GET /estoque/alertas.

create or replace view vw_alertas_estoque as
select
    id,
    nome,
    sku,
    saldo_atual,
    estoque_minimo,
    unidade,
    (estoque_minimo - saldo_atual) as quantidade_para_repor
from produtos
where ativo = true
  and saldo_atual < estoque_minimo;

-- Query equivalente, caso a equipe prefira nao usar view:
--
-- select
--     id,
--     nome,
--     sku,
--     saldo_atual,
--     estoque_minimo,
--     unidade,
--     (estoque_minimo - saldo_atual) as quantidade_para_repor
-- from produtos
-- where ativo = true
--   and saldo_atual < estoque_minimo;
