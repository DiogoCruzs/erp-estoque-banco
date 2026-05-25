-- Seed completo do modulo de Estoque
-- Banco alvo: PostgreSQL / Supabase
--
-- Este script foi ajustado para o schema do banco criado anteriormente:
-- produtos(id, nome, sku, saldo_atual, estoque_minimo, unidade, ...)
-- movimentacoes_estoque(produto_id, tipo, quantidade, saldo_anterior, saldo_posterior, justificativa, origem, ...)

begin;

insert into produtos (
    nome,
    sku,
    saldo_atual,
    estoque_minimo,
    unidade
) values (
    'Camiseta ERP Universitario',
    'CAM-001',
    8,
    10,
    'un'
)
on conflict (sku) do update set
    nome = excluded.nome,
    saldo_atual = excluded.saldo_atual,
    estoque_minimo = excluded.estoque_minimo,
    unidade = excluded.unidade,
    atualizado_em = now();

delete from movimentacoes_estoque
where produto_id = (
    select id
    from produtos
    where sku = 'CAM-001'
);

insert into movimentacoes_estoque (
    produto_id,
    tipo,
    quantidade,
    saldo_anterior,
    saldo_posterior,
    justificativa,
    origem,
    criado_em
)
select
    p.id,
    dados.tipo,
    dados.quantidade,
    dados.saldo_anterior,
    dados.saldo_posterior,
    dados.justificativa,
    'seed_estoque',
    dados.criado_em
from produtos p
cross join (
    values
        (
            'entrada',
            50,
            0,
            50,
            'Entrada inicial do estoque para demonstracao',
            now() - interval '4 days'
        ),
        (
            'saida',
            12,
            50,
            38,
            'Venda simulada para cliente',
            now() - interval '3 days'
        ),
        (
            'saida',
            30,
            38,
            8,
            'Venda simulada em lote',
            now() - interval '2 days'
        ),
        (
            'inventario',
            0,
            8,
            8,
            'Contagem fisica confirmou o saldo atual',
            now() - interval '1 day'
        )
) as dados(tipo, quantidade, saldo_anterior, saldo_posterior, justificativa, criado_em)
where p.sku = 'CAM-001';

commit;

-- Conferencia rapida apos executar:
--
-- select * from produtos where sku = 'CAM-001';
--
-- select *
-- from movimentacoes_estoque
-- where produto_id = (select id from produtos where sku = 'CAM-001')
-- order by criado_em;
--
-- select * from vw_alertas_estoque;
