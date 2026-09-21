from sepsrisk.ingestion.parser import parse_balance
def test_balance():assert parse_balance('1,234.56')==1234.56 and parse_balance('1234,56')==1234.56
