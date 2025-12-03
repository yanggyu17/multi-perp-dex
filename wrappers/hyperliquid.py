from multi_perp_dex import MultiPerpDex, MultiPerpDexMixin
from .hyperliquid_ws_client import HLWSClientRaw, WS_POOL
import json
from typing import Dict, Optional, List, Dict, Tuple
import aiohttp
from aiohttp import TCPConnector
import asyncio

BASE_URL = "https://api.hyperliquid.xyz"
BASE_WS = "wss://api.hyperliquid.xyz/ws"

class HyperliquidExchange(MultiPerpDexMixin,MultiPerpDex):
    def __init__(self, 
              wallet_address = None,        # required
              wallet_private_key = None,    # optional, required when by_agent = False
              agent_api_address = None,     # optional, required when by_agent = True
              agent_api_private_key = None, # optional, required when by_agent = True
              by_agent = True,              # recommend to use True
              vault_address = None,         # optional, sub-account address
              *,
              ws_client = None, # ws client가 외부에서 생성됐으면 그걸 사용
              fetch_by_ws = False, # fetch pos, balance, and price by ws client
              signing_method = None, # special case: superstack, tread.fi
              ):

        self.by_agent = by_agent
        self.wallet_address = wallet_address

        # need error check
        if self.by_agent == False:
            self.wallet_private_key = wallet_private_key
            self.agent_api_address = None
            self.agent_api_private_key = None
        else:
            self.wallet_private_key = None
            self.agent_api_address = agent_api_address
            self.agent_api_private_key = agent_api_private_key

        self.vault_address = vault_address
        
        self.http_base = BASE_URL
        self.ws_base = BASE_WS
        self.spot_index_to_name = None
        self.spot_asset_index_to_pair = None
        self.spot_prices = None
        self.dex_list = ["hl"] # default and add

        self._http =  None

        # WS 관련 내부 상태
        self.ws_client: Optional[HLWSClientRaw] = ws_client if isinstance(ws_client, HLWSClientRaw) else None
        self._ws_owned: bool = self.ws_client is None   # comment: 풀에서 획득하면 True, 외부 주입이면 False
        self._ws_pool_key = None                        # comment: release 시 사용
        
        self.fetch_by_ws = fetch_by_ws
        self.signing_method = signing_method

    def _session(self) -> aiohttp.ClientSession:
        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession(
                connector=TCPConnector(
                    force_close=True,             # 매 요청 후 소켓 닫기 → 종료 시 잔여 소켓 최소화
                    enable_cleanup_closed=True,   # 종료 중인 SSL 소켓 정리 보조 (로그 억제)
                )
            )
        return self._http
    
    async def close(self):
        # HTTP 세션 종료 + WS 풀 release
        if self._http and not self._http.closed:
            await self._http.close()
        # 풀에서 소유한 WS만 release (외부 주입 WS는 소유권 없음)
        if self._ws_owned and self._ws_pool_key:
            ws_url, addr = self._ws_pool_key
            try:
                await WS_POOL.release(ws_url=ws_url, address=addr)
            except Exception:
                pass

    async def init(self):
        await self._init_spot_token_map() # for rest api 
        await self._get_dex_list()

    async def _get_dex_list(self):
        url = f"{self.http_base}/info"
        payload = {"type":"perpDexs"}
        headers = {"Content-Type": "application/json"}
        s = self._session()
        async with s.post(url, json=payload, headers=headers) as r:
            status = r.status
            try:
                resp = await r.json()
            except aiohttp.ContentTypeError:
                resp = await r.text()
        for e in resp:
            n = (e or{}).get("name")
            if n:
                self.dex_list.append(n)

    async def _init_spot_token_map(self):
        """
        REST info(spotMeta)를 통해
        - 토큰 인덱스 <-> 이름(USDC, PURR, ...) 맵
        - 스팟 페어 인덱스(spotInfo.index) <-> 'BASE/QUOTE' 및 (BASE, QUOTE) 맵
        을 1회 로드/갱신한다.
        """

        url = f"{self.http_base}/info"
        payload = {"type": "spotMeta"}
        headers = {"Content-Type": "application/json"}

        s = self._session()
        async with s.post(url, json=payload, headers=headers) as r:
            status = r.status
            try:
                resp = await r.json()
            except aiohttp.ContentTypeError:
                resp = await r.text()
        
        try:
            tokens = (resp or {}).get("tokens") or []
            universe = (resp or {}).get("universe") or (resp or {}).get("spotInfos") or []

            # 1) 토큰 맵(spotMeta.tokens[].index -> name)
            idx2name: Dict[int, str] = {}
            name2idx: Dict[str, int] = {}
            for t in tokens:
                if isinstance(t, dict) and "index" in t and "name" in t:
                    try:
                        idx = int(t["index"])
                        name = str(t["name"]).upper().strip()
                        if not name:
                            continue
                        idx2name[idx] = name
                        name2idx[name] = idx
                    except Exception as ex:
                        pass
            self.spot_index_to_name = idx2name
            self.spot_name_to_index = name2idx
            
            # 2) 페어 맵(spotInfo.index -> 'BASE/QUOTE' 및 (BASE, QUOTE))
            pair_by_index: Dict[int, str] = {}
            bq_by_index: Dict[int, tuple[str, str]] = {}
            ok = 0
            fail = 0
            for si in universe:
                if not isinstance(si, dict):
                    continue
                # 필수: spotInfo.index
                try:
                    s_idx = int(si.get("index"))
                except Exception:
                    fail += 1
                    continue

                # 우선 'tokens': [baseIdx, quoteIdx] 배열 처리
                base_idx = None
                quote_idx = None
                toks = si.get("tokens")
                if isinstance(toks, (list, tuple)) and len(toks) >= 2:
                    try:
                        base_idx = int(toks[0])
                        quote_idx = int(toks[1])
                    except Exception:
                        base_idx, quote_idx = None, None

                # 보조: 환경별 키(base/baseToken/baseTokenIndex, quote/...)
                if base_idx is None:
                    bi = si.get("base") or si.get("baseToken") or si.get("baseTokenIndex")
                    try:
                        base_idx = int(bi) if bi is not None else None
                    except Exception:
                        base_idx = None
                if quote_idx is None:
                    qi = si.get("quote") or si.get("quoteToken") or si.get("quoteTokenIndex")
                    try:
                        quote_idx = int(qi) if qi is not None else None
                    except Exception:
                        quote_idx = None

                base_name = idx2name.get(base_idx) if base_idx is not None else None
                quote_name = idx2name.get(quote_idx) if quote_idx is not None else None

                # name 필드가 'BASE/QUOTE'면 그대로, '@N' 등인 경우 토큰명으로 합성
                name_field = si.get("name")
                pair_name = None
                if isinstance(name_field, str) and "/" in name_field:
                    pair_name = name_field.strip().upper()
                    # base/quote 이름 보완
                    try:
                        b, q = pair_name.split("/", 1)
                        base_name = base_name or b
                        quote_name = quote_name or q
                    except Exception:
                        pass
                else:
                    if base_name and quote_name:
                        pair_name = f"{base_name}/{quote_name}"

                if pair_name and base_name and quote_name:
                    pair_by_index[s_idx] = pair_name
                    bq_by_index[s_idx] = (base_name, quote_name)
                    ok += 1
                else:
                    fail += 1

            self.spot_asset_index_to_pair = pair_by_index
            self.spot_asset_index_to_bq = bq_by_index

        except Exception as e:
            pass

    async def create_ws_client(self):
        """
        WS 커넥션을 '1회 연결 + 다중 구독'으로 운용.
        - 외부 ws_client가 주어지면 그것을 사용(연결/구독 보장 후 필요한 DEX만 추가 구독)
        - 없으면 전역 풀(WS_POOL)에서 (ws_url,address) 키로 하나를 획득하여 공유
        """
        # 기본 주소(서브계정 우선)
        address = self.vault_address if self.vault_address else self.wallet_address
        dex_list = list(set([d.lower() for d in (self.dex_list or ["hl"])]))

        # 1) 외부에서 ws_client가 주어진 경우: 연결/구독 보장 후 필요한 DEX 구독만 추가
        if self.ws_client is not None:
            # comment: 주소가 다르면 유저 스트림(webData3/spotState)은 이 인스턴스와 불일치할 수 있음
            try:
                await self.ws_client.ensure_spot_token_map_http() # rest api
                await self.ws_client.ensure_connected_and_subscribed()
                # 필요한 DEX를 동일 커넥션에서 추가 구독
                for dex in dex_list:
                    await self.ws_client.ensure_allmids_for(None if dex == "hl" else dex)
            except Exception as e:
                raise
            return

        # 2) 풀에서 획득(없으면 생성) → 연결/구독은 풀에서 처리
        #    키: (ws_base, address)
        #    참고: address=None이면 '가격 전용' 공유 커넥션
        # 풀 acquire
        client = await WS_POOL.acquire(
            ws_url=self.ws_base,
            http_base=self.http_base,
            address=address,
            dex=None,  # comment: 우선 기본(HL) allMids
        )
        # 필요한 다른 DEX allMids도 추가 구독
        for dex in dex_list:
            if dex != "hl":
                await client.ensure_allmids_for(dex)

        self.ws_client = client
        self._ws_owned = True
        self._ws_pool_key = (self.ws_base, (address or "").lower())

    async def create_order(self, symbol, side, amount, price=None, order_type='market'):
        pass

    async def get_position(self, symbol):
        pass
    
    async def close_position(self, symbol, position):
        pass
    
    async def get_collateral(self):
        pass
    
    async def get_open_orders(self, symbol):
        pass
    
    async def cancel_orders(self, symbol):
        pass

    async def get_mark_price(self,symbol,*,is_spot=False):
        if self.fetch_by_ws:
            try:
                return await self.get_mark_price_ws(symbol,is_spot=is_spot)
            except Exception as e:
                pass # fallback to rest api
        
        # default rest api
    
    async def get_mark_price_ws(self,symbol,*,is_spot=False):
        pass

    async def get_open_orders(self, symbol):
        pass
    

async def test():
    hl = HyperliquidExchange()
    await hl.init()
    print(hl.spot_index_to_name)
    print(hl.spot_name_to_index)

if __name__ == "__main__":
    asyncio.run(test())