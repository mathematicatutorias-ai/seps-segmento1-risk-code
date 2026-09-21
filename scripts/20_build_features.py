from sepsrisk.storage.analytics import open_analytics
from sepsrisk.features.engine import build_features
c=open_analytics();print(build_features(c));c.close()
