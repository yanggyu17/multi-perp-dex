from dataclasses import dataclass

@dataclass
class TreadfiHlKey:
    session_cookies: dict
    evm_private_key: str
    wallet_address: str
    account_name: str

TREADFIHL_KEY = TreadfiHlKey(
    session_cookies = {"csrftoken":"",
                       "sessionid":""}, # session cookies, can pass
    evm_private_key = '', # your evm address, can pass
    wallet_address = '', # required, main **OR** subaccount address of hyperliquid connected to treadfi
    account_name= '', # your account name of hyperliquid @ traedfi
    )
