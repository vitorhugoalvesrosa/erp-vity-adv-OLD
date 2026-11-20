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
python manage.py setup_access_control
python manage.py create_erp_users
python manage.py runserver
```

O painel administrativo fica em `http://127.0.0.1:8000/admin/` e permite gerenciar os dados de CRM, produtos e financeiro conforme o perfil de acesso.

`create_erp_users` solicita senhas sem exibi-las, valida cada senha e cria ou atualiza as contas `admin`, `gerente` e `operador`. Use senhas fortes e exclusivas; elas não devem ser incluídas no repositório ou na documentação.

No plano Free do Render, o comando interativo não pode ser executado pelo Shell. Para criar as contas sem atualizar o plano, configure temporariamente `ERP_BOOTSTRAP_ADMIN_PASSWORD`, `ERP_BOOTSTRAP_GERENTE_PASSWORD` e `ERP_BOOTSTRAP_OPERADOR_PASSWORD` nas variáveis do serviço. O deploy executa o bootstrap uma única vez após as migrations; quando o deploy concluir, remova essas três variáveis. A conclusão fica registrada no banco e reinícios seguintes não redefinem as senhas.

Se precisar redefinir a senha de `admin` depois do bootstrap, configure `ERP_BOOTSTRAP_ADMIN_PASSWORD` com a nova senha e `ERP_ADMIN_PASSWORD_RESET_TOKEN` com um token aleatório de pelo menos 32 caracteres. Após o deploy concluir, remova as duas variáveis. O token é registrado como usado e não redefinirá a senha novamente em reinícios.

## Perfis de acesso

- `admin`: superusuário com acesso total.
- `gerente`: acesso total às permissões do Django e aos recursos da API.
- `operador`: somente leitura nos recursos de CRM, produtos e financeiro, sem permissões de escrita ou gestão de usuários.

O deploy atualiza os grupos e suas permissões após aplicar as migrations.

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

O arquivo `render.yaml` configura o Web Service Python. No Blueprint, forneça em `DATABASE_URL` a URL interna de um PostgreSQL existente no mesmo workspace e região; o valor é solicitado pelo Render e não fica salvo no repositório. O serviço instala `requirements.txt`, coleta os arquivos estáticos com WhiteNoise, executa as migrations, atualiza os grupos de acesso e tenta o bootstrap único das contas ao iniciar, e então inicia o Gunicorn.

O Render gera `SECRET_KEY`. A configuração define `DEBUG=False` e redirecionamento HTTPS. O host externo é permitido via `RENDER_EXTERNAL_HOSTNAME`. Não publique arquivos `.env` ou credenciais; mantenha as variáveis secretas na configuração do ambiente do Render.
