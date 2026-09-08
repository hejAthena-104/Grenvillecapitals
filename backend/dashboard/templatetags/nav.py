"""Navigation helpers.

One map from URL name to tab, used by both the bottom bar and the sidebar.
Doing this in Python rather than as a chain of {% if %}s in the template is
what stops the two navs drifting apart, and it handles the duplicate URL
names (account_history/accounthistory, refer_user/referuser) that made the
old inline test fail to highlight.
"""
from django import template

register = template.Library()

# tab -> the url names that belong to it
TABS = {
    'home':     {'index'},
    'activity': {'account_history', 'accounthistory', 'withdrawal_history',
                 'other_history', 'deposits', 'new_deposit', 'payment',
                 'withdrawals', 'select_withdrawal_method', 'withdraw_funds'},
    'send':     {'transfers', 'local_transfer', 'international_transfer',
                 'transfer_funds', 'save_beneficiary', 'delete_beneficiary', 'swap'},
    'cards':    {'cards'},
    'profile':  {'profile', 'account_settings', 'manage_account_security',
                 'set_transaction_pin', 'kyc', 'refer_user', 'referuser',
                 'support', 'loans', 'grants', 'send_email'},
}

_URL_TO_TAB = {url: tab for tab, urls in TABS.items() for url in urls}


@register.simple_tag(takes_context=True)
def active_tab(context):
    """The bottom-bar tab that owns the current page, or ''."""
    match = context.get('request') and context['request'].resolver_match
    return _URL_TO_TAB.get(getattr(match, 'url_name', None), '') if match else ''


@register.simple_tag(takes_context=True)
def is_url(context, *names):
    """'active' when the current url name is any of `names`.

    Replaces the sidebar's `{% if url_name in 'a,b,c' %}`, which was a
    substring test: 'transfer' matched 'transfers,local_transfer' by accident.
    """
    match = context.get('request') and context['request'].resolver_match
    return 'active' if match and match.url_name in names else ''
