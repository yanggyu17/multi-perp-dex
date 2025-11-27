from multi_perp_dex import MultiPerpDex, MultiPerpDexMixin  # [UNCHANGED]

# [ADDED] exchange_factory의 함수들을 "지연 임포트"로 재노출
#        - 이렇게 해야 mpdex를 import할 때 wrappers의 무거운 의존성을 즉시 요구하지 않습니다.
async def create_exchange(exchange_name: str, key_params=None):  # [ADDED]
    # comment: 호출 시점에만 exchange_factory를 불러오므로, 선택적 의존성이 없을 경우에도 import mpdex는 안전합니다.
    from exchange_factory import create_exchange as _create_exchange  # [ADDED]
    return await _create_exchange(exchange_name, key_params)  # [ADDED]

def symbol_create(exchange_name: str, coin: str):  # [ADDED]
    from exchange_factory import symbol_create as _symbol_create  # [ADDED]
    return _symbol_create(exchange_name, coin)  # [ADDED]

# [ADDED] 개별 래퍼 클래스는 __getattr__로 지연 노출(필요할 때만 import)
#         사용 예: from mpdex import LighterExchange
import importlib  # [ADDED]

def __getattr__(name):  # [ADDED]
    mapping = {
        "LighterExchange": ("wrappers.lighter", "LighterExchange"),
        "BackpackExchange": ("wrappers.backpack", "BackpackExchange"),
        "EdgexExchange": ("wrappers.edgex", "EdgexExchange"),
        "GrvtExchange": ("wrappers.grvt", "GrvtExchange"),
        "ParadexExchange": ("wrappers.paradex", "ParadexExchange"),
        "TreadfiHlExchange": ("wrappers.treadfi_hl.py","TreadfiHlExchange")
    }
    if name in mapping:
        mod, attr = mapping[name]
        module = importlib.import_module(mod)
        return getattr(module, attr)
    raise AttributeError(f"module 'mpdex' has no attribute {name!r}")

__all__ = [  # [ADDED] 공개 심볼 명시
    "MultiPerpDex", "MultiPerpDexMixin",
    "create_exchange", "symbol_create",
    "LighterExchange", "BackpackExchange", "EdgexExchange", "GrvtExchange", "ParadexExchange", "TreadfiHlExchange"
]