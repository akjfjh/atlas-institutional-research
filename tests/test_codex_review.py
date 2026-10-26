"""Codex review is required, structured, and cannot silently become a numeric-only report."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from atlas.core.codex_review import CodexReviewer
from atlas.core.state import ResearchState
from atlas.core.coordinator import Coordinator
from atlas.config import Config
from atlas.reporting.reports import render_markdown


def state():
    return ResearchState(asset='BTC',instrument_id='BTC-USDT',mode='quick',
                         engine='codex',required_roles=['technical'],
                         snapshot={'mode':'offline_fixture','ticker':{'last':100,'ts':1760000000000}})


def response():
    return {'summary_simple_zh':'资料不够完整，现在先等。',
            'summary_simple_en':'The information is incomplete; wait for now.',
            'summary_zh':'价格证据不足，先等待新的已收盘行情确认。',
            'summary_en':'The evidence is incomplete; wait for a new confirmed close.',
            'market_direction':'UNCLEAR','entry_view':'WAIT',
            'reasoning_zh':'现有行情不足以支持方向判断，也没有完整的风控。',
            'reasoning_en':'The current data cannot support direction and full risk was not run.',
            'contrary_zh':'当前没有足够的相反证据。','contrary_en':'Contrary evidence is insufficient.',
            'key_evidence_ids':[],
            'role_reviews':[{'agent_id':'technical','work_simple_zh':'看价格图','result_simple_zh':'还看不清方向，先等。',
                             'work_simple_en':'Read the chart','result_simple_en':'The direction is unclear; wait.',
                             'work_zh':'核对行情时间','result_zh':'证据不足，等待',
                             'work_en':'Checked market timestamps','result_en':'Evidence incomplete; wait',
                             'evidence_ids':[]}]}


def test_codex_cli_review_uses_read_only_structured_result(monkeypatch):
    seen={}
    monkeypatch.setattr('atlas.core.codex_review.shutil.which',lambda name:'/fake/codex')
    def fake_run(command,**options):
        seen['command']=command;seen['prompt']=options['input']
        from pathlib import Path
        Path(command[command.index('--output-last-message')+1]).write_text(json.dumps(response()))
        return SimpleNamespace(returncode=0,stdout='',stderr='model: test-codex\n')
    monkeypatch.setattr('atlas.core.codex_review.subprocess.run',fake_run)
    result=CodexReviewer().review(state())
    assert result['status']=='complete' and result['model']=='test-codex'
    assert '--sandbox' in seen['command'] and 'read-only' in seen['command']
    assert '--ephemeral' in seen['command'] and '--output-schema' in seen['command']
    assert 'entry_gate' in seen['prompt'] and 'can_open' in seen['prompt']


def test_codex_mode_never_publishes_a_parameter_only_report():
    with pytest.raises(ValueError,match='Codex research review is incomplete'):
        render_markdown(state())


def test_codex_failure_leaves_no_completed_report(monkeypatch,tmp_path):
    class Service:
        def collect(self,*args,**kwargs):
            return {'mode':'offline_fixture','retrieved_at':'2025-10-09T00:00:00+00:00',
                    'ticker':{'last':100,'ts':1760000000000},'candles':{},'errors':[]}
    def fail(self,state):raise RuntimeError('Codex unavailable for test')
    monkeypatch.setattr(CodexReviewer,'review',fail)
    coordinator=Coordinator(Config(data_dir=tmp_path),service=Service())
    with pytest.raises(RuntimeError,match='Codex unavailable'):
        coordinator.research('BTC-USDT',mode='quick',engine='codex')
    row=coordinator.repo.list()[0]
    saved=coordinator.repo.load(row['research_id'])
    assert saved.completed_at is None and saved.codex_review=={}
    assert any(event['kind']=='codex_failed' for event in saved.events)
    assert not (tmp_path/'reports'/saved.research_id/'report.md').exists()
