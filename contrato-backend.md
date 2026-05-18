# Contrato para o Backend - Estoque

Este documento explica como o backend deve usar o banco de dados do estoque para responder ao frontend.

## Endpoints esperados pelo frontend

```http
GET /estoque/produtos
POST /estoque/produtos
POST /estoque/movimentacoes/entrada
POST /estoque/movimentacoes/saida
GET /estoque/alertas
POST /estoque/inventario/{prod_id}
```

## Mapeamento de campos

Tabela `produtos` no banco:

```text
id
nome
sku
saldo_atual
estoque_minimo
unidade
ativo
criado_em
atualizado_em
```

Resposta esperada pelo frontend:

```json
{
  "id": 1,
  "nome": "Camiseta ERP Universitario",
  "sku": "CAM-001",
  "saldoAtual": 50,
  "estoqueMinimo": 10,
  "unidade": "un"
}
```

Conversao obrigatoria:

```text
saldo_atual -> saldoAtual
estoque_minimo -> estoqueMinimo
produto_id -> produtoId
saldo_ajustado -> saldoAjustado
```

## Produtos

Para `GET /estoque/produtos`, buscar produtos ativos:

```sql
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
```

## Entrada de estoque

Payload recebido do frontend:

```json
{
  "produtoId": 1,
  "quantidade": 5
}
```

Regra:

1. Buscar o produto.
2. Somar a quantidade ao `saldo_atual`.
3. Registrar a movimentacao na tabela `movimentacoes_estoque` com tipo `entrada`.

## Saida de estoque

Payload recebido do frontend:

```json
{
  "produtoId": 1,
  "quantidade": 2
}
```

Regra:

1. Buscar o produto.
2. Validar se existe saldo suficiente.
3. Subtrair a quantidade do `saldo_atual`.
4. Registrar a movimentacao com tipo `saida`.

Se nao houver saldo suficiente, retornar erro `422` ou `400` com uma mensagem clara.

## Inventario

Payload recebido do frontend:

```json
{
  "produtoId": 1,
  "saldoAjustado": 20,
  "justificativa": "Ajuste apos contagem fisica"
}
```

Regra:

1. Buscar o produto pelo parametro `{prod_id}`.
2. Trocar o `saldo_atual` pelo saldo ajustado.
3. Registrar a movimentacao com tipo `inventario`.
4. Guardar a justificativa.

## Alertas

Para `GET /estoque/alertas`, o backend pode usar a view:

```sql
select
    id,
    nome,
    sku,
    saldo_atual,
    estoque_minimo,
    unidade,
    quantidade_para_repor
from vw_alertas_estoque
order by quantidade_para_repor desc;
```

O frontend atual usa principalmente a lista de produtos para calcular os alertas visualmente, mas este endpoint esta previsto no contrato de integracao.

## Observacao sobre status

O frontend consegue calcular o status assim:

```text
saldoAtual < estoqueMinimo => Reposicao
saldoAtual >= estoqueMinimo => Normal
```

O backend pode enviar esse campo se quiser, mas nao e obrigatorio para a tela atual.

## Query de apoio

O arquivo `queries-backend.sql` tem exemplos de transacoes para entrada, saida e inventario.

Essas queries sao uma referencia para a equipe do backend. Elas nao obrigam a equipe a usar SQL puro; o mesmo comportamento pode ser implementado com SQLAlchemy, desde que mantenha as mesmas regras.
