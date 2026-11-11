from rest_framework.routers import DefaultRouter

from .views import ContaViewSet, PropostaViewSet

router = DefaultRouter()
router.register(r"contas", ContaViewSet, basename="conta")
router.register(r"clientes", ContaViewSet, basename="cliente")
router.register(r"propostas", PropostaViewSet, basename="proposta")

urlpatterns = router.urls
