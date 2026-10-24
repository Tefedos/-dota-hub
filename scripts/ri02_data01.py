"""Read-only RI-02-DATA audit; writes only new audit artifacts, never production DB.
Run from repo root: .venv/bin/python scripts/ri02_data01.py capture|offline|experiments|verify
"""
import asyncio, ast, copy, csv, hashlib, json, subprocess, sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
OUT=ROOT/'docs/qa/ri02/data01'; OUT.mkdir(exist_ok=True,parents=True)
CAL=ROOT/'docs/qa/ri02/cal01/raw'
PILOTS=(9051271323,9057722463)
def dump(name,value):
    path=OUT/name; path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n')
def read(path): return json.loads(Path(path).read_text())
def sha(value): return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def state():
    files=[p for d in ('backend','frontend') for p in (ROOT/d).rglob('*') if p.is_file() and not any(x in p.parts for x in ('node_modules','__pycache__','.pytest_cache','dist','.mypy_cache','.venv')) and p.suffix in ('.py','.json','.tsx','.ts','.css','.toml')]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
async def capture():
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.core.config import Settings
    import httpx
    if (OUT/'capture.json').exists(): raise SystemExit('Capture already frozen; offline only')
    dump('baseline.json',{'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'status':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),'hashes':state(),'time':datetime.now(UTC).isoformat()})
    cfg=Settings(); engine=create_async_engine(cfg.database_url.get_secret_value(),hide_parameters=True)
    result={'captured_at':datetime.now(UTC).isoformat(),'transaction':'SET TRANSACTION READ ONLY','matches':{},'api':{}}
    async with engine.connect() as conn:
        await conn.execute(text('SET TRANSACTION READ ONLY'))
        result['schema']=[dict(r) for r in (await conn.execute(text("SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position"))).mappings()]
        for mid in PILOTS:
            row=(await conn.execute(text('SELECT match_id,fetch_status,raw_payload,fetched_at,created_at,updated_at FROM matches WHERE match_id=:id'),{'id':mid})).mappings().first()
            reports=[dict(r) for r in (await conn.execute(text('SELECT algorithm_version,status,completeness,computed_at,report_payload FROM match_analyses WHERE match_id=:id ORDER BY algorithm_version'),{'id':mid})).mappings()]
            dump(f'private/db_{mid}.json',{'match':dict(row) if row else None,'reports':reports})
            result['matches'][str(mid)]={'exists':row is not None,'raw_digest':sha(row['raw_payload']) if row else None,'frozen_cal_digest':sha(read(CAL/f'{mid}.json')),'fetch_status':row['fetch_status'] if row else None,'fetched_at':row['fetched_at'] if row else None,'reports':[{k:v for k,v in r.items() if k!='report_payload'} for r in reports]}
    await engine.dispose()
    async with httpx.AsyncClient(timeout=15,trust_env=False) as client:
        for mid in PILOTS:
            for prefix in ('local-alpha/matches','matches'):
                for section in ('overview','players','draft','ruiner','timeline'):
                    url=f'http://127.0.0.1:8000/api/v1/{prefix}/{mid}/{section}'
                    key=f'{prefix}/{mid}/{section}'
                    try:
                        r=await client.get(url); body=r.json()
                        dump(f'private/api_{prefix.replace("/","_")}_{mid}_{section}.json',body)
                        result['api'][key]={'status':r.status_code,'body_digest':sha(body),'headers':{k:v for k,v in r.headers.items() if k in ('cache-control','retry-after','content-type')}}
                    except Exception as exc: result['api'][key]={'error':type(exc).__name__}
        try:
            r=await client.get('http://127.0.0.1:8000/openapi.json')
            if r.status_code==200: dump('private/openapi.json',r.json())
            result['openapi_status']=r.status_code
        except Exception as exc: result['openapi_error']=type(exc).__name__
    dump('capture.json',result)
    print(json.dumps({'matches':result['matches'],'api':result['api']},default=str))

if __name__=='__main__' and sys.argv[1]=='capture': asyncio.run(capture())

P0M='match_id start_time duration game_mode lobby_type radiant_win radiant_score dire_score patch version replay_salt'.split()
P0P='player_slot hero_id account_id personaname isRadiant is_radiant leaver_status level hero_variant lane_role lane is_roaming position_est kills deaths assists hero_damage tower_damage hero_healing stuns teamfight_participation gold_per_min xp_per_min last_hits denies net_worth gold gold_spent total_gold total_xp obs_placed sen_placed observer_kills sentry_kills obs sen purchase_ward_observer purchase_ward_sentry obs_log camps_stacked creeps_stacked roshan_kills tower_kills courier_kills neutral_kills buyback_count lane_efficiency_pct'.split()
P1M='picks_bans draft_timings objectives teamfights radiant_gold_adv radiant_xp_adv kills_log buyback_log purchase_log'.split()
P1P=([f'item_{i}' for i in range(6)]+[f'backpack_{i}' for i in range(3)]+ 'item_neutral gold_t xp_t lh_t kills_log deaths_log buyback_log purchase_log connection_log sen_log lane_pos hero_damage_t hero_healing_t damage_inflictor damage_taken damage_targets ability_uses ability_targets ability_upgrades_arr item_uses neutral_item_history purchase_time'.split())
PM={k:k for k in 'hero_id account_id kills deaths assists last_hits denies hero_damage tower_damage hero_healing net_worth level buyback_count obs_placed sen_placed observer_kills sentry_kills player_slot'.split()}
PM.update(gold_per_min='gpm',xp_per_min='xpm',stuns='stun_duration_seconds',personaname='display_name',lane_role='position',position_est='performance_position',item_neutral='neutral_item',purchase_time='item_timings')
MM={k:'summary.'+k for k in P0M if k not in ('version','replay_salt','radiant_score','dire_score','radiant_win')}
MM.update(radiant_score='summary.radiant.score',dire_score='summary.dire.score',radiant_win='summary.winner')
OM={'deaths':'deaths_per_min','kills':'kill_participation','assists':'kill_participation','gold_per_min':'gpm','xp_per_min':'xpm','hero_damage':'hero_damage_per_min','tower_damage':'tower_damage_per_min','hero_healing':'healing_per_min',**{k:k for k in ('obs_placed','sen_placed','observer_kills','sentry_kills')}}
def get(value,path):
    for part in path.split('.'):
        if isinstance(value,dict): value=value.get(part)
        elif isinstance(value,(list,tuple)) and part.isdecimal(): value=value[int(part)] if int(part)<len(value) else None
        else: return None
    return value

def compact(v):
    if isinstance(v,(dict,list)) and len(json.dumps(v))>450: return json.dumps({'type':type(v).__name__,'count':len(v),'sha256':sha(v),'sample':str(v)[:120]},ensure_ascii=False)
    return json.dumps(v,ensure_ascii=False)

def diff(a,b,path=''):
    if type(a)!=type(b): return [path]
    if isinstance(a,dict): return sum((diff(a.get(k),b.get(k),path+'.'+k) for k in sorted(a.keys()|b.keys())),[])
    if isinstance(a,list): return [path+'.length'] if len(a)!=len(b) else sum((diff(x,y,f'{path}[{i}]') for i,(x,y) in enumerate(zip(a,b))),[])
    return [path] if a!=b else []

def offline():
    from statistics import median
    from app.services.match_normalization import normalize_match_snapshot
    from app.services.performance import analyze_performance
    from app.services.performance_config import PerformanceConfig
    from app.services.performance_preliminary import project_preliminary
    from app.services.player_catalog import hero_catalog
    from app.models.performance import RuinerReport
    from app.services.match_analysis import digest, MatchAnalysisService
    from app.models.match_api import MatchEnvelope
    cfg=PerformanceConfig(); _,catalog=hero_catalog(); names={k:v['name'] for k,v in catalog.items()}
    rows=[]; traces=[]; census=[]; api=[]
    cols='source_field source_json_path source_type priority source_presence storage_location backend_mapping normalized_field transformation derived_from used_in_ruiner expected_api_path actual_api_path observed_value discrepancy status evidence'.split()
    for source in sorted(CAL.glob('[0-9]*.json')):
        snap=read(source); raw=snap['match']; mid=raw['match_id']
        before=sha(snap); norm=normalize_match_snapshot(snap,hero_names=names); nd=norm.model_dump(mode='json')
        report=analyze_performance(norm); rd=report.model_dump(mode='json'); assert sha(snap)==before
        pp={p['player_slot']:p for p in nd['players']}; rr={p['player_slot']:p for p in rd['players']}
        live={s:read(OUT/f'private/api_local-alpha_matches_{mid}_{s}.json') for s in ('overview','players','draft','ruiner','timeline')} if mid in PILOTS else {}
        present=Counter()
        for scope,entries,fields0,fields1 in [('match',[raw],P0M,P1M),('player',raw['players'],P0P,P1P)]:
            for ix,entry in enumerate(entries):
                slot=entry.get('player_slot'); n=pp.get(slot,{})
                fields=sorted(set(entry)|set(fields0)|set(fields1))
                for f in fields:
                    v=entry.get(f); exists=f in entry; priority='P0' if f in fields0 else 'P1' if f in fields1 else 'P2'
                    mapped=None; nv=None; transform='not typed; retained in persisted sanitized raw'
                    if scope=='match':
                        mapped=MM.get(f); nv=get(nd,mapped) if mapped else None
                        if f in ('picks_bans','objectives','teamfights','radiant_gold_adv','radiant_xp_adv','kills_log','buyback_log','purchase_log'):
                            mapped='raw.draft' if f=='picks_bans' else 'raw.events.'+f; nv=get(nd,mapped)
                    else:
                        mapped=PM.get(f)
                        if f.startswith('item_') and f[5:].isdigit(): mapped='items.'+f[5:]
                        if f.startswith('backpack_') and f[9:].isdigit(): mapped='backpack_items.'+f[9:]
                        nv=get(n,mapped) if mapped else None
                        if f in ('kills_log','buyback_log','purchase_log'): mapped='raw.events.player_logs'; nv=[l[f] for l in nd['raw']['events']['player_logs'] if l['player_slot']==slot][0]
                    if mapped: transform='typed validation; no missing-to-zero substitution'
                    if f in ('duration','start_time'): transform+='; seconds (start_time Unix UTC)'
                    if f in ('gold_per_min','xp_per_min'): transform='nonnegative integer rename; already per minute, no duration division'
                    if f in ('hero_damage','tower_damage','hero_healing','deaths'): transform='nonnegative integer; evaluator rate = raw*60/duration, full float precision'
                    if f=='stuns': transform='finite nonnegative float seconds (fraction retained)'
                    if f=='position_est': transform='1..5 integer -> performance_position estimated; not inferred from lane'
                    if f=='lane_role': transform='1..4 -> lane label, evidence confirmed; not farm position'
                    if f=='personaname': transform='whitespace collapse, max80 chars, missing -> anonymous label'
                    if f in ('isRadiant','is_radiant'): transform='not consumed; team derived solely from player_slot<128'
                    if f=='radiant_win': transform='True->radiant; False->dire; other->null; no RI influence'
                    presence='present' if v is not None else 'null' if exists else 'absent'
                    if f=='account_id': presence='UNVERIFIED original HTTP; removed in saved snapshot'
                    status='PRESENT_CORRECT' if mapped and v is not None else 'NOT_MAPPED' if v is not None else 'MISSING_IN_SOURCE'
                    discrepancy=''
                    if scope=='player' and f=='leaver_status' and v is not None:
                        status='LOST_IN_BACKEND'; discrepancy='Preserved in PostgreSQL raw, absent in PlayerStat/RI; leaver_context_unknown'
                    if f=='account_id':
                        status='UNVERIFIED'; discrepancy='Sanitizer intentionally removes; original HTTP presence not recoverable from frozen snapshot'
                    if mapped and v is not None and nv is None:
                        status='PRESENT_INCORRECT'; discrepancy='nonnull source rejected by typed normalization; inspect source type/range'
                    sourcepath=f'$.match.{f}' if scope=='match' else f'$.match.players[{ix}].{f} (player_slot={slot})'
                    expected='not part of ruiner public DTO'; actual='not exposed'; usage='no'
                    if scope=='player':
                        if f in OM:
                            usage='yes: '+OM[f]; expected='ruiner.data.players[slot].observed_metrics.'+OM[f]
                        elif f in ('position_est','hero_id','player_slot'): usage='yes: role/cohort or roster'
                        if live:
                            rp=next(p for p in live['ruiner']['data']['players'] if p['player_slot']==slot)
                            lp=next(p for p in live['players']['data']['players'] if p['player_slot']==slot)
                            paths=[]
                            if f in OM and OM[f] in rp['observed_metrics']: paths.append('ruiner.data.players[slot].observed_metrics.'+OM[f])
                            if mapped and mapped.split('.')[0] in lp: paths.append('players.data.players[slot].'+mapped)
                            if f in ('hero_id','player_slot'): paths.append('ruiner.data.players[slot].'+f)
                            if f=='position_est': paths.append('ruiner.data.players[slot].position')
                            actual='; '.join(paths) if paths else 'not exposed'
                        elif f in OM: actual='UNVERIFIED REST; offline observed.'+OM[f]
                    else:
                        if f in ('duration','game_mode','radiant_score','dire_score'): usage='yes: denominator/gates'
                        if live and f in MM:
                            op={'radiant_win':'winner','radiant_score':'radiant.score','dire_score':'dire.score'}.get(f,f)
                            actual='overview.data.'+op if op.split('.')[0] in live['overview']['data'] else 'not exposed'
                    if f=='account_id': v='<removed; original presence unverified>'
                    if f=='account_id': nv=None
                    evidence=f'{source.relative_to(ROOT)}; sha256(canonical snapshot)={before}; match_id={mid}'
                    rows.append(dict(zip(cols,[f,sourcepath,type(entry.get(f)).__name__ if exists else 'missing',priority,presence,'matches.raw_payload'+sourcepath[1:] if mid in PILOTS else str(source.relative_to(ROOT))+' (research only; DB not asserted)',('match_normalization._player' if scope=='player' else 'normalize_match_snapshot') if mapped else 'none',mapped or '',transform,'player_slot' if f in ('isRadiant','is_radiant') else '',usage,expected,actual,compact({'raw':v,'normalized':nv,**({'observed':rr[slot]['observed_metrics'].get(OM[f])} if scope=='player' and f in OM else {})}),discrepancy,status,evidence])))
                    present[(priority,status)]+=1
        # Draft nested action fields, explicit source index; never infer order from roster.
        for i,action in enumerate(raw.get('picks_bans') or []):
            for key in ('hero_id','team','is_pick','order'):
                rows.append(dict(zip(cols,[key,f'$.match.picks_bans[{i}].{key}',type(action.get(key)).__name__,'P1','present' if key in action else 'absent','matches.raw_payload' if mid in PILOTS else str(source.relative_to(ROOT)),'match_normalization._draft',f'raw.draft.actions[{i}].'+('team_code' if key=='team' else key),'validate explicit source action; no synthetic order','','no','not a ruiner field','draft actions (section-specific)',compact(action.get(key)),'','PRESENT_CORRECT' if key in action else 'MISSING_IN_SOURCE',f'match_id={mid}; {source.relative_to(ROOT)}'])) )
        for p in rd['players']:
            slot=p['player_slot']; np=pp[slot]; rawp=next(x for x in raw['players'] if x['player_slot']==slot)
            cohort=[x for x in rd['players'] if x['team']==p['team'] and (p['role_group']=='unknown' or x['role_group']==p['role_group']) and x['player_slot']!=slot]
            weights=cfg.core_weights if p['role_group']=='core' else cfg.fallback_weights
            comparisons={}
            for metric,value in p['observed_metrics'].items():
                if metric in ('kda','kill_participation_counter_ratio'): continue
                peers={x['player_slot']:x['observed_metrics'][metric] for x in cohort if x['observed_metrics'].get(metric) is not None}
                ref=median(peers.values()) if peers else None
                floor=60/raw['duration'] if metric.endswith('_per_min') else 1/(raw['radiant_score'] if p['team']=='radiant' else raw['dire_score']) if metric=='kill_participation' and (raw['radiant_score'] if p['team']=='radiant' else raw['dire_score']) else 1
                usable=value is not None and len(peers)+1>=cfg.minimum_cohort and ref is not None and (ref!=0 or metric=='deaths_per_min')
                bad=good=None
                if usable:
                    denom=max(ref,floor); bad=min(1,max(0,((value-ref) if metric=='deaths_per_min' else (ref-value))/denom)); good=min(1,max(0,((ref-value) if metric=='deaths_per_min' else (value-ref))/denom))
                comparisons[metric]={'peer_values':peers,'reference':ref,'denominator_floor':floor,'comparison_available':usable,'bad':bad,'good':good}
            coverage=p['evidence_coverage']; weighted=sum(weights[k]*v for k,v in p['axes'].items() if v is not None)
            base=100*weighted/coverage if coverage else None
            credit_metrics=['tower_damage_per_min','healing_per_min','obs_placed','sen_placed','observer_kills','sentry_kills']+(['hero_damage_per_min'] if p['role_group']!='core' else [])
            fullcredit=cfg.maximum_positive_credit*max([comparisons[k]['good'] for k in credit_metrics if comparisons[k]['good'] is not None] or [0])
            recomputed=int(max(0,base-fullcredit)+.5) if coverage>=cfg.minimum_coverage and sum(v is not None for v in p['axes'].values())>=cfg.minimum_axes else None
            assert recomputed==p['error_index'], (mid,slot)
            traces.append({'match_id':mid,'slot':slot,'hero':names.get(p['hero_id']), 'summary':nd['summary'],'source':{k:rawp.get(k,'<absent>') for k in P0P if k not in ('account_id','personaname')},'normalized':{k:v for k,v in np.items() if k not in ('account_id','steam_id','display_name')},'normalized_derived':next(x for x in nd['derived'] if x['player_slot']==slot),'report':p,'cohort_slots':[x['player_slot'] for x in cohort],'comparisons':comparisons,'weights':weights,'weighted_sum':weighted,'base_before_credit':base,'credit_full_precision':fullcredit,'independent_index':recomputed,'team_report':rd['teams'][p['team']]})
        census.append({'match_id':mid,'source_fetched_at':snap.get('source_fetched_at'),'snapshot_digest':before,'status':snap.get('status'),'players':len(raw['players']),'scored':sum(p['error_index'] is not None for p in rd['players']),'quality':rd['quality'],'p0_counts':{s:sum(v for (prio,ss),v in present.items() if prio=='P0' and ss==s) for s in set(s for _,s in present)},'event_sections':{f:None if raw.get(f) is None else len(raw[f]) if isinstance(raw[f],list) else type(raw[f]).__name__ for f in P1M}})
        if mid in PILOTS:
            db=read(OUT/f'private/db_{mid}.json'); reports={r['algorithm_version']:r for r in db['reports']}; flow=reports['group_flow_v1']['report_payload']
            for section,env in live.items():
                stored=reports['group_flow_v1:'+section]; payload=stored['report_payload']; data=payload['data']
                projected=project_preliminary(RuinerReport.model_validate_json(json.dumps(data))).model_dump(mode='json') if section=='ruiner' else data
                row={'match_id':mid,'section':section,'envelope_keys':list(env),'data_keys':list(env['data']),'db_to_api_diffs':diff(data,env['data']),'projection_to_api_diffs':diff(projected,env['data']),'flow_config_matches_current':flow.get('config_version')==MatchAnalysisService(None,None).config_version,'source_digest_matches_flow':payload['source_digest']==flow['source_digest'],'source_digest_matches_current_raw':payload['source_digest']==digest({k:snap.get(k) for k in ('match','status','schema_version')}),'model_version':env['model_version'],'config_version':env['config_version'],'analyzed_at':env['analyzed_at'],'completeness':env['completeness'],'status':env['status'],'quality':env['data'].get('quality'),'limitations':env['limitations'],'retry_after_seconds':env['retry_after_seconds'],'envelope_schema_valid':bool(MatchEnvelope.model_validate_json(json.dumps(env)))}
                if section=='ruiner':
                    row.update(replay_vs_stored=diff(rd,data),replay_vs_api=diff(rd,env['data']),player_keys=list(env['data']['players'][0]),team_keys=list(env['data']['teams']['radiant']))
                api.append(row)
    dump('matrix_rows.json',{'columns':cols,'rows':rows})
    dump('traces.json',traces); dump('census.json',census); dump('api_comparison.json',api)
    p0=[r for r in rows if r['priority']=='P0']
    dump('coverage.json',{'matches':len(census),'players':len(traces),'rows':len(rows),'p0_rows':len(p0),'p0_distinct_fields':len(set(r['source_field'] for r in p0)),'p0_statuses':dict(Counter(r['status'] for r in p0)),'p0_enumerated_pct':100,'p0_verified_pct':100*sum(r['status']!='UNVERIFIED' for r in p0)/len(p0),'scored':sum(t['report']['error_index'] is not None for t in traces),'nonnull_index_empty_negative':[(t['match_id'],t['slot'],t['report']['error_index']) for t in traces if t['report']['error_index'] not in (None,0) and not t['report']['negative_signals']]})
    # Full callable inventory with actual line ranges; code map references this evidence.
    inventory=[]
    for path in sorted((ROOT/'backend/app').rglob('*.py')):
        tree=ast.parse(path.read_text())
        for n in ast.walk(tree):
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                inventory.append({'file':str(path.relative_to(ROOT)),'symbol':n.name,'line':n.lineno,'end':n.end_lineno})
    dump('code_symbols.json',inventory)
    print(json.dumps(read(OUT/'coverage.json'),ensure_ascii=False))

if __name__=='__main__' and sys.argv[1]=='offline': offline()
if __name__=='__main__' and sys.argv[1]=='verify':
    before=read(OUT/'baseline.json')['hashes']; after=state()
    changes=[k for k in set(before)|set(after) if before.get(k)!=after.get(k)]
    dump('scope_verification.json',{'production_and_existing_tests_changed':changes,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'status':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True)})
    print('Changed production/test files:',changes)
    assert not changes

async def experiments():
    from types import SimpleNamespace
    from unittest.mock import patch
    from app.integrations.opendota import parse_match_response, OpenDotaResult, OpenDotaStatus
    from app.services.match_normalization import normalize_match_snapshot
    from app.services.performance import analyze_performance
    from app.models.performance import RuinerReport
    from app.api.v1.matches import stored
    from app.core.errors import PublicError
    from app.services.match_ingestion import MatchIngestionService
    baseline=read(CAL/'9051271323.json'); results=[]
    def experiment(name,change):
        s=copy.deepcopy(baseline); change(s['match']); raw=s['match']
        parsed=parse_match_response(9051271323,raw,datetime.now(UTC))
        row={'id':name,'synthetic':True,'parser_status':parsed.status.value}
        try:
            n=normalize_match_snapshot(s); r=analyze_performance(n).model_dump(mode='json')
            row.update(normalizer='accepted',p0={k:r['players'][0][k] for k in ('error_index','axes','observed_metrics','evidence_coverage','reason_codes')},quality=r['quality'])
        except Exception as exc: row['normalizer']=type(exc).__name__
        results.append(row)
    for name,change in [
        ('missing_match_id',lambda m:m.pop('match_id')),
        ('zero_duration',lambda m:m.update(duration=0)),
        ('negative_stats',lambda m:m['players'][0].update(kills=-1,deaths=-1,gold_per_min=-1)),
        ('duplicate_slot',lambda m:m['players'][1].update(player_slot=0)),
        ('incomplete_roster',lambda m:m['players'].pop()),
        ('missing_hero',lambda m:m['players'][0].pop('hero_id')),
        ('missing_kda',lambda m:[m['players'][0].pop(k) for k in ('kills','deaths','assists')]),
        ('zero_score',lambda m:m.update(radiant_score=0)),
        ('small_score',lambda m:m.update(radiant_score=9)),
        ('kp_boundary_equal',lambda m:m['players'][0].update(kills=1,assists=9)),
        ('kp_over_score',lambda m:m['players'][0].update(kills=1,assists=11)),
        ('missing_damage_wards',lambda m:[m['players'][0].pop(k,None) for k in ('hero_damage','tower_damage','hero_healing','obs_placed','sen_placed','observer_kills','sentry_kills')]),
        ('unknown_position',lambda m:m['players'][0].pop('position_est')),
        ('leaver_status_2',lambda m:m['players'][0].update(leaver_status=2)),
        ('float_gpm',lambda m:m['players'][0].update(gold_per_min=211.5)),
        ('numeric_string_gpm',lambda m:m['players'][0].update(gold_per_min='211')),
        ('empty_arrays',lambda m:[m.update({k:[]}) for k in ('picks_bans','objectives','teamfights','radiant_gold_adv','radiant_xp_adv')]),
    ]: experiment(name,change)
    a=analyze_performance(normalize_match_snapshot(baseline)).model_dump(mode='json')
    s=copy.deepcopy(baseline);s['match']['players'][0]['leaver_status']=2
    results.append({'id':'leaver_end_to_end','synthetic':True,'unchanged_report':a==analyze_performance(normalize_match_snapshot(s)).model_dump(mode='json')})
    db=read(OUT/'private/db_9051271323.json'); source_rows={r['algorithm_version']:r for r in db['reports']}
    class Session:
        def __init__(self,raw): self.raw=raw
        async def get(self,*args): return SimpleNamespace(raw_payload=self.raw)
    for case in ('baseline','stale_raw','model_mismatch','config_mismatch','schema_mismatch','source_digest_mismatch','corrupt_preliminary','legacy_preliminary'):
        data=copy.deepcopy(source_rows); raw=copy.deepcopy(db['match']['raw_payload']); payload=data['group_flow_v1:ruiner']['report_payload']
        if case=='stale_raw': raw['match']['players'][0]['deaths']=99
        if case=='model_mismatch': payload['model_version']='different_model'
        if case=='config_mismatch': payload['config_version']='different_config'
        if case=='schema_mismatch': payload['schema_version']=999
        if case=='source_digest_mismatch': payload['source_digest']='wrong'
        if case=='corrupt_preliminary': payload['data']['teams']['dire']['preliminary_selection']['confidence']='medium'
        if case=='legacy_preliminary':
            for t in payload['data']['teams'].values(): t.pop('preliminary_selection',None)
        async def fake_get(session,match_id,version):
            r=copy.deepcopy(data[version]); r['computed_at']=datetime.fromisoformat(r['computed_at']) if r['computed_at'] else None; return SimpleNamespace(**r)
        before=sha(data)
        with patch('app.api.v1.matches.get_analysis',fake_get):
            try:
                res=await stored('9051271323','ruiner',RuinerReport,Session(raw)); body=json.loads(res.body)
                results.append({'id':'stored_'+case,'synthetic':True,'http':res.status_code,'model_version':body['model_version'],'data_model':body['data']['model_version'],'config_version':body['config_version'],'dire_projection':body['data']['teams']['dire']['preliminary_selection'],'data_unchanged':sha(data)==before})
            except PublicError as exc:
                results.append({'id':'stored_'+case,'synthetic':True,'http':exc.status_code,'code':exc.code,'data_unchanged':sha(data)==before})
    # In-memory repository stub observes actual pending/save lifecycle, no DB.
    current={'raw_payload':copy.deepcopy(baseline),'fetch_status':'ready'}; writes=[]
    class MemorySession:
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        def begin(self): return self
    async def upsert(session,match_id,**values):
        current.update(values);writes.append(copy.deepcopy(values))
    async def get_match(session,match_id): return SimpleNamespace(**current)
    class Provider:
        async def fetch_match(self,mid): return OpenDotaResult(OpenDotaStatus.API_UNAVAILABLE,mid)
    service=MatchIngestionService(MemorySession,Provider(),success_ttl_seconds=3600,error_ttl_seconds=60,not_found_ttl_seconds=300,clock=lambda:datetime(2030,1,1,tzinfo=UTC))
    with patch('app.services.match_ingestion.upsert_match',upsert),patch('app.services.match_ingestion.get_match',get_match):
        await service.ingest_match(9051271323)
    results.append({'id':'expired_good_snapshot_then_503','synthetic':True,'write_states':[v['raw_payload']['status'] for v in writes],'final_has_match':'match' in current['raw_payload'],'old_raw_retained_in_writes':any('match' in v['raw_payload'] for v in writes)})
    dump('experiments.json',results)
    print(json.dumps([{k:v for k,v in r.items() if k not in ('p0','dire_projection')} for r in results],ensure_ascii=False))

if __name__=='__main__' and sys.argv[1]=='experiments': asyncio.run(experiments())

async def source_check():
    import httpx
    evidence=[]
    async with httpx.AsyncClient(timeout=20,trust_env=False,follow_redirects=True) as client:
        for repo,path in [('core','sql/create_tables.sql'),('parser','src/main/java/opendota/Parse.java'),('dotaconstants','build/game_mode.json')]:
            url=f'https://api.github.com/repos/odota/{repo}/commits/master'
            try:
                r=await client.get(url,headers={'User-Agent':'DotaHub-read-only-data-audit'});r.raise_for_status(); commit=r.json()['sha']
                sourceurl=f'https://raw.githubusercontent.com/odota/{repo}/{commit}/{path}'
                src=await client.get(sourceurl);src.raise_for_status()
                dump(f'private/source_{repo}.json',{'url':sourceurl,'content':src.text})
                evidence.append({'repo':repo,'commit':commit,'url':f'https://github.com/odota/{repo}/blob/{commit}/{path}','read_at':datetime.now(UTC).isoformat(),'sha256':hashlib.sha256(src.content).hexdigest(),'http':src.status_code})
            except Exception as exc: evidence.append({'repo':repo,'error':type(exc).__name__})
    dump('source_evidence.json',evidence);print(json.dumps(evidence))
if __name__=='__main__' and sys.argv[1]=='sources': asyncio.run(source_check())

async def verifydb():
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.core.config import Settings
    engine=create_async_engine(Settings().database_url.get_secret_value(),hide_parameters=True)
    out={}
    async with engine.connect() as conn:
        await conn.execute(text('SET TRANSACTION READ ONLY'))
        for mid in PILOTS:
            row=(await conn.execute(text('SELECT match_id,fetch_status,raw_payload,fetched_at,created_at,updated_at FROM matches WHERE match_id=:id'),{'id':mid})).mappings().first()
            reports=[dict(r) for r in (await conn.execute(text('SELECT algorithm_version,status,completeness,computed_at,report_payload FROM match_analyses WHERE match_id=:id ORDER BY algorithm_version'),{'id':mid})).mappings()]
            # Same JSON encoding of timestamps as capture.
            value=json.loads(json.dumps({'match':dict(row),'reports':reports},default=str))
            out[str(mid)]={'raw_and_reports_unchanged':value==read(OUT/f'private/db_{mid}.json')}
        out['constraints']=[dict(r) for r in (await conn.execute(text("SELECT conrelid::regclass::text AS table_name,conname,pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE conrelid IN ('matches'::regclass,'match_analyses'::regclass) ORDER BY 1,2"))).mappings()]
        out['indexes']=[dict(r) for r in (await conn.execute(text("SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' AND tablename IN ('matches','match_analyses') ORDER BY 1,2"))).mappings()]
    await engine.dispose();dump('db_verification.json',out)
    print(json.dumps({k:v for k,v in out.items() if k not in ('constraints','indexes')}))
if __name__=='__main__' and sys.argv[1]=='verifydb': asyncio.run(verifydb())

def timeline_checks():
    from app.services.timeline import analyze_timeline
    from app.services.match_normalization import normalize_match_snapshot
    snap=read(CAL/'9051271323.json'); report=analyze_timeline(normalize_match_snapshot(snap)).model_dump(mode='json')
    event=next(x for x in report['events'] if x['type']=='tower' and x['time_start']==1048)
    cases=[]
    for team in (0,1,2,3):
        s=copy.deepcopy(snap);s['match']['objectives']=[{'type':'CHAT_MESSAGE_ROSHAN_KILL','time':100,'team':team}]
        r=analyze_timeline(normalize_match_snapshot(s)).model_dump(mode='json')
        cases.append({'synthetic':True,'raw_team':team,'events':[e for e in r['events'] if e['type']=='roshan']})
    live=read(OUT/'private/api_local-alpha_matches_9051271323_timeline.json')['data']
    live_event=next(e for e in live['events'] if e['type']=='tower' and e['time_start']==1048)
    assert live_event['team']==event['team'] and live_event['actors'][0]['team']==event['actors'][0]['team']
    dump('timeline_checks.json',{'live_api_event':live_event,'real_match_id':9051271323,'raw_objective':next(x for x in snap['match']['objectives'] if x['time']==1048),'actual_event':event,'synthetic_roshan':cases})
    print('Real tower actor/team:',event['actors'],event['team'])
if __name__=='__main__' and sys.argv[1]=='timeline': timeline_checks()

def validate():
    import math, xml.etree.ElementTree as ET
    from app.integrations.opendota import parse_match_response
    from app.services.match_normalization import normalize_match_snapshot
    from app.services.performance import analyze_performance
    checks=Counter(); failures=[]
    def check(label,ok):
        checks[label]+=1
        if not ok: failures.append(label)
    for path in sorted(CAL.glob('[0-9]*.json')):
        s=read(path); m=s['match']; mid=m['match_id']; n=normalize_match_snapshot(s)
        parsed=parse_match_response(mid,m,datetime.now(UTC))
        check('reparse_status',parsed.status.value==s['status'])
        check('sanitized_raw_reparse_unchanged',parsed.snapshot['match']==m)
        r=analyze_performance(n)
        check('deterministic_replay',r==analyze_performance(n))
        for raw,p,d,rp in zip(sorted(m['players'],key=lambda x:x['player_slot']),n.players,n.derived,r.players):
            for field,target in PM.items():
                if field in ('lane_role','position_est','personaname','account_id','purchase_time'):continue
                value=raw.get(field)
                if value is not None: check('scalar_raw_equals_normalized',getattr(p,target)==value)
            if 'isRadiant' in raw:check('side_equals_slot',raw['isRadiant']==(p.player_slot<128))
            for source,metric in [('deaths','deaths_per_min'),('hero_damage','hero_damage_per_min'),('tower_damage','tower_damage_per_min'),('hero_healing','healing_per_min')]:
                v=raw.get(source); actual=rp.observed_metrics[metric]
                check('rate_from_source',actual is None if v is None else math.isclose(actual,v*60/m['duration'],rel_tol=1e-12,abs_tol=1e-12))
            for source,target in [('gold_per_min','gpm'),('xp_per_min','xpm'),('obs_placed','obs_placed'),('sen_placed','sen_placed'),('observer_kills','observer_kills'),('sentry_kills','sentry_kills')]:
                check('observed_scalar_exact',rp.observed_metrics[target]==raw.get(source))
            score=m['radiant_score'] if p.player_slot<128 else m['dire_score']
            rawratio=(raw['kills']+raw['assists'])/score if score else None
            check('normalized_counter_ratio',d.kill_participation.value==(round(rawratio,4) if rawratio is not None else None))
            kda=(raw['kills']+raw['assists'])/raw['deaths'] if raw['deaths'] else None
            check('normalized_kda',d.kda.value==(round(kda,4) if kda is not None else None))
            check('observed_kda',rp.observed_metrics['kda']==kda)
    ts=read(OUT/'traces.json')
    for t in ts:
        r=t['report']; c=t['comparisons']; ownteam=[q for q in ts if q['match_id']==t['match_id'] and q['report']['team']==r['team']]
        enough_deaths=all(type(q['source']['deaths']) is int for q in ownteam) and sum(q['source']['deaths'] for q in ownteam)>=5
        expected={'survival':c['deaths_per_min']['bad'] if enough_deaths else None,'participation':c['kill_participation']['bad']}
        if r['role_group']=='core':
            e=[c[k]['bad'] for k in ('gpm','xpm')];expected.update(economy=sum(e)/2 if all(x is not None for x in e) else None,impact=c['hero_damage_per_min']['bad'])
        for key,v in expected.items():
            actual=r['axes'][key];check('independent_axis',actual is None if v is None else actual is not None and math.isclose(v,actual,abs_tol=1e-12))
    with (ROOT/'docs/RI_02_DATA_01_FIELD_MATRIX.csv').open(newline='') as f:
        csvrows=list(csv.DictReader(f))
    mr=read(OUT/'matrix_rows.json')
    check('csv_exact_roundtrip',csvrows==mr['rows'])
    check('csv_required_columns',list(csvrows[0])==mr['columns'])
    testroot=ET.parse(OUT/'pytest.xml').getroot();suite=testroot.find('testsuite')
    check('existing_suite_clean',suite.attrib['failures']=='0' and suite.attrib['errors']=='0' and suite.attrib['skipped']=='0')
    # Validate all internal absolute Markdown code references generated from AST.
    import re
    links=0
    for path in (ROOT/'docs').glob('RI_02_DATA_01_*.md'):
        for target,line in re.findall(r'\]\((/[^)]+):(\d+)\)',path.read_text()):
            file=Path(target); check('code_link_line_exists',file.exists() and int(line)<=len(file.read_text().splitlines()));links+=1
    dump('artifact_checks.json',{'counts':checks,'failures':failures,'total_checks':sum(checks.values()),'links':links})
    print(json.dumps({'total_checks':sum(checks.values()),'counts':checks,'failures':failures}))
    assert not failures
if __name__=='__main__' and sys.argv[1]=='validate': validate()
