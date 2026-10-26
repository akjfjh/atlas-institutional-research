from __future__ import annotations
import json,sqlite3,hashlib,os,shutil
from pathlib import Path
from atlas.core.state import ResearchState, now
from atlas.security import redact
class Repository:
    def __init__(self,data_dir):
        self.root=Path(data_dir).expanduser(); self.root.mkdir(parents=True,exist_ok=True)
        try: self.root.chmod(0o700)
        except OSError: pass
        self.path=self.root/'atlas.db'
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS research(id TEXT PRIMARY KEY,created_at TEXT,completed_at TEXT,asset TEXT,instrument TEXT,phase TEXT,decision TEXT,version INTEGER,state TEXT);
CREATE INDEX IF NOT EXISTS research_asset_time ON research(asset,created_at);
CREATE TABLE IF NOT EXISTS agent_versions(research_id TEXT,agent_id TEXT,version INTEGER,result TEXT,PRIMARY KEY(research_id,agent_id,version));
CREATE TABLE IF NOT EXISTS evidence(research_id TEXT,evidence_id TEXT,data TEXT,PRIMARY KEY(research_id,evidence_id));
CREATE TABLE IF NOT EXISTS event_log(research_id TEXT,event_id TEXT,kind TEXT,timestamp TEXT,data TEXT,PRIMARY KEY(research_id,event_id));
CREATE TABLE IF NOT EXISTS historical_events(event_id TEXT PRIMARY KEY,event_type TEXT,event_time TEXT,data TEXT);
CREATE INDEX IF NOT EXISTS historical_events_type_time ON historical_events(event_type,event_time);
CREATE TABLE IF NOT EXISTS outcomes(research_id TEXT,horizon_days INTEGER,observed_at TEXT,data TEXT,PRIMARY KEY(research_id,horizon_days));
CREATE TABLE IF NOT EXISTS report_hashes(research_id TEXT,format TEXT,sha256 TEXT,PRIMARY KEY(research_id,format));''')
        try:self.path.chmod(0o600)
        except OSError:pass
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10);db.execute('PRAGMA journal_mode=WAL');return db
    def save(self,state):
        raw=redact(state.model_dump(mode='json'))
        payload=json.dumps(raw,ensure_ascii=False,allow_nan=False)
        with self.connect() as db:
            previous=db.execute('SELECT state FROM research WHERE id=?',(state.research_id,)).fetchone()
            if previous:
                old=json.loads(previous[0])
                if old['version']!=state.version:raise ValueError('concurrent update: reload research state before saving')
                if old['snapshot'] and old['snapshot']!=raw['snapshot']:raise ValueError('original snapshot is immutable; create a new research ID')
                if set(old['evidence'])-set(raw['evidence']):raise ValueError('cannot remove original evidence')
            for eid,e in raw['evidence'].items():
                old_ev=db.execute('SELECT data FROM evidence WHERE research_id=? AND evidence_id=?',(state.research_id,eid)).fetchone()
                if old_ev and json.loads(old_ev[0])!=e:raise ValueError('evidence is immutable; create a new evidence ID')
            for aid,result in raw['results'].items():
                old_result=db.execute('SELECT result FROM agent_versions WHERE research_id=? AND agent_id=? AND version=?',(state.research_id,aid,result['version'])).fetchone()
                if old_result and json.loads(old_result[0])!=result:raise ValueError('agent versions are immutable; increment version')
            raw['version']=state.version+1
            payload=json.dumps(raw,ensure_ascii=False,allow_nan=False)
            db.execute('INSERT OR REPLACE INTO research VALUES(?,?,?,?,?,?,?,?,?)',(state.research_id,state.created_at,state.completed_at,state.asset,state.instrument_id,state.phase,state.decision,raw['version'],payload))
            for a,r in raw['results'].items():db.execute('INSERT OR IGNORE INTO agent_versions VALUES(?,?,?,?)',(state.research_id,a,r['version'],json.dumps(r,ensure_ascii=False)))
            for eid,e in raw['evidence'].items():db.execute('INSERT OR REPLACE INTO evidence VALUES(?,?,?)',(state.research_id,eid,json.dumps(e,ensure_ascii=False)))
            for e in raw['events']:db.execute('INSERT OR IGNORE INTO event_log VALUES(?,?,?,?,?)',(state.research_id,e['event_id'],e['kind'],e['timestamp'],json.dumps(e,ensure_ascii=False)))
        state.version=raw['version']
    def load(self,rid):
        with self.connect() as db:r=db.execute('SELECT state FROM research WHERE id=?',(rid,)).fetchone()
        if not r:raise KeyError('research ID not found: '+rid)
        return ResearchState.model_validate_json(r[0])
    def list(self,asset=None,days=None,limit=50):
        q='SELECT id,created_at,asset,instrument,phase,decision,version FROM research WHERE 1=1';args=[]
        if asset:q+=' AND asset=?';args.append(asset.upper())
        if days:
            from datetime import datetime,timedelta,timezone
            q+=' AND created_at>=?';args.append((datetime.now(timezone.utc)-timedelta(days=days)).isoformat())
        q+=' ORDER BY created_at DESC LIMIT ?';args.append(limit)
        with self.connect() as db:rows=db.execute(q,args).fetchall()
        return [dict(zip(['research_id','created_at','asset','instrument_id','phase','decision','version'],r)) for r in rows]
    def similar(self,asset,regime=None,limit=5):
        rows=self.list(asset,limit=20);out=[]
        for row in rows:
            st=self.load(row['research_id']);found=st.results.get('technical');rg=found.market_regime if found else 'unknown'
            if regime is None or rg==regime:out.append({**row,'market_regime':rg,'comparison_only':True})
        return out[:limit]
    def versions(self,rid):
        with self.connect() as db:rows=db.execute('SELECT result FROM agent_versions WHERE research_id=? ORDER BY agent_id,version',(rid,)).fetchall()
        return [json.loads(x[0]) for x in rows]
    def compare(self,a,b):
        sa,sb=self.load(a),self.load(b)
        return {'a':sa.model_dump(mode='json'),'b':sb.model_dump(mode='json'),'changed_decision':sa.decision!=sb.decision,'created_at':[sa.created_at,sb.created_at]}
    def delete(self,rid):
        self.load(rid)
        # Recoverable local deletion via SQLite backup; no remote state.
        backup=self.backup()
        with self.connect() as db:
            for table in ['agent_versions','evidence','event_log','outcomes','report_hashes']:db.execute(f'DELETE FROM {table} WHERE research_id=?',(rid,))
            db.execute('DELETE FROM research WHERE id=?',(rid,))
        reports=self.root/'reports'/rid
        if reports.exists(): shutil.move(str(reports),str(self.root/'backups'/(rid+'-'+now().replace(':','-'))))
        return {'deleted':rid,'backup':str(backup),'recoverable':True}
    def backup(self):
        dest=self.root/'backups';dest.mkdir(exist_ok=True)
        p=dest/('atlas-'+now().replace(':','-')+'.db')
        with self.connect() as db,sqlite3.connect(p) as target:db.backup(target)
        return p
    def add_events(self,events):
        with self.connect() as db:
            for e in events:db.execute('INSERT OR REPLACE INTO historical_events VALUES(?,?,?,?)',(e['event_id'],e['event_type'],str(e['event_time']),json.dumps(redact(e),ensure_ascii=False)))
    def events(self,event_type):
        with self.connect() as db:rows=db.execute('SELECT data FROM historical_events WHERE event_type=? ORDER BY event_time',(event_type,)).fetchall()
        return [json.loads(r[0]) for r in rows]
    def hash_report(self,rid,fmt,content):
        h=hashlib.sha256(content.encode()).hexdigest()
        with self.connect() as db:db.execute('INSERT OR REPLACE INTO report_hashes VALUES(?,?,?)',(rid,fmt,h))
        return h
    def check_report_hash(self,rid,fmt,content):
        with self.connect() as db:r=db.execute('SELECT sha256 FROM report_hashes WHERE research_id=? AND format=?',(rid,fmt)).fetchone()
        return bool(r and r[0]==hashlib.sha256(content.encode()).hexdigest())

    def lock(self,rid):
        from contextlib import contextmanager
        @contextmanager
        def held():
            folder=self.root/'locks';folder.mkdir(exist_ok=True)
            path=folder/(hashlib.sha256(rid.encode()).hexdigest()+'.lock')
            with open(path,'a+b') as handle:
                if os.name=='nt':
                    import msvcrt
                    handle.seek(0);handle.write(b'0');handle.flush();handle.seek(0)
                    msvcrt.locking(handle.fileno(),msvcrt.LK_LOCK,1)
                else:
                    import fcntl
                    fcntl.flock(handle,fcntl.LOCK_EX)
                try:yield
                finally:
                    if os.name=='nt':
                        handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
                    else:fcntl.flock(handle,fcntl.LOCK_UN)
        return held()
