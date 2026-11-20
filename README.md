# ERP Vity

Aplicação ERP em Django com API REST para CRM, produtos e financeiro, além do painel administrativo.

## Requisitos

- Python 3.11 ou superior
- PostgreSQL local ou uma URL de conexão PostgreSQL
- pip

## Configuração local

```bash
python -m venv .venv
source .venv/bin/activate  # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edite `.env` com os dados do PostgreSQL local. Quando `DATABASE_URL` estiver vazia, a aplicação usa `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` e `DB_PORT`. Defina também uma `SECRET_KEY` própria para o ambiente.

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

O painel administrativo fica em `http://127.0.0.1:8000/admin/`.

> `python manage.py create_admin` cria ou redefine o usuário `admin` com uma senha fixa para desenvolvimento. Não execute esse comando em produção; use `createsuperuser` para criar uma credencial segura.

## Aplicações

- `crm`: contas (leads, negociações e clientes) e propostas comerciais.
- `produtos`: catálogo, SKU, preços e quantidade em estoque.
- `financeiro`: pedidos de venda, contas a receber e pagamentos.
- `core`: página inicial e configuração do projeto Django em `erp_vity`.

As alterações de esquema do banco estão registradas nas migrations de cada aplicação.

## API

Todas as rotas abaixo são prefixadas por `/api/` e exigem autenticação. Para obter tokens, envie `username` e `password` a `POST /api/auth/token/`; use o token de acesso no cabeçalho `Authorization: Bearer <access>`. Renove-o em `POST /api/auth/token/refresh/` e valide-o em `POST /api/auth/token/verify/`.

| Recurso | Endpoint |
| --- | --- |
| Contas e clientes | `/api/crm/contas/`, `/api/crm/clientes/` |
| Propostas | `/api/crm/propostas/` |
| Produtos | `/api/produtos/` |
| Pedidos de venda | `/api/financeiro/pedidos-venda/` |
| Contas a receber | `/api/financeiro/contas-receber/` |
| Pagamentos | `/api/financeiro/pagamentos/` |

Os recursos oferecem operações de listagem, consulta por ID, criação, atualização e exclusão. Os endpoints de autenticação aceitam JSON.

Configure `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` ou `FRONTEND_URL` no `.env` quando a aplicação for acessada por um frontend em outra origem.

## Deploy no Render

O arquivo `render.yaml` configura o Web Service e o PostgreSQL. Conecte o repositório ao Render e crie os recursos pelo Blueprint; o serviço instala `requirements.txt`, coleta os arquivos estáticos com WhiteNoise, executa as migrations ao iniciar e inicia o Gunicorn.

O Render fornece `DATABASE_URL` e gera `SECRET_KEY`. A configuração define `DEBUG=False` e redirecionamento HTTPS. O host externo é permitido via `RENDER_EXTERNAL_HOSTNAME`. Não publique arquivos `.env` ou credenciais; mantenha as variáveis secretas na configuração do ambiente do Render.
