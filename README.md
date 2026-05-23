# Vale Verde Deck Beer — Sistema de Gestão

Sistema web Flask para Tabacaria / Lanchonete / Deck Beer com visual premium escuro, neon verde, mesas, comandas, PDV, estoque, KDS por setor, clientes/fiado, funcionários e relatórios.

## Correções desta versão

- Corrigido erro de deploy no Railway relacionado a `libpq.so.5` / `psycopg2`.
- Projeto travado em Python 3.12.8 via `runtime.txt` e `.python-version`.
- Incluído `Dockerfile` com `libpq5` e `libpq-dev` para garantir suporte ao PostgreSQL.
- Incluído `nixpacks.toml` como fallback caso o Railway use Nixpacks.
- `start.sh` cria tabelas e roda seed automaticamente antes do Gunicorn, evitando precisar de SSH no primeiro deploy.
- Uploads/fotos usam `RAILWAY_VOLUME_MOUNT_PATH` quando existir; localmente usa `uploads/`.

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

## Admin inicial

- Email: `admin@valeverde.com`
- Senha: `admin123`

Troque a senha depois do primeiro acesso.

## Uploads / fotos dos produtos

Sim, o sistema usa volume para salvar fotos.

No Railway, crie um volume no serviço web e monte, por exemplo, em:

```txt
/app/uploads
```

O Railway injeta a variável:

```env
RAILWAY_VOLUME_MOUNT_PATH=/app/uploads
```

O sistema usa automaticamente:

```python
UPLOAD_FOLDER = os.getenv("RAILWAY_VOLUME_MOUNT_PATH") or os.getenv("UPLOAD_FOLDER") or "uploads"
```

As imagens dos produtos são salvas em:

```txt
/app/uploads/products/
```

Localmente, se não existir volume, elas ficam em:

```txt
uploads/products/
```

## Rodando localmente

### Linux/macOS

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=run.py
python -m app.seed
flask run
```

### Windows PowerShell

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
$env:FLASK_APP="run.py"
python -m app.seed
flask run
```

O seed usa `db.create_all()`, então cria as tabelas automaticamente para o primeiro uso.

## Migrações manuais, se quiser usar Flask-Migrate

```bash
flask db init
flask db migrate -m "initial tables"
flask db upgrade
```

## Deploy no Railway

1. Crie um repositório no GitHub e envie este projeto.
2. No Railway, crie um novo projeto conectado ao GitHub.
3. Adicione um serviço PostgreSQL.
4. No serviço web, configure as variáveis:

```env
SECRET_KEY=uma-chave-forte
FLASK_ENV=production
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

5. Adicione um volume ao serviço web e monte em:

```txt
/app/uploads
```

6. O start command já está configurado como:

```bash
bash start.sh
```

7. O `start.sh` roda automaticamente:

```bash
python -m app.seed
gunicorn run:app --bind 0.0.0.0:${PORT:-8080}
```

Por isso, no primeiro deploy, o banco e o admin inicial já são criados sem precisar entrar por SSH.

## Se o Railway usar Dockerfile

O projeto já inclui um `Dockerfile` com Python 3.12 e bibliotecas do PostgreSQL:

```dockerfile
apt-get install -y gcc libpq5 libpq-dev
```

Isso corrige o erro:

```txt
ImportError: libpq.so.5: cannot open shared object file: No such file or directory
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
├── uploads/
├── config.py
├── run.py
├── requirements.txt
├── Procfile
├── railway.json
├── runtime.txt
├── .python-version
├── nixpacks.toml
├── Dockerfile
├── start.sh
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
