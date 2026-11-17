"""Explainable action ranking. Weights are heuristics, never traffic forecasts."""


def build_roadmap(audit: dict, gaps: dict) -> list:
    actions = []
    weights = {'Critical': 4, 'High': 3, 'Medium': 2, 'Low': 1}
    for issue in audit['issues']:
        impact = weights.get(issue['severity'], 1)
        actions.append(dict(action_type='technical_review', url=issue['url'],
            action=issue['recommendation'], evidence=issue['evidence'], rule_id=issue['rule_id'],
            impact=impact, effort=2, priority_score=impact / 2,
            horizon='short' if impact >= 3 else 'medium', depends_on=[]))
    for gap in gaps['content_gaps']:
        domains = gap['competitor_domains_count']
        actions.append(dict(action_type='content_review', keyword=gap['term'],
            action=gap['recommended_action'], evidence={'urls': gap['evidence_urls'],
            'domains': gap['competitor_domains']}, impact=min(domains, 4), effort=3,
            priority_score=round(min(domains, 4)/3, 3), horizon='medium', depends_on=['review_existing_coverage']))
    return sorted(actions, key=lambda a: (-a['priority_score'], a.get('url', ''), a.get('keyword', '')))
