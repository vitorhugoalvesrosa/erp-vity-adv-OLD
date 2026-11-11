from rest_framework import viewsets

from .models import Conta, Proposta
from .serializers import ContaSerializer, PropostaSerializer


class ContaViewSet(viewsets.ModelViewSet):
    queryset = Conta.objects.all().order_by("-data_criacao")
    serializer_class = ContaSerializer


class PropostaViewSet(viewsets.ModelViewSet):
    queryset = Proposta.objects.select_related("conta").all().order_by("-data_validade")
    serializer_class = PropostaSerializer
