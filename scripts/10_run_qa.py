from sepsrisk.storage.analytics import open_analytics
c=open_analytics();print('EEFF',c.execute('select count(*) from fact_eeff').fetchone()[0]);print('Rango',c.execute('select min(cutoff_date),max(cutoff_date) from fact_eeff').fetchone());c.close()
