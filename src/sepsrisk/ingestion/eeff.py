from pathlib import Path
import pandas as pd
from ..utils import norm_text,sha256_text,utcnow
from .parser import iter_table,match_columns,parse_balance,estimate_rows


def _normalize_chunk(raw,spec,segment):
    d=match_columns(raw,spec['canonical_columns'])
    # Avoid dayfirst warning when ISO dates are already present.
    raw_date=d['cutoff_date'].astype(str).str.strip()
    iso=raw_date.str.match(r'^\d{4}-\d{2}-\d{2}$',na=False)
    parsed=pd.Series(pd.NaT,index=d.index,dtype='datetime64[ns]')
    if iso.any(): parsed.loc[iso]=pd.to_datetime(raw_date.loc[iso],format='%Y-%m-%d',errors='coerce')
    if (~iso).any(): parsed.loc[~iso]=pd.to_datetime(raw_date.loc[~iso],dayfirst=True,errors='coerce')
    d['cutoff_date']=parsed.dt.date.astype('string')
    d['segment']=d.segment.map(lambda x:int(''.join(c for c in str(x) if c.isdigit()) or -1))
    d=d[d.segment==int(segment)].copy()
    if d.empty:
        return d.assign(record_sha256=pd.Series(dtype='string'),entity_name_norm=pd.Series(dtype='string'))
    d['ruc']=d.ruc.astype(str).str.replace(r'\.0$','',regex=True).str.strip()
    d['entity_name']=d.entity_name.astype(str).str.strip()
    d['entity_name_norm']=d.entity_name.map(norm_text)
    d['account']=d.account.astype(str).str.replace(r'\.0$','',regex=True).str.strip()
    d['account_description']=d.account_description.astype(str).str.strip()
    d['balance']=d.balance.map(parse_balance)
    d=d.dropna(subset=['cutoff_date','ruc','account','balance'])
    d['record_sha256']=[sha256_text(f'{date}|{r}|{a}|{v:.10f}') for date,r,a,v in zip(d.cutoff_date,d.ruc,d.account,d.balance)]
    return d


def stage_eeff(con,files,spec,segment,progress=None,label=None,chunksize=50000):
    """Stream source files into a TEMP staging table.

    Keeps only Segment 1 rows in memory per chunk and exposes row-level progress.
    """
    con.execute('DROP TABLE IF EXISTS temp.stg_eeff')
    con.execute('''CREATE TEMP TABLE stg_eeff(
        cutoff_date TEXT NOT NULL, segment INTEGER NOT NULL, ruc TEXT NOT NULL,
        entity_name TEXT NOT NULL, entity_name_norm TEXT NOT NULL,
        account TEXT NOT NULL, account_description TEXT, balance REAL,
        record_sha256 TEXT NOT NULL,
        PRIMARY KEY(cutoff_date,ruc,account)
    ) WITHOUT ROWID''')
    total_raw=0; kept=0; accepted=0
    for f in files:
        f=Path(f)
        if f.suffix.lower() not in spec['accepted_extensions']: continue
        accepted += 1
        total=estimate_rows(f)
        bar=progress.row_bar(total,f'{label or "EEFF"} · leyendo {f.name}') if progress is not None else None
        try:
            for raw in iter_table(f,chunksize=chunksize):
                total_raw += len(raw)
                d=_normalize_chunk(raw,spec,segment)
                if not d.empty:
                    rows=[(r.cutoff_date,int(r.segment),r.ruc,r.entity_name,r.entity_name_norm,r.account,r.account_description,float(r.balance),r.record_sha256) for r in d.itertuples(index=False)]
                    con.executemany('INSERT OR REPLACE INTO stg_eeff VALUES(?,?,?,?,?,?,?,?,?)',rows)
                    kept += len(rows)
                if bar is not None:
                    bar.update(len(raw));bar.set_postfix_str(f'S1={kept:,}',refresh=True)
        finally:
            if bar is not None: bar.close()
    staged=con.execute('SELECT count(*) FROM stg_eeff').fetchone()[0]
    return {'files':accepted,'rows_source':total_raw,'rows_segment':staged,'rows_segment_seen':kept}


def merge_staged_eeff(con,source_id,progress=None,label=None):
    now=utcnow()
    if progress is not None: progress.note('consolidando SQLite',f'{label or "EEFF"} · comparando SHA por registro')
    inserted=con.execute('''SELECT count(*) FROM stg_eeff s
        WHERE NOT EXISTS(SELECT 1 FROM fact_eeff f WHERE f.cutoff_date=s.cutoff_date AND f.ruc=s.ruc AND f.account=s.account)''').fetchone()[0]
    updated=con.execute('''SELECT count(*) FROM stg_eeff s JOIN fact_eeff f
        ON f.cutoff_date=s.cutoff_date AND f.ruc=s.ruc AND f.account=s.account
        WHERE f.record_sha256<>s.record_sha256''').fetchone()[0]
    unchanged=con.execute('''SELECT count(*) FROM stg_eeff s JOIN fact_eeff f
        ON f.cutoff_date=s.cutoff_date AND f.ruc=s.ruc AND f.account=s.account
        WHERE f.record_sha256=s.record_sha256''').fetchone()[0]

    # Dimensions in bulk.
    con.execute('''INSERT OR IGNORE INTO dim_entity(ruc,entity_name,entity_name_norm,first_seen,last_seen)
        SELECT ruc,MAX(entity_name),MAX(entity_name_norm),MIN(cutoff_date),MAX(cutoff_date) FROM stg_eeff GROUP BY ruc''')
    con.execute('''UPDATE dim_entity SET
        entity_name=(SELECT s.entity_name FROM stg_eeff s WHERE s.ruc=dim_entity.ruc ORDER BY s.cutoff_date DESC LIMIT 1),
        entity_name_norm=(SELECT s.entity_name_norm FROM stg_eeff s WHERE s.ruc=dim_entity.ruc ORDER BY s.cutoff_date DESC LIMIT 1),
        first_seen=min(COALESCE(first_seen,(SELECT min(cutoff_date) FROM stg_eeff s WHERE s.ruc=dim_entity.ruc)),(SELECT min(cutoff_date) FROM stg_eeff s WHERE s.ruc=dim_entity.ruc)),
        last_seen=max(COALESCE(last_seen,(SELECT max(cutoff_date) FROM stg_eeff s WHERE s.ruc=dim_entity.ruc)),(SELECT max(cutoff_date) FROM stg_eeff s WHERE s.ruc=dim_entity.ruc))
        WHERE ruc IN(SELECT DISTINCT ruc FROM stg_eeff)''')
    con.execute('''INSERT OR IGNORE INTO dim_account(account,account_description,account_level,parent_account)
        SELECT account,MAX(account_description),length(account),CASE WHEN length(account)>2 THEN substr(account,1,length(account)-2) END
        FROM stg_eeff GROUP BY account''')
    con.execute('''UPDATE dim_account SET account_description=(SELECT s.account_description FROM stg_eeff s WHERE s.account=dim_account.account LIMIT 1)
        WHERE account IN(SELECT DISTINCT account FROM stg_eeff)''')

    # Audit changed rows before updating canonical facts.
    con.execute('''INSERT INTO fact_eeff_audit(cutoff_date,ruc,account,old_balance,new_balance,old_sha256,new_sha256,source_id,changed_at)
        SELECT f.cutoff_date,f.ruc,f.account,f.balance,s.balance,f.record_sha256,s.record_sha256,?,?
        FROM fact_eeff f JOIN stg_eeff s ON f.cutoff_date=s.cutoff_date AND f.ruc=s.ruc AND f.account=s.account
        WHERE f.record_sha256<>s.record_sha256''',(source_id,now))

    # Bulk update changed rows.
    con.execute('''UPDATE fact_eeff SET
        segment=(SELECT s.segment FROM stg_eeff s WHERE s.cutoff_date=fact_eeff.cutoff_date AND s.ruc=fact_eeff.ruc AND s.account=fact_eeff.account),
        balance=(SELECT s.balance FROM stg_eeff s WHERE s.cutoff_date=fact_eeff.cutoff_date AND s.ruc=fact_eeff.ruc AND s.account=fact_eeff.account),
        record_sha256=(SELECT s.record_sha256 FROM stg_eeff s WHERE s.cutoff_date=fact_eeff.cutoff_date AND s.ruc=fact_eeff.ruc AND s.account=fact_eeff.account),
        source_id=?,updated_at=?
        WHERE EXISTS(SELECT 1 FROM stg_eeff s WHERE s.cutoff_date=fact_eeff.cutoff_date AND s.ruc=fact_eeff.ruc AND s.account=fact_eeff.account AND s.record_sha256<>fact_eeff.record_sha256)''',(source_id,now))

    # Bulk insert genuinely new rows.
    con.execute('''INSERT INTO fact_eeff(cutoff_date,ruc,segment,account,balance,record_sha256,source_id,updated_at)
        SELECT s.cutoff_date,s.ruc,s.segment,s.account,s.balance,s.record_sha256,?,?
        FROM stg_eeff s WHERE NOT EXISTS(
            SELECT 1 FROM fact_eeff f WHERE f.cutoff_date=s.cutoff_date AND f.ruc=s.ruc AND f.account=s.account)''',(source_id,now))
    return {'inserted':int(inserted),'updated':int(updated),'unchanged':int(unchanged)}


# Backward-compatible helpers used by tests/older scripts.
def normalize_eeff(files,spec,segment):
    frames=[]
    for f in files:
        f=Path(f)
        if f.suffix.lower() not in spec['accepted_extensions']: continue
        for raw in iter_table(f,chunksize=50000):
            d=_normalize_chunk(raw,spec,segment)
            if not d.empty: frames.append(d)
    if not frames:return pd.DataFrame(columns=['cutoff_date','segment','ruc','entity_name','account','account_description','balance','record_sha256'])
    return pd.concat(frames,ignore_index=True).drop_duplicates(['cutoff_date','ruc','account'],keep='last')


def upsert_eeff(con,df,source_id):
    con.execute('DROP TABLE IF EXISTS temp.stg_eeff')
    con.execute('''CREATE TEMP TABLE stg_eeff(cutoff_date TEXT NOT NULL,segment INTEGER NOT NULL,ruc TEXT NOT NULL,entity_name TEXT NOT NULL,entity_name_norm TEXT NOT NULL,account TEXT NOT NULL,account_description TEXT,balance REAL,record_sha256 TEXT NOT NULL,PRIMARY KEY(cutoff_date,ruc,account)) WITHOUT ROWID''')
    rows=[]
    for r in df.itertuples(index=False):
        rows.append((r.cutoff_date,int(r.segment),r.ruc,r.entity_name,norm_text(r.entity_name),r.account,r.account_description,float(r.balance),r.record_sha256))
    con.executemany('INSERT OR REPLACE INTO stg_eeff VALUES(?,?,?,?,?,?,?,?,?)',rows)
    return merge_staged_eeff(con,source_id)
