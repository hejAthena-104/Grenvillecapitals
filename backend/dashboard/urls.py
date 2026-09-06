from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Main dashboard
    path('', views.dashboard_index, name='index'),

    # Deposits
    path('deposits/', views.deposits, name='deposits'),
    path('newdeposit/', views.new_deposit, name='new_deposit'),
    path('payment/<int:transaction_id>/', views.payment, name='payment'),

    # Swap (USD <-> BTC)
    path('swap/', views.swap, name='swap'),

    # Transfers (local / international) + beneficiaries
    path('transfers/', views.transfers, name='transfers'),
    path('transfers/local/', views.local_transfer, name='local_transfer'),
    path('transfers/international/', views.international_transfer, name='international_transfer'),
    path('beneficiaries/save/', views.save_beneficiary, name='save_beneficiary'),
    path('beneficiaries/<int:pk>/delete/', views.delete_beneficiary, name='delete_beneficiary'),

    # Legacy crypto withdrawal flow (reused by the international "crypto" method)
    path('withdrawals/', views.withdrawals, name='withdrawals'),
    path('enter-amount/', views.select_withdrawal_method, name='select_withdrawal_method'),
    path('withdraw-funds/', views.withdraw_funds, name='withdraw_funds'),
    path('getotp/', views.request_otp, name='request_otp'),

    # Services (admin-reviewed)
    path('loans/', views.loans, name='loans'),
    path('grants/', views.grants, name='grants'),
    path('cards/', views.cards, name='cards'),

    # History
    path('account-history/', views.account_history, name='account_history'),
    path('accounthistory/', views.account_history, name='accounthistory'),
    path('withdrawal-history/', views.withdrawal_history, name='withdrawal_history'),
    path('other-history/', views.other_history, name='other_history'),

    # Referrals
    path('refer/', views.refer_user, name='refer_user'),
    path('referuser/', views.refer_user, name='referuser'),

    # Settings
    path('account-settings/', views.account_settings, name='account_settings'),
    path('manage-account-security/', views.manage_account_security, name='manage_account_security'),
    path('set-pin/', views.set_transaction_pin, name='set_transaction_pin'),

    # Support
    path('support/', views.support, name='support'),

    # Internal transfer (user-to-user) kept for compatibility
    path('transfer-funds/', views.transfer_funds, name='transfer_funds'),

    # Admin Email Management
    path('send-email/', views.send_email, name='send_email'),
]
