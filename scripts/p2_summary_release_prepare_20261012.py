# Created: 2026-10-12 JST
"""Prepare candidate-only sector-summary release files in a pinned private checkout.
Inputs: six successful retained staging ZIPs and six successful URL-gate JSONs.
No analytics, no source CSV edits, no Git commit/push by this script.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

SECTORS = ('technology','financials','consumer_goods','materials','capital_goods_others','transportation_utilities')
COUNTS = {'technology':593,'financials':593,'consumer_goods':593,'materials':593,'capital_goods_others':500,'transportation_utilities':498}
PIN = '0e2d5722d6764102adfe6995b793f533b60b1532'

def sha256(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def prepare(repo:Path, artifact_root:Path, checkpoint:Path)->dict:
    repo=repo.resolve()
    artifact_root=artifact_root.resolve()
    checkpoint=checkpoint.resolve()
    if checkpoint.exists():
        raise ValueError('checkpoint file must be new')
    sha=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    if sha!=PIN:
        raise ValueError('Private HEAD is not pinned')
    if subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True).strip():
        raise ValueError('Private staging checkout is not clean')
    if not (repo/'docs/ACTIONS_MIGRATION.md').is_file():
        raise ValueError('Private Actions migration rule missing')
    forbidden=subprocess.check_output(['git','-C',str(repo),'ls-tree','-r','--name-only','HEAD','--','.github/workflows/'],text=True)
    if forbidden.strip():
        raise ValueError('Private workflow is forbidden')
    plans=[]
    for sector in SECTORS:
        stage_zip=artifact_root/f'p2-staged-html-{sector}'/f'p2_candidate_summaries_{sector}.zip'
        stage_json=artifact_root/f'p2-staged-html-{sector}'/'staging_report.json'
        gate_json=artifact_root/f'p2-nextstage-gate-{sector}'/'nextstage_audit.json'
        stage=json.loads(stage_json.read_text(encoding='utf-8'))
        gate=json.loads(gate_json.read_text(encoding='utf-8'))
        if stage['status']!='PASS_STAGED_REQUIRES_DEPLOY_APPROVAL' or stage['core_sha']!=PIN or stage['sector']!=sector:
            raise ValueError('staging identity failed: '+sector)
        if gate['status']!='PASS' or gate['private_sha']!=PIN or gate['sector']!=sector:
            raise ValueError('URL gate identity failed: '+sector)
        if sha256(stage_zip.read_bytes())!=stage['archive_sha256']:
            raise ValueError('staging ZIP checksum failed: '+sector)
        if stage['candidate_html_pages']!=COUNTS[sector]:
            raise ValueError('staging page count failed: '+sector)
        base=f'preview/kabu/analysis/225_group_all_period/{sector}/summaries/'
        old_paths=subprocess.check_output(['git','-C',str(repo),'ls-tree','-r','--name-only','HEAD','--',base],text=True).splitlines()
        old={Path(p).name for p in old_paths if p.endswith('.html')}
        if len(old)!=712:
            raise ValueError('old 712 HTML inventory failed: '+sector)
        rows={}
        with zipfile.ZipFile(stage_zip) as zp:
            if zp.testzip() is not None:
                raise ValueError('ZIP integrity failed: '+sector)
            for entry in zp.infolist():
                pieces=Path(entry.filename).parts
                valid=re.fullmatch(r'(single|pair|triple)(?:_[a-z]+|-?[a-f0-9]+)\.html',pieces[-1]) if len(pieces)==3 else False
                if len(pieces)!=3 or pieces[:2]!=(sector,'summaries') or not valid:
                    raise ValueError('unexpected ZIP path '+entry.filename)
                if pieces[-1] in rows:
                    raise ValueError('duplicate staged file')
                rows[pieces[-1]]=zp.read(entry)
        new=set(rows)
        if len(new)!=COUNTS[sector]:
            raise ValueError('new HTML inventory failed: '+sector)
        family=gate['url_inventory']['families']
        old_only={name for item in family.values() for name in item['old_only_names']}
        new_only={name for item in family.values() for name in item['candidate_only_names']}
        if old-new!=old_only or new-old!=new_only:
            raise ValueError('staging ZIP disagrees with saved URL evidence: '+sector)
        evidence=gate['url_inventory']
        if (len(old-new),len(new-old),len(old&new))!=(evidence['old_only'],evidence['candidate_only'],evidence['both']):
            raise ValueError('URL cardinality mismatch: '+sector)
        directory=repo/base
        if not directory.is_dir() or any(not (directory/name).is_file() for name in old):
            raise ValueError('legacy HTML checkout incomplete: '+sector)
        plans.append((sector,directory,old,new,rows,stage['archive_sha256']))
    if sum(len(o-n) for _,_,o,n,_,_ in plans)!=914 or sum(len(n-o) for _,_,o,n,_,_ in plans)!=12:
        raise ValueError('global legacy URL migration totals mismatch')
    changed=[]
    for sector,directory,old,new,rows,digest in plans:
        for name in sorted(old-new):
            (directory/name).unlink()
        for name,raw in rows.items():
            (directory/name).write_bytes(raw)
        if {p.name for p in directory.glob('*.html')}!=new:
            raise ValueError('post-stage inventory mismatch: '+sector)
        changed.append({'sector':sector,'candidate_pages':len(new),'removed_old_urls':len(old-new),
                        'new_only_urls':len(new-old),'replaced_common_urls':len(old&new),
                        'source_artifact_sha256':digest})
    files=subprocess.check_output(['git','-C',str(repo),'status','--porcelain','--untracked-files=all'],text=True).splitlines()
    for entry in files:
        path=entry[3:].split(' -> ')[-1]
        parts=Path(path).parts
        if len(parts)<7 or parts[:4]!=('preview','kabu','analysis','225_group_all_period') or parts[4] not in SECTORS or parts[5]!='summaries':
            raise ValueError('unexpected modified path '+path)
    result={'status':'PASS_READY_TO_COMMIT_RELEASE_BRANCH','fixed_private_sha':sha,
            'new_summary_html_total':sum(COUNTS.values()),'old_only_removed':914,
            'new_only_added':12,'sectors':changed,
            'production_p2_changed':False,'source_csv_modified':False,
            'deployment_on_local_apache':False}
    checkpoint.parent.mkdir(parents=True,exist_ok=True)
    checkpoint.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--artifacts',type=Path,required=True)
    parser.add_argument('--checkpoint',type=Path,required=True)
    a=parser.parse_args()
    print(json.dumps(prepare(a.repo,a.artifacts,a.checkpoint),ensure_ascii=False))
