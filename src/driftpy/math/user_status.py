from driftpy.types import UserAccount, UserStatus


def is_user_protected_maker(user_account: UserAccount) -> bool:
    return (user_account.status & UserStatus.PROTECTED_MAKER) > 0
