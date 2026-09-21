from sepsrisk.storage.analytics import open_analytics
from sepsrisk.features.engine import build_features
from sepsrisk.inference.signals import build_signals
from sepsrisk.inference.survival import record_readiness
from sepsrisk.reporting.export_dashboard import export_dashboard
c=open_analytics();build_features(c);build_signals(c);record_readiness(c);print(export_dashboard(c));c.close()
