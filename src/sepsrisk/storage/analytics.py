from pathlib import Path
import pandas as pd
from ..config import load_yaml, project_root
from .parquet_store import eeff_files, parquet_root


def _root(root=None):return Path(root) if root else project_root()

def query_df(con,sql,params=None):
    cur=con.execute(sql,params or [])
    return cur.df()


def open_analytics(root=None):
    import duckdb
    root=_root(root);con=duckdb.connect(':memory:')
    files=eeff_files(root)
    if files:
        glob=(parquet_root(root)/'eeff/year=*/month=*/eeff.parquet').as_posix().replace("'","''")
        con.execute(f"""CREATE VIEW fact_eeff AS
            SELECT CAST(cutoff_date AS VARCHAR) cutoff_date, CAST(ruc AS VARCHAR) ruc,
                   CAST(segment AS INTEGER) segment, CAST(account AS VARCHAR) account,
                   CAST(balance AS DOUBLE) balance, CAST(record_sha256 AS VARCHAR) record_sha256,
                   CAST(entity_name AS VARCHAR) entity_name, CAST(entity_name_norm AS VARCHAR) entity_name_norm,
                   CAST(account_description AS VARCHAR) account_description
            FROM read_parquet('{glob}', hive_partitioning=true)""")
        con.execute('''CREATE VIEW dim_entity AS SELECT ruc,any_value(entity_name) entity_name,any_value(entity_name_norm) entity_name_norm,min(cutoff_date) first_seen,max(cutoff_date) last_seen FROM fact_eeff GROUP BY ruc''')
        con.execute('''CREATE VIEW dim_account AS SELECT account,any_value(account_description) account_description FROM fact_eeff GROUP BY account''')
    else:
        con.execute('''CREATE TABLE fact_eeff(cutoff_date VARCHAR,ruc VARCHAR,segment INTEGER,account VARCHAR,balance DOUBLE,record_sha256 VARCHAR,entity_name VARCHAR,entity_name_norm VARCHAR,account_description VARCHAR)''')
        con.execute('''CREATE VIEW dim_entity AS SELECT ruc,entity_name,entity_name_norm,min(cutoff_date) first_seen,max(cutoff_date) last_seen FROM fact_eeff GROUP BY ruc,entity_name,entity_name_norm''')
        con.execute('''CREATE VIEW dim_account AS SELECT account,account_description FROM fact_eeff GROUP BY account,account_description''')
    # Derived tables are deliberately ephemeral; canonical storage is Parquet facts.
    con.execute('''CREATE TABLE fact_feature(cutoff_date VARCHAR,ruc VARCHAR,feature VARCHAR,value DOUBLE,unit VARCHAR,method_version VARCHAR,calculated_at VARCHAR)''')
    con.execute('''CREATE TABLE fact_peer_stat(cutoff_date VARCHAR,feature VARCHAR,q25 DOUBLE,median DOUBLE,q75 DOUBLE,mean DOUBLE,std DOUBLE,n BIGINT,calculated_at VARCHAR)''')
    con.execute('''CREATE TABLE fact_signal(cutoff_date VARCHAR,ruc VARCHAR,signal VARCHAR,value DOUBLE,score DOUBLE,direction VARCHAR,detail VARCHAR,calculated_at VARCHAR)''')
    con.execute('''CREATE TABLE fact_risk_estimate(cutoff_date VARCHAR,ruc VARCHAR,horizon_months INTEGER,probability DOUBLE,lower_ci DOUBLE,upper_ci DOUBLE,model_version VARCHAR,calibrated_at VARCHAR)''')
    ep=parquet_root(root)/'events'/'events.parquet'
    if ep.exists():
        esc=ep.as_posix().replace("'","''");con.execute(f"CREATE VIEW entity_event AS SELECT CAST(ruc AS VARCHAR) ruc,CAST(event_date AS VARCHAR) event_date,CAST(event_type AS VARCHAR) event_type,CAST(adverse AS INTEGER) adverse,CAST(source_url AS VARCHAR) source_url,CAST(notes AS VARCHAR) notes FROM read_parquet('{esc}')")
    else:con.execute('''CREATE TABLE entity_event(ruc VARCHAR,event_date VARCHAR,event_type VARCHAR,adverse INTEGER,source_url VARCHAR,notes VARCHAR)''')
    return con
