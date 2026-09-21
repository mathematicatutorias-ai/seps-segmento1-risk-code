from sepsrisk.utils import norm_text,sha256_text
def test_norm():assert norm_text('Razón Social')=='RAZON SOCIAL'
def test_sha():assert sha256_text('x')==sha256_text('x')
