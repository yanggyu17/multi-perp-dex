# hyperliquid with treadfi (order by treadfi front api)
# price and get position directly by hyperliquid ws (to do)
from multi_perp_dex import MultiPerpDex, MultiPerpDexMixin
import aiohttp
from aiohttp import web
import asyncio
import json
import os
from typing import Optional, Dict
from eth_account import Account  
from eth_account.messages import encode_defunct  

class TreadfiHlExchange(MultiPerpDexMixin, MultiPerpDex):
	def __init__(
        self,
        session_cookies: Optional[Dict[str, str]] = None,
        evm_private_key: Optional[str] = None,
        wallet_address: str = None, # required
        account_name: str = None, # required
    ):
		self.wallet_address = wallet_address # will be used for get_position, get_collateral
		self.account_name = account_name
		self.url_base = "https://app.tread.fi/"
		self._http: Optional[aiohttp.ClientSession] = None
		self._logged_in = False
		self._cookies = session_cookies or {}
		self._pk = evm_private_key
		self._login_event: Optional[asyncio.Event] = None		
	
	async def login(self):
		"""
		1) session cookies가 있을경우 get_user_metadata 를 통해 정상 session인지 확인, 아닐시 2)->3)
		2) private key가 있을경우 msg 서명 -> signature 생성 -> session cookies udpate
		3) 1, 2둘다 없을 경우 webserver를 간단히 구동하여 msg 서명하게함 -> 서명시 signature 값 받아서 -> session cookies update
		2) or 3)의 경우도 get_user_metadata를 통해 data 확인후 "is_authenticated" 가 True면 login 확정
		서명 메시지
		"Sign in to Tread with nonce: {nonce}"
		"""
		pass

	async def logout(self):
		"""
		session cookies 재사용 금지용
		"""
		pass

	async def create_order(self, symbol, side, amount, price=None, order_type='market'):
		pass

	async def get_position(self, symbol):
		# to do, using ws
		pass
	
	async def close_position(self, symbol, position):
		return await super().close_position(symbol, position)
	
	async def get_collateral(self):
		# to do, using ws
		pass
	
	async def get_open_orders(self, symbol):
		pass
	
	async def cancel_orders(self, symbol):
		pass

	async def get_mark_price(self,symbol):
		# to do
		pass