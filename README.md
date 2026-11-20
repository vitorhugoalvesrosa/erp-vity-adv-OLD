# ERP Vity

ERP Vity com interface web em Django, API REST para CRM, produtos e financeiro, e painel administrativo restrito.

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

Acesse `http://127.0.0.1:8000/` para entrar no sistema. O frontend inclui painel geral e operações de consulta, cadastro, edição e exclusão para CRM, produtos, pedidos e financeiro. Os perfis de gerente e operador usam essa interface conforme suas permissões.

No cadastro de produtos, marque **É um serviço (não controla estoque)** para que a quantidade não seja mantida e apareça como não controlada.

O menu lateral pode ser recolhido e reaberto e lembra a preferência no navegador. A área **Administração**, visível somente para superusuários, reúne atalhos para usuários, grupos/permissões e todos os registros gerenciados pelo Django Admin. O Django Admin fica em `/admin/` e só pode ser acessado por uma conta superusuária (`admin`). O login e os recursos de negócio ficam no frontend próprio.

`create_erp_users` solicita senhas sem exibi-las, valida cada senha e cria ou atualiza as contas `admin`, `gerente` e `operador`. Use senhas fortes e exclusivas; elas não devem ser incluídas no repositório ou na documentação.

No plano Free do Render, o comando interativo não pode ser executado pelo Shell. Para criar as contas sem atualizar o plano, configure temporariamente `ERP_BOOTSTRAP_ADMIN_PASSWORD`, `ERP_BOOTSTRAP_GERENTE_PASSWORD` e `ERP_BOOTSTRAP_OPERADOR_PASSWORD` nas variáveis do serviço. O deploy executa o bootstrap uma única vez após as migrations; quando o deploy concluir, remova essas três variáveis. A conclusão fica registrada no banco e reinícios seguintes não redefinem as senhas.

Se precisar redefinir a senha de `admin` depois do bootstrap, configure `ERP_BOOTSTRAP_ADMIN_PASSWORD` com a nova senha e `ERP_ADMIN_PASSWORD_RESET_TOKEN` com um token aleatório de pelo menos 32 caracteres. Após o deploy concluir, remova as duas variáveis. O token é registrado como usado e não redefinirá a senha novamente em reinícios.

## E-mail

Um superusuário pode cadastrar SMTP autenticado em **Administração → Empresa e integrações**. A senha é criptografada no banco e a conexão pode ser testada no Django Admin. Se não houver configuração salva, o sistema aceita as variáveis `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` e `DEFAULT_FROM_EMAIL`. Para Gmail ou Outlook, use uma senha de aplicativo quando exigida pelo provedor; nunca coloque credenciais no repositório. Use `EMAIL_USE_TLS=True` na porta 587 ou `EMAIL_USE_SSL=True` na porta 465, sem ativar as duas opções ao mesmo tempo.

Antes de salvar senhas SMTP ou certificado A1, configure `CONFIG_ENCRYPTION_KEY` como segredo no Render e no `.env` local. Gere uma chave com `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. A chave não é armazenada no banco nem no repositório; guarde-a em local seguro e não a troque sem recriptografar os dados. O certificado `.pfx`/`.p12` e sua senha são validados e criptografados no banco, sem publicação em `/media/`.

O link **Esqueci minha senha** na tela de login envia um link de uso único para o endereço cadastrado no usuário. Administradores e gerentes também podem enviar comunicados aos usuários ativos com e-mail cadastrado pelo módulo **E-mails** no menu lateral. Cadastre e mantenha os endereços em Usuários no Django Admin.

## Perfis de acesso

- `admin`: superusuário com acesso total.
- `gerente`: acesso de leitura e escrita aos módulos do ERP e à API, sem acesso ao Django Admin.
- `operador`: somente leitura nos módulos de CRM, produtos e financeiro, sem permissões de escrita ou gestão de usuários.

O deploy atualiza os grupos e suas permissões após aplicar as migrations.

## Aplicações

- `crm`: contas (leads, negociações e clientes) e propostas comerciais.
- `produtos`: catálogo, SKU, preços e quantidade em estoque.
- `financeiro`: pedidos de venda, contas a receber e pagamentos.
- `pdv`: tela independente de caixa, movimentações, vendas com pagamentos divididos e histórico persistido no ERP.
- `core`: frontend, autenticação, comunicação por e-mail e configuração do projeto Django em `erp_vity`.

As alterações de esquema do banco estão registradas nas migrations de cada aplicação.

O PDV abre em uma nova aba sem a navegação geral do ERP. A operação comercial não depende de cadastro fiscal nem de comunicação com a SEFAZ: ao concluir uma pré-venda, o sistema registra a venda no ERP, atualiza o estoque de mercadorias e o caixa para valores recebidos em dinheiro. Pix e cartões são lançamentos manuais; o sistema não processa transações. A emissão de documentos fiscais permanece pendente e nenhuma NFS-e ou NFC-e é enviada pelo PDV.

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
