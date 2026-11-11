from rest_framework import viewsets

from .models import Produto
from .serializers import ProdutoSerializer


class ProdutoViewSet(viewsets.ModelViewSet):
    queryset = Produto.objects.all().order_by("-data_criacao")
    serializer_class = ProdutoSerializer
