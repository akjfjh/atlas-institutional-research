"""Optional MCP SDK stdio bridge. No MCP server is silently installed or launched."""
from __future__ import annotations
import asyncio
import json
from typing import Any
from atlas.integrations.skill_adapter import READ_COMMANDS

TOOLS={'ticker':'market_get_ticker','candles':'market_get_candles','instruments':'market_get_instruments',
       'orderbook':'market_get_orderbook','funding_rate':'market_get_funding_rate','open_interest':'market_get_open_interest',
       'mark_price':'market_get_mark_price','news_latest':'news_get_latest','coin_sentiment':'news_get_coin_sentiment','smartmoney_signal':'smartmoney_get_signal_overview_by_filter'}

def unwrap_read_data(data):
    """Official MCP may wrap OKX REST data inside two response envelopes."""
    for _ in range(3):
        if not isinstance(data,dict) or 'data' not in data:break
        if str(data.get('code','0')) not in {'0',''}:raise ValueError('upstream returned a nonzero OKX code')
        data=data['data']
    return data

class OKXMCPBridge:
    def __init__(self,command:list[str]|None=None,timeout:float=20):
        self.command=command;self.timeout=timeout
    def call(self,capability:str,params:dict)->dict:
        if capability not in TOOLS:raise PermissionError('MCP tool is not in the read allowlist')
        if not self.command:return {'ok':False,'error':{'provider':'okx_mcp','code':'not_configured','message':'Optional MCP command not configured'}}
        try:return asyncio.run(asyncio.wait_for(self._call(capability,params),timeout=self.timeout))
        except Exception as exc:return {'ok':False,'error':{'provider':'okx_mcp','code':'bridge_error','message':type(exc).__name__}}
    async def _call(self,capability:str,params:dict)->dict:
        from mcp import ClientSession,StdioServerParameters
        from mcp.client.stdio import stdio_client
        async with stdio_client(StdioServerParameters(command=self.command[0],args=self.command[1:])) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                tools=await session.list_tools()
                name=TOOLS[capability]
                if name not in {tool.name for tool in tools.tools}:
                    return {'ok':False,'error':{'provider':'okx_mcp','code':'unsupported_tool','message':name+' absent from server discovery'}}
                result=await session.call_tool(name,params)
                if result.isError:return {'ok':False,'error':{'provider':'okx_mcp','code':'tool_error','message':'MCP tool returned an error'}}
                data=getattr(result,'structuredContent',None)
                if data is None:
                    parts=[c.text for c in result.content if hasattr(c,'text')]
                    data=json.loads(''.join(parts))
                data=unwrap_read_data(data)
                return {'ok':True,'data':data,'source':'okx_mcp'}
