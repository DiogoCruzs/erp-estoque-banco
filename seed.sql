-- Seed completo do modulo de Estoque
-- Banco alvo: PostgreSQL / Supabase
--
-- Objetivo:
-- - Criar dados de exemplo para a loja que vende apenas uma camiseta.
-- - Deixar produto, saldo final, alerta e historico de movimentacoes prontos.
-- - Permitir reexecutar o script sem duplicar dados.
--
-- Observacao:
-- Este seed remove as movimentacoes anteriores do produto CAM-001 para recriar
-- um historico de exemplo consistente.

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

do $$
declare
    camiseta_id bigint;
    tem_saldo_anterior boolean;
    tem_saldo_posterior boolean;
    tem_saldo_ajustado boolean;
    tem_origem boolean;
begin
    select id
    into camiseta_id
    from produtos
    where sku = 'CAM-001';

    select exists (
        select 1
        from information_schema.columns
        where table_name = 'movimentacoes_estoque'
          and column_name = 'saldo_anterior'
    ) into tem_saldo_anterior;

    select exists (
        select 1
        from information_schema.columns
        where table_name = 'movimentacoes_estoque'
          and column_name = 'saldo_posterior'
    ) into tem_saldo_posterior;

    select exists (
        select 1
        from information_schema.columns
        where table_name = 'movimentacoes_estoque'
          and column_name = 'saldo_ajustado'
    ) into tem_saldo_ajustado;

    select exists (
        select 1
        from information_schema.columns
        where table_name = 'movimentacoes_estoque'
          and column_name = 'origem'
    ) into tem_origem;

    if tem_saldo_anterior and tem_saldo_posterior and tem_origem then
        insert into movimentacoes_estoque (
            produto_id,
            tipo,
            quantidade,
            saldo_anterior,
            saldo_posterior,
            justificativa,
            origem,
            criado_em
        ) values
            (
                camiseta_id,
                'entrada',
                50,
                0,
                50,
                'Entrada inicial do estoque para demonstracao',
                'seed_estoque',
                now() - interval '4 days'
            ),
            (
                camiseta_id,
                'saida',
                12,
                50,
                38,
                'Venda simulada para cliente',
                'seed_estoque',
                now() - interval '3 days'
            ),
            (
                camiseta_id,
                'saida',
                30,
                38,
                8,
                'Venda simulada em lote',
                'seed_estoque',
                now() - interval '2 days'
            ),
            (
                camiseta_id,
                'inventario',
                0,
                8,
                8,
                'Contagem fisica confirmou o saldo atual',
                'seed_estoque',
                now() - interval '1 day'
            );
    elsif tem_saldo_ajustado then
        insert into movimentacoes_estoque (
            produto_id,
            tipo,
            quantidade,
            justificativa,
            saldo_ajustado,
            criado_em
        ) values
            (
                camiseta_id,
                'entrada',
                50,
                'Entrada inicial do estoque para demonstracao',
                null,
                now() - interval '4 days'
            ),
            (
                camiseta_id,
                'saida',
                12,
                'Venda simulada para cliente',
                null,
                now() - interval '3 days'
            ),
            (
                camiseta_id,
                'saida',
                30,
                'Venda simulada em lote',
                null,
                now() - interval '2 days'
            ),
            (
                camiseta_id,
                'inventario',
                8,
                'Contagem fisica confirmou o saldo atual',
                8,
                now() - interval '1 day'
            );
    else
        insert into movimentacoes_estoque (
            produto_id,
            tipo,
            quantidade,
            justificativa,
            criado_em
        ) values
            (
                camiseta_id,
                'entrada',
                50,
                'Entrada inicial do estoque para demonstracao',
                now() - interval '4 days'
            ),
            (
                camiseta_id,
                'saida',
                12,
                'Venda simulada para cliente',
                now() - interval '3 days'
            ),
            (
                camiseta_id,
                'saida',
                30,
                'Venda simulada em lote',
                now() - interval '2 days'
            ),
            (
                camiseta_id,
                'inventario',
                8,
                'Contagem fisica confirmou o saldo atual',
                now() - interval '1 day'
            );
    end if;
end $$;

commit;

-- Conferencia rapida apos executar:
--
-- select * from produtos where sku = 'CAM-001';
-- select * from movimentacoes_estoque
-- where produto_id = (select id from produtos where sku = 'CAM-001')
-- order by criado_em;
-- select * from vw_alertas_estoque;
