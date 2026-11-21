from .models import CompanyProfile


def company_profile(request):
    profile = CompanyProfile.objects.first()
    return {
        "company_profile": profile,
        "company_display_name": (
            profile.trade_name or profile.legal_name if profile else "ERP Vity"
        ),
    }