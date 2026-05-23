# Vale Verde Deck Beer — Sistema de Gestão

Sistema web Flask para Tabacaria / Lanchonete / Deck Beer com visual premium escuro, neon verde, mesas, comandas, PDV, estoque, KDS por setor, clientes/fiado, funcionários e relatórios.

## Stack

- Python Flask
- PostgreSQL
- SQLAlchemy
- Flask-Migrate
- Flask-Login
- Jinja2 + Bootstrap 5 + JavaScript puro
- Gunicorn
- Railway + GitHub
- Uploads em volume persistente via `RAILWAY_VOLUME_MOUNT_PATH`

## Funcionalidades entregues

- Login funcional
- Perfis: Admin, Gerente, Atendente, Caixa, Cozinha, Bar e Narguilé
- Dashboard com faturamento, mesas, comandas, estoque baixo, descontos e cancelamentos
- Cadastro de produtos, categorias e setores
- Upload de imagem do produto em pasta/volume persistente
- Tela de mesas estilo card first-mobile
- Abertura de comanda
- Adição de itens na comanda
- Separação automática por setor de preparo
- KDS para Cozinha, Bar e Narguilé com atualização por AJAX/fetch
- Caixa/PDV básico com pagamentos múltiplos/parciais
- Pix, dinheiro, crédito, débito, fiado e vale
- Fechamento de conta e liberação automática da mesa
- Estoque com baixa automática por venda
- Movimentações manuais de estoque
- Clientes e fiado
- Funcionários por perfil
- Relatórios iniciais por período, pagamentos e produtos vendidos
- Seed inicial robusto

## Rodando localmente

### Linux/macOS

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=run.py
flask db init
flask db migrate -m "initial tables"
flask db upgrade
python -m app.seed
flask run
```

### Windows PowerShell

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
$env:FLASK_APP="run.py"
flask db init
flask db migrate -m "initial tables"
flask db upgrade
python -m app.seed
flask run
```

## Admin inicial

- Email: `admin@valeverde.com`
- Senha: `admin123`

Troque a senha depois do primeiro acesso.

## Deploy no Railway

1. Crie um repositório no GitHub e envie este projeto.
2. No Railway, crie um novo projeto conectado ao GitHub.
3. Adicione um serviço PostgreSQL.
4. Adicione um volume para uploads.
5. Configure as variáveis:

```env
SECRET_KEY=uma-chave-forte
FLASK_ENV=production
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

6. Para uploads persistentes, o app usa automaticamente:

```python
UPLOAD_FOLDER = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "uploads")
```

7. O deploy usa:

```bash
gunicorn run:app
```

8. Depois do primeiro deploy, rode no shell do Railway:

```bash
flask db upgrade
python -m app.seed
```

## Estrutura

```text
vale-verde-system/
├── app/
│   ├── auth/
│   ├── dashboard/
│   ├── tables/
│   ├── orders/
│   ├── products/
│   ├── stock/
│   ├── pos/
│   ├── kitchen/
│   ├── customers/
│   ├── reports/
│   ├── settings/
│   ├── static/
│   └── templates/
├── config.py
├── run.py
├── requirements.txt
├── Procfile
├── railway.json
└── README.md
```

## Próximas melhorias recomendadas

- Tela dedicada para composição/ficha técnica com baixa de insumos
- Impressão HTML/PDF por setor e comprovantes
- Transferir item entre mesas
- Juntar mesas e dividir por item com interface visual
- Auditoria detalhada de permissões por ação
- WebSocket/SSE no KDS para atualização em tempo real sem polling
- Exportação de relatórios em CSV/PDF
