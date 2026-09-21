from sepsrisk.storage.analytics import open_analytics
from sepsrisk.features.engine import build_features
from sepsrisk.inference.signals import build_signals
c=open_analytics();build_features(c);print(build_signals(c));c.close()
