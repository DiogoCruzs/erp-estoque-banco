-- Dados iniciais da loja
-- O trabalho pede uma loja que vende apenas uma camiseta.

insert into produtos (
    nome,
    sku,
    saldo_atual,
    estoque_minimo,
    unidade
) values (
    'Camiseta ERP Universitario',
    'CAM-001',
    50,
    10,
    'un'
)
on conflict (sku) do update set
    nome = excluded.nome,
    estoque_minimo = excluded.estoque_minimo,
    unidade = excluded.unidade,
    atualizado_em = now();
