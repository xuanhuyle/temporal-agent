# Load graphiti_core/search/search_filters.py in isolation (stub its two imports) to inspect generated Cypher.
import sys, types, enum, importlib.util
from datetime import datetime, timezone
root = '/tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/repos/graphiti/graphiti_core/search/search_filters.py'
class GraphProvider(enum.Enum):
    NEO4J='neo4j'; FALKORDB='falkordb'; KUZU='kuzu'; NEPTUNE='neptune'
for name in ['graphiti_core','graphiti_core.driver','graphiti_core.driver.driver','graphiti_core.helpers']:
    sys.modules[name]=types.ModuleType(name)
sys.modules['graphiti_core.driver.driver'].GraphProvider=GraphProvider
sys.modules['graphiti_core.helpers'].validate_node_labels=lambda v: None
spec=importlib.util.spec_from_file_location('sf', root); sf=importlib.util.module_from_spec(spec); spec.loader.exec_module(sf)
DF, Op, SF = sf.DateFilter, sf.ComparisonOperator, sf.SearchFilters
t1=datetime(2025,1,1,tzinfo=timezone.utc); t2=datetime(2025,6,1,tzinfo=timezone.utc); t=datetime(2025,3,1,tzinfo=timezone.utc)
print('OR of two non-null comparisons on valid_at:')
print(sf.edge_search_filter_query_constructor(SF(valid_at=[[DF(date=t1,comparison_operator=Op.greater_than_equal)],[DF(date=t2,comparison_operator=Op.less_than_equal)]]), GraphProvider.NEO4J))
print('Bitemporal as-of t (valid time + transaction time):')
asof=SF(valid_at=[[DF(date=t,comparison_operator=Op.less_than_equal)]],
        invalid_at=[[DF(date=t,comparison_operator=Op.greater_than)],[DF(comparison_operator=Op.is_null)]],
        created_at=[[DF(date=t,comparison_operator=Op.less_than_equal)]],
        expired_at=[[DF(date=t,comparison_operator=Op.greater_than)],[DF(comparison_operator=Op.is_null)]])
print(sf.edge_search_filter_query_constructor(asof, GraphProvider.NEO4J))
