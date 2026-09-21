def qa_eeff(df):
    issues=[]
    if df.empty:issues.append(('critical','empty','No hay filas del segmento objetivo'))
    elif df.duplicated(['cutoff_date','ruc','account']).any():issues.append(('critical','duplicates','Clave duplicada'))
    return issues
def critical(issues):return any(x[0]=='critical' for x in issues)
