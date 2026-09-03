# SERV FESTA REGISSOL

Sistema local e offline para controlar estoque, compras, vendas e lucro bruto estimado dos espetos.

## Iniciar no Windows

1. Instale Python 3.11 ou superior.
2. Execute `iniciar.bat`.
3. Na primeira abertura, crie o administrador com uma senha de pelo menos 10 caracteres.
4. Acesse `http://127.0.0.1:5000`.

O instalador verifica/cria um ambiente virtual e instala as únicas dependências locais (Flask e Werkzeug). O sistema escuta somente em `127.0.0.1` por padrão.

## Pastas importantes

- `data/serv_festa.db`: banco SQLite local.
- `data/backups/`: cópias locais, mantendo aproximadamente os últimos 30 backups.
- `app/`: rotas, regras de negócio, banco, templates e arquivos estáticos.

## Backup e restauração

Use Configurações → Fazer backup agora. A restauração pode ser feita na mesma tela enviando um arquivo `.db` válido; o sistema cria um backup automático antes, valida as tabelas essenciais e registra a ação. Em caso de emergência, pare o sistema e substitua `data/serv_festa.db` por uma cópia válida de `data/backups/`.

## Testes

Com Python disponível, execute:

```text
python -m unittest discover -s tests -v
```

O cálculo usa centavos inteiros. O custo dos produtos vendidos é congelado na venda e é diferente do total de compras.

