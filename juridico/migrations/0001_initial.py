from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("crm", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Processo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero_cnj", models.CharField(max_length=25, unique=True, verbose_name="Número CNJ")),
                ("titulo", models.CharField(max_length=255, verbose_name="Título")),
                ("parte_contraria", models.CharField(blank=True, max_length=255, verbose_name="Parte contrária")),
                ("tribunal", models.CharField(max_length=100, verbose_name="Tribunal")),
                ("vara", models.CharField(blank=True, max_length=120, verbose_name="Vara/comarca")),
                ("area", models.CharField(choices=[("civel", "Cível"), ("trabalhista", "Trabalhista"), ("tributario", "Tributário"), ("empresarial", "Empresarial"), ("criminal", "Criminal"), ("familia", "Família"), ("outra", "Outra")], default="civel", max_length=20)),
                ("status", models.CharField(choices=[("ativo", "Ativo"), ("suspenso", "Suspenso"), ("arquivado", "Arquivado"), ("encerrado", "Encerrado")], default="ativo", max_length=20)),
                ("valor_causa", models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name="Valor da causa")),
                ("observacoes", models.TextField(blank=True, verbose_name="Observações")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("cliente", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="processos", to="crm.conta", verbose_name="Cliente")),
                ("responsavel", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="processos_responsavel", to=settings.AUTH_USER_MODEL, verbose_name="Responsável")),
            ],
            options={"ordering": ["-atualizado_em"], "verbose_name": "Processo", "verbose_name_plural": "Processos"},
        ),
        migrations.CreateModel(
            name="Movimentacao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("data", models.DateField(verbose_name="Data")),
                ("descricao", models.CharField(max_length=500, verbose_name="Descrição")),
                ("origem", models.CharField(default="manual", max_length=30, verbose_name="Origem")),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                ("processo", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="movimentacoes", to="juridico.processo")),
            ],
            options={"ordering": ["-data", "-criada_em"], "verbose_name": "Movimentação", "verbose_name_plural": "Movimentações"},
        ),
        migrations.CreateModel(
            name="Prazo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=255, verbose_name="Título")),
                ("data_vencimento", models.DateField(verbose_name="Vencimento")),
                ("status", models.CharField(choices=[("aberto", "Aberto"), ("concluido", "Concluído"), ("perdido", "Perdido")], default="aberto", max_length=20)),
                ("observacoes", models.TextField(blank=True, verbose_name="Observações")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("processo", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="prazos", to="juridico.processo")),
                ("responsavel", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="prazos_responsavel", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["data_vencimento", "titulo"], "verbose_name": "Prazo", "verbose_name_plural": "Prazos"},
        ),
        migrations.CreateModel(
            name="Tarefa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=255, verbose_name="Título")),
                ("descricao", models.TextField(blank=True, verbose_name="Descrição")),
                ("prioridade", models.CharField(choices=[("baixa", "Baixa"), ("media", "Média"), ("alta", "Alta"), ("urgente", "Urgente")], default="media", max_length=20)),
                ("status", models.CharField(choices=[("pendente", "Pendente"), ("em_andamento", "Em andamento"), ("concluida", "Concluída"), ("cancelada", "Cancelada")], default="pendente", max_length=20)),
                ("vencimento", models.DateField(blank=True, null=True, verbose_name="Vencimento")),
                ("concluida_em", models.DateTimeField(blank=True, null=True)),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                ("processo", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="tarefas", to="juridico.processo")),
                ("responsavel", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tarefas_responsavel", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["status", "vencimento", "-prioridade"], "verbose_name": "Tarefa", "verbose_name_plural": "Tarefas"},
        ),
        migrations.CreateModel(
            name="Publicacao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("monitoramento", models.CharField(max_length=30, verbose_name="CPF/CNPJ/OAB monitorado")),
                ("tribunal", models.CharField(max_length=100, verbose_name="Tribunal")),
                ("titulo", models.CharField(max_length=255, verbose_name="Título")),
                ("conteudo", models.TextField(verbose_name="Conteúdo")),
                ("publicada_em", models.DateField(verbose_name="Data da publicação")),
                ("capturada_em", models.DateTimeField(auto_now_add=True)),
                ("urgente", models.BooleanField(default=False, verbose_name="Urgente")),
                ("processada", models.BooleanField(default=False, verbose_name="Processada")),
                ("processo", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="publicacoes", to="juridico.processo")),
            ],
            options={"ordering": ["-publicada_em", "-capturada_em"], "verbose_name": "Publicação", "verbose_name_plural": "Publicações"},
        ),
    ]
