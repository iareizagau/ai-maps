"""
Views for the unified `/account/` area.

One server-rendered route per section. Existing `/profile/` views in views.py
remain functional during the migration; these views are additive.
"""
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.http import Http404
from django.shortcuts import redirect, render

from . import account_panels, selectors
from .forms import UserProfileForm, UsernameChangeForm


@login_required
def account_root(request):
    return redirect('account_identity')


@login_required
def account_identity(request):
    return render(request, 'account/identity.html', {
        'user_form': UserProfileForm(instance=request.user),
    })


@login_required
def account_security(request):
    return render(request, 'account/security.html', {
        'username_form': UsernameChangeForm(instance=request.user),
        'password_form': PasswordChangeForm(request.user),
    })


@login_required
def account_social(request):
    following = (
        request.user.following_set
        .select_related('followed')
        .all()
        .order_by('app_context')
    )
    suggested_experts = selectors.get_top_experts(exclude_user=request.user, limit=6)
    followed_ids = following.values_list('followed_id', flat=True)

    return render(request, 'account/social.html', {
        'following': following,
        'suggested_experts': suggested_experts,
        'followed_ids': followed_ids,
    })


@login_required
def account_billing(request):
    return render(request, 'account/billing.html', {
        'subscriptions': request.user.subscriptions.order_by('app_slug'),
        'payment_methods': request.user.payment_methods.all(),
    })


@login_required
def account_apps(request):
    return render(request, 'account/apps_hub.html', {
        'panels': account_panels.collect_panels(request.user),
    })


@login_required
def account_app_panel(request, slug):
    response = account_panels.render_app_panel(request, slug)
    if response is None:
        raise Http404("This app has no detailed account panel yet.")
    return response


@login_required
def account_privacy(request):
    return render(request, 'account/privacy.html')
