from .models import CompanyProfile


def company_profile(request):
    profile = CompanyProfile.objects.first()
    return {
        "company_profile": profile,
        "sidebar_color": profile.sidebar_color if profile else "#171D35",
        "company_display_name": (
            profile.trade_name or profile.legal_name if profile else "ERP Vity ADV"
        ),
    }