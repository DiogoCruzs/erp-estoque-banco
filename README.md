# Entrega Banco de Dados - Modulo Estoque

Esta pasta contem a parte de banco de dados do modulo de Estoque/Almoxarifado do ERP universitario.

O objetivo e deixar a estrutura pronta para o backend implementar os endpoints esperados pelo frontend, sem precisar mudar o contrato da tela de estoque.

## Arquivos

- `schema.sql`: cria as tabelas `produtos` e `movimentacoes_estoque`.
- `seed.sql`: cadastra a camiseta da loja e cria movimentacoes de exemplo.
- `views.sql`: cria a view `vw_alertas_estoque` para produtos abaixo do estoque minimo.
- `queries-backend.sql`: exemplos de queries para entrada, saida e inventario.
- `contrato-backend.md`: explica como o backend deve mapear os campos do banco para o formato esperado pelo frontend.

## Ordem de execucao

Execute os arquivos nesta ordem no PostgreSQL/Supabase:

```sql
\i schema.sql
\i seed.sql
\i views.sql
```

No painel SQL do Supabase, cole e execute primeiro o conteudo de `schema.sql`, depois `seed.sql`, depois `views.sql`.

## Dados de exemplo

O seed cadastra uma loja que vende apenas uma camiseta e deixa um historico de movimentacoes pronto:

```text
Nome: Camiseta ERP Universitario
SKU: CAM-001
Entrada inicial: 50
Saidas simuladas: 12 + 30
Saldo final: 8
Estoque minimo: 10
Unidade: un
```

Como o saldo final fica abaixo do estoque minimo, a view `vw_alertas_estoque` tambem retorna um alerta de reposicao para a camiseta.

## Regras de integridade

O banco garante:

- SKU unico por produto.
- Saldo atual nunca negativo.
- Estoque minimo nunca negativo.
- Movimentacoes somente dos tipos `entrada`, `saida` e `inventario`.
- Quantidade de entrada/saida sempre maior que zero.
- Inventario pode registrar quantidade zero quando a contagem confirmar o mesmo saldo.
- Historico de movimentacoes ligado ao produto.

## Observacao importante

O banco usa nomes em `snake_case`, que e o padrao comum em SQL.

O frontend espera alguns campos em `camelCase`. Essa conversao deve ser feita pelo backend antes de responder JSON.
