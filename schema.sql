-- Modelagem do banco de dados do modulo de Estoque
-- Banco alvo: PostgreSQL / Supabase

create table if not exists produtos (
    id bigserial primary key,
    nome varchar(120) not null,
    sku varchar(40) not null unique,
    saldo_atual integer not null default 0,
    estoque_minimo integer not null default 0,
    unidade varchar(20) not null default 'un',
    ativo boolean not null default true,
    criado_em timestamptz not null default now(),
    atualizado_em timestamptz not null default now(),

    constraint ck_produtos_saldo_atual_nao_negativo
        check (saldo_atual >= 0),

    constraint ck_produtos_estoque_minimo_nao_negativo
        check (estoque_minimo >= 0)
);

create table if not exists movimentacoes_estoque (
    id bigserial primary key,
    produto_id bigint not null references produtos(id),
    tipo varchar(20) not null,
    quantidade integer not null,
    saldo_anterior integer not null,
    saldo_posterior integer not null,
    justificativa varchar(500),
    origem varchar(80),
    criado_em timestamptz not null default now(),

    constraint ck_movimentacoes_tipo_valido
        check (tipo in ('entrada', 'saida', 'inventario')),

    constraint ck_movimentacoes_quantidade_valida
        check (
            (tipo in ('entrada', 'saida') and quantidade > 0)
            or
            (tipo = 'inventario' and quantidade >= 0)
        ),

    constraint ck_movimentacoes_saldos_nao_negativos
        check (saldo_anterior >= 0 and saldo_posterior >= 0)
);

create index if not exists idx_produtos_sku
    on produtos (sku);

create index if not exists idx_produtos_estoque_baixo
    on produtos (saldo_atual, estoque_minimo)
    where ativo = true;

create index if not exists idx_movimentacoes_produto_id
    on movimentacoes_estoque (produto_id);

create index if not exists idx_movimentacoes_criado_em
    on movimentacoes_estoque (criado_em desc);

create or replace function atualizar_coluna_atualizado_em()
returns trigger as $$
begin
    new.atualizado_em = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_produtos_atualizado_em on produtos;

create trigger trg_produtos_atualizado_em
before update on produtos
for each row
execute function atualizar_coluna_atualizado_em();
