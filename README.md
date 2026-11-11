# ERP Vity

Estrutura inicial do projeto Django para rodar a aplicação.

## Requisitos

- Python 3.11+
- pip

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate  # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py create_admin
python manage.py runserver
```

## Acesso

- Usuário: `admin`
- Senha: `administrador`
- Painel administrativo: `http://127.0.0.1:8000/admin/`

## Observações

A aplicação foi montada com Django + templates em Python para iniciar o ERP.
