import pandas as pd
from sepsrisk.qa.core import qa_eeff,critical
def test_empty():assert critical(qa_eeff(pd.DataFrame()))
