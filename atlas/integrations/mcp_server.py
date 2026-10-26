"""Optional stdio MCP tools. No live order, transfer, earn or bot write tool exists."""
from __future__ import annotations
from atlas.security import redact

def create_server(config):
    from mcp.server.fastmcp import FastMCP
    from atlas.core.coordinator import Coordinator
    from atlas.core.storage import Repository
    from atlas.core.reviewer import RiskResearchAudit
    from atlas.cli import doctor
    server=FastMCP('ATLAS read-only research')
    @server.tool()
    def atlas_doctor()->dict:
        """Inspect local dependencies and READ permissions; no network probe or credentials returned."""
        return doctor(config)
    @server.tool()
    def atlas_research(instrument_id:str,mode:str='full',language:str|None=None)->dict:
        """Research a verified OKX instrument with Codex review of confirmed bars and source evidence; never trades."""
        if mode not in {'quick','full'}:raise ValueError('mode must be quick or full')
        selected=language or config.language
        if selected not in {'zh','en'}:raise ValueError('language must be zh or en')
        state=Coordinator(config).research(instrument_id,mode=mode,engine='codex',language=selected)
        return redact({'research_id':state.research_id,'phase':state.phase,'decision':state.decision,'engine':state.engine,
                       'codex_review_status':state.codex_review.get('status'),
                       'issues':[i.model_dump() for i in state.issues],'reports_dir':str(config.data_dir/'reports'/state.research_id)})
    @server.tool()
    def atlas_history(asset:str|None=None)->list[dict]:
        """Read local research archive index, optionally by asset."""
        return Repository(config.data_dir).list(asset)
    @server.tool()
    def atlas_report(research_id:str)->dict:
        """Read a local structured report by research ID; sanitized output."""
        return redact(Repository(config.data_dir).load(research_id).model_dump(mode='json'))
    @server.tool()
    def atlas_audit(research_id:str)->dict:
        """Recompute data and research gates; approval is research integrity, never trading permission."""
        state=Repository(config.data_dir).load(research_id);issues=RiskResearchAudit().review(state)
        return {'research_id':research_id,'issues':[i.model_dump() for i in issues],'approved':not any(i.severity in {'error','critical'} for i in issues)}
    return server

def serve(config):create_server(config).run(transport='stdio')
